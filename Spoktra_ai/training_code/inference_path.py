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


for item in data[:90681]:

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
You are a strict call quality analyst.
Your task is to detect whether the following issues are present in a customer-agent conversation.
Return ONLY a valid JSON object. No explanations, no extra text.

Issues to detect:
- repetition
- unclear_intro
- missing_confirmation
- long_agent_monologue
- compliance_risk

DETAILED RULES:
1. repetition = 1 ONLY if:
   - The agent repeats the SAME idea or sentence unnecessarily
   - Repetition must be redundant (not helpful clarification)
   Do NOT mark:
   - If agent rephrases or clarifies
   - If information is repeated with new context

2. unclear_intro = 1 ONLY if:
   - The FIRST agent message is confusing, incomplete, or grammatically incorrect
   Do NOT mark:
   - If greeting is missing but message is clear
   - If message is simple but understandable


3. missing_confirmation = 1 ONLY if ALL are true:
   - Agent takes a FINAL action (refund, exchange, escalation, cancellation, etc.)
   AND
   - Agent did NOT ask for confirmation
   AND
   - Customer did NOT clearly approve
   Do NOT mark:
   - If agent asks a question and customer agrees
   - If action happens AFTER customer consent
   - If discussion is still ongoing (no final action yet)

4. long_agent_monologue = 1 ONLY if ALL are true:
   - A SINGLE agent message has MORE THAN:
        • 3 sentences OR
        • 50 words
   AND
   - The message contains NO question
   AND
   - The message does NOT invite interaction
   Do NOT mark:
   - If message ends with a question
   - If message is interactive or conversational
   - If explanation is necessary and engaging

5. compliance_risk = 1 ONLY if:
   - Agent asks for sensitive data (OTP, password, PIN, CVV, card details)
   OR
   - Agent makes unrealistic guarantees (e.g., "100% guaranteed", "no risk")
   Do NOT mark:
   - Normal policy explanations
   - Refund timelines
   - Standard business communication

OUTPUT FORMAT (STRICT):
{
  "repetition": 0,
  "unclear_intro": 0,
  "missing_confirmation": 0,
  "long_agent_monologue": 0,
  "compliance_risk": 0
}

FINAL INSTRUCTIONS:
- Output ONLY JSON
- Do NOT add text before or after JSON
- Do NOT explain anything
- If unsure, return 0
- Be strict: only mark 1 when conditions are clearly satisfied

If message includes explanation but is part of a back-and-forth flow, do NOT mark as monologue.
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