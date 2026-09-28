import csv
import json
from collections import defaultdict

csv_file = "/home/codenomad/Desktop/GenAI/model_train/json_data/new.csv"
json_file = "calls.json"

calls = defaultdict(list)

with open(csv_file, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        calls[row["file_name"]].append({
            "speaker": row["speaker"].strip().lower(),
            "text": row["text"].strip()
        })

output = []
call_id = 1

for conversation in calls.values():
    output.append({
        "call_id": call_id,
        "conversation": conversation
    })
    call_id += 1

with open(json_file, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
