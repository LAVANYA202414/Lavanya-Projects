import json

input_filename = '/home/codenomad/Desktop/GenAI/model_train/file5.json'
output_filename = 'output.json'

with open(input_filename, 'r', encoding='utf-8') as file:
    data = json.load(file)

for item in data:
    if "conversation" not in item:
        continue

    normalized_conversation = []

    for msg in item["conversation"]:

        speaker = None
        text = None

        if "role" in msg and "content" in msg:
            if msg["role"] == "user":
                speaker = "customer"
            elif msg["role"] == "assistant":
                speaker = "agent"
            else:
                continue  # skip system/other

            text = msg["content"]

        elif "speaker" in msg and "text" in msg:
            speaker = msg["speaker"].strip().lower()
            if speaker not in ["agent", "customer"]:
                continue
            text = msg["text"]

        if speaker and text and text.strip():
            normalized_conversation.append({
                "speaker": speaker,
                "text": text.replace("’", "'")
            })

    item["conversation"] = normalized_conversation

with open(output_filename, 'w', encoding='utf-8') as file:
    json.dump(data, file, indent=4, ensure_ascii=False)

print(f"Fixed. Conversations normalized and saved to {output_filename}")
