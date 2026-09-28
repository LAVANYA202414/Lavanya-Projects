import json
import os
from ollama import chat


file_path = "/home/lavanya/Desktop/Lavanya/Spoktra_ai/training_code/cleaned_calls.json"
output_file = "llama_labels1.json"

with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Load output_file:
if os.path.exists(output_file):
    with open(output_file, "r", encoding="utf-8") as f:
        results = json.load(f)
else:
    results = []

# already processed texts:
processed_texts = set([item["text"] for item in results])


def ensure_list(data):
    if isinstance(data, dict):
        return data

    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                return parsed
        except:
            pass

    return {
        "repetition": 0,
        "unclear_intro": 0,
        "missing_confirmation": 0,
        "long_agent_monologue": 0,
        "compliance_risk": 0
    }


for item in data[:1200]:

    conversation = item["flattened_text"]

    # skip if already exists:
    if conversation in processed_texts:
        print("Skipping already processed call...")
        continue

        response = chat(
        model="llama3.2",
        messages=[
            {
                "role": "system",
                "content": """
You are a call quality analyst.

Detect these issues:
repetition
unclear_intro
missing_confirmation
long_agent_monologue
compliance_risk

Return only JSON:

{
 "repetition": 0,
 "unclear_intro": 0,
 "missing_confirmation": 0,
 "long_agent_monologue": 0,
 "compliance_risk": 0
}

if issue is present in call return 1 else return 0

don't write -> Here is the JSON output:
"""
            },
            {
                "role": "user",
                "content": conversation
            }
        ]
    )

    raw_output = response["message"]["content"]
    issue = ensure_list(raw_output)

    entry = {"text": conversation}
    entry.update(issue)

    results.append(entry)

    processed_texts.add(conversation)
    print(results)
    print(f"Processed: {len(results)}")

    # create json:
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)