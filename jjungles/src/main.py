# from datetime import datetime

# def format_deadlines(task_list, current_date_str):
#     # 1. Convert current_date_str (e.g., "2026-05-23") into a datetime object
#     current_date = datetime.strptime(current_date_str, "%Y-%m-%d")
    
#     results = []
#     for task in task_list:
#         # 2. Convert task["due_on"] into a datetime object
#         due_date = datetime.strptime(task["due_on"], "%Y-%m-%d")
#         print("DUE DATE:",due_date)

#         delta = due_date - current_date
#         days_left = delta.days
#         print("DAYS LEFT:",days_left)
#         if days_left == 0:
#             status = "DUE TODAY"
#         elif days_left < 0 :
#             status = "OVERDUE"
#         else:
#             status = f"{days_left} days left"
#         results.append(f"Task: {task['name']} | Status: {status}")
#     return results

# # Test Data
# tasks = [{"name": "Report", "due_on": "2026-05-25"}, {"name": "Coding", "due_on": "2026-05-20"}]
# today = "2026-05-23"
# print(format_deadlines(tasks, today))


# messy_tasks = [
#     {"name": "  fix BUG  ", "id": "T101"}, 
#     {"name": "submit report", "id": " t102 "},
#     {"name": None, "id": "T103"}]

# def clean_task_data(raw_tasks):
#     cleaned_list = []
#     for task in raw_tasks:
#         raw_name = task.get("name")
#         if raw_name:
#             new_name = raw_name.strip().title()

#         else:
#             new_name = "No Name Found"

#         new_id = task["id"].strip().upper()
#         cleaned_list.append({"name":new_name,"id":new_id})

#     return cleaned_list

# cleaned_tasks = clean_task_data(messy_tasks)
# print(cleaned_tasks)


tasks = [
    {"name": "Task 1", "status": "done"},
    {"name": "Task 2", "status": "pending"},
    {"name": "Task 3", "status": "done"},
    {"name": "Task 4", "status": "pending"}
]
from collections import Counter
def calculate_progress(tasks):
    tasks_len = len(tasks)
    if tasks_len == 0:
        return "No Task Found"
    count_done = 0
    for task in tasks:
        if task["status"] == "done":
            count_done += 1
            print("STATUS DONE...")
    progress = (count_done/tasks_len)*100
    print("PROGRESS:",progress)

    return f"Progress: {progress}% ({count_done}/{tasks_len}tasks completed)"
            

progress = calculate_progress(tasks)