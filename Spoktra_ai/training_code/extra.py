import json
from ollama import generate
from ollama import chat
import pandas as pd
import re


# file_path = "/home/lavanya/Desktop/Lavanya/Spoktra_ai/ml_data/merged1.json"
# with open(file_path, "r", encoding="utf-8") as file:
#     calls = json.load(file)

# new_json = []

# for call in calls:
#     issues = call.get("call_analysis", {}).get("issues", [])
    
#     if not issues:
#         issues = ["no_issue"]

#     new_entry = {
#         "flattened_text": call.get("flattened_text"),
#         # "issues": issues
#     }
#     new_json.append(new_entry)

# with open("cleaned_calls.json", "w", encoding="utf-8") as f:
#     json.dump(new_json, f, indent=4)

# print("Entries with no issues found:")

# for entry in new_json:
#     if "no_issue" in entry["issues"]:
#         print(entry)



# file_path = "/home/lavanya/Desktop/Lavanya/Spoktra_ai/training_code/cleaned_calls.json"

# with open(file_path, "r") as f:
#     data = json.load(f)

# first_2000 = []

# for item in data[:2000]:
#     first_2000.append({
#         "role": "user",
#         "content": item["flattened_text"]
#     })

# response = chat(
#     model="llama3",
#     messages=first_2000
# )

# print(response)



import json
from ollama import chat

file_path = "/home/lavanya/Desktop/Lavanya/Spoktra_ai/training_code/cleaned_calls.json"

with open(file_path, "r") as f:
    data = json.load(f)

results = []

for item in data[:1200]:

    conversation = item["flattened_text"]

    response = chat(
        model="llama3",
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

do not write explanation or anything. only give the result and the flattened text
"""
            },
            {
                "role": "user",
                "content": conversation
            }
        ]
    )

    raw_output = response["message"]["content"]

    try:
        json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)

        if json_match:
            issue_counts = json.loads(json_match.group())
        else:
            raise ValueError("No JSON found")

        entry = {"text": conversation}
        entry.update(issue_counts)

        results.append(entry)

    except Exception as e:
        print("Bad output:", raw_output)

with open("llama_labels1.json", "w") as f:
    json.dump(results, f, indent=4)