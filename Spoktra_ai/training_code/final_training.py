import json
import re
from collections import Counter

COMPLIANCE_TERMS = [ "guarantee", "100%", "no risk", "instant withdrawal", "PIN", "password", 
    "otp", "credit card", "KYC", "account number", "apt-out", "consent", "do not call", "authorized", 
    "disclaimer", "police", "legal action", "supervisor", "manager", "legal issue", "attorney", "cvv",
    "dispute" ,"EDD","free","fixed rate","don't leave a trail","send to my personal email",
    "card expiry","security code","verification code","aadhaar number","pan number","date of birth","billing address"
    ,"confidential information","risk-free","guaranteed returns","assured profit","act now",
    "escalation","account will be blocked","keep this confidential","minimum due",
    "account verification"]

CONFIRM_PHRASES = [
    "yes", "okay", "sure", "perfect", "got it", "cool","alright","ok","seems fine","I verify",
    "okay, understood","clear","that works", "sounds good", "acceptable", "fine with me",
    "i agree", "no problem", "yup", "yeah", "exactly","absolutely", "certainly", "confirmed",
    "acknowledged","all set","correct","right","definitely","100 percent","I confirm","I approve",
    "I accept","that is fine","works for me","go ahead","you can proceed","let's do it",
    "no objections","satisfied","okay then"
]

RISK_TERMS = [
    "pin",
    "password",
    "otp",
    "cvv",
    "verification code",
    "security code",
    "share your otp",
    "provide your pin",
    "tell me your password",
    "send to my personal email",
    "don't leave a trail",
    "keep this confidential",
    "guaranteed returns",
    "assured profit",
    "risk-free",
    "act now"
]

NEGATION_WORDS = [
    "not",
    "never",
    "don't",
    "do not",
    "should not",
    "will not"
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

IDENTITY_SIGNALS = ["my name", "in reference to", "you've reached", "regarding", "it's", "its", "you can address me as", "introduce","i'm called", "this is your agent", "I go by", "this is your advisor", "this is","i am", "here", "i'm", "speaking with", "i am calling", "can i have your name","agent"]
COMPANY_SIGNALS = ["from", "calling from","This call is being monitored or recorded"," this call is recorded","on behalf of", "this call may be recorded","for training and quality assurance","please verify your account number.","speaking with"]


def detect_clear_intro(first_agent_text):
    if not first_agent_text:
        return False

    text = first_agent_text.lower()

    identity = any(i in text for i in IDENTITY_SIGNALS)
    company = any(c in text for c in COMPANY_SIGNALS)

    # At least 1 component required
    return sum([ identity, company]) >= 1

def detect_repetition(agent_texts):
    cleaned = [re.sub(r"[^\w\s]", "", t.lower()).strip() for t in agent_texts]
    counts = Counter(cleaned)
    return any(c >= REPEAT_PHRASE_THRESHOLD for c in counts.values())

file_path = "/home/lavanya/Desktop/Lavanya/Spoktra_ai/ml_data/merged1.json"
output_file = "final_output.json"

with open(file_path, "r", encoding="utf-8") as f:
    calls = json.load(f)

print("Sample call structure:", calls[0])


for call in calls:

    conversation = call.get("conversation", [])

    call_issues = set()
    agent_texts = []
    customer_confirmed = False
    first_agent_text = None


    for turn in conversation:

        speaker = turn.get("speaker", "").lower()
        text = turn.get("text", "")

        if not text:
            continue

        if speaker == "agent":
            agent_texts.append(text.lower())

            if first_agent_text is None:
                first_agent_text = text

        elif speaker == "customer":
            if any(p in text.lower() for p in CONFIRM_PHRASES):
                customer_confirmed = True

    if detect_repetition(agent_texts):
        call_issues.add("repetition")

    if not detect_clear_intro(first_agent_text):
        call_issues.add("unclear_intro")

    RISK_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in RISK_TERMS) + r")\b",
    re.I
    )

    compliance_flag = False

    for text in agent_texts:

        for match in RISK_PATTERN.finditer(text):

            risk_word = match.group()
            start, end = match.span()

            # Take context window around the word
            window = text[max(0, start-40): min(len(text), end+40)]

            # If negation exists near the phrase -> safe
            if any(n in window for n in NEGATION_WORDS):
                continue

            compliance_flag = True
            break

        if compliance_flag:
            break

    if compliance_flag:
        call_issues.add("compliance_risk")

    if not customer_confirmed:
        call_issues.add("missing_confirmation")

    for text in agent_texts:
        if len(text.split()) > MAX_AGENT_TURN_WORDS:
            call_issues.add("long_agent_monologue")
            break

    score = max(0, min(100, 100 + sum(WEIGHTS[i] for i in call_issues)))

    if score >= 85:
        grade = "Excellent"
    elif score >= 70:
        grade = "Good"
    elif score >= 50:
        grade = "Average"
    else:
        grade = "Poor"

    call["call_analysis"] = {
        "issues": sorted(call_issues),
        "quality_score": score,
        "grade": grade
    }

    flattened = []

    for turn in conversation:
        speaker = turn.get("speaker", "").capitalize()
        text = turn.get("text", "")
        if text:
            flattened.append(f"{speaker}: {text}")

    call["flattened_text"] = "\n".join(flattened)


with open(output_file, "w", encoding="utf-8") as f:
    json.dump(calls, f, indent=2)

print(f" =====> \n Processed {len(calls)} calls into {output_file}")
