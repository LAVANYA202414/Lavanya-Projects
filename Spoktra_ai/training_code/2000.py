import os
import torch
import pandas as pd
import torch.nn as nn
from collections import Counter
from torch.optim import AdamW
from torch.utils.data import Dataset, DataLoader
from transformers import DistilBertModel, DistilBertTokenizerFast
from src.train import (LABELS,CallDataset,Call_Model,train_one_epoch,validate)
from src.inference import predict_call
from src.data_ingestion import DataIngestion
from config.path_config import load_config
from config.path_config import (ALL_DATA_FILE_PATH,TRAIN_DATA_FILE_PATH,TEST_DATA_FILE_PATH,VAL_DATA_FILE_PATH,SAMPLE_DATA_FILE_PATH,MODEL_PATH)

# CONFIG  
config = load_config()
MODEL_NAME = config["MODEL_NAME"]
BATCH_SIZE = config["BATCH_SIZE"]
MAX_LEN = int(config["MAX_LEN"])
LR = float(config.get("LR", 5e-5))
EPOCHS = config["EPOCHS"]

tokenizer = DistilBertTokenizerFast.from_pretrained(MODEL_NAME)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# DATA NORMALIZATION 
class DataNormalization:

    def split_data(self):

        raw_data = DataIngestion._read_train_data_file(ALL_DATA_FILE_PATH)
        if isinstance(raw_data, dict):
            return {
                "status": "failed",
                "error": raw_data.get("error")
            }

        sample_data = DataIngestion.extract_sample_data(
            raw_data, SAMPLE_DATA_FILE_PATH
        )

        if not isinstance(sample_data, pd.DataFrame) or sample_data.empty:
            return {
                "status": "failed",
                "train_df": [],
                "test_df": [],
                "val_df": [],
            }

        # Manual split 
        train_df = sample_data.iloc[:1500]
        test_df  = sample_data.iloc[1500:1800]
        val_df   = sample_data.iloc[1800:2000]

        # Issue counter
        def count_issues(df):
            counter = Counter()
            if df is None or df.empty:
                return counter

            for analysis in df["call_analysis"]:
                if isinstance(analysis, dict):
                    issues = analysis.get("issues", [])
                    if isinstance(issues, list):
                        counter.update(issues)

            return counter

        train_counter = count_issues(train_df)
        test_counter  = count_issues(test_df)
        val_counter   = count_issues(val_df)

        print("Train label distribution:", train_counter)
        print("Test label distribution:", test_counter)
        print("Val label distribution:", val_counter)

        # Save splits
        train_df.to_json(TRAIN_DATA_FILE_PATH, orient="records", indent=2)
        test_df.to_json(TEST_DATA_FILE_PATH, orient="records", indent=2)
        val_df.to_json(VAL_DATA_FILE_PATH, orient="records", indent=2)

        return {
            "status": "success",
            "train_df": train_df,
            "test_df": test_df,
            "val_df": val_df,
            "train_label_dist": dict(train_counter),
            "test_label_dist": dict(test_counter),
            "val_label_dist": dict(val_counter),
        }


# MAIN 
if __name__ == "__main__":

    data_obj = DataNormalization()
    res = data_obj.split_data()

    if res.get("status") == "failed":
        print(res.get("error", "Unknown error"))
        exit()

    train_df = res["train_df"]
    test_df  = res["test_df"]
    val_df   = res["val_df"]

    train_loader = DataLoader(
        CallDataset(train_df, tokenizer=tokenizer, max_len=MAX_LEN),
        batch_size=BATCH_SIZE,
        shuffle=True
    )

    val_loader = DataLoader(
        CallDataset(val_df, tokenizer=tokenizer, max_len=MAX_LEN),
        batch_size=BATCH_SIZE,
        shuffle=False
    )

    model = Call_Model().to(device)

    if os.path.exists(MODEL_PATH):
        print("FOUND SAVED MODEL! Loading weights ...")
        model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
        model.eval()
        skip_training = True
    else:
        print("No saved model found. Preparing for training ...")
        skip_training = False

    optimizer = AdamW(model.parameters(), lr=LR)

    # class imbalance handling
    weights = torch.tensor([5.0, 5.0, 1.0, 5.0, 1.0]).to(device)
    cls_loss_fn = nn.BCEWithLogitsLoss(pos_weight=weights)
    reg_loss_fn = nn.MSELoss()

    best_val_loss = float("inf")

    if not skip_training:
        for epoch in range(EPOCHS):
            print(f"\n--- Epoch {epoch + 1}/{EPOCHS} ---")
            torch.cuda.empty_cache()

            train_loss = train_one_epoch(
                model, train_loader, optimizer,
                device, cls_loss_fn, reg_loss_fn
            )

            best_val_loss = validate(
                model, val_loader, device,
                cls_loss_fn, reg_loss_fn,
                epoch, train_loss, best_val_loss
            )

        print(f"Best Val Loss: {best_val_loss:.4f}")

    torch.save(model.state_dict(), MODEL_PATH)
    print(f"Saved model at {MODEL_PATH}")


#  INFERENCE
def conversation_to_flattened_text(conversation):
    return "\n".join(
        f"{turn['speaker'].capitalize()}: {turn['text']}"
        for turn in conversation
    )


conversation = [
    {
        "speaker": "customer",
        "text": "Hello, I'd like to request a refund for a product I purchased about two months ago. I know it's past the usual 30-day return window, but I had a medical emergency that prevented me from returning it sooner."
    },
    {
        "speaker": "agent",
        "text": "Thank you for contacting ShopEase customer support. My name is Riya, and I'll be assisting you today. I'm sorry to hear about the situation you experienced. While our standard return policy is 30 days, we do review exception requests in special circumstances. To get started, could you please provide your order number and any medical documentation, such as a doctor's note or hospital records?"
    },
    {
        "speaker": "customer",
        "text": "Yes, I have a doctor's note available. The order number is #123456789. I'm really hoping an exception can be made."
    },
    {
        "speaker": "agent",
        "text": "Thank you for sharing the order number and confirming the documentation. I've noted these details. Since this request falls outside the standard return window, it will require approval from a manager. I will submit the request for review today, and you can expect an update within 24 to 48 business hours. Could you please confirm whether you would prefer to be contacted by email or phone?"
    },
    {
        "speaker": "customer",
        "text": "Email would be best. Please let me know what they decide."
    },
    {
        "speaker": "agent",
        "text": "Certainly. I will ensure you receive an email update regarding the decision. If the exception is approved, we’ll guide you through the return and refund process. If it’s not approved, I’ll clearly explain the reason and outline any available next steps or alternatives."
    },
    {
        "speaker": "customer",
        "text": "Okay, thank you. What happens if the manager denies the request? Is there an escalation process?"
    },
    {
        "speaker": "agent",
        "text": "Yes, if the initial review is denied, you may request a further escalation. This would involve submitting the case to a senior manager or an appeals team for additional review. I can walk you through that process if needed. For now, I’ll focus on getting the initial request reviewed and will contact you via email with the outcome."
    }
]

text = conversation_to_flattened_text(conversation)

prediction = predict_call(
    text,
    model,
    tokenizer,
    device,
    MAX_LEN,
    LABELS
)

print("TEXT:\n", text)
print("PREDICTION:\n", prediction)
