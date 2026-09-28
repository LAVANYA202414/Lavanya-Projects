import json
import pandas as pd

file_path = "/home/lavanya/Desktop/Lavanya/Spoktra_ai/training_code/json.json"

with open(file_path,"r",encoding="utf-8") as file:
    data = json.load(file)

print("Data:\n",data)

flattened_data = []

for user in data:
    name = user["info"]["name"]
    city = user["info"]["city"]

    clean_person = {
        "id":user["id"],
        "name":name,
        "city":city,
        "active":user["active"]
    }

    flattened_data.append(clean_person)

print("flattened_data:\n",flattened_data)

df = pd.DataFrame(flattened_data)
print("DATA FRAME:\n",df)

mumbai_users = df[df["city"] == "Mumbai"]

print("Users from Mumbai city:\n", mumbai_users)

print("\nNames of people in Mumbai:")
print(mumbai_users["name"])