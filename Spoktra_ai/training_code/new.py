import json
import re
from collections import Counter



INTRO_KEYWORDS = [
    "my name", "calling from", "this is", "regarding",
    "this call may be recorded", "calling on behalf of",
    "you've reached", "at your service",
    "in reference to", "i noticed",
    "is this a good time?", "do you have a moment?",
    "for training and quality assurance",
    "this call is being monitored",
    "before we proceed",
    "how may i assist you?"
]

COMPLIANCE_TERMS = [
    "guarantee", "100%", "no risk", "instant withdrawal",
    "pin", "password", "otp", "credit card",
    "kyc", "account number", "legal action"
]

CONFIRM_PHRASES = [
    "yes", "okay", "sure", "acceptable",
    "sounds good", "that works", "confirmed"
]

MAX_AGENT_TURN_WORDS = 60
REPEAT_PHRASE_THRESHOLD = 3

WEIGHTS = {
    "repetition": -5,
    "unclear_intro": -5,
    "missing_confirmation": -20,
    "long_agent_monologue": -10,
    "compliance_risk": -30
}



def detect_repetition(agent_texts):
    cleaned = [re.sub(r"[^\w\s]", "", t.lower()).strip() for t in agent_texts]
    counts = Counter(cleaned)
    return any(c >= REPEAT_PHRASE_THRESHOLD for c in counts.values())


def parse_conversation(text_block):
    """
    Converts:
    'Customer: Hello\nAgent: Hi'
    into structured list:
    [{'speaker': 'customer', 'text': 'Hello'}, ...]
    """
    conversation = []

    lines = text_block.split("\n")

    for line in lines:
        if ":" in line:
            speaker, text = line.split(":", 1)
            conversation.append({
                "speaker": speaker.strip().lower(),
                "text": text.strip()
            })

    return conversation


file_path = "/home/lavanya/Desktop/Lavanya/Spoktra_ai/ml_data/ml_data.json"
output_file = "merged2.json"

all_calls = []

with open(file_path, "r", encoding="utf-8") as f:
    calls = json.load(f)

for idx, call in enumerate(calls):

    text_block = call.get("text", "")
    conversation = parse_conversation(text_block)

    call_issues = set()
    call_improvements = set()
    agent_texts = []
    customer_confirmed = False

    for turn in conversation:
        speaker = turn["speaker"]
        text = turn["text"].lower()

        if speaker == "agent":
            agent_texts.append(text)

        elif speaker == "customer":
            if any(p in text for p in CONFIRM_PHRASES):
                customer_confirmed = True

    # Repetition
    if detect_repetition(agent_texts):
        call_issues.add("repetition")

    # Unclear Intro
    first_agent = next((t for t in conversation if t["speaker"] == "agent"), None)
    if first_agent:
        if not any(k in first_agent["text"].lower() for k in INTRO_KEYWORDS):
            call_issues.add("unclear_intro")

    # Compliance
    full_agent_text = " ".join(agent_texts)
    if any(term in full_agent_text for term in COMPLIANCE_TERMS):
        call_issues.add("compliance_risk")

    # Missing Confirmation
    if not customer_confirmed:
        call_issues.add("missing_confirmation")

    # Long Monologue
    for turn in conversation:
        if turn["speaker"] == "agent":
            if len(turn["text"].split()) > MAX_AGENT_TURN_WORDS:
                call_issues.add("long_agent_monologue")
                break

    # Score
    score = max(0, min(100, 100 + sum(WEIGHTS[i] for i in call_issues)))

    if score >= 85:
        grade = "Excellent"
    elif score >= 70:
        grade = "Good"
    elif score >= 50:
        grade = "Average"
    else:
        grade = "Poor"

    merged_call = {
        "id": idx,
        "original_text": text_block,
        "call_analysis": {
            "issues": sorted(call_issues),
            "quality_score": score,
            "grade": grade
        }
    }

    all_calls.append(merged_call)


with open(output_file, "w", encoding="utf-8") as f:
    json.dump(all_calls, f, indent=2)

print(f"Processed {len(all_calls)} calls into {output_file}")
