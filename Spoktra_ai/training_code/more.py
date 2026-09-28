import json
import random
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import DistilBertTokenizerFast, DistilBertModel
from torch.optim import AdamW


# CONFIG
MODEL_NAME = "distilbert-base-uncased"
MAX_LEN = 256
BATCH_SIZE = 8
EPOCHS = 3
LR = 2e-5

LABELS = [
    "repetition",
    "unclear_intro",
    "missing_confirmation",
    "long_agent_monologue",
    "compliance_risk"
]

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# LOAD & PREPARE DATA
print("LOADING DATA.\n")
with open("/home/lavanya/Desktop/Lavanya/Spoktra_ai/ml_data/output_2000_records.json", "r") as f:
    raw_data = json.load(f)

# convert issues to binary vector
def issues_to_labels(issues):
    return [1 if label in issues else 0 for label in LABELS]

data = []
# convert each call to ml format
for call in raw_data:
    data.append({
        "text": call.get("flattened_text", ""),
        # multi-label classification target
        "labels": issues_to_labels( 
            call.get("call_analysis", {}).get("issues", [])
        ),
        # regression target (0–1)
        "score": call.get("call_analysis", {}).get("quality_score", 0) / 100
    })

random.shuffle(data)


# ==> SPLIT THE DATA TRAIN 80%, VALIDATION 10%, TEST 10%
n = len(data)
train_data = data[:int(0.8 * n)]
val_data   = data[int(0.8 * n):int(0.9 * n)]
test_data  = data[int(0.9 * n):]


# ==> CREATE PYTORCH DATASET
tokenizer = DistilBertTokenizerFast.from_pretrained(MODEL_NAME)
print("STARTING CLASS ")
class CallDataset(Dataset):
    def __init__(self, data):
        self.data = data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        # Converts text → token IDs , Truncates long calls , Pads short calls
        tokens = tokenizer(
            item["text"],
            truncation=True,
            padding="max_length",
            max_length=MAX_LEN,
            return_tensors="pt"
        )

        return {
            "input_ids": tokens["input_ids"][0],
            "attention_mask": tokens["attention_mask"][0],
            "labels": torch.tensor(item["labels"], dtype=torch.float),
            "score": torch.tensor(item["score"], dtype=torch.float)
        }

train_loader = DataLoader(CallDataset(train_data), batch_size=BATCH_SIZE, shuffle=True)
val_loader   = DataLoader(CallDataset(val_data), batch_size=BATCH_SIZE)
test_loader  = DataLoader(CallDataset(test_data), batch_size=BATCH_SIZE)


# ==> MODEL ARCHITECTURE -> ENCODER, CLASSIFICATION HEAD, REGRESSION HEAD
print("MODEL WORK STARTING")

# custom neural network
class CallModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.bert = DistilBertModel.from_pretrained(MODEL_NAME)
        self.classifier = nn.Linear(768, len(LABELS))
        self.regressor = nn.Linear(768, 1)

    def forward(self, input_ids, attention_mask):
        # CLS token -> for classification tasks
        x = self.bert(input_ids, attention_mask).last_hidden_state[:, 0]
        labels = self.classifier(x)
        score = self.regressor(x).squeeze()
        return labels, score

model = CallModel().to(device)


# LOSS AND OPTIMIZER
print("LOSS AND OPTIMIZER")
    # for classification 
cls_loss_fn = nn.BCEWithLogitsLoss()
    # for regression
reg_loss_fn = nn.MSELoss()

optimizer = AdamW(model.parameters(), lr=LR)

# ==>OPTIMIZER
# TRAIN AND VALIDATE
best_val_loss = float("inf")

for epoch in range(EPOCHS): 
    print("EPOCH FOR LOOP STARTING \n", epoch)

    # ---- TRAIN ----
    model.train()
    train_loss = 0

    for batch in train_loader:
        print("for loop in epoch")
        optimizer.zero_grad()

        labels_pred, score_pred = model(
            batch["input_ids"].to(device),
            batch["attention_mask"].to(device)
        )

        loss_cls = cls_loss_fn(labels_pred, batch["labels"].to(device))
        loss_reg = reg_loss_fn(score_pred, batch["score"].to(device))
        loss = loss_cls + 0.2 * loss_reg

        # training dataset used here
        loss.backward()
        optimizer.step()

        train_loss += loss.item()

    train_loss /= len(train_loader)


    # ---- VALIDATE ----
    print("VALIDATING \n")
    model.eval()
    val_loss = 0

    with torch.no_grad():
        for batch in val_loader:
            labels_pred, score_pred = model(
                batch["input_ids"].to(device),
                batch["attention_mask"].to(device)
            )

            loss_cls = cls_loss_fn(labels_pred, batch["labels"].to(device))
            loss_reg = reg_loss_fn(score_pred, batch["score"].to(device))
            val_loss += (loss_cls + loss_reg).item()

    val_loss /= len(val_loader)

    print(f"Epoch {epoch+1}")
    print(f"Train Loss: {train_loss:.4f}")
    print(f"Val Loss:   {val_loss:.4f}")

    # validation dataset
    if val_loss < best_val_loss:
        best_val_loss = val_loss
        torch.save(model.state_dict(), "best_model.pt")
        print("Saved best model\n")



# INFERENCE FUNCTION
print("INFERENCE FUNCTION STARTING \n")

def predict_call(text):
    model.eval()

    tokens = tokenizer(
        text,
        truncation=True,
        padding="max_length",
        max_length=MAX_LEN,
        return_tensors="pt"
    )

    with torch.no_grad():
        logits, score = model(
            tokens["input_ids"].to(device),
            tokens["attention_mask"].to(device)
        )

    # converts raw output of logits into Numpy array of probabilites for the first item in a batch.
    probs = torch.sigmoid(logits)[0].cpu().numpy()

    # SAFE threshold loading
    try:
        with open("thresholds.json") as f:
            THRESHOLDS = json.load(f)
    except FileNotFoundError:
        THRESHOLDS = {label: 0.5 for label in LABELS}

    issues = [
        LABELS[i]
        for i, p in enumerate(probs)
        if p > THRESHOLDS[LABELS[i]]
    ]

    return {
        "issues": issues,
        "quality_score": round(float(score.item() * 100), 2)
    }


# TEST PREDICTION
result = predict_call(
  {
    "call_id": "CALL_101",
    "conversation": [
      { "speaker": "agent", "text": "Hello, thank you for calling support. This is Rahul." },
      { "speaker": "customer", "text": "Hi, my internet is not working." },
      { "speaker": "agent", "text": "I can help with that. Are the modem lights on?" },
      { "speaker": "customer", "text": "Yes, they are on." }
    ]
  },
)
print(result)



# import torch
# import numpy as np
# from sklearn.metrics import precision_recall_fscore_support, mean_absolute_error, mean_squared_error
# from tqdm import tqdm

# # CONFIG
# THRESHOLD = 0.5   # temporary, will tune later
# MODEL_PATH = "best_model.pt"

# # LOAD BEST MODEL
# model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
# model.eval()

# print("\nMODEL LOADED FOR EVALUATION\n")

# # STORAGE
# all_true_labels = []
# all_pred_labels = []

# all_true_scores = []
# all_pred_scores = []

# all_pred_probs = []


# # RUN ON TEST DATA
# with torch.no_grad():
#     for batch in tqdm(test_loader, desc="Evaluating"):
#         input_ids = batch["input_ids"].to(device)
#         attention_mask = batch["attention_mask"].to(device)

#         true_labels = batch["labels"].cpu().numpy()
#         true_scores = batch["score"].cpu().numpy()

#         logits, score_preds = model(input_ids, attention_mask)

#         probs = torch.sigmoid(logits).cpu().numpy()
#         pred_labels = (probs > THRESHOLD).astype(int)

#         all_true_labels.append(true_labels)
#         # all_pred_labels.append(pred_labels)
#         # all_pred_labels.append(probs)   # store probabilities, not binary
#         all_pred_probs.append(probs)
#         all_pred_labels.append((probs > THRESHOLD).astype(int))

#         all_true_scores.extend(true_scores)
#         all_pred_scores.extend(score_preds.cpu().numpy())

# # CONCAT RESULTS
# y_true = np.vstack(all_true_labels)
# y_pred = np.vstack(all_pred_labels)

# y_true_scores = np.array(all_true_scores)
# y_pred_scores = np.array(all_pred_scores)

# y_pred_probs = np.vstack(all_pred_probs)

# # MULTI-LABEL CLASSIFICATION METRICS
# print("\nISSUE DETECTION METRICS (PER LABEL)\n")

# precision, recall, f1, support = precision_recall_fscore_support(
#     y_true,
#     y_pred,
#     average=None,
#     zero_division=0
# )

# for i, label in enumerate(LABELS):
#     print(f"{label:25s} | "
#           f"Precision: {precision[i]:.3f} | "
#           f"Recall: {recall[i]:.3f} | "
#           f"F1: {f1[i]:.3f} | "
#           f"Support: {support[i]}")

# # REGRESSION METRICS
# mae = mean_absolute_error(y_true_scores, y_pred_scores)
# # rmse = mean_squared_error(y_true_scores, y_pred_scores, squared=False)
# rmse = mean_squared_error(y_true_scores, y_pred_scores) ** 0.5


# print("\nQUALITY SCORE METRICS\n")
# print(f"MAE  (avg error): {mae * 100:.2f} points")
# print(f"RMSE (big errors): {rmse * 100:.2f} points")

# # OVERALL SUMMARY
# print("\nSUMMARY\n")
# print(f"Average F1 score: {np.mean(f1):.3f}")
# print(f"Average Precision: {np.mean(precision):.3f}")
# print(f"Average Recall: {np.mean(recall):.3f}")



# import pandas as pd

# error_records = []

# model.eval()

# with torch.no_grad():
#     for batch_idx, batch in enumerate(test_loader):
#         input_ids = batch["input_ids"].to(device)
#         attention_mask = batch["attention_mask"].to(device)

#         texts = batch["input_ids"]  # we re-decode later
#         true_labels = batch["labels"].cpu().numpy()

#         logits, _ = model(input_ids, attention_mask)
#         probs = torch.sigmoid(logits).cpu().numpy()
#         preds = (probs > 0.5).astype(int)

#         for i in range(len(true_labels)):
#             for j, label in enumerate(LABELS):
#                 if preds[i][j] != true_labels[i][j]:
#                     error_records.append({
#                         "issue": label,
#                         "true": int(true_labels[i][j]),
#                         "pred": int(preds[i][j]),
#                         "probability": probs[i][j]
#                     })

# df_errors = pd.DataFrame(error_records)
# print("\nTotal errors:", len(df_errors))


# # Separate FALSE POSITIVES and FALSE NEGATIVES
# false_positives = df_errors[(df_errors.true == 0) & (df_errors.pred == 1)]
# false_negatives = df_errors[(df_errors.true == 1) & (df_errors.pred == 0)]

# print("\nFALSE POSITIVES PER ISSUE")
# print(false_positives.issue.value_counts())

# print("\nFALSE NEGATIVES PER ISSUE")
# print(false_negatives.issue.value_counts())


# # threshold 
# from sklearn.metrics import f1_score

# optimal_thresholds = {}
# thresholds = [i / 100 for i in range(30, 91, 5)]  # 0.30 → 0.90

# for label_idx, label in enumerate(LABELS):
#     best_f1 = 0
#     best_threshold = 0.5

#     for t in thresholds:
#         preds = (y_pred[:, label_idx] > t).astype(int)
#         f1 = f1_score(y_true[:, label_idx], preds, zero_division=0)

#         if f1 > best_f1:
#             best_f1 = f1
#             best_threshold = t

#     optimal_thresholds[label] = best_threshold


# import json

# with open("thresholds.json", "w") as f:
#     json.dump(optimal_thresholds, f, indent=2)

# print("\nThresholds saved to thresholds.json")