import math
from datetime import timedelta
import re
import csv
import json
from ollama import chat
from datetime import datetime
from collections import Counter

today = datetime.now().date()
underutilized_per = 0.5
hours_per_day = 8

# # Get remaining
# def get_remaining(candidate):
#     return candidate["remaining"]

# Load tasks assignments -> who is currently working on which task
def load_task_assignments(assign_file):
    task_owner = {}
    all_assigned_users = []
    with open(assign_file, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            users = (row.get("user_id") or "0").strip()
            user_ids = users if users != "" else "0"
            task_owner[row["task_id"]] = user_ids
            if user_ids != "0": 
                all_assigned_users.append(user_ids)
    return task_owner, all_assigned_users


# Load user capacity -> weekly capacity of the user
def load_user_capacity(users_file):
    user_capacity = {}
    with open(users_file, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            user_capacity[row["id"]] = float(row.get("weekly_capacity", 0))
    return user_capacity


# Load user skills
def load_user_skills(skill_file):
    user_skills = {}
    with open(skill_file, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            skill = row["skill_id"]
            user = row["user_id"]
            # Skip empty rows
            if not skill or not user:
                continue
            if skill not in user_skills:
                user_skills[skill] = []
            user_skills[skill].append(user)
    return user_skills


# Load tasks
def load_tasks(task_file):
    with open(task_file, "r", encoding="utf-8") as file:
        return list(csv.DictReader(file))


# User workload
def calculate_user_workload(all_tasks, task_owner):
    user_total_hours = {}
    # Skip tasks that are completed or client approval pending
    for row in all_tasks:
        if row["state"] in ["completed", "client_approval_pending"]:
            continue
        task_id = row["id"]
        assignee = str(task_owner.get(task_id, "0")).strip()
        hours = float(row.get("estimated_hours") or 0.0)
        # Add these hours to the user's running total
        user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours
    return user_total_hours


# Sort candidates
def sort_candidates(candidate):
    # a person with 40 hours free (-40) comes before someone with 10 hours free (-10)
    highest_remaining = -candidate["remaining"]
    # If two people have the same free hours,we pick the one who is less buzy
    lowest_task_count = candidate["task_count"]
    return (highest_remaining, lowest_task_count)


# Helper to sort by total load (lowest hours first)
def sort_by_load(user_dict):
    return user_dict["total_load"]


def generate_suggestion(status, original_assignee, reassigned_to, final_load):
    if status == "OVERLOADED":
        return f"Original assignee {original_assignee} is over capacity; reassigned to user {reassigned_to}."

    elif status == "DELAYED":
        if reassigned_to != original_assignee:
            return f"Task is past deadline; reassigned from user {original_assignee} to user {reassigned_to}."
        else:
            return "Task is past deadline; escalate immediately."

    elif status == "DELAYED_TIMELINE_EXTENSION":
        return f"All skilled resources fully booked; task queued for user {reassigned_to} and will begin after {final_load} hours."

    elif status == "USER_UNDERUTILIZED_BUT_LATE":
        return f"Assignee {original_assignee} has low workload but task is late; reassigned to user {reassigned_to}."

    elif status == "UNASSIGNED_NOW_ASSIGNED":
        return f"Task was unassigned; reassigned to user {reassigned_to}."

    elif status == "NO_SKILLED_USER_FOUND":
        return "No skilled resource found for this task; escalate to management immediately."

    elif status == "ON_TIME":
        return "On track; continue routine monitoring."

    return "Manual review required."


# Check status and process tasks
def process_tasks(all_tasks, task_owner, user_capacity, user_skills, user_total_hours, user_task_count):
    tasks_summary = []
    for row in all_tasks:
        # Skip completed or client_approval_pending tasks
        if row["state"] in ["completed", "client_approval_pending"]:
            continue 
        
        # For each task, takes original user, hours required, and owner's current capacity
        task_id = int(row["id"])
        deadline = row["date_deadline"]
        required_skill = row.get("required_skill_id")
        hours = float(row.get("estimated_hours") or 0.0)
        
        # Get the id of the person currently assigned to this task
        original_assignee = str(task_owner.get(str(task_id), "0")).strip()
        # Get the users workload and capacity
        total_workload = user_total_hours.get(original_assignee, 0.0)
        capacity = user_capacity.get(original_assignee, 0.0)

        # Convert string deadline to date object for comparison
        deadline_date = None
        if deadline:
            deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

        # Task Status
        if deadline_date and today > deadline_date:
            if original_assignee == "0":
                status = "UNASSIGNED"
            elif total_workload >= capacity:
                status = "OVERLOADED"
            elif 0 < total_workload < (capacity * underutilized_per):
                status = "USER_UNDERUTILIZED_BUT_LATE"
            else:
                status = "DELAYED"
        else:
            status = "ON_TIME"

        reassigned_to = original_assignee

        # Reassignment Logic
        if status != "ON_TIME":
            if not required_skill:
                print(f" Task {task_id} has no required_skill_id — cannot reassign")
                tasks_summary.append({
                    "tasks_id":task_id,
                    "status":"NO_SKILLED_USER_FOUND",
                    "original_assignee":original_assignee,
                    "reassigned_to":original_assignee,
                    "hours":hours,
                    "final_load":0.0,
                    "deadline":deadline_date
                })
                continue
            # Task has no assignee
            if status == "UNASSIGNED":
                skilled_users = user_skills.get(required_skill, [])
                if not skilled_users:
                    # Nobody in the system knows this skill
                    print(f" Task {task_id} is UNASSIGNED and no skilled users found for skill {required_skill}")
                    tasks_summary.append({
                        "task_id": task_id,
                        "status":status,
                        "original_assignee":original_assignee,
                        "reassigned_to":"0",
                        "hours":hours,
                        "final_load":0.0,
                        "deadline":deadline_date
                    })
                    continue

                # Find skilled users who still have time for this task
                candidates = []
                for user_id in skilled_users:
                    user_id = str(user_id).strip()
                    load = user_total_hours.get(user_id, 0.0)
                    cap = user_capacity.get(user_id, 0.0)
                    if load + hours <= cap:
                        # This user has capacity to take the task
                        candidates.append({
                            "user_id": user_id,
                            "remaining": cap - load,
                            "task_count": user_task_count.get(user_id, 0) 
                        })

                if candidates:
                    # Get the best available person and assign the task to them
                    candidates.sort(key=sort_candidates)
                    best = candidates[0]
                    reassigned_to = best["user_id"]
                    # Update the user's load for future task account for this new assignment
                    user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
                    user_task_count[reassigned_to] += 1
                    status = "UNASSIGNED_NOW_ASSIGNED"
                    tasks_summary.append({
                        "task_id": task_id,
                        "status": status,
                        "original_assignee": original_assignee,
                        "reassigned_to": reassigned_to,
                        "hours": hours,
                        "final_load": 0.0,
                        "deadline":deadline_date
                    })
                    continue 
                else:
                    # All are buzy, pick whoever has the lightest load -> they will be free soonest
                    # lowest_load = 999999.0
                    lowest_load = float("inf")
                    reassigned_to = None
                    for skilled_user in skilled_users:
                        user_id = str(skilled_user).strip()
                        current_load = user_total_hours.get(user_id,0.0)

                        if current_load < lowest_load:
                            lowest_load = current_load
                            reassigned_to = user_id

                    # This task will have to wait
                    status = "DELAYED_TIMELINE_EXTENSION"

                    tasks_summary.append({
                        "task_id":task_id,
                        "status": status,
                        "original_assignee": original_assignee,
                        "reassigned_to": reassigned_to,
                        "hours": hours,
                        "final_load": 0.0,
                        "deadline":deadline_date
                    })
                    continue

            # if status is just delayed and user has capacity, keep the original assignee
            if status == "DELAYED" and original_assignee != "0":
                total_workload = user_total_hours.get(original_assignee,0.0)
                capacity = user_capacity.get(original_assignee,0.0)
                if total_workload <= capacity:
                    tasks_summary.append({
                        "task_id":task_id,
                        "status":status,
                        "original_assignee":original_assignee,
                        "reassigned_to":original_assignee,
                        "hours":hours,
                        "final_load":0.0,
                        "deadline":deadline_date
                    })
                    # skip reassignment logic entirely
                    continue
            # when no skilled users found
            candidates = []
            # Users we have already evaluated to avoid duplicates
            seen = set()
            skilled_users = user_skills.get(required_skill, [])

            if not skilled_users:
                # Skill doesn't exist
                print(f"=====> Task {task_id}: No users found with skill '{required_skill}' — cannot reassign")
                tasks_summary.append({
                    "task_id": task_id,
                    "status": "NO_SKILLED_USER_FOUND",
                    "original_assignee": original_assignee,
                    "reassigned_to": original_assignee,  # keep original assignee
                    "hours": hours,
                    "final_load": 0.0,
                    "deadline":deadline_date
                })
                continue
            # Filter for skilled users who have enough weekly capacity
            for user_ids in skilled_users:
                user_id = str(user_ids).strip()
                if user_id in seen:
                    continue # skip if already checked
                seen.add(user_id)

                # dont reassign to the same person
                if status in ("USER_UNDERUTILIZED_BUT_LATE","DELAYED") and user_id == original_assignee:
                    continue
                load = user_total_hours.get(user_id, 0.0)
                cap = user_capacity.get(user_id, 0.0)
                
                # finds users with the right skill who can fit these new hours into their current capacity
                if load + hours <= cap:
                    candidates.append({
                        "user_id": user_id,
                        "remaining": cap - load,
                        "task_count": user_task_count.get(user_id, 0)
                    })

            if candidates:
                # Pick the best candidate -> most free hours + fewest tasks
                candidates.sort(key=sort_candidates)
                best_user = candidates[0]
                reassigned_to = best_user["user_id"]

                # update new assignee workload for future tasks
                user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
                user_task_count[reassigned_to] += 1
                
                # ermove task hours of original assignee
                if original_assignee != "0" and original_assignee != reassigned_to:
                    user_total_hours[original_assignee] = max(0.0,user_total_hours.get(original_assignee, 0.0) - hours)
                    user_task_count[original_assignee] = max(0,user_task_count.get(original_assignee, 0) - 1)
            else:
                # No one has free capacity — pick the person who will be free soonest
                load_skilled_list = []
                seen_load = set()
                for user_ids in skilled_users:
                    user_id = str(user_ids).strip()
                    if user_id in seen_load:
                        continue
                    seen_load.add(user_id)
                    # don't queue to the same perspn
                    if status in ("USER_UNDERUTILIZED_BUT_LATE", "DELAYED") and user_id == original_assignee:
                        continue
                    load_skilled_list.append({
                        "user_id": user_id,
                        "total_load": user_total_hours.get(user_id, 0.0)
                    })

                if load_skilled_list:
                    # Pick person with the lowest current hour load
                    load_skilled_list.sort(key=sort_by_load)

                    reassigned_to = load_skilled_list[0]["user_id"]
                    # mark timeline extension -> go into queue
                    status = "DELAYED_TIMELINE_EXTENSION"

                    # user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours

                    # don't add hours to their current load yet
                    # The task starts AFTER they finish current work
                    # delayed_assignments will track when they'll be free
                else:
                    # Keep the original assignee if no skilled users found
                    reassigned_to = original_assignee
                    status = "DELAYED_TIMELINE_EXTENSION"
                # else:
                #     reassigned_to = original_assignee
                # print("\nLOAD SKILLED LIST:\n",load_skilled_list)
        print(f"\nTask {task_id} -> Reassigned to: {reassigned_to} (Status: {status})\n")

        # Record the result
        tasks_summary.append({
            "task_id": task_id,
            "status": status,
            "original_assignee": original_assignee,
            "reassigned_to": reassigned_to,
            "hours": hours,
            "final_load":0.0,
            "deadline":deadline_date
        })

    # print("\nTASKS SUMMARY:\n", tasks_summary)
    # print("\nTOTAL TASKS:", len(all_tasks))
    # print("\nTASKS SUMMARY COUNT:", len(tasks_summary))
    # print(f"\nDEBUG: Successfully processed {len(tasks_summary)} tasks.")
    return tasks_summary


# AFTER-PROCESSING: Calculate new deadlines for queued tasks
# def delayed_assignments(tasks_summary, user_skills, user_total_hours):
#     for row in tasks_summary:
#         if row["status"] == "DELAYED_TIMELINE_EXTENSION":
#             assignee = row["reassigned_to"]
#             # Count after how many hours user will be free
#             free_after_hours = user_total_hours.get(assignee, 0.0)
#             # Stored for hours suggestion message
#             row["final_load"] = free_after_hours

#             # (free_after_hours + row["hours"]) -> Total Hours the person is now committed to.
#             # (existing queue + this task's hours) / 8 hours per day, rounded up
#             days_needed = math.ceil((free_after_hours + row["hours"]) / 8)
#             row["new_deadline"] = (today + timedelta(days=days_needed)).strftime("%Y-%m-%d")
#             # Add tasks hours to the queue for next queued tasks
#             user_total_hours[assignee] = free_after_hours + row["hours"]
#         else:
#             # task doesnt need timeline extension - clear final load and keep original deadline
#             row["final_load"] = 0.0
#             row["new_deadline"] = row.get("deadline", "")

    # return tasks_summary


def delayed_assignments(tasks_summary, user_skills, user_total_hours):
    for row in tasks_summary:
        person = row["reassigned_to"]

        if row["status"] == "DELAYED_TIMELINE_EXTENSION":
            current_work = user_total_hours.get(person, 0.0)
            row["final_load"] = current_work

            # Total hours = existing workload + this task's hours
            total_hours = current_work + row["hours"]

            # Convert to days, round up manually
            days_needed = int(total_hours / hours_per_day)
            # Divide the total hours by 8. If the remainder is NOT zero, it means the worker has a partial day of work left over.
            if total_hours % hours_per_day != 0:
                days_needed += 1

            # Use task's original deadline as the base date, fallback to today
            base_date = row.get("deadline") or today

            row["new_deadline"] = (base_date + timedelta(days=days_needed)).strftime("%Y-%m-%d")

            # Update their load for the next queued task
            user_total_hours[person] = total_hours

        else:
            row["final_load"] = 0.0
            row["new_deadline"] = row.get("deadline", "")

    return tasks_summary


# Reason and Suggestion generation
def generate_ai_output(tasks_summary):
    print("============ ENTERED GENERATE AI OUTPUT ===========")
    final_output = []
    # how many tasks to send to the ai at once (smaller = more reliable responses)
    chunk_size = 5

    # pre-defined text used if the Ai fails or return empty response
    fallback_reasons = {
        "ON_TIME": "Task is progressing on schedule with no issues.",
        "OVERLOADED": "Assignee exceeded weekly capacity; task rebalanced to an available resource.",
        "DELAYED": "Task has passed its deadline and requires immediate attention.",
        "USER_UNDERUTILIZED_BUT_LATE": "Assignee has available capacity but the task is still late.",
        "DELAYED_TIMELINE_EXTENSION": "All team members are at full capacity; assigned to earliest available person."
    }
    fallback_suggestions = {
        "ON_TIME": "Continue monitoring progress and ensure no blockers arise.(fallback)",
        "OVERLOADED": "Review workload distribution and consider hiring or redistributing tasks.(fallback)",
        "DELAYED": "Prioritize this task and check.(fallback)",
        "USER_UNDERUTILIZED_BUT_LATE": "Investigate why the task is late despite available capacity.(fallback)",
        "DELAYED_TIMELINE_EXTENSION": "Extend the task deadline and inform stakeholders of the new timeline.(fallback)"
    }

    prompt = f"""
IMPORTANT: Respond with ONLY a valid JSON array. No preamble, no markdown.
You are a Project Manager AI.

Your task is to take the provided 'suggestion' field and ensure it is formatted correctly into a JSON response. 

Constraints:
- Return one entry per task. Output array MUST have SAME LENGTH as input array ({chunk_size}).
- Do NOT change the meaning of the provided suggestion.
- Format: [{{"task_id": 123, "suggestion": "text from input"}}]
"""



    # process tasks in batches - chunk_size
    for i in range(0, len(tasks_summary), chunk_size):
        chunk = tasks_summary[i: i + chunk_size]
        # Tell AI how many tasks are there in this batch
        chunk_instruction = f"- This chunk has EXACTLY {len(chunk)} tasks. Return EXACTLY {len(chunk)} entries."
        try:
            # Call model
            response = chat(
                model="llama3.2",
                messages=[
                    # {"role": "system", "content": prompt},
                    {"role": "system", "content": prompt + chunk_instruction},
                    {"role": "user", "content": json.dumps(chunk, default=str)}
                ],
                options={"temperature": 0}
            )
            content = response.message.content.strip()

            # Debug: print raw AI response to catch formatting issues
            print(f"\n=====> Raw AI response for chunk {i}:\n{content}\n")

            # Clean markdown fences if present
            content = re.sub(r"```(?:json)?", "", content).strip()
            content = content.strip("`").strip()

            # Extract JSON array
            match = re.search(r'\[.*?\]', content, re.DOTALL)
            if not match:
                raise ValueError(f"No JSON array found in AI response: {content[:200]}")

            ai_output = json.loads(match.group())

            # Validate all task_ids are present
            # returned_ids = {str(r.get("task_id")) for r in ai_output}
            # expected_ids = {str(item["task_id"]) for item in chunk}
            # missing_ids = expected_ids - returned_ids
            # if missing_ids:
            #     print(f"[WARNING] AI missed task_ids: {missing_ids} — using fallback for those")

            # check how many tasks AI returned
            if len(ai_output) != len(chunk):
                print(f"=====> AI returned {len(ai_output)} tasks but expected {len(chunk)}")
                returned_ids = {str(r.get("task_id")) for r in ai_output}
                expected_ids = {str(item["task_id"]) for item in chunk}
                print(f"=====> Missing task_ids: {expected_ids - returned_ids}")

            # mapping, to find AI results by task_id
            ai_map = {str(r.get("task_id")): r for r in ai_output}

            # for each task in chunk - build final output row
            for item in chunk:
                suggestion = generate_suggestion(
                    item["status"],
                    item["original_assignee"],
                    item["reassigned_to"],
                    item.get("final_load", 0.0)
                )

                reason = fallback_reasons.get(item["status"], "Manual review required.")

                final_output.append({
                    # all fields from tasks_summary
                    **item,
                    "reason": reason,
                    "suggestion": suggestion
                })

            # for item in chunk:
            #     t_id = str(item["task_id"])
            #     status = item["status"]
            #     reassigned_to = item["reassigned_to"]
            #     original_assignee = item["original_assignee"]
            #     final_load = item.get("final_load", 0.0)


            #     ai_data = ai_map.get(t_id)

            #     # Use AI data if valid, else fall back to status-specific defaults
            #     reason = (ai_data.get("reason") if ai_data and ai_data.get("reason") else None) \
            #              or fallback_reasons.get(status, "Manual review required.")
            #     suggestion = (ai_data.get("suggestion") if ai_data else None) or fallback_suggestions.get(status)

            #     if status == "DELAYED_TIMELINE_EXTENSION":
            #         # LLM sometimes applies DELAYED rule here — override it
            #         if "queued" not in suggestion.lower() or "hours" not in suggestion.lower():
            #             suggestion = f"All skilled resources fully booked; task queued for user {reassigned_to} and will begin after {final_load} hours."

            #     elif status == "OVERLOADED":
            #         # LLM sometimes applies DELAYED_TIMELINE_EXTENSION rule here — override it
            #         if "queued" in suggestion.lower() or "booked" in suggestion.lower():
            #             suggestion = f"Original assignee {original_assignee} is over capacity; reassigned to user {reassigned_to}."


            #     elif status == "DELAYED":
            #         # LLM sometimes says "escalate" even when reassigned to a different user
            #         if reassigned_to != original_assignee and "escalate" in suggestion.lower():
            #             suggestion = f"Task is past deadline; reassigned from user {original_assignee} to user {reassigned_to}."

            #     elif status == "USER_UNDERUTILIZED_BUT_LATE":
            #         # LLM sometimes forgets to mention the new assignee
            #         if reassigned_to != original_assignee and reassigned_to not in suggestion:
            #             suggestion = f"Assignee {original_assignee} has low workload but task is late; reassigned to user {reassigned_to}."
                        
            #     final_output.append({
            #         **item, # Get all the fields like task_id,status ...
            #         "reason": reason,
            #         "suggestion": suggestion
            #     })

            print(f"=====> Chunk {i} processed successfully. Tasks so far: {len(final_output)}")

        except json.JSONDecodeError as e:
            # fallback if AI returned something invalid
            print(f"=====> JSON parse failed for chunk {i}: {e}")
            for item in chunk:
                status = item["status"]
                final_output.append({
                    **item, # Get all the fields like task_id,status ...
                    "reason": fallback_reasons.get(status, "Manual review required."),
                    "suggestion": fallback_suggestions.get(status, "Check resource availability.")
                })
    # print("final output ===========:\n", final_output)
    return final_output




# Save the output
# def save_output(final_output, output_file):
#     with open(output_file, "w", encoding="utf-8") as file:
#         columns = [
#             "task_id", "status", "original_assignee", "reassigned_to", 
#             "reason", "suggestion", "hours", "final_load"
#         ]

#         writer = csv.DictWriter(file, fieldnames=columns)
#         writer.writeheader()
#         writer.writerows(final_output)
        
#     for row in final_output:
#         print("\nROW SAVED:\n", row)


# def save_output(final_output, output_file):
#     with open(output_file, "w", encoding="utf-8", newline="") as file:
#         columns = [
#             "task_id", "status", "original_assignee", "reassigned_to",
#             "reason", "suggestion", "hours", "final_load",
#             "deadline","new_deadline"
#         ]
#         # quoting=csv.QUOTE_ALL -> tells python to put double qoutes
#         writer = csv.DictWriter(file, fieldnames=columns, quoting=csv.QUOTE_ALL)
#         writer.writeheader()
#         writer.writerows(final_output)


def save_output(final_output, output_file):
    # Open the file for writing
    with open(output_file, "w", encoding="utf-8", newline="") as file:
        columns = [
            "task_id", "status", "original_assignee", "reassigned_to",
            "reason", "suggestion", "hours", "final_load", "deadline","new_deadline"
        ]
        # quoting=csv.QUOTE_ALL -> add double qoutes on each piece of data
        writer = csv.DictWriter(file, fieldnames=columns, quoting=csv.QUOTE_ALL)
        writer.writeheader()

        # Write each row one by one
        for row in final_output:
            # Create a simple dictionary for the row we are about to write
            clean_row = {}
            for col in columns:
                # Get the value from the data, use empty string if missing
                value = row.get(col, "")
                # Convert the value to a string 
                clean_row[col] = str(value)
            
            # Write the single line to the file
            writer.writerow(clean_row)
    
            print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(clean_row, indent=2, default=str))


# Execution Code
def main():
    task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
    assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
    skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
    users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"
    output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

    task_owner, all_assigned_users = load_task_assignments(assign_file)
    user_capacity = load_user_capacity(users_file)
    user_skills = load_user_skills(skill_file)
    all_tasks = load_tasks(task_file)

    user_task_count = Counter(all_assigned_users)
    user_total_hours = calculate_user_workload(all_tasks, task_owner)

    tasks_summary = process_tasks(
        all_tasks,
        task_owner,
        user_capacity,
        user_skills,
        user_total_hours,
        user_task_count,
    )

    updated_tasks_summary= delayed_assignments(tasks_summary, user_skills, user_total_hours)
    # print("updated_tasks_summary : \n ", updated_tasks_summary)
    # print("==="*45)
    # print()
    final_output = generate_ai_output(updated_tasks_summary)
    # print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2, default=str))
 
    save_output(final_output, output_file)


if __name__ == "__main__":
    main()

























# import math
# from datetime import timedelta
# import re
# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# today = datetime.now().date()
# underutilized_per = 0.5
# hours_per_day = 8

# # # Get remaining
# # def get_remaining(candidate):
# #     return candidate["remaining"]

# # Load tasks assignments -> who is currently working on which task
# def load_task_assignments(assign_file):
#     task_owner = {}
#     all_assigned_users = []

#     with open(assign_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             users = (row.get("user_id") or "0").strip()
#             user_ids = users if users != "" else "0"
#             task_owner[row["task_id"]] = user_ids
#             all_assigned_users.append(user_ids)
#     return task_owner, all_assigned_users


# # Load user capacity -> weekly capacity of the user
# def load_user_capacity(users_file):
#     user_capacity = {}
#     with open(users_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             user_capacity[row["id"]] = float(row.get("weekly_capacity", 0))
#     return user_capacity


# # Load user skills
# def load_user_skills(skill_file):
#     user_skills = {}

#     with open(skill_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             skill = row["skill_id"]
#             user = row["user_id"]
#             if skill not in user_skills:
#                 user_skills[skill] = []
#             user_skills[skill].append(user)

#     # print("\nuser_skills:\n", user_skills)
#     return user_skills


# # Load tasks
# def load_tasks(task_file):
#     with open(task_file, "r", encoding="utf-8") as file:
#         return list(csv.DictReader(file))


# # User workload
# def calculate_user_workload(all_tasks, task_owner):
#     user_total_hours = {}
#     # Skip tasks that are completed or client approval pending
#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = row["id"]
#         assignee = str(task_owner.get(task_id, "0")).strip()
#         hours = float(row.get("estimated_hours") or 0.0)

#         # Add these hours to the user's running total
#         user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

#     # print("\nuser_total_hours:\n", user_total_hours)
#     return user_total_hours


# # Sort candidates
# def sort_candidates(candidate):
#     # a person with 40 hours free (-40) comes before someone with 10 hours free (-10)
#     highest_remaining = -candidate["remaining"]
#     # If two people have the same free hours,we pick the one who is less buzy
#     lowest_task_count = candidate["task_count"]

#     # print("HIGHEST REMAINING CANDIDATES:\n",highest_remaining)
#     # print("\nLOWEST TASK COUNT:\n",lowest_task_count)
#     return (highest_remaining, lowest_task_count)


# # Helper to sort by total load (lowest hours first)
# def sort_by_load(user_dict):
#     return user_dict["total_load"]


# def generate_suggestion(status, original_assignee, reassigned_to, final_load):
#     if status == "OVERLOADED":
#         return f"Original assignee {original_assignee} is over capacity; reassigned to user {reassigned_to}."

#     elif status == "DELAYED":
#         if reassigned_to != original_assignee:
#             return f"Task is past deadline; reassigned from user {original_assignee} to user {reassigned_to}."
#         else:
#             return "Task is past deadline; escalate immediately."

#     elif status == "DELAYED_TIMELINE_EXTENSION":
#         return f"All skilled resources fully booked; task queued for user {reassigned_to} and will begin after {final_load} hours."

#     elif status == "USER_UNDERUTILIZED_BUT_LATE":
#         return f"Assignee {original_assignee} has low workload but task is late; reassigned to user {reassigned_to}."

#     elif status == "UNASSIGNED_NOW_ASSIGNED":
#         return f"Task was unassigned; reassigned to user {reassigned_to}."

#     elif status == "NO_SKILLED_USER_FOUND":
#         return "No skilled resource found for this task; escalate to management immediately."

#     elif status == "ON_TIME":
#         return "On track; continue routine monitoring."

#     return "Manual review required."


# # Check status and process tasks
# def process_tasks(all_tasks, task_owner, user_capacity, user_skills, user_total_hours, user_task_count):
#     tasks_summary = []
#     for row in all_tasks:
#         # Skip completed or client_approval_pending tasks
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue 
        
#         # For each task, takes original user, hours required, and owner's current capacity
#         task_id = int(row["id"])
#         deadline = row["date_deadline"]
#         required_skill = row.get("required_skill_id")
#         hours = float(row.get("estimated_hours") or 0.0)
        
#         # Get the id of the person currently assigned to this task
#         original_assignee = str(task_owner.get(str(task_id), "0")).strip()
#         # Get the users workload and capacity
#         total_workload = user_total_hours.get(original_assignee, 0.0)
#         capacity = user_capacity.get(original_assignee, 0.0)

#         # Convert string deadline to date object for comparison
#         deadline_date = None
#         if deadline:
#             deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#         # Task Status
#         if deadline_date and today > deadline_date:
#             if original_assignee == "0":
#                 status = "UNASSIGNED"
#             elif total_workload >= capacity:
#                 status = "OVERLOADED"
#             elif 0 < total_workload < (capacity * underutilized_per):
#                 status = "USER_UNDERUTILIZED_BUT_LATE"
#             else:
#                 status = "DELAYED"
#         else:
#             status = "ON_TIME"

#         reassigned_to = original_assignee

#         # Reassignment Logic
#         if status != "ON_TIME":
#             # Task has no assignee
#             if status == "UNASSIGNED":
#                 skilled_users = user_skills.get(required_skill, [])
#                 if not skilled_users:
#                     # Nobody in the system knows this skill
#                     print(f"[WARNING] Task {task_id} is UNASSIGNED and no skilled users found for skill {required_skill}")
#                     tasks_summary.append({
#                         "task_id": task_id,
#                         "status":status,
#                         "original_assignee":original_assignee,
#                         "reassigned_to":"0",
#                         "hours":hours,
#                         "final_load":0.0,
#                         "deadline":deadline_date
#                     })
#                     continue

#                 # Find skilled users who still have time for this task
#                 candidates = []
#                 for user_id in skilled_users:
#                     user_id = str(user_id).strip()
#                     load = user_total_hours.get(user_id, 0.0)
#                     cap = user_capacity.get(user_id, 0.0)
#                     if load + hours <= cap:
#                         # This user has capacity to take the task
#                         candidates.append({
#                             "user_id": user_id,
#                             "remaining": cap - load,
#                             "task_count": user_task_count.get(user_id, 0) 
#                         })

#                 if candidates:
#                     # Get the best available person and assign the task to them
#                     candidates.sort(key=sort_candidates)
#                     best = candidates[0]
#                     reassigned_to = best["user_id"]
#                     # Update the user's load for future task account for this new assignment
#                     user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#                     user_task_count[reassigned_to] += 1
#                     status = "UNASSIGNED_NOW_ASSIGNED"
#                     tasks_summary.append({
#                         "task_id": task_id,
#                         "status": status,
#                         "original_assignee": original_assignee,
#                         "reassigned_to": reassigned_to,
#                         "hours": hours,
#                         "final_load": 0.0,
#                         "deadline":deadline_date
#                     })
#                     continue 
#                 else:
#                     # All are buzy, pick whoever has the lightest load -> they will be free soonest
#                     # lowest_load = 999999.0
#                     lowest_load = float("inf")
#                     reassigned_to = None
#                     for skilled_user in skilled_users:
#                         user_id = str(skilled_user).strip()
#                         current_load = user_total_hours.get(user_id,0.0)

#                         if current_load < lowest_load:
#                             lowest_load = current_load
#                             reassigned_to = user_id

#                     # This task will have to wait
#                     status = "DELAYED_TIMELINE_EXTENSION"

#                     tasks_summary.append({
#                         "task_id":task_id,
#                         "status": status,
#                         "original_assignee": original_assignee,
#                         "reassigned_to": reassigned_to,
#                         "hours": hours,
#                         "final_load": 0.0,
#                         "deadline":deadline_date
#                     })
#                     continue

#             # if status is just delayed and user has capacity, keep the original assignee
#             if status == "DELAYED" and original_assignee != "0":
#                 total_workload = user_total_hours.get(original_assignee,0.0)
#                 capacity = user_capacity.get(original_assignee,0.0)
#                 if total_workload <= capacity:
#                     tasks_summary.append({
#                         "task_id":task_id,
#                         "status":status,
#                         "original_assignee":original_assignee,
#                         "reassigned_to":original_assignee,
#                         "hours":hours,
#                         "final_load":0.0,
#                         "deadline":deadline_date
#                     })
#                     # skip reassignment logic entirely
#                     continue
#             # when no skilled users found
#             candidates = []
#             # Users we have already evaluated to avoid duplicates
#             seen = set()
#             skilled_users = user_skills.get(required_skill, [])

#             if not skilled_users:
#                 # Skill doesn't exist
#                 print(f"=====> Task {task_id}: No users found with skill '{required_skill}' — cannot reassign")
#                 tasks_summary.append({
#                     "task_id": task_id,
#                     "status": "NO_SKILLED_USER_FOUND",
#                     "original_assignee": original_assignee,
#                     "reassigned_to": original_assignee,  # keep original assignee
#                     "hours": hours,
#                     "final_load": 0.0,
#                     "deadline":deadline_date
#                 })
#                 continue
#             # Filter for skilled users who have enough weekly capacity
#             for user_ids in skilled_users:
#                 user_id = str(user_ids).strip()
#                 if user_id in seen:
#                     continue # skip if already checked
#                 seen.add(user_id)

#                 # dont reassign to the same person
#                 if status in ("USER_UNDERUTILIZED_BUT_LATE","DELAYED") and user_id == original_assignee:
#                     continue
#                 load = user_total_hours.get(user_id, 0.0)
#                 cap = user_capacity.get(user_id, 0.0)
                
#                 # finds users with the right skill who can fit these new hours into their current capacity
#                 if load + hours <= cap:
#                     candidates.append({
#                         "user_id": user_id,
#                         "remaining": cap - load,
#                         "task_count": user_task_count.get(user_id, 0)
#                     })

#             if candidates:
#                 # Pick the best candidate -> most free hours + fewest tasks
#                 candidates.sort(key=sort_candidates)
#                 best_user = candidates[0]
#                 reassigned_to = best_user["user_id"]

#                 # update new assignee workload for future tasks
#                 user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#                 user_task_count[reassigned_to] += 1
                
#                 # ermove task hours of original assignee
#                 if original_assignee != "0" and original_assignee != reassigned_to:
#                     user_total_hours[original_assignee] = max(0.0,user_total_hours.get(original_assignee, 0.0) - hours)
#                     user_task_count[original_assignee] = max(0,user_task_count.get(original_assignee, 0) - 1)
#             else:
#                 # No one has free capacity — pick the person who will be free soonest
#                 load_skilled_list = []
#                 seen_load = set()
#                 for user_ids in skilled_users:
#                     user_id = str(user_ids).strip()
#                     if user_id in seen_load:
#                         continue
#                     seen_load.add(user_id)
#                     # don't queue to the same perspn
#                     if status in ("USER_UNDERUTILIZED_BUT_LATE", "DELAYED") and user_id == original_assignee:
#                         continue
#                     load_skilled_list.append({
#                         "user_id": user_id,
#                         "total_load": user_total_hours.get(user_id, 0.0)
#                     })

#                 if load_skilled_list:
#                     # Pick person with the lowest current hour load
#                     load_skilled_list.sort(key=sort_by_load)

#                     reassigned_to = load_skilled_list[0]["user_id"]
#                     # mark timeline extension -> go into queue
#                     status = "DELAYED_TIMELINE_EXTENSION"

#                     # user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours

#                     # don't add hours to their current load yet
#                     # The task starts AFTER they finish current work
#                     # delayed_assignments will track when they'll be free
#                 else:
#                     # Keep the original assignee if no skilled users found
#                     reassigned_to = original_assignee
#                     status = "DELAYED_TIMELINE_EXTENSION"
#                 # else:
#                 #     reassigned_to = original_assignee
#                 # print("\nLOAD SKILLED LIST:\n",load_skilled_list)
#         print(f"\nTask {task_id} -> Reassigned to: {reassigned_to} (Status: {status})\n")

#         # Record the result
#         tasks_summary.append({
#             "task_id": task_id,
#             "status": status,
#             "original_assignee": original_assignee,
#             "reassigned_to": reassigned_to,
#             "hours": hours,
#             "final_load":0.0,
#             "deadline":deadline_date
#         })

#     # print("\nTASKS SUMMARY:\n", tasks_summary)
#     # print("\nTOTAL TASKS:", len(all_tasks))
#     # print("\nTASKS SUMMARY COUNT:", len(tasks_summary))
#     # print(f"\nDEBUG: Successfully processed {len(tasks_summary)} tasks.")
#     return tasks_summary


# # AFTER-PROCESSING: Calculate new deadlines for queued tasks
# # def delayed_assignments(tasks_summary, user_skills, user_total_hours):
# #     for row in tasks_summary:
# #         if row["status"] == "DELAYED_TIMELINE_EXTENSION":
# #             assignee = row["reassigned_to"]
# #             # Count after how many hours user will be free
# #             free_after_hours = user_total_hours.get(assignee, 0.0)
# #             # Stored for hours suggestion message
# #             row["final_load"] = free_after_hours

# #             # (free_after_hours + row["hours"]) -> Total Hours the person is now committed to.
# #             # (existing queue + this task's hours) / 8 hours per day, rounded up
# #             days_needed = math.ceil((free_after_hours + row["hours"]) / 8)
# #             row["new_deadline"] = (today + timedelta(days=days_needed)).strftime("%Y-%m-%d")
# #             # Add tasks hours to the queue for next queued tasks
# #             user_total_hours[assignee] = free_after_hours + row["hours"]
# #         else:
# #             # task doesnt need timeline extension - clear final load and keep original deadline
# #             row["final_load"] = 0.0
# #             row["new_deadline"] = row.get("deadline", "")

#     # return tasks_summary


# def delayed_assignments(tasks_summary, user_skills, user_total_hours):
#     for row in tasks_summary:
#         person = row["reassigned_to"]

#         if row["status"] == "DELAYED_TIMELINE_EXTENSION":
#             current_work = user_total_hours.get(person, 0.0)
#             row["final_load"] = current_work

#             # Total hours = existing workload + this task's hours
#             total_hours = current_work + row["hours"]

#             # Convert to days, round up manually
#             days_needed = int(total_hours / hours_per_day)
#             # Divide the total hours by 8. If the remainder is NOT zero, it means the worker has a partial day of work left over.
#             if total_hours % hours_per_day != 0:
#                 days_needed += 1

#             # Use task's original deadline as the base date, fallback to today
#             base_date = row.get("deadline") or today

#             row["new_deadline"] = (base_date + timedelta(days=days_needed)).strftime("%Y-%m-%d")

#             # Update their load for the next queued task
#             user_total_hours[person] = total_hours

#         else:
#             row["final_load"] = 0.0
#             row["new_deadline"] = row.get("deadline", "")

#     return tasks_summary


# # Reason and Suggestion generation
# def generate_ai_output(tasks_summary):
#     print("============ ENTERED GENERATE AI OUTPUT ===========")
#     final_output = []
#     # how many tasks to send to the ai at once (smaller = more reliable responses)
#     chunk_size = 5

#     # pre-defined text used if the Ai fails or return empty response
#     fallback_reasons = {
#         "ON_TIME": "Task is progressing on schedule with no issues.",
#         "OVERLOADED": "Assignee exceeded weekly capacity; task rebalanced to an available resource.",
#         "DELAYED": "Task has passed its deadline and requires immediate attention.",
#         "USER_UNDERUTILIZED_BUT_LATE": "Assignee has available capacity but the task is still late.",
#         "DELAYED_TIMELINE_EXTENSION": "All team members are at full capacity; assigned to earliest available person."
#     }
#     fallback_suggestions = {
#         "ON_TIME": "Continue monitoring progress and ensure no blockers arise.(fallback)",
#         "OVERLOADED": "Review workload distribution and consider hiring or redistributing tasks.(fallback)",
#         "DELAYED": "Prioritize this task and check.(fallback)",
#         "USER_UNDERUTILIZED_BUT_LATE": "Investigate why the task is late despite available capacity.(fallback)",
#         "DELAYED_TIMELINE_EXTENSION": "Extend the task deadline and inform stakeholders of the new timeline.(fallback)"
#     }

#     prompt = f"""
# IMPORTANT: Respond with ONLY a valid JSON array. No preamble, no markdown.
# You are a Project Manager AI.

# Your task is to take the provided 'suggestion' field and ensure it is formatted correctly into a JSON response. 

# Constraints:
# - Return one entry per task. Output array MUST have SAME LENGTH as input array ({chunk_size}).
# - Do NOT change the meaning of the provided suggestion.
# - Format: [{{"task_id": 123, "suggestion": "text from input"}}]
# """



#     # process tasks in batches - chunk_size
#     for i in range(0, len(tasks_summary), chunk_size):
#         chunk = tasks_summary[i: i + chunk_size]
#         # Tell AI how many tasks are there in this batch
#         chunk_instruction = f"- This chunk has EXACTLY {len(chunk)} tasks. Return EXACTLY {len(chunk)} entries."
#         try:
#             # Call model
#             response = chat(
#                 model="llama3.2",
#                 messages=[
#                     # {"role": "system", "content": prompt},
#                     {"role": "system", "content": prompt + chunk_instruction},
#                     {"role": "user", "content": json.dumps(chunk, default=str)}
#                 ],
#                 options={"temperature": 0}
#             )
#             content = response.message.content.strip()

#             # Debug: print raw AI response to catch formatting issues
#             print(f"\n=====> Raw AI response for chunk {i}:\n{content}\n")

#             # Clean markdown fences if present
#             content = re.sub(r"```(?:json)?", "", content).strip()
#             content = content.strip("`").strip()

#             # Extract JSON array
#             match = re.search(r'\[.*?\]', content, re.DOTALL)
#             if not match:
#                 raise ValueError(f"No JSON array found in AI response: {content[:200]}")

#             ai_output = json.loads(match.group())

#             # Validate all task_ids are present
#             # returned_ids = {str(r.get("task_id")) for r in ai_output}
#             # expected_ids = {str(item["task_id"]) for item in chunk}
#             # missing_ids = expected_ids - returned_ids
#             # if missing_ids:
#             #     print(f"[WARNING] AI missed task_ids: {missing_ids} — using fallback for those")

#             # check how many tasks AI returned
#             if len(ai_output) != len(chunk):
#                 print(f"=====> AI returned {len(ai_output)} tasks but expected {len(chunk)}")
#                 returned_ids = {str(r.get("task_id")) for r in ai_output}
#                 expected_ids = {str(item["task_id"]) for item in chunk}
#                 print(f"=====> Missing task_ids: {expected_ids - returned_ids}")

#             # mapping, to find AI results by task_id
#             ai_map = {str(r.get("task_id")): r for r in ai_output}

#             # for each task in chunk - build final output row
#             for item in chunk:
#                 suggestion = generate_suggestion(
#                     item["status"],
#                     item["original_assignee"],
#                     item["reassigned_to"],
#                     item.get("final_load", 0.0)
#                 )

#                 reason = fallback_reasons.get(item["status"], "Manual review required.")

#                 final_output.append({
#                     # all fields from tasks_summary
#                     **item,
#                     "reason": reason,
#                     "suggestion": suggestion
#                 })

#             # for item in chunk:
#             #     t_id = str(item["task_id"])
#             #     status = item["status"]
#             #     reassigned_to = item["reassigned_to"]
#             #     original_assignee = item["original_assignee"]
#             #     final_load = item.get("final_load", 0.0)


#             #     ai_data = ai_map.get(t_id)

#             #     # Use AI data if valid, else fall back to status-specific defaults
#             #     reason = (ai_data.get("reason") if ai_data and ai_data.get("reason") else None) \
#             #              or fallback_reasons.get(status, "Manual review required.")
#             #     suggestion = (ai_data.get("suggestion") if ai_data else None) or fallback_suggestions.get(status)

#             #     if status == "DELAYED_TIMELINE_EXTENSION":
#             #         # LLM sometimes applies DELAYED rule here — override it
#             #         if "queued" not in suggestion.lower() or "hours" not in suggestion.lower():
#             #             suggestion = f"All skilled resources fully booked; task queued for user {reassigned_to} and will begin after {final_load} hours."

#             #     elif status == "OVERLOADED":
#             #         # LLM sometimes applies DELAYED_TIMELINE_EXTENSION rule here — override it
#             #         if "queued" in suggestion.lower() or "booked" in suggestion.lower():
#             #             suggestion = f"Original assignee {original_assignee} is over capacity; reassigned to user {reassigned_to}."


#             #     elif status == "DELAYED":
#             #         # LLM sometimes says "escalate" even when reassigned to a different user
#             #         if reassigned_to != original_assignee and "escalate" in suggestion.lower():
#             #             suggestion = f"Task is past deadline; reassigned from user {original_assignee} to user {reassigned_to}."

#             #     elif status == "USER_UNDERUTILIZED_BUT_LATE":
#             #         # LLM sometimes forgets to mention the new assignee
#             #         if reassigned_to != original_assignee and reassigned_to not in suggestion:
#             #             suggestion = f"Assignee {original_assignee} has low workload but task is late; reassigned to user {reassigned_to}."
                        
#             #     final_output.append({
#             #         **item, # Get all the fields like task_id,status ...
#             #         "reason": reason,
#             #         "suggestion": suggestion
#             #     })

#             print(f"=====> Chunk {i} processed successfully. Tasks so far: {len(final_output)}")

#         except json.JSONDecodeError as e:
#             # fallback if AI returned something invalid
#             print(f"=====> JSON parse failed for chunk {i}: {e}")
#             for item in chunk:
#                 status = item["status"]
#                 final_output.append({
#                     **item, # Get all the fields like task_id,status ...
#                     "reason": fallback_reasons.get(status, "Manual review required."),
#                     "suggestion": fallback_suggestions.get(status, "Check resource availability.")
#                 })
#     # print("final output ===========:\n", final_output)
#     return final_output




# # Save the output
# # def save_output(final_output, output_file):
# #     with open(output_file, "w", encoding="utf-8") as file:
# #         columns = [
# #             "task_id", "status", "original_assignee", "reassigned_to", 
# #             "reason", "suggestion", "hours", "final_load"
# #         ]

# #         writer = csv.DictWriter(file, fieldnames=columns)
# #         writer.writeheader()
# #         writer.writerows(final_output)
        
# #     for row in final_output:
# #         print("\nROW SAVED:\n", row)


# # def save_output(final_output, output_file):
# #     with open(output_file, "w", encoding="utf-8", newline="") as file:
# #         columns = [
# #             "task_id", "status", "original_assignee", "reassigned_to",
# #             "reason", "suggestion", "hours", "final_load",
# #             "deadline","new_deadline"
# #         ]
# #         # quoting=csv.QUOTE_ALL -> tells python to put double qoutes
# #         writer = csv.DictWriter(file, fieldnames=columns, quoting=csv.QUOTE_ALL)
# #         writer.writeheader()
# #         writer.writerows(final_output)


# def save_output(final_output, output_file):
#     # Open the file for writing
#     with open(output_file, "w", encoding="utf-8", newline="") as file:
#         columns = [
#             "task_id", "status", "original_assignee", "reassigned_to",
#             "reason", "suggestion", "hours", "final_load", "deadline","new_deadline"
#         ]
#         # quoting=csv.QUOTE_ALL -> add double qoutes on each piece of data
#         writer = csv.DictWriter(file, fieldnames=columns, quoting=csv.QUOTE_ALL)
#         writer.writeheader()

#         # Write each row one by one
#         for row in final_output:
#             # Create a simple dictionary for the row we are about to write
#             clean_row = {}
#             for col in columns:
#                 # Get the value from the data, use empty string if missing
#                 value = row.get(col, "")
#                 # Convert the value to a string 
#                 clean_row[col] = str(value)
            
#             # Write the single line to the file
#             writer.writerow(clean_row)
    
#             print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(clean_row, indent=2, default=str))


# # Execution Code
# def main():
#     task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
#     assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
#     skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
#     users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"
#     output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

#     task_owner, all_assigned_users = load_task_assignments(assign_file)
#     user_capacity = load_user_capacity(users_file)
#     user_skills = load_user_skills(skill_file)
#     all_tasks = load_tasks(task_file)

#     user_task_count = Counter(all_assigned_users)
#     user_total_hours = calculate_user_workload(all_tasks, task_owner)

#     tasks_summary = process_tasks(
#         all_tasks,
#         task_owner,
#         user_capacity,
#         user_skills,
#         user_total_hours,
#         user_task_count,
#     )

#     updated_tasks_summary= delayed_assignments(tasks_summary, user_skills, user_total_hours)
#     # print("updated_tasks_summary : \n ", updated_tasks_summary)
#     # print("==="*45)
#     # print()
#     final_output = generate_ai_output(updated_tasks_summary)
#     # print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2, default=str))
 
#     save_output(final_output, output_file)


# if __name__ == "__main__":
#     main()






















# import math
# from datetime import timedelta
# import re
# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# today = datetime.now().date()
# underutilized_per = 0.5
# hours_per_day = 8

# # # Get remaining
# # def get_remaining(candidate):
# #     return candidate["remaining"]

# # Load tasks assignments -> who is currently working on which task
# def load_task_assignments(assign_file):
#     task_owner = {}
#     all_assigned_users = []

#     with open(assign_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             users = (row.get("user_id") or "0").strip()
#             user_ids = users if users != "" else "0"
#             task_owner[row["task_id"]] = user_ids
#             all_assigned_users.append(user_ids)
#     # print("\nALL ASSIGNED USERS:\n",all_assigned_users)
#     # print("\nTASK OWNER:\n", task_owner)
#     return task_owner, all_assigned_users


# # Load user capacity -> weekly capacity of the user
# def load_user_capacity(users_file):
#     user_capacity = {}
#     with open(users_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             user_capacity[row["id"]] = float(row.get("weekly_capacity", 0))
#     # print("\nuser_capacity:\n", user_capacity)
#     return user_capacity


# # Load user skills
# def load_user_skills(skill_file):
#     user_skills = {}

#     with open(skill_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             skill = row["skill_id"]
#             user = row["user_id"]
#             if skill not in user_skills:
#                 user_skills[skill] = []
#             user_skills[skill].append(user)

#     # print("\nuser_skills:\n", user_skills)
#     return user_skills


# # Load tasks
# def load_tasks(task_file):
#     with open(task_file, "r", encoding="utf-8") as file:
#         return list(csv.DictReader(file))


# # User workload
# def calculate_user_workload(all_tasks, task_owner):
#     user_total_hours = {}
#     # Skip tasks that are completed or client approval pending
#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = row["id"]
#         assignee = str(task_owner.get(task_id, "0")).strip()
#         hours = float(row.get("estimated_hours") or 0.0)

#         # Add these hours to the user's running total
#         user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

#     # print("\nuser_total_hours:\n", user_total_hours)
#     return user_total_hours


# # Sort candidates
# def sort_candidates(candidate):
#     # a person with 40 hours free (-40) comes before someone with 10 hours free (-10)
#     highest_remaining = -candidate["remaining"]
#     # If two people have the same free hours,we pick the one who is less buzy
#     lowest_task_count = candidate["task_count"]

#     # print("HIGHEST REMAINING CANDIDATES:\n",highest_remaining)
#     # print("\nLOWEST TASK COUNT:\n",lowest_task_count)
#     return (highest_remaining, lowest_task_count)


# # Helper to sort by total load (lowest hours first)
# def sort_by_load(user_dict):
#     return user_dict["total_load"]


# def generate_suggestion(status, original_assignee, reassigned_to, final_load):
#     if status == "OVERLOADED":
#         return f"Original assignee {original_assignee} is over capacity; reassigned to user {reassigned_to}."

#     elif status == "DELAYED":
#         if reassigned_to != original_assignee:
#             return f"Task is past deadline; reassigned from user {original_assignee} to user {reassigned_to}."
#         else:
#             return "Task is past deadline; escalate immediately."

#     elif status == "DELAYED_TIMELINE_EXTENSION":
#         return f"All skilled resources fully booked; task queued for user {reassigned_to} and will begin after {final_load} hours."

#     elif status == "USER_UNDERUTILIZED_BUT_LATE":
#         return f"Assignee {original_assignee} has low workload but task is late; reassigned to user {reassigned_to}."

#     elif status == "UNASSIGNED_NOW_ASSIGNED":
#         return f"Task was unassigned; reassigned to user {reassigned_to}."

#     elif status == "NO_SKILLED_USER_FOUND":
#         return "No skilled resource found for this task; escalate to management immediately."

#     elif status == "ON_TIME":
#         return "On track; continue routine monitoring."

#     return "Manual review required."


# # Check status and process tasks
# def process_tasks(all_tasks, task_owner, user_capacity, user_skills, user_total_hours, user_task_count):
#     tasks_summary = []
#     for row in all_tasks:
#         # Skip completed or client_approval_pending tasks
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue 
        
#         # For each task, takes original user, hours required, and owner's current capacity
#         task_id = int(row["id"])
#         deadline = row["date_deadline"]
#         required_skill = row.get("required_skill_id")
#         hours = float(row.get("estimated_hours") or 0.0)
        
#         # Get the id of the person currently assigned to this task
#         original_assignee = str(task_owner.get(str(task_id), "0")).strip()
#         # Get the users workload and capacity
#         total_workload = user_total_hours.get(original_assignee, 0.0)
#         capacity = user_capacity.get(original_assignee, 0.0)

#         # Convert string deadline to date object for comparison
#         deadline_date = None
#         if deadline:
#             deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#         # Task Status
#         if deadline_date and today > deadline_date:
#             if original_assignee == "0":
#                 status = "UNASSIGNED"
#             elif total_workload >= capacity:
#                 status = "OVERLOADED"
#             elif 0 < total_workload < (capacity * underutilized_per):
#                 status = "USER_UNDERUTILIZED_BUT_LATE"
#             else:
#                 status = "DELAYED"
#         else:
#             status = "ON_TIME"

#         reassigned_to = original_assignee

#         # Reassignment Logic
#         if status != "ON_TIME":
#             # Task has no assignee
#             if status == "UNASSIGNED":
#                 skilled_users = user_skills.get(required_skill, [])
#                 if not skilled_users:
#                     # Nobody in the system knows this skill
#                     print(f"[WARNING] Task {task_id} is UNASSIGNED and no skilled users found for skill {required_skill}")
#                     tasks_summary.append({
#                         "task_id": task_id,
#                         "status":status,
#                         "original_assignee":original_assignee,
#                         "reassigned_to":"0",
#                         "hours":hours,
#                         "final_load":0.0,
#                         "deadline":deadline_date
#                     })
#                     continue

#                 # Find skilled users who still have time for this task
#                 candidates = []
#                 for user_id in skilled_users:
#                     user_id = str(user_id).strip()
#                     load = user_total_hours.get(user_id, 0.0)
#                     cap = user_capacity.get(user_id, 0.0)
#                     if load + hours <= cap:
#                         # This user has capacity to take the task
#                         candidates.append({
#                             "user_id": user_id,
#                             "remaining": cap - load,
#                             "task_count": user_task_count.get(user_id, 0) 
#                         })

#                 if candidates:
#                     # Get the best available person and assign the task to them
#                     candidates.sort(key=sort_candidates)
#                     best = candidates[0]
#                     reassigned_to = best["user_id"]
#                     # Update the user's load for future task account for this new assignment
#                     user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#                     user_task_count[reassigned_to] += 1
#                     status = "UNASSIGNED_NOW_ASSIGNED"
#                     tasks_summary.append({
#                         "task_id": task_id,
#                         "status": status,
#                         "original_assignee": original_assignee,
#                         "reassigned_to": reassigned_to,
#                         "hours": hours,
#                         "final_load": 0.0,
#                         "deadline":deadline_date
#                     })
#                     continue 
#                 else:
#                     # All are buzy, pick whoever has the lightest load -> they will be free soonest
#                     # lowest_load = 999999.0
#                     lowest_load = float("inf")
#                     reassigned_to = None
#                     for skilled_user in skilled_users:
#                         user_id = str(skilled_user).strip()
#                         current_load = user_total_hours.get(user_id,0.0)

#                         if current_load < lowest_load:
#                             lowest_load = current_load
#                             reassigned_to = user_id

#                     # This task will have to wait
#                     status = "DELAYED_TIMELINE_EXTENSION"

#                     tasks_summary.append({
#                         "task_id":task_id,
#                         "status": status,
#                         "original_assignee": original_assignee,
#                         "reassigned_to": reassigned_to,
#                         "hours": hours,
#                         "final_load": 0.0,
#                         "deadline":deadline_date
#                     })
#                     continue

#             # if status is just delayed and user has capacity, keep the original assignee
#             if status == "DELAYED" and original_assignee != "0":
#                 total_workload = user_total_hours.get(original_assignee,0.0)
#                 capacity = user_capacity.get(original_assignee,0.0)
#                 if total_workload <= capacity:
#                     tasks_summary.append({
#                         "task_id":task_id,
#                         "status":status,
#                         "original_assignee":original_assignee,
#                         "reassigned_to":original_assignee,
#                         "hours":hours,
#                         "final_load":0.0,
#                         "deadline":deadline_date
#                     })
#                     # skip reassignment logic entirely
#                     continue
#             # when no skilled users found
#             candidates = []
#             # Users we have already evaluated to avoid duplicates
#             seen = set()
#             skilled_users = user_skills.get(required_skill, [])

#             if not skilled_users:
#                 # Skill doesn't exist
#                 print(f"=====> Task {task_id}: No users found with skill '{required_skill}' — cannot reassign")
#                 tasks_summary.append({
#                     "task_id": task_id,
#                     "status": "NO_SKILLED_USER_FOUND",
#                     "original_assignee": original_assignee,
#                     "reassigned_to": original_assignee,  # keep original assignee
#                     "hours": hours,
#                     "final_load": 0.0,
#                     "deadline":deadline_date
#                 })
#                 continue
#             # Filter for skilled users who have enough weekly capacity
#             for user_ids in skilled_users:
#                 user_id = str(user_ids).strip()
#                 if user_id in seen:
#                     continue # skip if already checked
#                 seen.add(user_id)

#                 # dont reassign to the same person
#                 if status in ("USER_UNDERUTILIZED_BUT_LATE","DELAYED") and user_id == original_assignee:
#                     continue
#                 load = user_total_hours.get(user_id, 0.0)
#                 cap = user_capacity.get(user_id, 0.0)
                
#                 # finds users with the right skill who can fit these new hours into their current capacity
#                 if load + hours <= cap:
#                     candidates.append({
#                         "user_id": user_id,
#                         "remaining": cap - load,
#                         "task_count": user_task_count.get(user_id, 0)
#                     })

#             if candidates:
#                 # Pick the best candidate -> most free hours + fewest tasks
#                 candidates.sort(key=sort_candidates)
#                 best_user = candidates[0]
#                 reassigned_to = best_user["user_id"]

#                 # update new assignee workload for future tasks
#                 user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#                 user_task_count[reassigned_to] += 1
                
#                 # ermove task hours of original assignee
#                 if original_assignee != "0" and original_assignee != reassigned_to:
#                     user_total_hours[original_assignee] = max(0.0,user_total_hours.get(original_assignee, 0.0) - hours)
#                     user_task_count[original_assignee] = max(0,user_task_count.get(original_assignee, 0) - 1)
#             else:
#                 # No one has free capacity — pick the person who will be free soonest
#                 load_skilled_list = []
#                 seen_load = set()
#                 for user_ids in skilled_users:
#                     user_id = str(user_ids).strip()
#                     if user_id in seen_load:
#                         continue
#                     seen_load.add(user_id)
#                     # don't queue to the same perspn
#                     if status in ("USER_UNDERUTILIZED_BUT_LATE", "DELAYED") and user_id == original_assignee:
#                         continue
#                     load_skilled_list.append({
#                         "user_id": user_id,
#                         "total_load": user_total_hours.get(user_id, 0.0)
#                     })

#                 if load_skilled_list:
#                     # Pick person with the lowest current hour load
#                     load_skilled_list.sort(key=sort_by_load)

#                     reassigned_to = load_skilled_list[0]["user_id"]
#                     # mark timeline extension -> go into queue
#                     status = "DELAYED_TIMELINE_EXTENSION"

#                     # user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours

#                     # don't add hours to their current load yet
#                     # The task starts AFTER they finish current work
#                     # delayed_assignments will track when they'll be free
#                 else:
#                     # Keep the original assignee if no skilled users found
#                     reassigned_to = original_assignee
#                     status = "DELAYED_TIMELINE_EXTENSION"
#                 # else:
#                 #     reassigned_to = original_assignee
#                 # print("\nLOAD SKILLED LIST:\n",load_skilled_list)
#         print(f"\nTask {task_id} -> Reassigned to: {reassigned_to} (Status: {status})\n")

#         # Record the result
#         tasks_summary.append({
#             "task_id": task_id,
#             "status": status,
#             "original_assignee": original_assignee,
#             "reassigned_to": reassigned_to,
#             "hours": hours,
#             "final_load":0.0,
#             "deadline":deadline_date
#         })

#     # print("\nTASKS SUMMARY:\n", tasks_summary)
#     # print("\nTOTAL TASKS:", len(all_tasks))
#     # print("\nTASKS SUMMARY COUNT:", len(tasks_summary))
#     # print(f"\nDEBUG: Successfully processed {len(tasks_summary)} tasks.")
#     return tasks_summary


# # AFTER-PROCESSING: Calculate new deadlines for queued tasks
# # def delayed_assignments(tasks_summary, user_skills, user_total_hours):
# #     for row in tasks_summary:
# #         if row["status"] == "DELAYED_TIMELINE_EXTENSION":
# #             assignee = row["reassigned_to"]
# #             # Count after how many hours user will be free
# #             free_after_hours = user_total_hours.get(assignee, 0.0)
# #             # Stored for hours suggestion message
# #             row["final_load"] = free_after_hours

# #             # (free_after_hours + row["hours"]) -> Total Hours the person is now committed to.
# #             # (existing queue + this task's hours) / 8 hours per day, rounded up
# #             days_needed = math.ceil((free_after_hours + row["hours"]) / 8)
# #             row["new_deadline"] = (today + timedelta(days=days_needed)).strftime("%Y-%m-%d")
# #             # Add tasks hours to the queue for next queued tasks
# #             user_total_hours[assignee] = free_after_hours + row["hours"]
# #         else:
# #             # task doesnt need timeline extension - clear final load and keep original deadline
# #             row["final_load"] = 0.0
# #             row["new_deadline"] = row.get("deadline", "")

#     # return tasks_summary


# def delayed_assignments(tasks_summary, user_skills, user_total_hours):
#     for row in tasks_summary:
#         # Get the person who will do the work
#         person = row["reassigned_to"]

#         if row["status"] == "DELAYED_TIMELINE_EXTENSION":
#             # See how many hours they are already busy
#             current_work = user_total_hours.get(person, 0.0)
#             row["final_load"] = current_work
            
#             # Add the new task's hours
#             total_hours = current_work + row["hours"]
            
#             # If 30 hours / 8 = 3.75, we need 4 days.
#             days_needed = int(total_hours / hours_per_day)
#             if days_needed > int(days_needed):
#                 days_needed = int(days_needed) + 1
#             else:
#                 days_needed = int(days_needed)
            
#             # Calculate the new date . timedelta -> move forward
#             new_date = today + timedelta(days=days_needed)
#             # strftime -> string format time
#             row["new_deadline"] = new_date.strftime("%Y-%m-%d")
            
#             # Update their total work for the next task
#             user_total_hours[person] = total_hours
            
#         else:
#             # If not delayed, just keep everything as it was
#             row["final_load"] = 0.0
#             row["new_deadline"] = row.get("deadline", "")
            
#     return tasks_summary


# # Reason and Suggestion generation
# def generate_ai_output(tasks_summary):
#     print("============ ENTERED GENERATE AI OUTPUT ===========")
#     final_output = []
#     # how many tasks to send to the ai at once (smaller = more reliable responses)
#     chunk_size = 5

#     # pre-defined text used if the Ai fails or return empty response
#     fallback_reasons = {
#         "ON_TIME": "Task is progressing on schedule with no issues.",
#         "OVERLOADED": "Assignee exceeded weekly capacity; task rebalanced to an available resource.",
#         "DELAYED": "Task has passed its deadline and requires immediate attention.",
#         "USER_UNDERUTILIZED_BUT_LATE": "Assignee has available capacity but the task is still late.",
#         "DELAYED_TIMELINE_EXTENSION": "All team members are at full capacity; assigned to earliest available person."
#     }
#     fallback_suggestions = {
#         "ON_TIME": "Continue monitoring progress and ensure no blockers arise.(fallback)",
#         "OVERLOADED": "Review workload distribution and consider hiring or redistributing tasks.(fallback)",
#         "DELAYED": "Prioritize this task and check.(fallback)",
#         "USER_UNDERUTILIZED_BUT_LATE": "Investigate why the task is late despite available capacity.(fallback)",
#         "DELAYED_TIMELINE_EXTENSION": "Extend the task deadline and inform stakeholders of the new timeline.(fallback)"
#     }

#     prompt = f"""
# IMPORTANT: Respond with ONLY a valid JSON array. No preamble, no markdown.
# You are a Project Manager AI.

# Your task is to take the provided 'suggestion' field and ensure it is formatted correctly into a JSON response. 

# Constraints:
# - Return one entry per task. Output array MUST have SAME LENGTH as input array ({chunk_size}).
# - Do NOT change the meaning of the provided suggestion.
# - Format: [{{"task_id": 123, "suggestion": "text from input"}}]
# """



#     # process tasks in batches - chunk_size
#     for i in range(0, len(tasks_summary), chunk_size):
#         chunk = tasks_summary[i: i + chunk_size]
#         # Tell AI how many tasks are there in this batch
#         chunk_instruction = f"- This chunk has EXACTLY {len(chunk)} tasks. Return EXACTLY {len(chunk)} entries."
#         try:
#             # Call model
#             response = chat(
#                 model="llama3.2",
#                 messages=[
#                     # {"role": "system", "content": prompt},
#                     {"role": "system", "content": prompt + chunk_instruction},
#                     {"role": "user", "content": json.dumps(chunk, default=str)}
#                 ],
#                 options={"temperature": 0}
#             )
#             content = response.message.content.strip()

#             # Debug: print raw AI response to catch formatting issues
#             print(f"\n=====> Raw AI response for chunk {i}:\n{content}\n")

#             # Clean markdown fences if present
#             content = re.sub(r"```(?:json)?", "", content).strip()
#             content = content.strip("`").strip()

#             # Extract JSON array
#             match = re.search(r'\[.*?\]', content, re.DOTALL)
#             if not match:
#                 raise ValueError(f"No JSON array found in AI response: {content[:200]}")

#             ai_output = json.loads(match.group())

#             # Validate all task_ids are present
#             # returned_ids = {str(r.get("task_id")) for r in ai_output}
#             # expected_ids = {str(item["task_id"]) for item in chunk}
#             # missing_ids = expected_ids - returned_ids
#             # if missing_ids:
#             #     print(f"[WARNING] AI missed task_ids: {missing_ids} — using fallback for those")

#             # check how many tasks AI returned
#             if len(ai_output) != len(chunk):
#                 print(f"=====> AI returned {len(ai_output)} tasks but expected {len(chunk)}")
#                 returned_ids = {str(r.get("task_id")) for r in ai_output}
#                 expected_ids = {str(item["task_id"]) for item in chunk}
#                 print(f"=====> Missing task_ids: {expected_ids - returned_ids}")

#             # mapping, to find AI results by task_id
#             ai_map = {str(r.get("task_id")): r for r in ai_output}

#             # for each task in chunk - build final output row
#             for item in chunk:
#                 suggestion = generate_suggestion(
#                     item["status"],
#                     item["original_assignee"],
#                     item["reassigned_to"],
#                     item.get("final_load", 0.0)
#                 )

#                 reason = fallback_reasons.get(item["status"], "Manual review required.")

#                 final_output.append({
#                     # all fields from tasks_summary
#                     **item,
#                     "reason": reason,
#                     "suggestion": suggestion
#                 })

#             # for item in chunk:
#             #     t_id = str(item["task_id"])
#             #     status = item["status"]
#             #     reassigned_to = item["reassigned_to"]
#             #     original_assignee = item["original_assignee"]
#             #     final_load = item.get("final_load", 0.0)


#             #     ai_data = ai_map.get(t_id)

#             #     # Use AI data if valid, else fall back to status-specific defaults
#             #     reason = (ai_data.get("reason") if ai_data and ai_data.get("reason") else None) \
#             #              or fallback_reasons.get(status, "Manual review required.")
#             #     suggestion = (ai_data.get("suggestion") if ai_data else None) or fallback_suggestions.get(status)

#             #     if status == "DELAYED_TIMELINE_EXTENSION":
#             #         # LLM sometimes applies DELAYED rule here — override it
#             #         if "queued" not in suggestion.lower() or "hours" not in suggestion.lower():
#             #             suggestion = f"All skilled resources fully booked; task queued for user {reassigned_to} and will begin after {final_load} hours."

#             #     elif status == "OVERLOADED":
#             #         # LLM sometimes applies DELAYED_TIMELINE_EXTENSION rule here — override it
#             #         if "queued" in suggestion.lower() or "booked" in suggestion.lower():
#             #             suggestion = f"Original assignee {original_assignee} is over capacity; reassigned to user {reassigned_to}."


#             #     elif status == "DELAYED":
#             #         # LLM sometimes says "escalate" even when reassigned to a different user
#             #         if reassigned_to != original_assignee and "escalate" in suggestion.lower():
#             #             suggestion = f"Task is past deadline; reassigned from user {original_assignee} to user {reassigned_to}."

#             #     elif status == "USER_UNDERUTILIZED_BUT_LATE":
#             #         # LLM sometimes forgets to mention the new assignee
#             #         if reassigned_to != original_assignee and reassigned_to not in suggestion:
#             #             suggestion = f"Assignee {original_assignee} has low workload but task is late; reassigned to user {reassigned_to}."
                        
#             #     final_output.append({
#             #         **item, # Get all the fields like task_id,status ...
#             #         "reason": reason,
#             #         "suggestion": suggestion
#             #     })

#             print(f"=====> Chunk {i} processed successfully. Tasks so far: {len(final_output)}")

#         except json.JSONDecodeError as e:
#             # fallback if AI returned something invalid
#             print(f"=====> JSON parse failed for chunk {i}: {e}")
#             for item in chunk:
#                 status = item["status"]
#                 final_output.append({
#                     **item, # Get all the fields like task_id,status ...
#                     "reason": fallback_reasons.get(status, "Manual review required."),
#                     "suggestion": fallback_suggestions.get(status, "Check resource availability.")
#                 })
#     # print("final output ===========:\n", final_output)
#     return final_output




# # Save the output
# # def save_output(final_output, output_file):
# #     with open(output_file, "w", encoding="utf-8") as file:
# #         columns = [
# #             "task_id", "status", "original_assignee", "reassigned_to", 
# #             "reason", "suggestion", "hours", "final_load"
# #         ]

# #         writer = csv.DictWriter(file, fieldnames=columns)
# #         writer.writeheader()
# #         writer.writerows(final_output)
        
# #     for row in final_output:
# #         print("\nROW SAVED:\n", row)


# # def save_output(final_output, output_file):
# #     with open(output_file, "w", encoding="utf-8", newline="") as file:
# #         columns = [
# #             "task_id", "status", "original_assignee", "reassigned_to",
# #             "reason", "suggestion", "hours", "final_load",
# #             "deadline","new_deadline"
# #         ]
# #         # quoting=csv.QUOTE_ALL -> tells python to put double qoutes
# #         writer = csv.DictWriter(file, fieldnames=columns, quoting=csv.QUOTE_ALL)
# #         writer.writeheader()
# #         writer.writerows(final_output)


# def save_output(final_output, output_file):
#     # Open the file for writing
#     with open(output_file, "w", encoding="utf-8", newline="") as file:
#         columns = [
#             "task_id", "status", "original_assignee", "reassigned_to",
#             "reason", "suggestion", "hours", "final_load", "new_deadline"
#         ]
#         # quoting=csv.QUOTE_ALL -> add double qoutes on each piece of data
#         writer = csv.DictWriter(file, fieldnames=columns, quoting=csv.QUOTE_ALL)
#         writer.writeheader()

#         # Write each row one by one
#         for row in final_output:
#             # Create a simple dictionary for the row we are about to write
#             clean_row = {}
#             for col in columns:
#                 # Get the value from the data, use empty string if missing
#                 value = row.get(col, "")
#                 # Convert the value to a string 
#                 clean_row[col] = str(value)
            
#             # Write the single line to the file
#             writer.writerow(clean_row)
    
#             print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(clean_row, indent=2, default=str))


# # Execution Code
# def main():
#     task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
#     assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
#     skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
#     users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"
#     output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

#     task_owner, all_assigned_users = load_task_assignments(assign_file)
#     user_capacity = load_user_capacity(users_file)
#     user_skills = load_user_skills(skill_file)
#     all_tasks = load_tasks(task_file)

#     user_task_count = Counter(all_assigned_users)
#     user_total_hours = calculate_user_workload(all_tasks, task_owner)

#     tasks_summary = process_tasks(
#         all_tasks,
#         task_owner,
#         user_capacity,
#         user_skills,
#         user_total_hours,
#         user_task_count,
#     )

#     updated_tasks_summary= delayed_assignments(tasks_summary, user_skills, user_total_hours)
#     # print("updated_tasks_summary : \n ", updated_tasks_summary)
#     # print("==="*45)
#     # print()
#     final_output = generate_ai_output(updated_tasks_summary)
#     # print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2, default=str))
 
#     save_output(final_output, output_file)


# if __name__ == "__main__":
#     main()










# import re
# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# today = datetime.now().date()
# underutilized_per = 0.5

# # # Get remaining
# # def get_remaining(candidate):
# #     return candidate["remaining"]

# # Load tasks assignments -> who is currently working on which task
# def load_task_assignments(assign_file):
#     task_owner = {}
#     all_assigned_users = []

#     with open(assign_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             users = (row.get("user_id") or "0").strip()
#             user_ids = users if users != "" else "0"
#             task_owner[row["task_id"]] = user_ids
#             all_assigned_users.append(user_ids)
#     print("\nALL ASSIGNED USERS:\n",all_assigned_users)
#     print("\nTASK OWNER:\n", task_owner)
#     return task_owner, all_assigned_users


# # Load user capacity -> weekly capacity of the user
# def load_user_capacity(users_file):
#     user_capacity = {}
#     with open(users_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             user_capacity[row["id"]] = float(row.get("weekly_capacity", 0))
#     print("\nuser_capacity:\n", user_capacity)
#     return user_capacity


# # Load user skills
# def load_user_skills(skill_file):
#     user_skills = {}

#     with open(skill_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             skill = row["skill_id"]
#             user = row["user_id"]
#             if skill not in user_skills:
#                 user_skills[skill] = []
#             user_skills[skill].append(user)

#     print("\nuser_skills:\n", user_skills)
#     return user_skills


# # Load tasks
# def load_tasks(task_file):
#     with open(task_file, "r", encoding="utf-8") as file:
#         return list(csv.DictReader(file))


# # User workload
# def calculate_user_workload(all_tasks, task_owner):
#     user_total_hours = {}
#     # Skip tasks that are completed or client approval pending
#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = row["id"]
#         assignee = str(task_owner.get(task_id, "0")).strip()
#         hours = float(row.get("estimated_hours") or 0.0)

#         # Add these hours to the user's running total
#         user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

#     print("\nuser_total_hours:\n", user_total_hours)
#     return user_total_hours


# # Sort candidates
# def sort_candidates(candidate):
#     # a person with 40 hours free (-40) comes before someone with 10 hours free (-10)
#     highest_remaining = -candidate["remaining"]
#     # If two people have the same free hours,we pick the one who is less buzy
#     lowest_task_count = candidate["task_count"]

#     print("HIGHEST REMAINING CANDIDATES:\n",highest_remaining)
#     print("\nLOWEST TASK COUNT:\n",lowest_task_count)
#     return (highest_remaining, lowest_task_count)


# # Helper to sort by total load (lowest hours first)
# def sort_by_load(user_dict):
#     return user_dict["total_load"]


# def generate_suggestion(status, original_assignee, reassigned_to, final_load):
#     if status == "OVERLOADED":
#         return f"Original assignee {original_assignee} is over capacity; reassigned to user {reassigned_to}."

#     elif status == "DELAYED":
#         if reassigned_to != original_assignee:
#             return f"Task is past deadline; reassigned from user {original_assignee} to user {reassigned_to}."
#         else:
#             return "Task is past deadline; escalate immediately."

#     elif status == "DELAYED_TIMELINE_EXTENSION":
#         return f"All skilled resources fully booked; task queued for user {reassigned_to} and will begin after {final_load} hours."

#     elif status == "USER_UNDERUTILIZED_BUT_LATE":
#         return f"Assignee {original_assignee} has low workload but task is late; reassigned to user {reassigned_to}."

#     elif status == "UNASSIGNED_NOW_ASSIGNED":
#         return f"Task was unassigned; reassigned to user {reassigned_to}."

#     elif status == "NO_SKILLED_USER_FOUND":
#         return "No skilled resource found for this task; escalate to management immediately."

#     elif status == "ON_TIME":
#         return "On track; continue routine monitoring."

#     return "Manual review required."


# # Check status and process tasks
# def process_tasks(all_tasks, task_owner, user_capacity, user_skills, user_total_hours, user_task_count):
#     tasks_summary = []
#     for row in all_tasks:
#         # Skip completed or client_approval_pending tasks
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue 
        
#         # For each task, takes original user, hours required, and owner's current capacity
#         task_id = int(row["id"])
#         deadline = row["date_deadline"]
#         required_skill = row.get("required_skill_id")
#         hours = float(row.get("estimated_hours") or 0.0)
        
#         # Get the id of the person currently assigned to this task
#         original_assignee = str(task_owner.get(str(task_id), "0")).strip()
#         total_workload = user_total_hours.get(original_assignee, 0.0)
#         capacity = user_capacity.get(original_assignee, 0.0)

#         # Convert string deadline to date object for comparison
#         deadline_date = None
#         if deadline:
#             deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#         # Task Status
#         if deadline_date and today > deadline_date:
#             if original_assignee == "0":
#                 status = "UNASSIGNED"
#             elif total_workload >= capacity:
#                 status = "OVERLOADED"
#             elif 0 < total_workload < (capacity * underutilized_per):
#                 status = "USER_UNDERUTILIZED_BUT_LATE"
#             else:
#                 status = "DELAYED"
#         else:
#             status = "ON_TIME"

#         reassigned_to = original_assignee
#         final_load = 0.0
#         # Reassignment Logic -> catch all non-ON_TIME statuses
#         if status != "ON_TIME":

#             if status == "UNASSIGNED":
#                 skilled_users = user_skills.get(required_skill, [])
#                 if not skilled_users:
#                     print(f"[WARNING] Task {task_id} is UNASSIGNED and no skilled users found for skill {required_skill}")
#                     tasks_summary.append({
#                         "task_id": task_id,
#                         "status":status,
#                         "original_assignee":original_assignee,
#                         "reassigned_to":"0",
#                         "hours":hours,
#                         "final_load":0.0
#                     })
#                     continue
#                 candidates = []
#                 for user_id in skilled_users:
#                     user_id = str(user_id).strip()
#                     load = user_total_hours.get(user_id, 0.0)
#                     cap = user_capacity.get(user_id, 0.0)
#                     if load + hours <= cap:
#                         candidates.append({
#                             "user_id": user_id,
#                             "remaining": cap - load,
#                             "task_count": user_task_count.get(user_id, 0) 
#                         })

#                 if candidates:
#                     candidates.sort(key=sort_candidates)
#                     best = candidates[0]
#                     reassigned_to = best["user_id"]
#                     user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#                     user_task_count[reassigned_to] += 1
#                     status = "UNASSIGNED_NOW_ASSIGNED"
#                     tasks_summary.append({                        # FIX: append + continue were missing
#                         "task_id": task_id,
#                         "status": status,
#                         "original_assignee": original_assignee,
#                         "reassigned_to": reassigned_to,
#                         "hours": hours,
#                         "final_load": 0.0
#                     })
#                     continue 
#                 else:
#                     lowest_load = 999999.0
#                     reassigned_to = None
#                     for s_user in skilled_users:
#                         u_id = str(s_user).strip()
#                         current_load = user_total_hours.get(u_id,0.0)

#                         if current_load < lowest_load:
#                             lowest_load = current_load
#                             reassigned_to = u_id

#                     status = "DELAYED_TIMELINE_EXTENSION"

#                     tasks_summary.append({
#                         "task_id":task_id,
#                         "status": status,
#                         "original_assignee": original_assignee,
#                         "reassigned_to": reassigned_to,
#                         "hours": hours,
#                         "final_load": 0.0
#                     })
#                     continue
#             # if status is just delayed and user has capacity, keep the original assignee
#             if status == "DELAYED" and original_assignee != "0":
#                 total_workload = user_total_hours.get(original_assignee,0.0)
#                 capacity = user_capacity.get(original_assignee,0.0)
#                 if total_workload <= capacity:
#                     tasks_summary.append({
#                         "task_id":task_id,
#                         "status":status,
#                         "original_assignee":original_assignee,
#                         "reassigned_to":original_assignee,
#                         "hours":hours,
#                         "final_load":0.0
#                     })
#                     # skip reassignment logic entirely
#                     continue
#             # when no skilled users found
#             candidates = []
#             seen = set()
#             skilled_users = user_skills.get(required_skill, [])

#             if not skilled_users:
#                 print(f"[WARNING] Task {task_id}: No users found with skill '{required_skill}' — cannot reassign")
#                 tasks_summary.append({
#                     "task_id": task_id,
#                     "status": "NO_SKILLED_USER_FOUND",
#                     "original_assignee": original_assignee,
#                     "reassigned_to": original_assignee,  # keep as-is
#                     "hours": hours,
#                     "final_load": 0.0
#                 })
#                 continue  # skip rest of reassignment logic

#             # Filter for skilled users who have enough weekly capacity remaining
#             for user_ids in skilled_users:
#                 user_id = str(user_ids).strip()
#                 if user_id in seen:
#                     continue
#                 seen.add(user_id)
#                 # Avoid re-assigning to the same underutilized user who is already late
#                 if status in ("USER_UNDERUTILIZED_BUT_LATE","DELAYED") and user_id == original_assignee:
#                     continue
#                 load = user_total_hours.get(user_id, 0.0)
#                 cap = user_capacity.get(user_id, 0.0)
                
#                 # It finds users with the right skill who can fit these new hours into their current capacity
#                 if load + hours <= cap:
#                     candidates.append({
#                         "user_id": user_id,
#                         "remaining": cap - load,
#                         "task_count": user_task_count.get(user_id, 0)
#                     })

#             if candidates:
#                 # Pick the best candidate -> most free hours + fewest tasks
#                 candidates.sort(key=sort_candidates)
#                 best_user = candidates[0]
#                 reassigned_to = best_user["user_id"]

#                 # Update workload immediately for the next loop iteration
#                 user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#                 user_task_count[reassigned_to] += 1

#                 if original_assignee != "0" and original_assignee != reassigned_to:
#                     user_total_hours[original_assignee] = max(0.0,user_total_hours.get(original_assignee, 0.0) - hours)
#                     user_task_count[original_assignee] = max(0,user_task_count.get(original_assignee, 0) - 1)
#             else:
#                 # No one has free capacity — pick the person who will be free soonest
#                 load_skilled_list = []
#                 seen_load = set()
#                 for user_ids in skilled_users:
#                     user_id = str(user_ids).strip()
#                     if user_id in seen_load:
#                         continue
#                     seen_load.add(user_id)
#                     if status in ("USER_UNDERUTILIZED_BUT_LATE", "DELAYED") and user_id == original_assignee:
#                         continue
#                     load_skilled_list.append({
#                         "user_id": user_id,
#                         "total_load": user_total_hours.get(user_id, 0.0)
#                     })
                
#                 if not load_skilled_list:
#                     print(f"[WARNING] Task {task_id}: No skilled user other than original '{original_assignee}'. "
#                         f"Queuing to least-loaded skilled user including original.")
#                     for user in skilled_users:
#                         user_id = str(user).strip()
#                         if useri_id in seen_load:
#                             continue
#                         seen_load.add(user_id)
#                         load_skilled_list.append({
#                             "user_id": user_id,
#                             "total_load": user_total_hours.get(user_id, 0.0) + delayed_queue_load.get(user_id, 0.0)
#                         })

#                 if load_skilled_list:
#                     # Pick person with the lowest current hour load
#                     load_skilled_list.sort(key=sort_by_load)

#                     reassigned_to = load_skilled_list[0]["user_id"]
#                     status = "DELAYED_TIMELINE_EXTENSION"
#                     # user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours  # ✅

#                     # don't add hours to their current load yet
#                     # The task starts AFTER they finish current work
#                     # delayed_assignments will track when they'll be free
#                 else:
#                     # Keep the original assigneeif no skilled users found
#                     reassigned_to = original_assignee
#                     # status = "DELAYED_TIMELINE_EXTENSION"
#                 final_load = user_total_hours.get(reassigned_to, 0.0) + delayed_queue_load.get(reassigned_to, 0.0)
#                 delayed_queue_load[reassigned_to] = delayed_queue_load.get(reassigned_to, 0.0) + hours
#                 status = "DELAYED_TIMELINE_EXTENSION"

#                 # else:
#                 #     reassigned_to = original_assignee
#                 print("\nLOAD SKILLED LIST:\n",load_skilled_list)
#         print(f"\nTask {task_id} -> Reassigned to: {reassigned_to} (Status: {status})\n")

#         # Record the result
#         tasks_summary.append({
#             "task_id": task_id,
#             "status": status,
#             "original_assignee": original_assignee,
#             "reassigned_to": reassigned_to,
#             "hours": hours,
#             "final_load":0.0
#         })

#     print("\nTASKS SUMMARY:\n", tasks_summary)
#     print("\nTOTAL TASKS:", len(all_tasks))
#     print("\nTASKS SUMMARY COUNT:", len(tasks_summary))
#     print(f"\nDEBUG: Successfully processed {len(tasks_summary)} tasks.")
#     return tasks_summary


# # Only process tasks that needs time extension
# # def delayed_assignments(tasks_summary, user_skills, user_total_hours):
# #     for row in tasks_summary:
# #         if row["status"] == "DELAYED_TIMELINE_EXTENSION":
# #             task_id = row["task_id"]
# #             assignee = row["reassigned_to"]

# #             # This is when they finish current work = when this task can start
# #             free_after_hours = user_total_hours.get(assignee, 0.0)
# #             row["final_load"] = free_after_hours
            
# #             print("FINAL LOAD:\n",row["final_load"])
# #             print(f"--> DELAYED TASK {task_id}: assigned to {assignee}")
# #             print(f"--> They are free after {free_after_hours} hours of current work")
# #             print(f"--> Task will start only after that — no overloading")

# #             # NOW add the task hours (task starts after they're free)
# #             user_total_hours[assignee] = free_after_hours + row["hours"]
# #         else:
# #             row["final_load"] = 0.0

# #     return tasks_summary

# # Reason and Suggestion generation
# def generate_ai_output(tasks_summary):
#     print("============ ENTERED GENERATE AI OUTPUT ===========")
#     final_output = []
#     # It splits the big list into small group of 10 tasks
#     chunk_size = 5

#     # pre-defined text used if the Ai fails or return empty response
#     fallback_reasons = {
#         "ON_TIME": "Task is progressing on schedule with no issues.",
#         "OVERLOADED": "Assignee exceeded weekly capacity; task rebalanced to an available resource.",
#         "DELAYED": "Task has passed its deadline and requires immediate attention.",
#         "USER_UNDERUTILIZED_BUT_LATE": "Assignee has available capacity but the task is still late.",
#         "DELAYED_TIMELINE_EXTENSION": "All team members are at full capacity; assigned to earliest available person."
#     }
#     fallback_suggestions = {
#         "ON_TIME": "Continue monitoring progress and ensure no blockers arise.(fallback)",
#         "OVERLOADED": "Review workload distribution and consider hiring or redistributing tasks.(fallback)",
#         "DELAYED": "Prioritize this task and check.(fallback)",
#         "USER_UNDERUTILIZED_BUT_LATE": "Investigate why the task is late despite available capacity.(fallback)",
#         "DELAYED_TIMELINE_EXTENSION": "Extend the task deadline and inform stakeholders of the new timeline.(fallback)"
#     }

#     prompt = """
#         IMPORTANT: Respond with ONLY a valid JSON array. No preamble, no markdown, no explanations.
#         You are a Project Manager AI.

#         Data available: task_id, status, original_assignee, reassigned_to, hours, final_load.

#         These are the ONLY valid statuses and their rules. Match EXACTLY on the status field:

#         - "OVERLOADED": assignee exceeded capacity, task moved to someone else.
#             → "Original assignee [original_assignee] is over capacity; reassigned to user [reassigned_to]."

#         - "DELAYED": deadline passed, reassigned to a different skilled user.
#             → If reassigned_to != original_assignee: "Task is past deadline; reassigned from user [original_assignee] to user [reassigned_to]."
#             → If reassigned_to == original_assignee: "Task is past deadline; escalate immediately."

#         - "DELAYED_TIMELINE_EXTENSION": ALL skilled users are fully booked, task is QUEUED.
#             → ALWAYS use: "All skilled resources fully booked; task queued for user [reassigned_to] and will begin after [final_load] hours."
#             → NEVER use the DELAYED rule for this status, even if reassigned_to == original_assignee.

#         - "USER_UNDERUTILIZED_BUT_LATE": assignee has low workload but task is late.
#             → "Assignee [original_assignee] has low workload but task is late; reassigned to user [reassigned_to]."
        
#         - "UNASSIGNED_NOW_ASSIGNED": task had no owner, now assigned.
#             → "Task was unassigned; reassigned to user [reassigned_to]..."

#         - "NO_SKILLED_USER_FOUND": no skilled user exists, needs manual review.
#             → "No skilled resource found for this task; escalate to management immediately."

#         - "ON_TIME": no action needed.
#             → "On track; continue routine monitoring."

#         Constraints:
#         - Process tasks IN THE EXACT ORDER they appear in the input.
#         - Return one entry per task. Output array MUST have SAME LENGTH as input array.
#         - Use ONLY task_ids from the input. Never skip or invent task_ids.
#         f"- Input has EXACTLY {chunk_size} tasks. Output MUST have EXACTLY {chunk_size} entries. Never skip a task_id.\n- Return ONLY: [{{\"task_id\": 123, \"suggestion\": \"text\"}}]"
#         """


#     # Loop through the summary list in increments of 10
#     for i in range(0, len(tasks_summary), chunk_size):
#         chunk = tasks_summary[i: i + chunk_size]
#         chunk_instruction = f"- This chunk has EXACTLY {len(chunk)} tasks. Return EXACTLY {len(chunk)} entries."
#         try:
#             # Call model
#             response = chat(
#                 model="llama3.2",
#                 messages=[
#                     # {"role": "system", "content": prompt},
#                     {"role": "system", "content": prompt + chunk_instruction},
#                     {"role": "user", "content": json.dumps(chunk)}
#                 ],
#                 options={"temperature": 0}
#             )
#             content = response.message.content.strip()

#             # Debug: print raw AI response to catch formatting issues
#             print(f"\n[DEBUG] Raw AI response for chunk {i}:\n{content}\n")

#             # Clean markdown fences if present
#             content = re.sub(r"```(?:json)?", "", content).strip()
#             content = content.strip("`").strip()

#             # Extract JSON array
#             match = re.search(r'\[.*?\]', content, re.DOTALL)
#             if not match:
#                 raise ValueError(f"No JSON array found in AI response: {content[:200]}")

#             ai_output = json.loads(match.group())

#             # Validate all task_ids are present
#             # returned_ids = {str(r.get("task_id")) for r in ai_output}
#             # expected_ids = {str(item["task_id"]) for item in chunk}
#             # missing_ids = expected_ids - returned_ids
#             # if missing_ids:
#             #     print(f"[WARNING] AI missed task_ids: {missing_ids} — using fallback for those")

#             if len(ai_output) != len(chunk):
#                 print(f"[WARNING] AI returned {len(ai_output)} tasks but expected {len(chunk)}")
#                 returned_ids = {str(r.get("task_id")) for r in ai_output}
#                 expected_ids = {str(item["task_id"]) for item in chunk}
#                 print(f"[WARNING] Missing task_ids: {expected_ids - returned_ids}")


#             ai_map = {str(r.get("task_id")): r for r in ai_output}

#             for item in chunk:
#                 suggestion = generate_suggestion(
#                     item["status"],
#                     item["original_assignee"],
#                     item["reassigned_to"],
#                     item.get("final_load", 0.0)
#                 )

#                 reason = fallback_reasons.get(item["status"], "Manual review required.")

#                 final_output.append({
#                     **item,
#                     "reason": reason,
#                     "suggestion": suggestion
#                 })

#             # for item in chunk:
#             #     t_id = str(item["task_id"])
#             #     status = item["status"]
#             #     reassigned_to = item["reassigned_to"]
#             #     original_assignee = item["original_assignee"]
#             #     final_load = item.get("final_load", 0.0)


#             #     ai_data = ai_map.get(t_id)

#             #     # Use AI data if valid, else fall back to status-specific defaults
#             #     reason = (ai_data.get("reason") if ai_data and ai_data.get("reason") else None) \
#             #              or fallback_reasons.get(status, "Manual review required.")
#             #     suggestion = (ai_data.get("suggestion") if ai_data else None) or fallback_suggestions.get(status)

#             #     if status == "DELAYED_TIMELINE_EXTENSION":
#             #         # LLM sometimes applies DELAYED rule here — override it
#             #         if "queued" not in suggestion.lower() or "hours" not in suggestion.lower():
#             #             suggestion = f"All skilled resources fully booked; task queued for user {reassigned_to} and will begin after {final_load} hours."

#             #     elif status == "OVERLOADED":
#             #         # LLM sometimes applies DELAYED_TIMELINE_EXTENSION rule here — override it
#             #         if "queued" in suggestion.lower() or "booked" in suggestion.lower():
#             #             suggestion = f"Original assignee {original_assignee} is over capacity; reassigned to user {reassigned_to}."


#             #     elif status == "DELAYED":
#             #         # LLM sometimes says "escalate" even when reassigned to a different user
#             #         if reassigned_to != original_assignee and "escalate" in suggestion.lower():
#             #             suggestion = f"Task is past deadline; reassigned from user {original_assignee} to user {reassigned_to}."

#             #     elif status == "USER_UNDERUTILIZED_BUT_LATE":
#             #         # LLM sometimes forgets to mention the new assignee
#             #         if reassigned_to != original_assignee and reassigned_to not in suggestion:
#             #             suggestion = f"Assignee {original_assignee} has low workload but task is late; reassigned to user {reassigned_to}."
                        
#             #     final_output.append({
#             #         **item, # Get all the fields like task_id,status ...
#             #         "reason": reason,
#             #         "suggestion": suggestion
#             #     })

#             print(f"[DEBUG] Chunk {i} processed successfully. Tasks so far: {len(final_output)}")

#         except json.JSONDecodeError as e:
#             print(f"[ERROR] JSON parse failed for chunk {i}: {e}")
#             for item in chunk:
#                 status = item["status"]
#                 final_output.append({
#                     **item, # Get all the fields like task_id,status ...
#                     "reason": fallback_reasons.get(status, "Manual review required."),
#                     "suggestion": fallback_suggestions.get(status, "Check resource availability.")
#                 })

#         # except Exception as e:
#         #     print(f"[ERROR] Unexpected error in chunk {i}: {e}")
#         #     for item in chunk:
#         #         final_output.append({
#         #             **item, # Get all the fields like task_id,status ...
#         #             # "reason": "Manual review required.",
#         #             "suggestion": "Check resource availability."
#         #         })

#     return final_output


# # Save the output
# # def save_output(final_output, output_file):
# #     with open(output_file, "w", encoding="utf-8") as file:
# #         writer = csv.DictWriter(file, fieldnames=[
# #             "task_id", 
# #             "status", 
# #             "original_assignee", 
# #             "reassigned_to", 
# #             "reason", 
# #             "suggestion",
# #             # Add these when working on delayed_assignments:
# #             # "hours",
# #             # "final_load"
# #         ])
# #         writer.writeheader()
# #         writer.writerows(final_output)

# #     for row in final_output:
# #         print("\nROWS:\n", row)

# def save_output(final_output,output_file):
#     with open(output_file,"w", encoding = "utf-8") as file:
#         file.write(final_output)

#     with open(output_file,"r", encoding = "utf-8") as file:
#         final_reader = csv.DictReader(file)
#         for row in final_reader:
#             print("\n \n")

    

# # Execution Code
# def main():
#     task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
#     assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
#     skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
#     users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"
#     output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

#     task_owner, all_assigned_users = load_task_assignments(assign_file)
#     user_capacity = load_user_capacity(users_file)
#     user_skills = load_user_skills(skill_file)
#     all_tasks = load_tasks(task_file)

#     user_task_count = Counter(all_assigned_users)
#     user_total_hours = calculate_user_workload(all_tasks, task_owner)

#     tasks_summary = process_tasks(
#         all_tasks,
#         task_owner,
#         user_capacity,
#         user_skills,
#         user_total_hours,
#         user_task_count,
#     )

#     # updated_tasks_summary= delayed_assignments(tasks_summary, user_skills, user_total_hours)
#     print("updated_tasks_summary : \n ", tasks_summary)
#     print("==="*45)
#     print()
#     final_output = generate_ai_output(tasks_summary)
#     print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2))
 
#     save_output(final_output, output_file)


# if __name__ == "__main__":
#     main()

















# import re
# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# today = datetime.now().date()
# underutilized_per = 0.5


# def load_task_assignments(assign_file):
#     task_owner = {}
#     all_assigned_users = []

#     with open(assign_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             users = (row.get("user_id") or "0").strip()
#             user_ids = users if users != "" else "0"
#             task_owner[row["task_id"]] = user_ids
#             all_assigned_users.append(user_ids)

#     print("\nALL ASSIGNED USERS:\n", all_assigned_users)
#     print("\nTASK OWNER:\n", task_owner)
#     return task_owner, all_assigned_users


# def load_user_capacity(users_file):
#     user_capacity = {}
#     with open(users_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             user_capacity[row["id"]] = float(row.get("weekly_capacity", 0))
#     print("\nuser_capacity:\n", user_capacity)
#     return user_capacity


# def load_user_skills(skill_file):
#     user_skills = {}
#     with open(skill_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             skill = row["skill_id"]
#             user = row["user_id"]
#             if skill not in user_skills:
#                 user_skills[skill] = []
#             user_skills[skill].append(user)
#     print("\nuser_skills:\n", user_skills)
#     return user_skills


# def load_tasks(task_file):
#     with open(task_file, "r", encoding="utf-8") as file:
#         return list(csv.DictReader(file))


# def calculate_user_workload(all_tasks, task_owner):
#     user_total_hours = {}
#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue
#         task_id = row["id"]
#         assignee = str(task_owner.get(task_id, "0")).strip()
#         hours = float(row.get("estimated_hours") or 0.0)
#         user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours
#     print("\nuser_total_hours:\n", user_total_hours)
#     return user_total_hours


# def sort_candidates(candidate):
#     return (-candidate["remaining"], candidate["task_count"])


# def sort_by_load(user_dict):
#     return user_dict["total_load"]


# def generate_suggestion(status, original_assignee, reassigned_to, final_load):
#     if status == "OVERLOADED":
#         return f"Original assignee {original_assignee} is over capacity; reassigned to user {reassigned_to}."
#     elif status == "DELAYED":
#         if reassigned_to != original_assignee:
#             return f"Task is past deadline; reassigned from user {original_assignee} to user {reassigned_to}."
#         else:
#             return "Task is past deadline; escalate immediately."
#     elif status == "DELAYED_TIMELINE_EXTENSION":
#         return f"All skilled resources fully booked; task queued for user {reassigned_to} and will begin after {final_load} hours."
#     elif status == "USER_UNDERUTILIZED_BUT_LATE":
#         return f"Assignee {original_assignee} has low workload but task is late; reassigned to user {reassigned_to}."
#     elif status == "UNASSIGNED_NOW_ASSIGNED":
#         return f"Task was unassigned; reassigned to user {reassigned_to}."
#     elif status == "NO_SKILLED_USER_FOUND":
#         return "No skilled resource found for this task; escalate to management immediately."
#     elif status == "ON_TIME":
#         return "On track; continue routine monitoring."
#     return "Manual review required."


# def process_tasks(all_tasks, task_owner, user_capacity, user_skills, user_total_hours, user_task_count):
#     tasks_summary = []
#     delayed_queue_load = {}

#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = int(row["id"])
#         deadline = row["date_deadline"]
#         required_skill = row.get("required_skill_id")
#         hours = float(row.get("estimated_hours") or 0.0)

#         original_assignee = str(task_owner.get(str(task_id), "0")).strip()
#         total_workload = user_total_hours.get(original_assignee, 0.0)
#         capacity = user_capacity.get(original_assignee, 0.0)

#         deadline_date = None
#         if deadline:
#             deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#         # --- FIX: Check overloaded REGARDLESS of deadline ---
#         is_past_deadline = deadline_date and today > deadline_date
#         is_overloaded = original_assignee != "0" and total_workload >= capacity
#         is_underutilized = 0 < total_workload < (capacity * underutilized_per)

#         if original_assignee == "0" and is_past_deadline:
#             status = "UNASSIGNED"
#         elif is_overloaded:
#             status = "OVERLOADED"  # Overloaded takes priority regardless of deadline
#         elif is_past_deadline and is_underutilized:
#             status = "USER_UNDERUTILIZED_BUT_LATE"
#         elif is_past_deadline:
#             status = "DELAYED"
#         else:
#             status = "ON_TIME"

#         reassigned_to = original_assignee
#         final_load = 0.0

#         if status == "ON_TIME":
#             tasks_summary.append({
#                 "task_id": task_id, "status": status,
#                 "original_assignee": original_assignee,
#                 "reassigned_to": reassigned_to, "hours": hours, "final_load": 0.0
#             })
#             continue

#         skilled_users = user_skills.get(required_skill, [])

#         # --- UNASSIGNED branch ---
#         if status == "UNASSIGNED":
#             if not skilled_users:
#                 tasks_summary.append({
#                     "task_id": task_id, "status": "NO_SKILLED_USER_FOUND",
#                     "original_assignee": original_assignee,
#                     "reassigned_to": "0", "hours": hours, "final_load": 0.0
#                 })
#                 continue

#             candidates = [
#                 {
#                     "user_id": str(u).strip(),
#                     "remaining": user_capacity.get(str(u).strip(), 0.0) - user_total_hours.get(str(u).strip(), 0.0),
#                     "task_count": user_task_count.get(str(u).strip(), 0)
#                 }
#                 for u in skilled_users
#                 if user_total_hours.get(str(u).strip(), 0.0) + hours <= user_capacity.get(str(u).strip(), 0.0)
#             ]

#             if candidates:
#                 candidates.sort(key=sort_candidates)
#                 best = candidates[0]
#                 reassigned_to = best["user_id"]
#                 user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#                 user_task_count[reassigned_to] += 1
#                 status = "UNASSIGNED_NOW_ASSIGNED"
#                 final_load = 0.0
#             else:
#                 # Queue to least-loaded skilled user (exclude none since unassigned)
#                 load_list = sorted(
#                     [{"user_id": str(u).strip(),
#                       "total_load": user_total_hours.get(str(u).strip(), 0.0) + delayed_queue_load.get(str(u).strip(), 0.0)}
#                      for u in skilled_users],
#                     key=sort_by_load
#                 )
#                 reassigned_to = load_list[0]["user_id"]
#                 final_load = user_total_hours.get(reassigned_to, 0.0) + delayed_queue_load.get(reassigned_to, 0.0)
#                 delayed_queue_load[reassigned_to] = delayed_queue_load.get(reassigned_to, 0.0) + hours
#                 status = "DELAYED_TIMELINE_EXTENSION"

#             tasks_summary.append({
#                 "task_id": task_id, "status": status,
#                 "original_assignee": original_assignee,
#                 "reassigned_to": reassigned_to, "hours": hours, "final_load": final_load
#             })
#             continue

#         # --- DELAYED: keep original if they have capacity ---
#         if status == "DELAYED":
#             if user_total_hours.get(original_assignee, 0.0) <= user_capacity.get(original_assignee, 0.0):
#                 tasks_summary.append({
#                     "task_id": task_id, "status": status,
#                     "original_assignee": original_assignee,
#                     "reassigned_to": original_assignee, "hours": hours, "final_load": 0.0
#                 })
#                 continue

#         # --- General reassignment: OVERLOADED, USER_UNDERUTILIZED_BUT_LATE, DELAYED (no capacity) ---
#         if not skilled_users:
#             tasks_summary.append({
#                 "task_id": task_id, "status": "NO_SKILLED_USER_FOUND",
#                 "original_assignee": original_assignee,
#                 "reassigned_to": original_assignee, "hours": hours, "final_load": 0.0
#             })
#             continue

#         exclude_original = status in ("USER_UNDERUTILIZED_BUT_LATE", "DELAYED", "OVERLOADED")

#         candidates = []
#         seen = set()
#         for u in skilled_users:
#             user_id = str(u).strip()
#             if user_id in seen:
#                 continue
#             seen.add(user_id)
#             if exclude_original and user_id == original_assignee:
#                 continue
#             load = user_total_hours.get(user_id, 0.0)
#             cap = user_capacity.get(user_id, 0.0)
#             if load + hours <= cap:
#                 candidates.append({
#                     "user_id": user_id,
#                     "remaining": cap - load,
#                     "task_count": user_task_count.get(user_id, 0)
#                 })

#         if candidates:
#             candidates.sort(key=sort_candidates)
#             best_user = candidates[0]
#             reassigned_to = best_user["user_id"]
#             user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#             user_task_count[reassigned_to] += 1
#             # FIX: reduce original assignee's load since task moves away
#             if original_assignee != "0" and original_assignee != reassigned_to:
#                 user_total_hours[original_assignee] = max(0.0, user_total_hours.get(original_assignee, 0.0) - hours)
#                 user_task_count[original_assignee] = max(0, user_task_count.get(original_assignee, 0) - 1)
#             final_load = 0.0
#         else:
#             # No one has capacity — queue to least loaded skilled user (excluding original if applicable)
#             seen_load = set()
#             load_list = []
#             for u in skilled_users:
#                 user_id = str(u).strip()
#                 if user_id in seen_load:
#                     continue
#                 seen_load.add(user_id)
#                 if exclude_original and user_id == original_assignee:
#                     continue
#                 load_list.append({
#                     "user_id": user_id,
#                     "total_load": user_total_hours.get(user_id, 0.0) + delayed_queue_load.get(user_id, 0.0)
#                 })

#             if load_list:
#                 load_list.sort(key=sort_by_load)
#                 reassigned_to = load_list[0]["user_id"]
#             else:
#                 reassigned_to = original_assignee  # last resort

#             final_load = user_total_hours.get(reassigned_to, 0.0) + delayed_queue_load.get(reassigned_to, 0.0)
#             delayed_queue_load[reassigned_to] = delayed_queue_load.get(reassigned_to, 0.0) + hours
#             status = "DELAYED_TIMELINE_EXTENSION"

#         print(f"\nTask {task_id} -> Reassigned to: {reassigned_to} (Status: {status}, final_load: {final_load})\n")
#         tasks_summary.append({
#             "task_id": task_id, "status": status,
#             "original_assignee": original_assignee,
#             "reassigned_to": reassigned_to, "hours": hours, "final_load": final_load
#         })

#     return tasks_summary


# def generate_ai_output(tasks_summary):
#     print("============ ENTERED GENERATE AI OUTPUT ===========")
#     final_output = []
#     chunk_size = 5

#     fallback_reasons = {
#         "ON_TIME": "Task is progressing on schedule with no issues.",
#         "OVERLOADED": "Assignee exceeded weekly capacity; task rebalanced to an available resource.",
#         "DELAYED": "Task has passed its deadline and requires immediate attention.",
#         "USER_UNDERUTILIZED_BUT_LATE": "Assignee has available capacity but the task is still late.",
#         "DELAYED_TIMELINE_EXTENSION": "All team members are at full capacity; assigned to earliest available person.",
#         "UNASSIGNED_NOW_ASSIGNED": "Task had no owner and has now been assigned to an available skilled resource.",
#         "NO_SKILLED_USER_FOUND": "No user with the required skill is available; manual intervention needed.",
#     }

#     for i in range(0, len(tasks_summary), chunk_size):
#         chunk = tasks_summary[i: i + chunk_size]

#         for item in chunk:
#             status = item["status"]
#             # FIX: use generate_suggestion with correct final_load (no longer always 0)
#             suggestion = generate_suggestion(
#                 status,
#                 item["original_assignee"],
#                 item["reassigned_to"],
#                 item.get("final_load", 0.0)  # FIX: was always 0.0 before
#             )
#             reason = fallback_reasons.get(status, "Manual review required.")

#             final_output.append({
#                 **item,
#                 "reason": reason,
#                 "suggestion": suggestion
#             })

#         print(f"[DEBUG] Chunk {i} processed. Tasks so far: {len(final_output)}")

#     return final_output


# def save_output(final_output, output_file):
#     # FIX: fieldnames now match exactly what we write — hours and final_load included
#     fieldnames = [
#         "task_id",
#         "status",
#         "original_assignee",
#         "reassigned_to",
#         "reason",
#         "suggestion",
#         "hours",       # FIX: uncommented — needed for transparency
#         "final_load",  # FIX: uncommented — now has correct non-zero values
#     ]
#     with open(output_file, "w", encoding="utf-8", newline="") as file:
#         writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
#         writer.writeheader()
#         writer.writerows(final_output)

#     for row in final_output:
#         print("\nROW:", row)




        


# def main():
#     task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
#     assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
#     skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
#     users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"
#     output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

#     task_owner, all_assigned_users = load_task_assignments(assign_file)
#     user_capacity = load_user_capacity(users_file)
#     user_skills = load_user_skills(skill_file)
#     all_tasks = load_tasks(task_file)

#     user_task_count = Counter(all_assigned_users)
#     user_total_hours = calculate_user_workload(all_tasks, task_owner)

#     tasks_summary = process_tasks(
#         all_tasks, task_owner, user_capacity,
#         user_skills, user_total_hours, user_task_count,
#     )

#     print("tasks_summary:\n", tasks_summary)
#     print("===" * 45)

#     final_output = generate_ai_output(tasks_summary)
#     print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2))

#     save_output(final_output, output_file)


# if __name__ == "__main__":
#     main()


















# import re
# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# today = datetime.now().date()
# underutilized_per = 0.5


# # Load tasks assignments -> who is currently working on which task
# def load_task_assignments(assign_file):
#     task_owner = {}
#     all_assigned_users = []

#     with open(assign_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             users = (row.get("user_id") or "0").strip()
#             user_ids = users if users != "" else "0"
#             task_owner[row["task_id"]] = user_ids
#             all_assigned_users.append(user_ids)

#     print("\nALL ASSIGNED USERS:\n", all_assigned_users)
#     print("\nTASK OWNER:\n", task_owner)
#     return task_owner, all_assigned_users


# # Load user capacity -> weekly capacity of the user
# def load_user_capacity(users_file):
#     user_capacity = {}

#     with open(users_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             user_capacity[row["id"]] = float(row.get("weekly_capacity", 0))

#     print("\nuser_capacity:\n", user_capacity)
#     return user_capacity


# # Load user skills
# def load_user_skills(skill_file):
#     user_skills = {}

#     with open(skill_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             skill = row["skill_id"]
#             user = row["user_id"]
#             if skill not in user_skills:
#                 user_skills[skill] = []
#             user_skills[skill].append(user)

#     print("\nuser_skills:\n", user_skills)
#     return user_skills


# # Load tasks
# def load_tasks(task_file):
#     with open(task_file, "r", encoding="utf-8") as file:
#         return list(csv.DictReader(file))


# # User workload
# def calculate_user_workload(all_tasks, task_owner):
#     user_total_hours = {}

#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = row["id"]
#         assignee = str(task_owner.get(task_id, "0")).strip()
#         hours = float(row.get("estimated_hours") or 0.0)
#         user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

#     print("\nuser_total_hours:\n", user_total_hours)
#     return user_total_hours


# # Sort candidates — most free hours first, then fewest tasks
# def sort_candidates(candidate):
#     highest_remaining = -candidate["remaining"]
#     lowest_task_count = candidate["task_count"]
#     print("HIGHEST REMAINING CANDIDATES:\n", highest_remaining)
#     print("\nLOWEST TASK COUNT:\n", lowest_task_count)
#     return (highest_remaining, lowest_task_count)


# # Helper to sort by total load (lowest hours first) — NO lambda
# def sort_by_load(user_dict):
#     return user_dict["total_load"]


# # ----------------------------------------------------------------
# # CHECK STATUS AND PROCESS TASKS
# # ----------------------------------------------------------------
# def process_tasks(all_tasks, task_owner, user_capacity, user_skills, user_total_hours, user_task_count):
#     tasks_summary = []

#     for row in all_tasks:
#         # Skip completed or client_approval_pending tasks
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = int(row["id"])
#         deadline = row["date_deadline"]
#         required_skill = row.get("required_skill_id")
#         hours = float(row.get("estimated_hours") or 0.0)

#         original_assignee = str(task_owner.get(str(task_id), "0")).strip()
#         total_workload = user_total_hours.get(original_assignee, 0.0)
#         capacity = user_capacity.get(original_assignee, 0.0)

#         deadline_date = None
#         if deadline:
#             deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#         # ── Determine Status ──────────────────────────────────────
#         if deadline_date and today > deadline_date:
#             if original_assignee == "0":
#                 status = "UNASSIGNED"
#             elif total_workload >= capacity:
#                 status = "OVERLOADED"
#             elif 0 < total_workload < (capacity * underutilized_per):
#                 status = "USER_UNDERUTILIZED_BUT_LATE"
#             else:
#                 status = "DELAYED"
#         else:
#             status = "ON_TIME"

#         reassigned_to = original_assignee

#         # ── Reassignment Logic ────────────────────────────────────
#         if status != "ON_TIME":

#             # ── FIX 5: UNASSIGNED — explicit dedicated branch ─────
#             if status == "UNASSIGNED":
#                 skilled_users = user_skills.get(required_skill, [])

#                 if not skilled_users:
#                     print(f"[WARNING] Task {task_id} is UNASSIGNED and no skilled users found for skill {required_skill}")
#                     tasks_summary.append({
#                         "task_id": task_id,
#                         "status": status,
#                         "original_assignee": original_assignee,
#                         "reassigned_to": "0",
#                         "hours": hours,
#                         "final_load": 0.0
#                     })
#                     continue

#                 candidates = []
#                 for user_id in skilled_users:
#                     user_id = str(user_id).strip()
#                     load = user_total_hours.get(user_id, 0.0)
#                     cap = user_capacity.get(user_id, 0.0)
#                     if load + hours <= cap:
#                         candidates.append({
#                             "user_id": user_id,
#                             "remaining": cap - load,
#                             "task_count": user_task_count.get(user_id, 0)
#                         })

#                 if candidates:
#                     candidates.sort(key=sort_candidates)
#                     best = candidates[0]                          # FIX: was 'canidates' (typo)
#                     reassigned_to = best["user_id"]
#                     user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#                     user_task_count[reassigned_to] += 1
#                     status = "UNASSIGNED_NOW_ASSIGNED"
#                     tasks_summary.append({                        # FIX: append + continue were missing
#                         "task_id": task_id,
#                         "status": status,
#                         "original_assignee": original_assignee,
#                         "reassigned_to": reassigned_to,
#                         "hours": hours,
#                         "final_load": 0.0
#                     })
#                     continue                                       # FIX: was falling through to DELAYED block

#                 else:
#                     # No one free — pick the person with the lowest load (will be free soonest)
#                     lowest_load = 999999.0
#                     reassigned_to = None
#                     for s_user in skilled_users:
#                         u_id = str(s_user).strip()
#                         current_load = user_total_hours.get(u_id, 0.0)
#                         if current_load < lowest_load:
#                             lowest_load = current_load
#                             reassigned_to = u_id
#                     status = "DELAYED_TIMELINE_EXTENSION"         # FIX: moved outside for loop (was inside, set on every iteration)

#                     tasks_summary.append({
#                         "task_id": task_id,
#                         "status": status,
#                         "original_assignee": original_assignee,
#                         "reassigned_to": reassigned_to,
#                         "hours": hours,
#                         "final_load": 0.0
#                     })
#                     continue

#             # ── FIX 1: DELAYED — removed early exit, now reassigns ─
#             # Old code kept the original assignee and did 'continue'
#             # Now we let it fall through to the candidate-finding logic below
#             if status == "DELAYED" and original_assignee != "0":
#                 pass  # FIX: intentionally fall through to reassignment

#             # ── FIX 6: Warn when no skilled users found ───────────
#             candidates = []
#             seen = set()
#             skilled_users = user_skills.get(required_skill, [])

#             if not skilled_users:
#                 print(f"[WARNING] Task {task_id}: No users found with skill '{required_skill}' — cannot reassign")
#                 tasks_summary.append({
#                     "task_id": task_id,
#                     "status": "NO_SKILLED_USER_FOUND",
#                     "original_assignee": original_assignee,
#                     "reassigned_to": original_assignee,
#                     "hours": hours,
#                     "final_load": 0.0
#                 })
#                 continue

#             # Filter skilled users who can fit these hours in their capacity
#             for user_ids in skilled_users:
#                 user_id = str(user_ids).strip()
#                 if user_id in seen:
#                     continue
#                 seen.add(user_id)
#                 # Don't reassign back to the same late/underutilized user
#                 if status in ("USER_UNDERUTILIZED_BUT_LATE", "DELAYED") and user_id == original_assignee:
#                     continue
#                 load = user_total_hours.get(user_id, 0.0)
#                 cap = user_capacity.get(user_id, 0.0)
#                 if load + hours <= cap:
#                     candidates.append({
#                         "user_id": user_id,
#                         "remaining": cap - load,
#                         "task_count": user_task_count.get(user_id, 0)
#                     })

#             if candidates:
#                 candidates.sort(key=sort_candidates)
#                 best_user = candidates[0]
#                 reassigned_to = best_user["user_id"]

#                 user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#                 user_task_count[reassigned_to] += 1

#                 # ── FIX 4: Decrement original assignee's hours and task count ──
#                 if original_assignee != "0" and original_assignee != reassigned_to:
#                     user_total_hours[original_assignee] = max(0.0, user_total_hours.get(original_assignee, 0.0) - hours)
#                     user_task_count[original_assignee] = max(0, user_task_count.get(original_assignee, 0) - 1)

#             else:
#                 # No one has free capacity — pick the person who will be free soonest
#                 load_skilled_list = []
#                 seen_load = set()
#                 for user_ids in skilled_users:
#                     user_id = str(user_ids).strip()
#                     if user_id in seen_load:
#                         continue
#                     seen_load.add(user_id)
#                     if status in ("USER_UNDERUTILIZED_BUT_LATE", "DELAYED") and user_id == original_assignee:
#                         continue
#                     load_skilled_list.append({
#                         "user_id": user_id,
#                         "total_load": user_total_hours.get(user_id, 0.0)
#                     })

#                 if load_skilled_list:
#                     load_skilled_list.sort(key=sort_by_load)
#                     reassigned_to = load_skilled_list[0]["user_id"]
#                     status = "DELAYED_TIMELINE_EXTENSION"
#                 else:
#                     reassigned_to = original_assignee
#                     status = "DELAYED_TIMELINE_EXTENSION"

#                 print("\nLOAD SKILLED LIST:\n", load_skilled_list)

#         print(f"\nTask {task_id} -> Reassigned to: {reassigned_to} (Status: {status})\n")

#         tasks_summary.append({
#             "task_id": task_id,
#             "status": status,
#             "original_assignee": original_assignee,
#             "reassigned_to": reassigned_to,
#             "hours": hours,
#             "final_load": 0.0
#         })

#     print("\nTASKS SUMMARY:\n", tasks_summary)
#     print("\nTOTAL TASKS:", len(all_tasks))
#     print("\nTASKS SUMMARY COUNT:", len(tasks_summary))
#     print(f"\nDEBUG: Successfully processed {len(tasks_summary)} tasks.")
#     return tasks_summary


# # ----------------------------------------------------------------
# # HANDLE QUEUED / TIMELINE EXTENDED TASKS
# # ----------------------------------------------------------------
# def delayed_assignments(tasks_summary, user_skills, user_total_hours):
#     for row in tasks_summary:
#         if row["status"] == "DELAYED_TIMELINE_EXTENSION":
#             task_id = row["task_id"]
#             assignee = row["reassigned_to"]

#             free_after_hours = user_total_hours.get(assignee, 0.0)
#             row["final_load"] = free_after_hours

#             print(f"--> DELAYED TASK {task_id}: assigned to {assignee}")
#             print(f"--> They are free after {free_after_hours} hours of current work")
#             print(f"--> Task will start only after that — no overloading")

#             user_total_hours[assignee] = free_after_hours + row["hours"]
#         else:
#             row["final_load"] = 0.0

#     return tasks_summary


# # ----------------------------------------------------------------
# # GENERATE AI REASONS AND SUGGESTIONS
# # ----------------------------------------------------------------
# def generate_ai_output(tasks_summary):
#     print("============ ENTERED GENERATE AI OUTPUT ===========")
#     final_output = []
#     chunk_size = 10

#     fallback_reasons = {
#         "ON_TIME": "Task is progressing on schedule with no issues.",
#         "OVERLOADED": "Assignee exceeded weekly capacity; task rebalanced to an available resource.",
#         "DELAYED": "Task has passed its deadline and requires immediate attention.",
#         "USER_UNDERUTILIZED_BUT_LATE": "Assignee has available capacity but the task is still late.",
#         "DELAYED_TIMELINE_EXTENSION": "All team members are at full capacity; assigned to earliest available person.",
#         "UNASSIGNED": "Task has no assignee and deadline has passed.",
#         "UNASSIGNED_NOW_ASSIGNED": "Task was unassigned; now assigned to an available skilled user.",
#         "NO_SKILLED_USER_FOUND": "No user with the required skill was found; manual intervention needed."
#     }
#     fallback_suggestions = {
#         "ON_TIME": "Continue monitoring progress and ensure no blockers arise.(fallback)",
#         "OVERLOADED": "Review workload distribution and consider hiring or redistributing tasks.(fallback)",
#         "DELAYED": "Prioritize this task and check for blockers.(fallback)",
#         "USER_UNDERUTILIZED_BUT_LATE": "Investigate why the task is late despite available capacity.(fallback)",
#         "DELAYED_TIMELINE_EXTENSION": "Extend the task deadline and inform stakeholders of the new timeline.(fallback)",
#         "UNASSIGNED": "Assign this task immediately to an available skilled resource.(fallback)",
#         "UNASSIGNED_NOW_ASSIGNED": "Monitor the newly assigned user to ensure timely completion.(fallback)",
#         "NO_SKILLED_USER_FOUND": "Escalate to management — no skilled resource available.(fallback)"
#     }

#     # FIX 3: Changed to f-string so {chunk_size} is actually interpolated
#     prompt = f"""
#         IMPORTANT: Respond with ONLY a valid JSON array. No preamble, no markdown, no explanations.
#         You are a Project Manager AI.

#         Data available: task_id, status, original_assignee, reassigned_to, hours, final_load.

#         These are the ONLY valid statuses and their rules. Match EXACTLY on the status field:

#         - "OVERLOADED": assignee exceeded capacity, task moved to someone else.
#             → "Original assignee [original_assignee] is over capacity; reassigned to user [reassigned_to]."

#         - "DELAYED": deadline passed, reassigned to a different skilled user.
#             → If reassigned_to != original_assignee: "Task is past deadline; reassigned from user [original_assignee] to user [reassigned_to]."
#             → If reassigned_to == original_assignee: "Task is past deadline and no alternative resource found; escalate immediately."

#         - "DELAYED_TIMELINE_EXTENSION": ALL skilled users are fully booked, task is QUEUED.
#             → ALWAYS use: "All skilled resources fully booked; task queued for user [reassigned_to] and will begin after [final_load] hours."
#             → NEVER use the DELAYED rule for this status, even if reassigned_to == original_assignee.

#         - "USER_UNDERUTILIZED_BUT_LATE": assignee has low workload but task is late.
#             → "Assignee [original_assignee] has low workload but task is late; reassigned to user [reassigned_to]."

#         - "UNASSIGNED_NOW_ASSIGNED": task had no owner, now assigned.
#             → "Task was unassigned; reassigned to user [reassigned_to] who has the required skill and capacity."

#         - "NO_SKILLED_USER_FOUND": no skilled user exists, needs manual review.
#             → "No skilled resource found for this task; escalate to management immediately."

#         - "ON_TIME": no action needed.
#             → "On track; continue routine monitoring."

#         Constraints:
#         - Process tasks IN THE EXACT ORDER they appear in the input.
#         - Return one entry per task. Output array MUST have SAME LENGTH as input array.
#         - Use ONLY task_ids from the input. Never skip or invent task_ids.
#         - Input has EXACTLY {chunk_size} tasks max per chunk. Return EXACTLY the same number of entries as input.
#         - Return ONLY: [{{"task_id": 123, "suggestion": "text"}}]
#         """

#     for i in range(0, len(tasks_summary), chunk_size):
#         chunk = tasks_summary[i: i + chunk_size]
#         try:
#             response = chat(
#                 model="llama3.2",
#                 messages=[
#                     {"role": "system", "content": prompt},
#                     {"role": "user", "content": json.dumps(chunk)}
#                 ],
#                 options={"temperature": 0}
#             )
#             content = response.message.content.strip()
#             print(f"\n[DEBUG] Raw AI response for chunk {i}:\n{content}\n")

#             content = re.sub(r"```(?:json)?", "", content).strip()
#             content = content.strip("`").strip()

#             match = re.search(r'\[.*?\]', content, re.DOTALL)
#             if not match:
#                 raise ValueError(f"No JSON array found in AI response: {content[:200]}")

#             ai_output = json.loads(match.group())

#             if len(ai_output) != len(chunk):
#                 print(f"[WARNING] AI returned {len(ai_output)} tasks but expected {len(chunk)}")
#                 returned_ids = {str(r.get("task_id")) for r in ai_output}
#                 expected_ids = {str(item["task_id"]) for item in chunk}
#                 print(f"[WARNING] Missing task_ids: {expected_ids - returned_ids}")

#             ai_map = {str(r.get("task_id")): r for r in ai_output}

#             for item in chunk:
#                 t_id = str(item["task_id"])
#                 status = item["status"]
#                 reassigned_to = item["reassigned_to"]
#                 original_assignee = item["original_assignee"]
#                 final_load = item.get("final_load", 0.0)

#                 ai_data = ai_map.get(t_id)

#                 reason = (ai_data.get("reason") if ai_data and ai_data.get("reason") else None) \
#                          or fallback_reasons.get(status, "Manual review required.")
#                 suggestion = (ai_data.get("suggestion") if ai_data else None) \
#                              or fallback_suggestions.get(status, "Check resource availability.")

#                 # Override guards — fix LLM mistakes per status
#                 if status == "DELAYED_TIMELINE_EXTENSION":
#                     if "queued" not in suggestion.lower() or "hours" not in suggestion.lower():
#                         suggestion = f"All skilled resources fully booked; task queued for user {reassigned_to} and will begin after {final_load} hours."

#                 elif status == "OVERLOADED":
#                     if "queued" in suggestion.lower() or "booked" in suggestion.lower():
#                         suggestion = f"Original assignee {original_assignee} is over capacity; reassigned to user {reassigned_to}."

#                 elif status == "DELAYED":
#                     if reassigned_to != original_assignee and "escalate" in suggestion.lower():
#                         suggestion = f"Task is past deadline; reassigned from user {original_assignee} to user {reassigned_to}."

#                 elif status == "USER_UNDERUTILIZED_BUT_LATE":
#                     if reassigned_to != original_assignee and reassigned_to not in suggestion:
#                         suggestion = f"Assignee {original_assignee} has low workload but task is late; reassigned to user {reassigned_to}."

#                 final_output.append({
#                     **item,
#                     "reason": reason,
#                     "suggestion": suggestion
#                 })

#             print(f"[DEBUG] Chunk {i} processed successfully. Tasks so far: {len(final_output)}")

#         except json.JSONDecodeError as e:
#             print(f"[ERROR] JSON parse failed for chunk {i}: {e}")
#             for item in chunk:
#                 status = item["status"]
#                 final_output.append({
#                     **item,
#                     "reason": fallback_reasons.get(status, "Manual review required."),
#                     "suggestion": fallback_suggestions.get(status, "Check resource availability.")
#                 })

#     return final_output


# # ----------------------------------------------------------------
# # SAVE OUTPUT TO CSV
# # ----------------------------------------------------------------
# def save_output(final_output, output_file):
#     with open(output_file, "w", encoding="utf-8") as file:
#         writer = csv.DictWriter(file, fieldnames=[
#             "task_id",
#             "status",
#             "original_assignee",
#             "reassigned_to",
#             "reason",
#             "suggestion",
#             "hours",
#             "final_load"
#         ])
#         writer.writeheader()
#         writer.writerows(final_output)

#     for row in final_output:
#         print("\nROWS:\n", row)


# # ----------------------------------------------------------------
# # MAIN
# # ----------------------------------------------------------------
# def main():
#     task_file   = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
#     assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
#     skill_file  = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
#     users_file  = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"
#     output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

#     task_owner, all_assigned_users = load_task_assignments(assign_file)
#     user_capacity = load_user_capacity(users_file)
#     user_skills = load_user_skills(skill_file)
#     all_tasks = load_tasks(task_file)

#     user_task_count = Counter(all_assigned_users)
#     user_total_hours = calculate_user_workload(all_tasks, task_owner)

#     tasks_summary = process_tasks(
#         all_tasks,
#         task_owner,
#         user_capacity,
#         user_skills,
#         user_total_hours,
#         user_task_count,
#     )

#     updated_tasks_summary = delayed_assignments(tasks_summary, user_skills, user_total_hours)
#     print("updated_tasks_summary:\n", updated_tasks_summary)
#     print("===" * 45)

#     final_output = generate_ai_output(updated_tasks_summary)
#     print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2))

#     save_output(final_output, output_file)


# if __name__ == "__main__":
#     main()

















# import re
# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# today = datetime.now().date()
# underutilized_per = 0.5

# # # Get remaining
# # def get_remaining(candidate):
# #     return candidate["remaining"]

# # Load tasks assignments -> who is currently working on which task
# def load_task_assignments(assign_file):
#     task_owner = {}
#     all_assigned_users = []

#     with open(assign_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             users = (row.get("user_id") or "0").strip()
#             user_ids = users if users != "" else "0"
#             task_owner[row["task_id"]] = user_ids
#             all_assigned_users.append(user_ids)
#     print("\nALL ASSIGNED USERS:\n",all_assigned_users)
#     print("\nTASK OWNER:\n", task_owner)
#     return task_owner, all_assigned_users


# # Load user capacity -> weekly capacity of the user
# def load_user_capacity(users_file):
#     user_capacity = {}

#     with open(users_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             user_capacity[row["id"]] = float(row.get("weekly_capacity", 0))

#     print("\nuser_capacity:\n", user_capacity)
#     return user_capacity


# # Load user skills
# def load_user_skills(skill_file):
#     user_skills = {}

#     with open(skill_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             skill = row["skill_id"]
#             user = row["user_id"]
#             if skill not in user_skills:
#                 user_skills[skill] = []
#             user_skills[skill].append(user)

#     print("\nuser_skills:\n", user_skills)
#     return user_skills


# # Load tasks
# def load_tasks(task_file):
#     with open(task_file, "r", encoding="utf-8") as file:
#         return list(csv.DictReader(file))


# # User workload
# def calculate_user_workload(all_tasks, task_owner):
#     user_total_hours = {}
#     # Skip tasks that are completed or client approval pending
#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = row["id"]
#         assignee = str(task_owner.get(task_id, "0")).strip()
#         hours = float(row.get("estimated_hours") or 0.0)

#         # Add these hours to the user's running total
#         user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

#     print("\nuser_total_hours:\n", user_total_hours)
#     return user_total_hours


# # Sort candidates
# def sort_candidates(candidate):
#     # a person with 40 hours free (-40) comes before someone with 10 hours free (-10)
#     highest_remaining = -candidate["remaining"]
#     # If two people have the same free hours,we pick the one who is less buzy
#     lowest_task_count = candidate["task_count"]

#     print("HIGHEST REMAINING CANDIDATES:\n",highest_remaining)
#     print("\nLOWEST TASK COUNT:\n",lowest_task_count)
#     return (highest_remaining, lowest_task_count)


# # Helper to sort by total load (lowest hours first)
# def sort_by_load(user_dict):
#     return user_dict["total_load"]


# # Check status and process tasks
# def process_tasks(all_tasks, task_owner, user_capacity, user_skills, user_total_hours, user_task_count):
#     tasks_summary = []
#     for row in all_tasks:
#         # Skip completed or client_approval_pending tasks
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue 
        
#         # For each task, takes original user, hours required, and owner's current capacity
#         task_id = int(row["id"])
#         deadline = row["date_deadline"]
#         required_skill = row.get("required_skill_id")
#         hours = float(row.get("estimated_hours") or 0.0)
        
#         # Get the id of the person currently assigned to this task
#         original_assignee = str(task_owner.get(str(task_id), "0")).strip()
#         total_workload = user_total_hours.get(original_assignee, 0.0)
#         capacity = user_capacity.get(original_assignee, 0.0)

#         # Convert string deadline to date object for comparison
#         deadline_date = None
#         if deadline:
#             deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#         # Task Status
#         if deadline_date and today > deadline_date:
#             if original_assignee == "0":
#                 status = "UNASSIGNED"
#             elif total_workload >= capacity:
#                 status = "OVERLOADED"
#             elif 0 < total_workload < (capacity * underutilized_per):
#                 status = "USER_UNDERUTILIZED_BUT_LATE"
#             else:
#                 status = "DELAYED"
#         else:
#             status = "ON_TIME"

#         reassigned_to = original_assignee

#         # Reassignment Logic -> catch all non-ON_TIME statuses
#         if status != "ON_TIME":
#             # if status is just delayed and user has capacity, keep the original assignee
#             # if status == "DELAYED" and original_assignee != "0":
#             #     total_workload = user_total_hours.get(original_assignee,0.0)
#             #     capacity = user_capacity.get(original_assignee,0.0)
#             #     if total_workload <= capacity:
#             #         tasks_summary.append({
#             #             "task_id":task_id,
#             #             "status":status,
#             #             "original_assignee":original_assignee,
#             #             "reassigned_to":original_assignee,
#             #             "hours":hours,
#             #             "final_load":0.0
#             #         })
#             #         # skip reassignment logic entirely
#             #         continue
#             candidates = []
#             seen = set()
#             skilled_users = user_skills.get(required_skill, [])

#             # Filter for skilled users who have enough weekly capacity remaining
#             for user_ids in skilled_users:
#                 user_id = str(user_ids).strip()
#                 if user_id in seen:
#                     continue
#                 seen.add(user_id)
#                 # Avoid re-assigning to the same underutilized user who is already late
#                 if status in ("USER_UNDERUTILIZED_BUT_LATE","DELAYED") and user_id == original_assignee:
#                     continue
#                 load = user_total_hours.get(user_id, 0.0)
#                 cap = user_capacity.get(user_id, 0.0)
                
#                 # It finds users with the right skill who can fit these new hours into their current capacity
#                 if load + hours <= cap:
#                     candidates.append({
#                         "user_id": user_id,
#                         "remaining": cap - load,
#                         "task_count": user_task_count.get(user_id, 0)
#                     })

#             if candidates:
#                 # Pick the best candidate -> most free hours + fewest tasks
#                 candidates.sort(key=sort_candidates)
#                 best_user = candidates[0]
#                 reassigned_to = best_user["user_id"]

#                 # Update workload immediately for the next loop iteration
#                 user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#                 user_task_count[reassigned_to] += 1 
#             else:
#                 # No one has free capacity — pick the person who will be free soonest
#                 load_skilled_list = []
#                 seen_load = set()
#                 for user_ids in skilled_users:
#                     user_id = str(user_ids).strip()
#                     if user_id in seen_load:
#                         continue
#                     seen_load.add(user_id)
#                     if status in ("USER_UNDERUTILIZED_BUT_LATE", "DELAYED") and user_id == original_assignee:
#                         continue
#                     load_skilled_list.append({
#                         "user_id": user_id,
#                         "total_load": user_total_hours.get(user_id, 0.0)
#                     })

#                 if load_skilled_list:
#                     # Pick person with the lowest current hour load
#                     load_skilled_list.sort(key=sort_by_load)

#                     reassigned_to = load_skilled_list[0]["user_id"]
#                     status = "DELAYED_TIMELINE_EXTENSION"
#                     # user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours  # ✅

#                     # don't add hours to their current load yet
#                     # The task starts AFTER they finish current work
#                     # delayed_assignments will track when they'll be free
#                 else:
#                     # Keep the original assigneeif no skilled users found
#                     reassigned_to = original_assignee
#                     status = "DELAYED_TIMELINE_EXTENSION"
#                 # else:
#                 #     reassigned_to = original_assignee
#                 print("\nLOAD SKILLED LIST:\n",load_skilled_list)
#         print(f"\nTask {task_id} -> Reassigned to: {reassigned_to} (Status: {status})\n")

#         # Record the result
#         tasks_summary.append({
#             "task_id": task_id,
#             "status": status,
#             "original_assignee": original_assignee,
#             "reassigned_to": reassigned_to,
#             "hours": hours,
#             "final_load":0.0
#         })

#     print("\nTASKS SUMMARY:\n", tasks_summary)
#     print("\nTOTAL TASKS:", len(all_tasks))
#     print("\nTASKS SUMMARY COUNT:", len(tasks_summary))
#     print(f"\nDEBUG: Successfully processed {len(tasks_summary)} tasks.")
#     return tasks_summary


# # Only process tasks that needs time extension
# def delayed_assignments(tasks_summary, user_skills, user_total_hours):
#     for row in tasks_summary:
#         if row["status"] == "DELAYED_TIMELINE_EXTENSION":
#             task_id = row["task_id"]
#             assignee = row["reassigned_to"]

#             # This is when they finish current work = when this task can start
#             free_after_hours = user_total_hours.get(assignee, 0.0)
#             row["final_load"] = free_after_hours
            

#             print(f"--> DELAYED TASK {task_id}: assigned to {assignee}")
#             print(f"--> They are free after {free_after_hours} hours of current work")
#             print(f"--> Task will start only after that — no overloading")

#             # NOW add the task hours (task starts after they're free)
#             user_total_hours[assignee] = free_after_hours + row["hours"]
#         else:
#             row["final_load"] = 0.0

#     return tasks_summary

# # Reason and Suggestion generation
# def generate_ai_output(tasks_summary):
#     print("============ ENTERED GENERATE AI OUTPUT ===========")
#     final_output = []
#     # It splits the big list into small group of 10 tasks
#     chunk_size = 10

#     # pre-defined text used if the Ai fails or return empty response
#     # fallback_reasons = {
#     #     "ON_TIME": "Task is progressing on schedule with no issues.",
#     #     "OVERLOADED": "Assignee exceeded weekly capacity; task rebalanced to an available resource.",
#     #     "DELAYED": "Task has passed its deadline and requires immediate attention.",
#     #     "USER_UNDERUTILIZED_BUT_LATE": "Assignee has available capacity but the task is still late.",
#     #     "DELAYED_TIMELINE_EXTENSION": "All team members are at full capacity; assigned to earliest available person."
#     # }
#     fallback_suggestions = {
#         "ON_TIME": "Continue monitoring progress and ensure no blockers arise.(fallback)",
#         "OVERLOADED": "Review workload distribution and consider hiring or redistributing tasks.(fallback)",
#         "DELAYED": "Prioritize this task and check.(fallback)",
#         "USER_UNDERUTILIZED_BUT_LATE": "Investigate why the task is late despite available capacity.(fallback)",
#         "DELAYED_TIMELINE_EXTENSION": "Extend the task deadline and inform stakeholders of the new timeline.(fallback)"
#     }

#     prompt = """
#         IMPORTANT: Respond with ONLY a valid JSON array. No preamble, no markdown, no explanations.
#         You are a Project Manager AI.

#         Data available: task_id, status, original_assignee, reassigned_to, hours, final_load.

#         These are the ONLY valid statuses and their rules. Match EXACTLY on the status field:

#         - "OVERLOADED": assignee exceeded capacity, task moved to someone else.
#             → "Original assignee [original_assignee] is over capacity; reassigned to user [reassigned_to]."

#         - "DELAYED": deadline passed, reassigned to a different skilled user.
#             → If reassigned_to != original_assignee: "Task is past deadline; reassigned from user [original_assignee] to user [reassigned_to]."
#             → If reassigned_to == original_assignee: "Task is past deadline and no alternative resource found; escalate immediately."

#         - "DELAYED_TIMELINE_EXTENSION": ALL skilled users are fully booked, task is QUEUED.
#             → ALWAYS use: "All skilled resources fully booked; task queued for user [reassigned_to] and will begin after [final_load] hours."
#             → NEVER use the DELAYED rule for this status, even if reassigned_to == original_assignee.

#         - "USER_UNDERUTILIZED_BUT_LATE": assignee has low workload but task is late.
#             → "Assignee [original_assignee] has low workload but task is late; reassigned to user [reassigned_to]."

#         - "ON_TIME": no action needed.
#             → "On track; continue routine monitoring."

#         Constraints:
#         - Process tasks IN THE EXACT ORDER they appear in the input.
#         - Return one entry per task. Output array MUST have SAME LENGTH as input array.
#         - Use ONLY task_ids from the input. Never skip or invent task_ids.
#         - Return ONLY: [{"task_id": 123, "suggestion": "text"}]
#         """


#     # Loop through the summary list in increments of 10
#     for i in range(0, len(tasks_summary), chunk_size):
#         chunk = tasks_summary[i: i + chunk_size]
#         try:
#             # Call model
#             response = chat(
#                 model="llama3.2",
#                 messages=[
#                     {"role": "system", "content": prompt},
#                     {"role": "user", "content": json.dumps(chunk)}
#                 ],
#                 options={"temperature": 0}
#             )
#             content = response.message.content.strip()

#             # Debug: print raw AI response to catch formatting issues
#             print(f"\n[DEBUG] Raw AI response for chunk {i}:\n{content}\n")

#             # Clean markdown fences if present
#             content = re.sub(r"```(?:json)?", "", content).strip()
#             content = content.strip("`").strip()

#             # Extract JSON array
#             match = re.search(r'\[.*?\]', content, re.DOTALL)
#             if not match:
#                 raise ValueError(f"No JSON array found in AI response: {content[:200]}")

#             ai_output = json.loads(match.group())

#             # Validate all task_ids are present
#             # returned_ids = {str(r.get("task_id")) for r in ai_output}
#             # expected_ids = {str(item["task_id"]) for item in chunk}
#             # missing_ids = expected_ids - returned_ids
#             # if missing_ids:
#             #     print(f"[WARNING] AI missed task_ids: {missing_ids} — using fallback for those")

#             ai_map = {str(r.get("task_id")): r for r in ai_output}

#             for item in chunk:
#                 t_id = str(item["task_id"])
#                 status = item["status"]
#                 reassigned_to = item["reassigned_to"]
#                 original_assignee = item["original_assignee"]
#                 final_load = item.get("final_load", 0.0)


#                 ai_data = ai_map.get(t_id)

#                 # Use AI data if valid, else fall back to status-specific defaults
#                 # reason = (ai_data.get("reason") if ai_data and ai_data.get("reason") else None) \
#                 #          or fallback_reasons.get(status, "Manual review required.")
#                 suggestion = (ai_data.get("suggestion") if ai_data else None) or fallback_suggestions.get(status)

#                 if status == "DELAYED_TIMELINE_EXTENSION":
#                     # LLM sometimes applies DELAYED rule here — override it
#                     if "queued" not in suggestion.lower() or "hours" not in suggestion.lower():
#                         suggestion = f"All skilled resources fully booked; task queued for user {reassigned_to} and will begin after {final_load} hours."

#                 elif status == "OVERLOADED":
#                     # LLM sometimes applies DELAYED_TIMELINE_EXTENSION rule here — override it
#                     if "queued" in suggestion.lower() or "booked" in suggestion.lower():
#                         suggestion = f"Original assignee {original_assignee} is over capacity; reassigned to user {reassigned_to}."


#                 elif status == "DELAYED":
#                     # LLM sometimes says "escalate" even when reassigned to a different user
#                     if reassigned_to != original_assignee and "escalate" in suggestion.lower():
#                         suggestion = f"Task is past deadline; reassigned from user {original_assignee} to user {reassigned_to}."

#                 elif status == "USER_UNDERUTILIZED_BUT_LATE":
#                     # LLM sometimes forgets to mention the new assignee
#                     if reassigned_to != original_assignee and reassigned_to not in suggestion:
#                         suggestion = f"Assignee {original_assignee} has low workload but task is late; reassigned to user {reassigned_to}."
                        
#                 final_output.append({
#                     **item, # Get all the fields like task_id,status ...
#                     # "reason": reason,
#                     "suggestion": suggestion
#                 })

#             print(f"[DEBUG] Chunk {i} processed successfully. Tasks so far: {len(final_output)}")

#         except json.JSONDecodeError as e:
#             print(f"[ERROR] JSON parse failed for chunk {i}: {e}")
#             for item in chunk:
#                 status = item["status"]
#                 final_output.append({
#                     **item, # Get all the fields like task_id,status ...
#                     # "reason": fallback_reasons.get(status, "Manual review required."),
#                     "suggestion": fallback_suggestions.get(status, "Check resource availability.")
#                 })

#         # except Exception as e:
#         #     print(f"[ERROR] Unexpected error in chunk {i}: {e}")
#         #     for item in chunk:
#         #         final_output.append({
#         #             **item, # Get all the fields like task_id,status ...
#         #             # "reason": "Manual review required.",
#         #             "suggestion": "Check resource availability."
#         #         })

#     return final_output


# # Save the output
# def save_output(final_output, output_file):
#     with open(output_file, "w", encoding="utf-8") as file:
#         writer = csv.DictWriter(file, fieldnames=[
#             "task_id", 
#             "status", 
#             "original_assignee", 
#             "reassigned_to", 
#             # "reason", 
#             "suggestion",

#             # Add these when working on delayed_assignments:
#             "hours",
#             "final_load"
#         ])
#         writer.writeheader()
#         writer.writerows(final_output)

#     for row in final_output:
#         print("\nROWS:\n", row)

# # Execution Code
# def main():
#     task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
#     assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
#     skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
#     users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"
#     output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

#     task_owner, all_assigned_users = load_task_assignments(assign_file)
#     user_capacity = load_user_capacity(users_file)
#     user_skills = load_user_skills(skill_file)
#     all_tasks = load_tasks(task_file)

#     user_task_count = Counter(all_assigned_users)
#     user_total_hours = calculate_user_workload(all_tasks, task_owner)

#     tasks_summary = process_tasks(
#         all_tasks,
#         task_owner,
#         user_capacity,
#         user_skills,
#         user_total_hours,
#         user_task_count,
#     )

#     updated_tasks_summary= delayed_assignments(tasks_summary, user_skills, user_total_hours)
#     print("updated_tasks_summary : \n ", updated_tasks_summary)
#     print("==="*45)
#     print()
#     final_output = generate_ai_output(updated_tasks_summary)
#     print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2))
 
#     save_output(final_output, output_file)


# if __name__ == "__main__":
#     main()























# import re
# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# today = datetime.now().date()
# underutilized_per = 0.5

# # Get remaining
# def get_remaining(candidate):
#     return candidate["remaining"]

# # Load tasks assignments
# def load_task_assignments(assign_file):
#     task_owner = {}
#     all_assigned_users = []

#     with open(assign_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             users = (row.get("user_id") or "0").strip()
#             user_ids = users if users != "" else "0"
#             task_owner[row["task_id"]] = user_ids
#             all_assigned_users.append(user_ids)
#     print("\nALL ASSIGNED USERS:\n",all_assigned_users)
#     print("\nTASK OWNER:\n", task_owner)
#     return task_owner, all_assigned_users

# # Load user capacity
# def load_user_capacity(users_file):
#     user_capacity = {}

#     with open(users_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             user_capacity[row["id"]] = float(row.get("weekly_capacity", 0))

#     print("\nuser_capacity:\n", user_capacity)
#     return user_capacity

# # Load user skills
# def load_user_skills(skill_file):
#     user_skills = {}

#     with open(skill_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             skill = row["skill_id"]
#             user = row["user_id"]
#             if skill not in user_skills:
#                 user_skills[skill] = []
#             user_skills[skill].append(user)

#     print("\nuser_skills:\n", user_skills)
#     return user_skills

# # Load tasks
# def load_tasks(task_file):
#     with open(task_file, "r", encoding="utf-8") as file:
#         return list(csv.DictReader(file))

# # User workload
# def calculate_user_workload(all_tasks, task_owner):
#     user_total_hours = {}

#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = row["id"]
#         assignee = str(task_owner.get(task_id, "0")).strip()
#         hours = float(row.get("estimated_hours") or 0.0)

#         user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

#     print("\nuser_total_hours:\n", user_total_hours)
#     return user_total_hours

# # Sort candidates
# def sort_candidates(candidate):
#     highest_remaining = -candidate["remaining"]
#     lowest_task_count = candidate["task_count"]

#     print("HIGHEST REMAINING CANDIDATES:\n",highest_remaining)
#     print("\nLOWEST TASK COUNT:\n",lowest_task_count)
#     return (highest_remaining, lowest_task_count)

# # Helper to sort by total load (lowest hours first)
# def sort_by_load(user_dict):
#     return user_dict["total_load"]

# # Check status and process tasks
# def process_tasks(all_tasks, task_owner, user_capacity, user_skills, user_total_hours, user_task_count):
#     tasks_summary = []
#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue 
            
#         task_id = int(row["id"])
#         deadline = row["date_deadline"]
#         required_skill = row.get("required_skill_id")
#         hours = float(row.get("estimated_hours") or 0.0)
#         original_assignee = str(task_owner.get(str(task_id), "0")).strip()
        
#         total_workload = user_total_hours.get(original_assignee, 0.0)
#         capacity = user_capacity.get(original_assignee, 0.0)
        
#         deadline_date = None
#         if deadline:
#             deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#         # Determining Status
#         if deadline_date and today > deadline_date:
#             if original_assignee == "0":
#                 status = "UNASSIGNED"
#             elif total_workload > capacity:
#                 status = "OVERLOADED"
#             elif 0 < total_workload < (capacity * underutilized_per):
#                 status = "USER_UNDERUTILIZED_BUT_LATE"
#             else:
#                 status = "DELAYED"
#         else:
#             status = "ON_TIME"

#         reassigned_to = original_assignee

#         # Reassignment Logic (Modified to catch all non-ON_TIME statuses)
#         if status != "ON_TIME":
#             candidates = []
#             skilled_users = user_skills.get(required_skill, [])

#             for user_ids in skilled_users:
#                 user_id = str(user_ids).strip()
#                 load = user_total_hours.get(user_id, 0.0)
#                 cap = user_capacity.get(user_id, 0.0)
                
#                 if load + hours <= cap:
#                     candidates.append({
#                         "user_id": user_id,
#                         "remaining": cap - load,
#                         "task_count": user_task_count.get(user_id, 0)
#                     })

#             if candidates:
#                 candidates.sort(key=sort_candidates)
#                 best_user = candidates[0]
#                 reassigned_to = best_user["user_id"]

#                 # Update workload immediately for the next loop iteration
#                 user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#                 user_task_count[reassigned_to] += 1 
#             else:
#                 # No one has free capacity — pick the person who will be free soonest
#                 load_skilled_list = []
#                 for user_ids in skilled_users:
#                     user_id = str(user_ids).strip()
#                     load_skilled_list.append({
#                         "user_id": user_id,
#                         "total_load": user_total_hours.get(user_id, 0.0)
#                     })

#                 if load_skilled_list:
#                     load_skilled_list.sort(key=sort_by_load)
#                     reassigned_to = load_skilled_list[0]["user_id"]
#                     status = "DELAYED_TIMELINE_EXTENSION"

#                     # don't add hours to their current load yet
#                     # The task starts AFTER they finish current work
#                     # delayed_assignments will track when they'll be free
#                 else:
#                     reassigned_to = original_assignee
#                     status = "DELAYED_TIMELINE_EXTENSION"
#                 # else:
#                 #     reassigned_to = original_assignee
#                 print("\nLOAD SKILLED LIST:\n",load_skilled_list)
#         print(f"\nTask {task_id} -> Reassigned to: {reassigned_to} (Status: {status})\n")
#         tasks_summary.append({
#             "task_id": task_id,
#             "status": status,
#             "original_assignee": original_assignee,
#             "reassigned_to": reassigned_to,
#             "hours": hours
#         })

#     print("\nTASKS SUMMARY:\n", tasks_summary)
#     print("\nTOTAL TASKS:", len(all_tasks))
#     print("\nTASKS SUMMARY COUNT:", len(tasks_summary))
#     print(f"\nDEBUG: Successfully processed {len(tasks_summary)} tasks.")
#     return tasks_summary


# def delayed_assignments(tasks_summary, user_skills, user_total_hours):
#     for row in tasks_summary:
#         if row["status"] == "DELAYED_TIMELINE_EXTENSION":
#             task_id = row["task_id"]
#             assignee = row["reassigned_to"]

#             # This is when they finish current work = when this task can start
#             free_after_hours = user_total_hours.get(assignee, 0.0)
#             row["final_load"] = free_after_hours

#             print(f"--> DELAYED TASK {task_id}: assigned to {assignee}")
#             print(f"--> They are free after {free_after_hours} hours of current work")
#             print(f"--> Task will start only after that — no overloading")

#             # NOW add the task hours (task starts after they're free)
#             user_total_hours[assignee] = free_after_hours + row["hours"]
#         else:
#             row["final_load"] = 0.0

#     return tasks_summary

# # Reason and Suggestion generation
# def generate_ai_output(tasks_summary):
#     print("============ ENTERED GENERATE AI OUTPUT ===========")
#     final_output = []
#     chunk_size = 10
    
#     # Detailed prompt to force valid JSON
#     prompt = """
#     You are a Project Manager. Return ONLY a JSON list of objects.
#     JSON Format: [{"task_id": 123, "reason": "text", "suggestion": "text"}]
#     Rules:
#     - ON_TIME: Task is on schedule.
#     - OVERLOADED: Assignee over capacity; rebalanced.
#     - DELAYED_TIMELINE_EXTENSION: All resources full; assigned to earliest available. Extend timeline.
#     No preamble, no markdown, no conversational text.
#     """

#     for i in range(0, len(tasks_summary), chunk_size):
#         chunk = tasks_summary[i: i + chunk_size]
#         try:
#             response = chat(
#                 model="llama3.2",
#                 messages=[{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps(chunk)}],
#                 options={"temperature": 0}
#             )
#             content = response.message.content.strip()
            
#             # --- START STRONG CLEANING ---
#             # Remove markdown backticks if present
#             content = content.replace("```json", "").replace("```", "").strip()
            
#             # Extract just the JSON array part
#             match = re.search(r'\[.*\]', content, re.DOTALL)
#             if match:
#                 json_content = match.group()
#                 ai_output = json.loads(json_content)
#             else:
#                 raise ValueError("No JSON array found in AI response")
#             # --- END STRONG CLEANING ---

#             ai_map = {str(r.get("task_id")): r for r in ai_output}

#             for item in chunk:
#                 t_id = str(item["task_id"])
#                 # Fallback if a specific task_id is missing from AI result
#                 ai_data = ai_map.get(t_id, {"reason": "System Rebalanced", "suggestion": "Review workflow"})
                
#                 final_output.append({
#                     **item, # Keeps task_id, status, assignee, reassigned_to, hours, final_load
#                     "reason": ai_data.get("reason"),
#                     "suggestion": ai_data.get("suggestion")
#                 })
#         except Exception as e:
#             print(f"Batch {i} Error: {e}")
#             for item in chunk:
#                 # Better default fallback if AI fails completely
#                 fallback_reason = "Manual Review" if item['status'] != 'ON_TIME' else "Progressing Normally"
#                 final_output.append({**item, "reason": fallback_reason, "suggestion": "Check resource availability"})
                
#     return final_output


# # Save the output
# def save_output(final_output, output_file):
#     with open(output_file, "w", encoding="utf-8") as file:
#         writer = csv.DictWriter(file, fieldnames=[
#             "task_id", 
#             "status", 
#             "original_assignee", 
#             "reassigned_to", 
#             "reason", 
#             "suggestion",

#             # Add these when working on delayed_assignments:
#             "hours",
#             "final_load"
#         ])
#         writer.writeheader()
#         writer.writerows(final_output)

#     for row in final_output:
#         print("\nROWS:\n", row)

# # Execution Code
# def main():
#     task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
#     assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
#     skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
#     users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"
#     output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

#     task_owner, all_assigned_users = load_task_assignments(assign_file)
#     user_capacity = load_user_capacity(users_file)
#     user_skills = load_user_skills(skill_file)
#     all_tasks = load_tasks(task_file)

#     user_task_count = Counter(all_assigned_users)
#     user_total_hours = calculate_user_workload(all_tasks, task_owner)

#     tasks_summary = process_tasks(
#         all_tasks,
#         task_owner,
#         user_capacity,
#         user_skills,
#         user_total_hours,
#         user_task_count,
#     )

#     updated_tasks_summary= delayed_assignments(tasks_summary, user_skills, user_total_hours)
#     print("updated_tasks_summary : \n ", updated_tasks_summary)
#     print("==="*45)
#     print()
#     final_output = generate_ai_output(updated_tasks_summary)
#     print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2))
 
#     save_output(final_output, output_file)


# if __name__ == "__main__":
#     main()


























# import re
# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# today = datetime.now().date()
# underutilized_per = 0.5

# # Get remaining
# def get_remaining(candidate):
#     print("\nGET REMAINING:\n",candidate)
#     return candidate["remaining"]

# # Load tasks assignments
# def load_task_assignments(assign_file):
#     task_owner = {}
#     all_assigned_users = []

#     with open(assign_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             users = (row.get("user_id") or "0").strip()
#             user_ids = users if users != "" else "0"
#             task_owner[row["task_id"]] = user_ids
#             all_assigned_users.append(user_ids)
#     print("\nALL ASSIGNED USERS:\n",all_assigned_users)
#     print("\nTASK OWNER:\n", task_owner)
#     return task_owner, all_assigned_users

# # Load user capacity
# def load_user_capacity(users_file):
#     user_capacity = {}

#     with open(users_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             user_capacity[row["id"]] = float(row.get("weekly_capacity", 0))

#     print("\nuser_capacity:\n", user_capacity)
#     return user_capacity

# # Load user skills
# def load_user_skills(skill_file):
#     user_skills = {}

#     with open(skill_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             skill = row["skill_id"]
#             user = row["user_id"]
#             if skill not in user_skills:
#                 user_skills[skill] = []
#             user_skills[skill].append(user)

#     print("\nuser_skills:\n", user_skills)
#     return user_skills

# # Load tasks
# def load_tasks(task_file):
#     with open(task_file, "r", encoding="utf-8") as file:
#         return list(csv.DictReader(file))

# # User workload
# def calculate_user_workload(all_tasks, task_owner):
#     user_total_hours = {}

#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = row["id"]
#         assignee = str(task_owner.get(task_id, "0")).strip()
#         hours = float(row.get("estimated_hours") or 0.0)

#         user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

#     print("\nuser_total_hours:\n", user_total_hours)
#     return user_total_hours

# # Sort candidates
# def sort_candidates(candidate):
#     highest_remaining = -candidate["remaining"]
#     lowest_task_count = candidate["task_count"]

#     print("HIGHEST REMAINING CANDIDATES:\n",highest_remaining)
#     print("\nLOWEST TASK COUNT:\n",lowest_task_count)
#     return (highest_remaining, lowest_task_count)

# # Helper to sort by total load (lowest hours first)
# def sort_by_load(user_dict):
#     return user_dict["total_load"]

# # Check status and process tasks
# def process_tasks(all_tasks, task_owner, user_capacity, user_skills, user_total_hours, user_task_count):
#     tasks_summary = []
#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue 
            
#         task_id = int(row["id"])
#         deadline = row["date_deadline"]
#         required_skill = row.get("required_skill_id")
#         hours = float(row.get("estimated_hours") or 0.0)
#         original_assignee = str(task_owner.get(str(task_id), "0")).strip()
        
#         total_workload = user_total_hours.get(original_assignee, 0.0)
#         capacity = user_capacity.get(original_assignee, 0.0)
        
#         deadline_date = None
#         if deadline:
#             deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#         # Determining Status
#         if deadline_date and today > deadline_date:
#             if original_assignee == "0":
#                 status = "UNASSIGNED"
#             elif total_workload > capacity:
#                 status = "OVERLOADED"
#             elif 0 < total_workload < (capacity * underutilized_per):
#                 status = "USER_UNDERUTILIZED_BUT_LATE"
#             else:
#                 status = "DELAYED"
#         else:
#             status = "ON_TIME"

#         reassigned_to = original_assignee

#         # Reassignment Logic (Modified to catch all non-ON_TIME statuses)
#         if status != "ON_TIME":
#             candidates = []
#             skilled_users = user_skills.get(required_skill, [])

#             for user_ids in skilled_users:
#                 user_id = str(user_ids).strip()
#                 load = user_total_hours.get(user_id, 0.0)
#                 cap = user_capacity.get(user_id, 0.0)
                
#                 if load + hours <= cap:
#                     candidates.append({
#                         "user_id": user_id,
#                         "remaining": cap - load,
#                         "task_count": user_task_count.get(user_id, 0)
#                     })
            
#             if candidates:
#                 candidates.sort(key=sort_candidates)
#                 best_user = candidates[0]
#                 reassigned_to = best_user["user_id"]
                
                
#                 # Update workload immediately for the next loop iteration
#                 user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#                 user_task_count[reassigned_to] += 1 
#             else:
#                 # If no one has capacity,pick person with the lowest workload
#                 load_skilled_list = []
#                 for user_ids in skilled_users:
#                     user_id = str(user_ids).strip()
#                     load_skilled_list.append({
#                         "user_id":user_id,
#                         "total_load":user_total_hours.get(user_id,0.0)
#                     })

#                 if load_skilled_list:
#                     load_skilled_list.sort(key=sort_by_load)
#                     reassigned_to = load_skilled_list[0]["user_id"]
#                     status = "DELAYED_TIMELINE_EXTENSION"
#                     user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to,0.0) + hours
#                     user_task_count[reassigned_to] += 1
#                 else:
#                     reassigned_to = original_assignee
#                 print("\nLOAD SKILLED LIST:\n",load_skilled_list)
#         print(f"Task {task_id} -> Reassigned to: {reassigned_to} (Status: {status})")
#         tasks_summary.append({
#             "task_id": task_id,
#             "status": status,
#             "original_assignee": original_assignee,
#             "reassigned_to": reassigned_to,
#             "hours": hours
#         })

#     print("\nTASKS SUMMARY:\n", tasks_summary)
#     print("TOTAL TASKS:", len(all_tasks))
#     print("TASKS SUMMARY COUNT:", len(tasks_summary))
#     print(f"DEBUG: Successfully processed {len(tasks_summary)} tasks.")
#     return tasks_summary


# def delayed_assignments(tasks_summary,user_skills,user_total_hours):
#     for row in tasks_summary:
#         if row["status"] in ["DELAYED","DELAYED_TIMELINE_EXTENSION"]:
#             task_id = row["task_id"]
#             print(f"--> ANALYZING DELAYED TASK: {task_id}")
#             print(f"--> Current Assignee: {row['original_assignee']} -> Reassigned to: {row['reassigned_to']}")
#             final_load = user_total_hours.get(row['reassigned_to'], 0.0)
#             row["final_load"] = final_load
#             print(f"--> Resource {row['reassigned_to']} will be free after {final_load} total hours of work.")
#         else:
#             row["final_load"] = 0.0
    
#     return tasks_summary

# # Reason and Suggestion generation
# def generate_ai_output(tasks_summary):
#     print("============ ENTERED GENERATE AI OUTPUT ===========")
#     final_output = []
#     chunk_size = 10
    
#     prompt = """
#     Return ONLY a JSON list. No preamble, no explanation.
#     JSON Format: [{"task_id": int, "reason": "string", "suggestion": "string"}]
#     """

#     for i in range(0, len(tasks_summary), chunk_size):
#         chunk = tasks_summary[i: i + chunk_size]
#         try:
#             response = chat(
#                 model="llama3.2",
#                 messages=[{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps(chunk)}],
#                 options={"temperature": 0}
#             )
#             content = response.message.content.strip()
            
#             # --- START OF FIX: Robust JSON Extraction ---
#             # Find the first '[' and the last ']'
#             match = re.search(r'\[.*\]', content, re.DOTALL)
#             if match:
#                 json_content = match.group()
#                 ai_output = json.loads(json_content)
#             else:
#                 print(f"Could not find JSON array in response: {content[:50]}...")
#                 raise ValueError("AI response format invalid")
#             # --- END OF FIX ---

#             ai_map = {str(r.get("task_id")): r for r in ai_output}
            
#             for item in chunk:
#                 t_id = str(item["task_id"])
#                 # Safe Fallback if a specific ID is missing in AI response
#                 ai_data = ai_map.get(t_id, {"reason": "System Rebalance", "suggestion": "Review Capacity"})
#                 final_output.append({
#                     "task_id": t_id,
#                     "status": item["status"],
#                     "original_assignee": item["original_assignee"],
#                     "reassigned_to": item["reassigned_to"],
#                     "reason": ai_data.get("reason"),
#                     "suggestion": ai_data.get("suggestion"),
#                     "hours": item.get("hours", 0),
#                     "final_load": item.get("final_load", 0)
#                 })
#         except Exception as e:
#             print(f"Error in batch {i}: {e}")
#             # Ensure script continues even if AI fails for one batch
#             for item in chunk:
#                 final_output.append({**item, "reason": "AI Error", "suggestion": "Manual Review"})
                
#     return final_output



# # Save the output
# def save_output(final_output, output_file):
#     with open(output_file, "w", encoding="utf-8") as file:
#         writer = csv.DictWriter(file, fieldnames=[
#             "task_id", 
#             "status", 
#             "original_assignee", 
#             "reassigned_to", 
#             "reason", 
#             "suggestion",
#             "hours",
#             "final_load"
#         ])
#         writer.writeheader()
#         writer.writerows(final_output)

#     for row in final_output:
#         print("\nROWS:\n", row)

# # Execution Code
# def main():
#     task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
#     assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
#     skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
#     users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"
#     output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

#     task_owner, all_assigned_users = load_task_assignments(assign_file)
#     user_capacity = load_user_capacity(users_file)
#     user_skills = load_user_skills(skill_file)
#     all_tasks = load_tasks(task_file)

#     user_task_count = Counter(all_assigned_users)
#     user_total_hours = calculate_user_workload(all_tasks, task_owner)

#     tasks_summary = process_tasks(
#         all_tasks,
#         task_owner,
#         user_capacity,
#         user_skills,
#         user_total_hours,
#         user_task_count,
#     )

#     updated_tasks_summary= delayed_assignments(tasks_summary, user_skills, user_total_hours)
#     print("updated_tasks_summary : \n ", updated_tasks_summary)
#     print("==="*45)
#     print()
#     final_output = generate_ai_output(updated_tasks_summary)
#     print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2))
 
#     save_output(final_output, output_file)


# if __name__ == "__main__":
#     main()
































# import re
# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# today = datetime.now().date()
# underutilized_per = 0.5

# # Get remaining
# def get_remaining(candidate):
#     print("\nGET REMAINING:\n",candidate)
#     return candidate["remaining"]

# # Load tasks assignments
# def load_task_assignments(assign_file):
#     task_owner = {}
#     all_assigned_users = []

#     with open(assign_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             users = (row.get("user_id") or "0").strip()
#             user_ids = users if users != "" else "0"
#             task_owner[row["task_id"]] = user_ids
#             all_assigned_users.append(user_ids)
#     print("\nALL ASSIGNED USERS:\n",all_assigned_users)
#     print("\nTASK OWNER:\n", task_owner)
#     return task_owner, all_assigned_users

# # Load user capacity
# def load_user_capacity(users_file):
#     user_capacity = {}

#     with open(users_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             user_capacity[row["id"]] = float(row.get("weekly_capacity", 0))

#     print("\nuser_capacity:\n", user_capacity)
#     return user_capacity

# # Load user skills
# def load_user_skills(skill_file):
#     user_skills = {}

#     with open(skill_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             skill = row["skill_id"]
#             user = row["user_id"]
#             if skill not in user_skills:
#                 user_skills[skill] = []
#             user_skills[skill].append(user)

#     print("\nuser_skills:\n", user_skills)
#     return user_skills

# # Load tasks
# def load_tasks(task_file):
#     with open(task_file, "r", encoding="utf-8") as file:
#         return list(csv.DictReader(file))

# # User workload
# def calculate_user_workload(all_tasks, task_owner):
#     user_total_hours = {}

#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = row["id"]
#         assignee = str(task_owner.get(task_id, "0")).strip()
#         hours = float(row.get("estimated_hours") or 0.0)

#         user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

#     print("\nuser_total_hours:\n", user_total_hours)
#     return user_total_hours

# # Sort candidates
# def sort_candidates(candidate):
#     highest_remaining = -candidate["remaining"]
#     lowest_task_count = candidate["task_count"]

#     print("HIGHEST REMAINING CANDIDATES:\n",highest_remaining)
#     print("\nLOWEST TASK COUNT:\n",lowest_task_count)
#     return (highest_remaining, lowest_task_count)

# # Helper to sort by total load (lowest hours first)
# def sort_by_load(user_dict):
#     return user_dict["total_load"]

# # Check status and process tasks
# def process_tasks(all_tasks, task_owner, user_capacity, user_skills, user_total_hours, user_task_count):
#     tasks_summary = []
#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue 
            
#         task_id = int(row["id"])
#         deadline = row["date_deadline"]
#         required_skill = row.get("required_skill_id")
#         hours = float(row.get("estimated_hours") or 0.0)
#         original_assignee = str(task_owner.get(str(task_id), "0")).strip()
        
#         total_workload = user_total_hours.get(original_assignee, 0.0)
#         capacity = user_capacity.get(original_assignee, 0.0)
        
#         deadline_date = None
#         if deadline:
#             deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#         # Determining Status
#         if deadline_date and today > deadline_date:
#             if original_assignee == "0":
#                 status = "UNASSIGNED"
#             elif total_workload > capacity:
#                 status = "OVERLOADED"
#             elif 0 < total_workload < (capacity * underutilized_per):
#                 status = "USER_UNDERUTILIZED_BUT_LATE"
#             else:
#                 status = "DELAYED"
#         else:
#             status = "ON_TIME"

#         reassigned_to = original_assignee

#         # Reassignment Logic (Modified to catch all non-ON_TIME statuses)
#         if status != "ON_TIME":
#             candidates = []
#             skilled_users = user_skills.get(required_skill, [])

#             for user_ids in skilled_users:
#                 user_id = str(user_ids).strip()
#                 load = user_total_hours.get(user_id, 0.0)
#                 cap = user_capacity.get(user_id, 0.0)
                
#                 if load + hours <= cap:
#                     candidates.append({
#                         "user_id": user_id,
#                         "remaining": cap - load,
#                         "task_count": user_task_count.get(user_id, 0)
#                     })
            
#             if candidates:
#                 candidates.sort(key=sort_candidates)
#                 best_user = candidates[0]
#                 reassigned_to = best_user["user_id"]
                
                
#                 # Update workload immediately for the next loop iteration
#                 user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#                 user_task_count[reassigned_to] += 1
#             else:
#                 # If no one has capacity,pick person with the lowest workload
#                 load_skilled_list = []
#                 for user_ids in skilled_users:
#                     user_id = str(user_ids).strip()
#                     load_skilled_list.append({
#                         "user_id":user_id,
#                         "total_load":user_total_hours.get(user_id,0.0)
#                     })

#                 if load_skilled_list:
#                     load_skilled_list.sort(key=sort_by_load)
#                     reassigned_to = load_skilled_list[0]["user_id"]
#                     status = "DELAYED_TIMELINE_EXTENSION"
#                     user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to,0.0) + hours
#                     user_task_count[reassigned_to] += 1
#                 else:
#                     reassigned_to = original_assignee
#                 print("\nLOAD SKILLED LIST:\n",load_skilled_list)
#         print(f"Task {task_id} -> Reassigned to: {reassigned_to} (Status: {status})")
#         tasks_summary.append({
#             "task_id": task_id,
#             "status": status,
#             "original_assignee": original_assignee,
#             "reassigned_to": reassigned_to,
#             "hours": hours
#         })

#     print("\nTASKS SUMMARY:\n", tasks_summary)
#     print("TOTAL TASKS:", len(all_tasks))
#     print("TASKS SUMMARY COUNT:", len(tasks_summary))
#     return tasks_summary


# def delayed_assignments(tasks_summary,user_skills,user_total_hours):
#     for row in tasks_summary:
#         if row["status"] in ["DELAYED","DELAYED_TIMELINE_EXTENSION"]:
#             task_id = row["task_id"]
#             print(f"--> ANALYZING DELAYED TASK: {task_id}")
#             print(f"--> Current Assignee: {row['original_assignee']} -> Reassigned to: {row['reassigned_to']}")
#             final_load = user_total_hours.get(row['reassigned_to'], 0.0)
#             row["final_load"] = final_load
#             print(f"--> Resource {row['reassigned_to']} will be free after {final_load} total hours of work.")
#         else:
#             row["final_load"] = 0.0
    
#     return tasks_summary

# # Reason and Suggestion generation
# def generate_ai_output(tasks_summary):
#     print("hitting "*70)
#     final_output = []
#     chunk_size = 10

#     for i in range(0, len(tasks_summary), chunk_size):
#         chunk = tasks_summary[i: i + chunk_size]

#         prompt = """
#             You are an intelligent Project Manager summarizing resource reallocation. 
#             Write a professional 'reason' and 'suggestion' based strictly on the Task Status.

#             STRICT CONTEXT RULES:
#             1. If status is "ON_TIME":
#             - Reason: "Task is progressing on schedule."
#             - Suggestion: "Continue monitoring current progress."

#             2. If status is "OVERLOADED" and reassigned_to matches original_assignee:
#             - Reason: "Current user is over capacity and no alternative skilled resource is available."
#             - Suggestion: "Extend the project timeline or adjust the task priority."

#             3. If status is "OVERLOADED" and reassigned_to is DIFFERENT:
#             - Reason: "Original assignee was over capacity."
#             - Suggestion: f"Reassigned to User {reassigned_to} (who has the lightest workload) for balance."

#             4. If status is "DELAYED":
#             - Reason: "Task is past the deadline."
#             - Suggestion: "Request an immediate status update and increase the project timeline."

#             5. If status is "UNASSIGNED":
#             - Reason: "Task was missing a designated owner."
#             - Suggestion: "Allocated to a skilled resource to initiate work."

#             6. If status is "DELAYED_TIMELINE_EXTENSION":
#             - Reason: "All skilled resources are at capacity; task moved to user with the earliest availability."
#             - Suggestion: "Increase the project timeline to accommodate current workload."

#             STRICT CONSTRAINTS:
#             - DO NOT suggest "adding another resource" or "hiring".
#             - If no one is free, always prioritize "extending the timeline".
#             - Ensure the 'reason' and 'suggestion' fields are never swapped.

#             STRICT OUTPUT: 
#             Return ONLY a JSON list of objects: [{"task_id": int, "reason": "string", "suggestion": "string"}]
#             """


#         response = chat(
#             model="llama3.2",
#             messages=[
#                 {"role": "system", "content": prompt},
#                 {"role": "user", "content": json.dumps(chunk)}
#             ],
#             options={"temperature": 0}
#         )

#         try:
#             content = response.message.content.strip()
#             print("RAW AI RESPONSE:\n", content)
#             if content.startswith("```"):
#                 content = content.split("```")[1]  # remove ```
#                 if content.startswith("json"):
#                     content = content[4:]  # remove 'json'
#             if "```" in content:
#                 content = content.split("```")[0]
#             content = content.strip()
#             start = content.find("[")
#             end = content.rfind("]") + 1

#             if start == -1 or end == -1:
#                 raise ValueError("No valid JSON found")

#             json_content = content[start:end]
#             json_content = re.sub(r",\s*]", "]", json_content)
#             ai_output = json.loads(json_content)

#             ai_map = {str(r["task_id"]): r for r in ai_output}

#             for item in chunk:
#                 task_id = str(item["task_id"])
#                 is_delayed = item["status"] in ["DELAYED", "DELAYED_TIMELINE_EXTENSION"]
#                 default_sugg = "Review capacity" if item["status"] == "DELAYED" else "REVIEW CAPACITY"
#                 reason_data = ai_map.get(task_id, {"reason": "SYSTEM REBALANCE", "suggestion": default_sugg})

#                 final_output.append({
#                     "task_id": task_id,
#                     "status": item["status"],
#                     "original_assignee": item["original_assignee"],
#                     "reassigned_to": item["reassigned_to"],
#                     "reason": reason_data.get("reason"),
#                     "suggestion": reason_data.get("suggestion")
#                 })
#         except Exception as e:
#             print(f"Error processing batch: {e}")

#     return final_output

# # Save the output
# def save_output(final_output, output_file):
#     with open(output_file, "w", encoding="utf-8") as file:
#         writer = csv.DictWriter(file, fieldnames=[
#             "task_id", "status", "original_assignee",
#             "reassigned_to", "reason", "suggestion"
#         ])
#         writer.writeheader()
#         writer.writerows(final_output)

#     for row in final_output:
#         print("\nROWS:\n", row)

# # Execution Code
# def main():
#     task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
#     assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
#     skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
#     users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"
#     output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

#     task_owner, all_assigned_users = load_task_assignments(assign_file)
#     user_capacity = load_user_capacity(users_file)
#     user_skills = load_user_skills(skill_file)
#     all_tasks = load_tasks(task_file)

#     user_task_count = Counter(all_assigned_users)
#     user_total_hours = calculate_user_workload(all_tasks, task_owner)

#     tasks_summary = process_tasks(
#         all_tasks,
#         task_owner,
#         user_capacity,
#         user_skills,
#         user_total_hours,
#         user_task_count,
#     )

#     updated_tasks_summary= delayed_assignments(tasks_summary, user_skills, user_total_hours)
#     print("updated_tasks_summary : \n ", updated_tasks_summary)
#     print("==="*70)
#     print()
#     final_output = generate_ai_output(updated_tasks_summary)
#     print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2))
 
#     save_output(final_output, output_file)


# if __name__ == "__main__":
#     main()





















# import re
# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# today = datetime.now().date()
# underutilized_per = 0.5

# # Get remaining
# def get_remaining(candidate):
#     print("\nGET REMAINING:\n",candidate)
#     return candidate["remaining"]

# # Load tasks assignments
# def load_task_assignments(assign_file):
#     task_owner = {}
#     all_assigned_users = []

#     with open(assign_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             users = (row.get("user_id") or "0").strip()
#             user_ids = users if users != "" else "0"
#             task_owner[row["task_id"]] = user_ids
#             all_assigned_users.append(user_ids)
#     print("\nALL ASSIGNED USERS:\n",all_assigned_users)
#     print("\nTASK OWNER:\n", task_owner)
#     return task_owner, all_assigned_users

# # Load user capacity
# def load_user_capacity(users_file):
#     user_capacity = {}

#     with open(users_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             user_capacity[row["id"]] = float(row.get("weekly_capacity", 0))

#     print("\nuser_capacity:\n", user_capacity)
#     return user_capacity

# # Load user skills
# def load_user_skills(skill_file):
#     user_skills = {}

#     with open(skill_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             skill = row["skill_id"]
#             user = row["user_id"]
#             if skill not in user_skills:
#                 user_skills[skill] = []
#             user_skills[skill].append(user)

#     print("\nuser_skills:\n", user_skills)
#     return user_skills

# # Load tasks
# def load_tasks(task_file):
#     with open(task_file, "r", encoding="utf-8") as file:
#         return list(csv.DictReader(file))

# # User workload
# def calculate_user_workload(all_tasks, task_owner):
#     user_total_hours = {}

#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = row["id"]
#         assignee = str(task_owner.get(task_id, "0")).strip()
#         hours = float(row.get("estimated_hours") or 0.0)

#         user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

#     print("\nuser_total_hours:\n", user_total_hours)
#     return user_total_hours

# # Sort candidates
# def sort_candidates(candidate):
#     highest_remaining = -candidate["remaining"]
#     lowest_task_count = candidate["task_count"]

#     print("HIGHEST REMAINING CANDIDATES:\n",highest_remaining)
#     print("\nLOWEST TASK COUNT:\n",lowest_task_count)
#     return (highest_remaining, lowest_task_count)

# # Helper to sort by total load (lowest hours first)
# def sort_by_load(user_dict):
#     return user_dict["total_load"]

# # Check status and process tasks
# def process_tasks(all_tasks, task_owner, user_capacity, user_skills, user_total_hours, user_task_count):
#     tasks_summary = []
#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue 
            
#         task_id = int(row["id"])
#         deadline = row["date_deadline"]
#         required_skill = row.get("required_skill_id")
#         hours = float(row.get("estimated_hours") or 0.0)
#         original_assignee = str(task_owner.get(str(task_id), "0")).strip()
        
#         total_workload = user_total_hours.get(original_assignee, 0.0)
#         capacity = user_capacity.get(original_assignee, 0.0)
        
#         deadline_date = None
#         if deadline:
#             deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#         # Determining Status
#         if deadline_date and today > deadline_date:
#             if original_assignee == "0":
#                 status = "UNASSIGNED"
#             elif total_workload > capacity:
#                 status = "OVERLOADED"
#             elif 0 < total_workload < (capacity * underutilized_per):
#                 status = "USER_UNDERUTILIZED_BUT_LATE"
#             else:
#                 status = "DELAYED"
#         else:
#             status = "ON_TIME"

#         reassigned_to = original_assignee

#         # Reassignment Logic (Modified to catch all non-ON_TIME statuses)
#         if status != "ON_TIME":
#             candidates = []
#             skilled_users = user_skills.get(required_skill, [])

#             for user_ids in skilled_users:
#                 user_id = str(user_ids).strip()
#                 load = user_total_hours.get(user_id, 0.0)
#                 cap = user_capacity.get(user_id, 0.0)
                
#                 if load + hours <= cap:
#                     candidates.append({
#                         "user_id": user_id,
#                         "remaining": cap - load,
#                         "task_count": user_task_count.get(user_id, 0)
#                     })
            
#             if candidates:
#                 candidates.sort(key=sort_candidates)
#                 best_user = candidates[0]
#                 reassigned_to = best_user["user_id"]
                
#                 # Update workload immediately for the next loop iteration
#                 user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#                 user_task_count[reassigned_to] += 1
#             else:
#                 # If no one has capacity,pick person with the lowest workload
#                 load_skilled_list = []
#                 for user_ids in skilled_users:
#                     user_id = str(user_ids).strip()
#                     load_skilled_list.append({
#                         "user_id":user_id,
#                         "total_load":user_total_hours.get(user_id,0.0)
#                     })

#                 if load_skilled_list:
#                     load_skilled_list.sort(key=sort_by_load)
#                     reassigned_to = load_skilled_list[0]["user_id"]
#                     status = "DELAYED_TIMELINE_EXTENSION"
#                     user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to,0.0) + hours
#                     user_task_count[reassigned_to] += 1
#                 else:
#                     reassigned_to = original_assignee
#                 print("\nLOAD SKILLED LIST:\n",load_skilled_list)
#         print(f"Task {task_id} -> Reassigned to: {reassigned_to} (Status: {status})")
#         tasks_summary.append({
#             "task_id": task_id,
#             "status": status,
#             "original_assignee": original_assignee,
#             "reassigned_to": reassigned_to,
#             "hours": hours
#         })

#     print("\nTASKS SUMMARY:\n", tasks_summary)
#     print("TOTAL TASKS:", len(all_tasks))
#     print("TASKS SUMMARY COUNT:", len(tasks_summary))
#     return tasks_summary


# def delayed_assignments(tasks_summary,user_skills,user_total_hours):
#     for row in tasks_summary:
#         if row["status"] in ["DELAYED","DELAYED_TIMELINE_EXTENSION"]:
#             task_id = row["task_id"]
#             print(f"--> ANALYZING DELAYED TASK: {task_id}")
#             print(f"--> Current Assignee: {row['original_assignee']} -> Reassigned to: {row['reassigned_to']}")
#             final_load = user_total_hours.get(row['reassigned_to'], 0.0)
#             print(f"--> Resource {row['reassigned_to']} will be free after {final_load} total hours of work.")


# # Reason and Suggestion generation
# def generate_ai_output(tasks_summary):
#     final_output = []
#     chunk_size = 10

#     for i in range(0, len(tasks_summary), chunk_size):
#         chunk = tasks_summary[i: i + chunk_size]

#         prompt = """
# You are an intelligent Project Manager summarizing resource reallocation. 
# Write a professional 'reason' and 'suggestion' based strictly on the Task Status.

# STRICT CONTEXT RULES:
# 1. If status is "ON_TIME":
#    - Reason: "Task is progressing on schedule."
#    - Suggestion: "Continue monitoring current progress."

# 2. If status is "OVERLOADED" and reassigned_to matches original_assignee:
#    - Reason: "Current user is over capacity and no alternative skilled resource is available."
#    - Suggestion: "Extend the project timeline or adjust the task priority."

# 3. If status is "OVERLOADED" and reassigned_to is DIFFERENT:
#    - Reason: "Original assignee was over capacity."
#    - Suggestion: f"Reassigned to User {reassigned_to} (who has the lightest workload) for balance."

# 4. If status is "DELAYED":
#    - Reason: "Task is past the deadline."
#    - Suggestion: "Request an immediate status update and increase the project timeline."

# 5. If status is "UNASSIGNED":
#    - Reason: "Task was missing a designated owner."
#    - Suggestion: "Allocated to a skilled resource to initiate work."

# 6. If status is "DELAYED_TIMELINE_EXTENSION":
#    - Reason: "All skilled resources are at capacity; task moved to user with the earliest availability."
#    - Suggestion: "Increase the project timeline to accommodate current workload."

# STRICT CONSTRAINTS:
# - DO NOT suggest "adding another resource" or "hiring".
# - If no one is free, always prioritize "extending the timeline".
# - Ensure the 'reason' and 'suggestion' fields are never swapped.

# STRICT OUTPUT: 
# Return ONLY a JSON list of objects: [{"task_id": int, "reason": "string", "suggestion": "string"}]
# """


#         response = chat(
#             model="llama3.2",
#             messages=[
#                 {"role": "system", "content": prompt},
#                 {"role": "user", "content": json.dumps(chunk)}
#             ],
#             options={"temperature": 0}
#         )

#         try:
#             content = response.message.content.strip()
#             print("RAW AI RESPONSE:\n", content)
#             if content.startswith("```"):
#                 content = content.split("```")[1]  # remove ```
#                 if content.startswith("json"):
#                     content = content[4:]  # remove 'json'
#             if "```" in content:
#                 content = content.split("```")[0]
#             content = content.strip()
#             start = content.find("[")
#             end = content.rfind("]") + 1

#             if start == -1 or end == -1:
#                 raise ValueError("No valid JSON found")

#             json_content = content[start:end]
#             json_content = re.sub(r",\s*]", "]", json_content)
#             ai_output = json.loads(json_content)

#             ai_map = {str(r["task_id"]): r for r in ai_output}

#             for item in chunk:
#                 task_id = str(item["task_id"])
#                 is_delayed = item["status"] in ["DELAYED", "DELAYED_TIMELINE_EXTENSION"]
#                 default_sugg = "Review capacity" if item["status"] == "DELAYED" else "REVIEW CAPACITY"
#                 reason_data = ai_map.get(task_id, {"reason": "SYSTEM REBALANCE", "suggestion": default_sugg})

#                 final_output.append({
#                     "task_id": task_id,
#                     "status": item["status"],
#                     "original_assignee": item["original_assignee"],
#                     "reassigned_to": item["reassigned_to"],
#                     "reason": reason_data.get("reason"),
#                     "suggestion": reason_data.get("suggestion")
#                 })
#         except Exception as e:
#             print(f"Error processing batch: {e}")

#     return final_output

# # Save the output
# def save_output(final_output, output_file):
#     with open(output_file, "w", encoding="utf-8") as file:
#         writer = csv.DictWriter(file, fieldnames=[
#             "task_id", "status", "original_assignee",
#             "reassigned_to", "reason", "suggestion"
#         ])
#         writer.writeheader()
#         writer.writerows(final_output)

#     for row in final_output:
#         print("\nROWS:\n", row)

# # Execution Code
# def main():
#     task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
#     assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
#     skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
#     users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"
#     output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

#     task_owner, all_assigned_users = load_task_assignments(assign_file)
#     user_capacity = load_user_capacity(users_file)
#     user_skills = load_user_skills(skill_file)
#     all_tasks = load_tasks(task_file)

#     user_task_count = Counter(all_assigned_users)
#     user_total_hours = calculate_user_workload(all_tasks, task_owner)

#     tasks_summary = process_tasks(
#         all_tasks,
#         task_owner,
#         user_capacity,
#         user_skills,
#         user_total_hours,
#         user_task_count,
#     )

#     delayed_assignments(tasks_summary, user_skills, user_total_hours)

#     final_output = generate_ai_output(tasks_summary)
#     print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2))

#     save_output(final_output, output_file)


# if __name__ == "__main__":
#     main()
































# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# today = datetime.now().date()
# underutilized_per = 0.5


# def get_remaining(candidate):
#     return candidate["remaining"]


# def load_task_assignments(assign_file):
#     task_owner = {}
#     all_assigned_users = []

#     with open(assign_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             users = (row.get("user_id") or "0").strip()
#             user_ids = users if users != "" else "0"
#             task_owner[row["task_id"]] = user_ids
#             all_assigned_users.append(user_ids)

#     print("\nTASK OWNER:\n", task_owner)
#     return task_owner, all_assigned_users


# def load_user_capacity(users_file):
#     user_capacity = {}

#     with open(users_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             user_capacity[row["id"]] = float(row.get("weekly_capacity", 0))

#     print("\nuser_capacity:\n", user_capacity)
#     return user_capacity


# def load_user_skills(skill_file):
#     user_skills = {}

#     with open(skill_file, "r", encoding="utf-8") as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             skill = row["skill_id"]
#             user = row["user_id"]
#             if skill not in user_skills:
#                 user_skills[skill] = []
#             user_skills[skill].append(user)

#     print("\nuser_skills:\n", user_skills)
#     return user_skills


# def load_tasks(task_file):
#     with open(task_file, "r", encoding="utf-8") as file:
#         return list(csv.DictReader(file))


# def calculate_user_workload(all_tasks, task_owner):
#     user_total_hours = {}

#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = row["id"]
#         assignee = str(task_owner.get(task_id, "0")).strip()
#         hours = float(row.get("estimated_hours") or 0.0)

#         user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

#     print("\nuser_total_hours:\n", user_total_hours)
#     return user_total_hours


# def sort_candidates(candidate):
#     highest_remaining = -candidate["remaining"]
#     lowest_task_count = candidate["task_count"]
#     return (highest_remaining, lowest_task_count)


# def process_tasks(all_tasks, task_owner, user_capacity, user_skills, user_total_hours, user_task_count):
#     tasks_summary = []

#     for row in all_tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = int(row["id"])
#         deadline = row["date_deadline"]
#         required_skill = row.get("required_skill_id")
#         hours = float(row.get("estimated_hours") or 0.0)
#         original_assignee = str(task_owner.get(str(task_id), "0")).strip()

#         if not original_assignee:
#             original_assignee = "0"

#         total_workload = user_total_hours.get(original_assignee, 0.0)
#         capacity = user_capacity.get(original_assignee, 0.0)

#         deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date() if deadline else None

#         if original_assignee == "0":
#             status = "UNASSIGNED"
#         elif deadline_date and today > deadline_date:
#             status = "DELAYED"
#         elif total_workload > capacity:
#             status = "OVERLOADED"
#         elif 0 < total_workload < (capacity * underutilized_per):
#             status = "USER_UNDERUTILIZED_BUT_LATE"
#         else:
#             status = "ON_TIME"

#         reassigned_to = original_assignee

#         if status in ["OVERLOADED", "UNASSIGNED", "DELAYED"]:
#             candidates = []
#             skilled_users = user_skills.get(required_skill, [])

#             for user_ids in skilled_users:
#                 user_id = str(user_ids).strip()
#                 load = user_total_hours.get(user_id, 0.0)
#                 cap = user_capacity.get(user_id, 0.0)

#                 if load + hours <= cap:
#                     candidates.append({
#                         "user_id": user_id,
#                         "remaining": cap - load,
#                         "task_count": user_task_count.get(user_id, 0)
#                     })

#             if candidates:
#                 candidates.sort(key=sort_candidates)
#                 best_user = candidates[0]
#                 reassigned_to = best_user["user_id"]

#                 user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#                 user_task_count[reassigned_to] += 1

#         tasks_summary.append({
#             "task_id": task_id,
#             "status": status,
#             "original_assignee": original_assignee,
#             "reassigned_to": reassigned_to,
#             "hours": hours
#         })

#     print("\nTASKS SUMMARY:\n", tasks_summary)
#     return tasks_summary


# def generate_ai_output(tasks_summary):
#     final_output = []
#     chunk_size = 10

#     for i in range(0, len(tasks_summary), chunk_size):
#         chunk = tasks_summary[i: i + chunk_size]

#             prompt = """
# You are an intelligent Project Manager summarizing resource reallocation.
# Write a professional 'reason' and 'suggestion' based strictly on the provided Task Status and IDs.

# STRICT CONTEXT RULES:
# 1. If status is "ON_TIME":
#    - Reason: "Task is progressing on schedule."
#    - Suggestion: "Continue monitoring current progress."
# 2. If status is "OVERLOADED" and reassigned_to matches original_assignee:
#    - Reason: "User is over capacity but no alternative skilled resource was found."
#    - Suggestion: "Consider extending the deadline or adding temporary support."
# 3. If status is "OVERLOADED" and reassigned_to is DIFFERENT:
#    - Reason: "Original assignee was over capacity."
#    - Suggestion: f"Reassigned to User {reassigned_to} to balance team workload."
# 4. If status is "DELAYED":
#    - Reason: "Task is past the deadline."
#    - Suggestion: "Prioritize this task immediately or adjust project timeline."
# 5. If status is "UNASSIGNED":
#    - Reason: "Task was missing a designated owner."
#    - Suggestion: "Allocated to a skilled resource to initiate work."
# 6. If status is "USER_UNDERUTILIZED_BUT_LATE":
#    - Reason: "Task is behind schedule despite resource availability."
#    - Suggestion: "Review task complexity or potential blockers with the owner."

# STRICT OUTPUT: Return ONLY a JSON list of objects:
# [{"task_id": int, "reason": "string", "suggestion": "string"}]
# """

#         response = chat(
#             model="llama3.2",
#             messages=[
#                 {"role": "system", "content": prompt},
#                 {"role": "user", "content": json.dumps(chunk)}
#             ],
#             options={"temperature": 0}
#         )

#         try:
#             ai_output = json.loads(response.message.content)
#             ai_map = {str(r["task_id"]): r for r in ai_output}

#             for item in chunk:
#                 task_id = str(item["task_id"])
#                 reason_data = ai_map.get(task_id, {"reason": "Automated balance", "suggestion": "Review capacity"})

#                 final_output.append({
#                     "task_id": task_id,
#                     "status": item["status"],
#                     "original_assignee": item["original_assignee"],
#                     "reassigned_to": item["reassigned_to"],
#                     "reason": reason_data.get("reason"),
#                     "suggestion": reason_data.get("suggestion")
#                 })
#         except Exception as e:
#             print(f"Error processing batch: {e}")

#     return final_output


# def save_output(final_output, output_file):
#     with open(output_file, "w", encoding="utf-8") as file:
#         writer = csv.DictWriter(file, fieldnames=[
#             "task_id", "status", "original_assignee",
#             "reassigned_to", "reason", "suggestion"
#         ])
#         writer.writeheader()
#         writer.writerows(final_output)

#     for row in final_output:
#         print("\nROWS:\n", row)


# def main():
#     task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
#     assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
#     skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
#     users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"
#     output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

#     task_owner, all_assigned_users = load_task_assignments(assign_file)
#     user_capacity = load_user_capacity(users_file)
#     user_skills = load_user_skills(skill_file)
#     all_tasks = load_tasks(task_file)

#     user_task_count = Counter(all_assigned_users)
#     user_total_hours = calculate_user_workload(all_tasks, task_owner)

#     tasks_summary = process_tasks(
#         all_tasks,
#         task_owner,
#         user_capacity,
#         user_skills,
#         user_total_hours,
#         user_task_count
#     )

#     final_output = generate_ai_output(tasks_summary)
#     print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2))

#     save_output(final_output, output_file)


# if __name__ == "__main__":
#     main()



















# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []
# user_capacity = {}
# user_skills = {}
# user_total_hours = {}
# underutilized_per = 0.5

# def get_remaining(candidate):
#     return candidate["remaining"]


# # Load task assignments
# with open(assign_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         users = (row.get("user_id") or "0").strip()
#         user_ids = users if users != "" else "0"
#         task_owner[row["task_id"]] = user_ids
#         all_assigned_users.append(user_ids)

# print("\nTASK OWNER:\n",task_owner)

# # Load user capacity
# with open(users_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         # how much work each user can handle
#         user_capacity[row["id"]] = float(row.get("weekly_capacity", 0))

# print("\nuser_capacity:\n",user_capacity)

# # Get the skill id and user id. Saves skill id as the key and user as the value
# with open(skill_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         skill = row["skill_id"]
#         user = row["user_id"]
#         if skill not in user_skills:
#             user_skills[skill] = []
#         user_skills[skill].append(user)

# print("\nSKILL:\n",skill)
# print("\nuser_skills:\n",user_skills)

# # Count tasks users have
# user_task_count = Counter(all_assigned_users)

# # Load tasks
# with open(task_file, "r", encoding="utf-8") as file:
#     all_tasks = list(csv.DictReader(file))

# # WORKLOAD LOOP
# for row in all_tasks:
#     # is_auto = str(row.get("auto_assigned")).strip().lower() == "False"
#     # Skip id task is completed or client approval is pending
#     # if row["state"] in ["completed", "client_approval_pending"] and not is_auto:
#     #     continue

#     if row["state"] in ["completed","client_approval_pending"]:
#         continue

#     # auto_assigned = row["auto_assigned"]
#     # print("AUTO ASSIGNED:\n", auto_assigned)

#     # Get task id and the assignee
#     task_id = row["id"]
#     assignee = str(task_owner.get(task_id, "0")).strip()
#     # Get estimated hours
#     hours = float(row.get("estimated_hours") or 0.0)

#     # assignee as the key , and value as the sum of tasks hours
#     user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

# print("\nuser_total_hours:\n",user_total_hours)

# # ai_tasks = []

# def sort_candidates(candidate):
#     # "-" -> user with most free hours will be moved to the front of the list
#     highest_remaining = -candidate["remaining"]
#     # if two users have the exact same remaining hours, it looks at the second element.
#     # It will then pick the person with the fewest tasks currently assigned to them.
#     lowest_task_count = candidate["task_count"]
#     return (highest_remaining, lowest_task_count)

# # DECISION LOOP
# tasks_summary = []

# for row in all_tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = int(row["id"])
#     deadline = row["date_deadline"]
#     required_skill = row.get("required_skill_id")
#     hours = float(row.get("estimated_hours") or 0.0)
#     original_assignee = str(task_owner.get(str(task_id), "0")).strip()
#     if not original_assignee:
#         original_assignee = "0"

#     total_workload = user_total_hours.get(original_assignee, 0.0)
#     capacity = user_capacity.get(original_assignee, 0.0)

#     deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date() if deadline else None
#     if original_assignee == "0":
#         status = "UNASSIGNED"
#     elif deadline_date and today > deadline_date:
#         status = "DELAYED"
#     elif total_workload > capacity:
#         status = "OVERLOADED"
#     elif 0 < total_workload < (capacity * underutilized_per):
#         status = "USER_UNDERUTILIZED_BUT_LATE"
#     else:
#         status = "ON_TIME"

#     reassigned_to = original_assignee

#     # REASSIGMENT :
#     if status in ["OVERLOADED", "UNASSIGNED", "DELAYED"]:
#         candidates = []
#         # get skilled users.
#         skilled_users = user_skills.get(required_skill,[])

#         for user_ids in skilled_users:
#             user_id = str(user_ids).strip()
#             load = user_total_hours.get(user_id, 0.0)
#             cap = user_capacity.get(user_id, 0.0)

#             # filter candidates -> only users who can handle this task
#             if load + hours <= cap:
#                 candidates.append({
#                     "user_id": user_id,
#                     "remaining": cap - load,
#                     "task_count": user_task_count.get(user_id, 0)
#                 })
#         if candidates:
#             # sorts
#             candidates.sort(key=sort_candidates)
#             best_user = candidates[0]
#             reassigned_to = best_user["user_id"]

#             # update workload -> no over assigning the same user later
#             user_total_hours[reassigned_to] = user_total_hours.get(reassigned_to, 0.0) + hours
#             user_task_count[reassigned_to] += 1
#         else:
#             # No available skilled user
#             reassigned_to = original_assignee

#     tasks_summary.append ({
#         "task_id": task_id,
#         "status": status,
#         "original_assignee": original_assignee,
#         "reassigned_to": reassigned_to,
#         "hours": hours
#     })

# print("\nCANDIDATES:\n",candidates)
# print("\nTASKS SUMMARY:\n",tasks_summary)

# final_output = []
# chunk_size = 10

# for i in range(0, len(tasks_summary), chunk_size):
#     chunk = tasks_summary[i : i + chunk_size]

#     prompt = """
# You are an intelligent Project Manager summarizing resource reallocation.
# Write a professional 'reason' and 'suggestion' based strictly on the provided Task Status and IDs.

# STRICT CONTEXT RULES:
# 1. If status is "ON_TIME":
#    - Reason: "Task is progressing on schedule."
#    - Suggestion: "Continue monitoring current progress."
# 2. If status is "OVERLOADED" and reassigned_to matches original_assignee:
#    - Reason: "User is over capacity but no alternative skilled resource was found."
#    - Suggestion: "Consider extending the deadline or adding temporary support."
# 3. If status is "OVERLOADED" and reassigned_to is DIFFERENT:
#    - Reason: "Original assignee was over capacity."
#    - Suggestion: f"Reassigned to User {reassigned_to} to balance team workload."
# 4. If status is "DELAYED":
#    - Reason: "Task is past the deadline."
#    - Suggestion: "Prioritize this task immediately or adjust project timeline."
# 5. If status is "UNASSIGNED":
#    - Reason: "Task was missing a designated owner."
#    - Suggestion: "Allocated to a skilled resource to initiate work."
# 6. If status is "USER_UNDERUTILIZED_BUT_LATE":
#    - Reason: "Task is behind schedule despite resource availability."
#    - Suggestion: "Review task complexity or potential blockers with the owner."

# STRICT OUTPUT: Return ONLY a JSON list of objects:
# [{"task_id": int, "reason": "string", "suggestion": "string"}]
# """

#     response = chat(
#             model = "llama3.2",
#             messages = [
#                 {"role":"system", "content":prompt},
#                 {"role":"user", "content":json.dumps(chunk)}
#             ],
#             options={"temperature": 0}
#         )    
#     try:
#         ai_output = json.loads(response.message.content)
#         # mapping ai response
#         ai_map = {}
#         for r in ai_output:
#             key = str(r["task_id"])
#             ai_map[key] = r

#         for item in chunk:
#             task_id = str(item["task_id"])
#             reason_data = ai_map.get(task_id, {"reason": "Automated balance", "suggestion": "Review capacity"})

#             final_output.append({
#                 "task_id": task_id,
#                 "status": item["status"],
#                 "original_assignee": item["original_assignee"],
#                 "reassigned_to": item["reassigned_to"],
#                 "reason": reason_data.get("reason"),
#                 "suggestion": reason_data.get("suggestion")
#             })
#     except Exception as e:
#         print(f"Error processing batch: {e}")

# print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2))

# output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

# with open(output_file, "w", encoding="utf-8") as file:
#     writer = csv.DictWriter(file, fieldnames=["task_id",
#     "status", 
#     "original_assignee", 
#     "reassigned_to", 
#     "reason", 
#     "suggestion"])
#     writer.writeheader()
#     writer.writerows(final_output)

# for row in final_output:
#     print("\nROWS :\n",row)













# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []
# user_capacity = {}
# user_skills = {}
# user_total_hours = {}
# underutilized_per = 0.5

# def get_remaining(candidate):
#     return candidate["remaining"]


# # Load task assignments
# with open(assign_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         user_id = (row.get("user_id") or "0")
#         task_owner[row["task_id"]] = user_id
#         all_assigned_users.append(user_id)

# print("\nALL ASSIGNED USERS:\n",all_assigned_users)

# # Load user capacity
# with open(users_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         user_capacity[row["id"]] = float(row.get("weekly_capacity", 0))

# print("\nuser_capacity:\n",user_capacity)


# # Get the skill id and user id. Saves skill id as the key and user as the value
# with open(skill_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         skill = row["skill_id"]
#         user = row["user_id"]
#         if skill not in user_skills:
#             user_skills[skill] = []
#         user_skills[skill].append(user)
    
# print("\nuser_skills:\n",user_skills)


# # Count tasks users have
# user_task_count = Counter(all_assigned_users)

# # Load tasks
# with open(task_file, "r", encoding="utf-8") as file:
#     all_tasks = list(csv.DictReader(file))

# # WORKLOAD LOOP
# for row in all_tasks:
#     # Skip id task is completed or client approval is pending
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     # Get task id and the assignee
#     task_id = row["id"]
#     assignee = str(task_owner.get(task_id, "0"))
#     # Get estimated hours
#     hours = float(row.get("estimated_hours") or 0.0)

#     # assignee as the key , and value as the sum of tasks hours
#     user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

# print("\nuser_total_hours:\n",user_total_hours)


# ai_tasks = []

# # DECISION LOOP
# for row in all_tasks:
#     # Skip if tasks is completed or client approval is pending
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = int(row["id"])
#     deadline = row["date_deadline"]
#     required_skill = row.get("required_skill_id")
#     # description = row.get("name", "")
#     # print("DESCRIPTION:\n", description)

#     original_assignee =  str(task_owner.get(str(task_id), "0")).strip()
#     total_workload = user_total_hours.get(original_assignee, 0.0)
#     capacity = user_capacity.get(original_assignee, 0.0)

#     # Status logic
#     deadline_date = None
#     if deadline:
#         deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#     if deadline_date and today > deadline_date:
#         status = "DELAYED"
#         if original_assignee == "0":
#             status = "UNASSIGNED"
#         elif total_workload > capacity:
#             status = "OVERLOADED"
#         # check tasks hours are less than 50% of their capacity. check if user has some work.
#         elif 0 < total_workload < (capacity * underutilized_per):
#             status = "USER_UNDERUTILIZED_BUT_LATE"
#             print(f"USER : {original_assignee} , UNDERUTILISED : LOAD {total_workload}h CAPACITY: {capacity}")
#     else:
#         status = "ON_TIME"

#     # Candidates
#     candidates = []
#     for user in user_skills.get(required_skill, []):
#         user = str(user).strip()
#         load = user_total_hours.get(user,0)
#         user_cap = user_capacity.get(user,0)

#         if load < user_cap or user == original_assignee:
#             candidates.append({
#                 "user_id": int(user),
#                 "remaining": round(user_cap - load, 2),
#                 "task_count": user_task_count.get(user, 0),
#                 "capacity": user_cap,
#                 "current_load": load,
#             })

#     # print("\ncandidates:\n",candidates)
#     listing = []
#     for candidate in candidates:
#         # print(candidate["user_id"])
#         listing.append(candidate["user_id"])
#     print("LISTING\n",listing)

#     candidates.sort(key=get_remaining, reverse=True)

#     ai_tasks.append({
#         "task_id": task_id,
#         "status": status,
#         "estimated_hours": hours,
#         # "task_description": description,
#         "required_skill": required_skill,
#         "original_assignee": int(original_assignee) if original_assignee.isdigit() else 0,
#         "candidates": candidates
#     })


# prompt = """
# You are an AI Resource Planner. Your objective is to optimize task distribution based on workload data
# CORE CONSTRAINTS:
# 1. CAPACITY LIMIT: Never assign a task if (current_load + task_hours) > capacity. 
# 2. OPTIMAL SELECTION: Prioritize candidates with the highest remaining capacity (capacity - current_load).
# 3. SYSTEM OVERFLOW: If no candidate has sufficient remaining capacity, set reassigned_to = 0 and Suggestion: "ADD ANOTHER USER OR INCREASE TIMELINE".
# 4. DYNAMIC UPDATING: Treat load as cumulative. Update a candidate’s current_load immediately after a reassignment before evaluating the next task.

# REASSIGNMENT LOGIC:

# - ON_TIME: Maintain original_assignee. Reason: "On schedule." Suggestion: "Continue monitoring."
# - OVERLOADED: Move to candidate with the lowest load and task count. Reason: "Current user is over capacity." Suggestion: "Reassigned to balance workload."
# - DELAYED: If the assignee is under capacity, keep them. If overloaded, move to the best candidate. Reason: "Task delayed." Suggestion: "Consider additional support or timeline adjustment."
# - UNASSIGNED: Assign to candidate with lowest load/task count. Reason: "Task was unassigned." Suggestion: "Assigned to available skilled resource."
# - UNDERUTILIZED_BUT_LATE: Maintain original_assignee. Reason: "User has available capacity." Suggestion: "Focus on completing delayed task."

# OPERATIONAL RULES:
# - RETENTION: Ensure original users retain at least one task if they were managing multiple.
# - BALANCING: Distribute tasks evenly; avoid saturating a single resource.

# OUTPUT FORMAT:
# Return ONLY a valid JSON list. No text or markdown formatting.

# [
#   {
#     "task_id": int,
#     "reassigned_to": int,
#     "reason": string,
#     "suggestion": string
#   }
# ]

# """

# all_results = []
# size = 10

# for i in range(0, len(ai_tasks), size):
#     chunk = ai_tasks[i:i+size]
#     response = chat(
#         model = "llama3.2",
#         messages = [
#             {"role":"system", "content":prompt},
#             {"role":"user", "content":json.dumps(chunk)}
#         ],
#         options={"temperature": 0}
#     )

#     content = response.message.content

#     try:
#         result = json.loads(content)
#         all_results.extend(result)

#         for assignment in result:
#             # task_id = str(assignment["task_id"])
#             new_user = str(assignment.get("reassigned_to", "0")).strip()
#             if new_user == "0":
#                 continue            
#             # Find the task in your ai_tasks list to get its hours
#             task_data = next((item for item in ai_tasks if str(item["task_id"]) == task_id), None)

#             if task_data and new_user != str(task_data["original_assignee"]):
#                 task_hours = float(task_data.get("estimated_hours", 0))
#                 user_total_hours[new_user] = user_total_hours.get(new_user, 0.0) + task_hours
#                 user_task_count[new_user] = user_task_count.get(new_user, 0) + 1

#     except Exception as e:
#         print(f"Error parsing AI response: {e}")

# ai_map = {str(item["task_id"]): item for item in all_results}

# print("\nai_map:\n", json.dumps(ai_map, indent=2))

# final_output = []

# for task in ai_tasks:
#     task_id_str = str(task["task_id"])
#     ai_result = ai_map.get(task_id_str)
    
#     if ai_result:
#         reassigned_to = str(ai_result.get("reassigned_to","0"))
#         reason = ai_result.get("reason","")
#         suggestion = ai_result.get("suggestion","")
#     else:
#         reassigned_to = str(task["original_assignee"])
#         reason = "AI did not return a result for this task."
#         suggestion = "Manual review required."

#     final_output.append({
#         "task_id": task_id_str,
#         "status": status,
#         "original_assignee": task["original_assignee"],
#         "reassigned_to": reassigned_to,
#         "reason": reason,
#         "suggestion": suggestion
#     })
#     # clean_assignee = task["original_assignee"]
#     # status = task["status"]
#     # task_hours = float(task.get("estimated_hours") or 8.0)
    
#     # # 1. Get the AI's reason and suggestion
#     # reason = ai_result.get("reason", "Status unknown.")
#     # suggestion = ai_result.get("suggestion", "Manual review required.")
    
#     # # 2. DECIDE ASSIGNEE: If status is healthy, keep original
#     # if status in ["ON_TIME", "USER_UNDERUTILIZED_BUT_LATE"]:
#     #     reassigned_to = clean_assignee
#     # else:
#     #     # 3. CAPACITY ENFORCEMENT: Pick the best candidate with room
#     #     current_candidates = task.get("candidates", [])
        
#     #     # Sort so lowest load is at candidates[0]
#     #     current_candidates.sort(key=get_load)
        
#     #     found_user = False
#     #     for person in current_candidates:
#     #         if person['current_load'] + task_hours <= person['capacity']:
#     #             reassigned_to = person['user_id']
                
#     #             # UPDATE LOAD IMMEDIATELY so the next task sees this user is busy
#     #             person['current_load'] += task_hours
#     #             user_total_hours[str(reassigned_to)] = person['current_load']
                
#     #             found_user = True
#     #             break # Stop searching, we found a match
        
#     #     if not found_user:
#     #         reassigned_to = 0
#     #         reason = "Capacity Exhausted"
#     #         suggestion = "No available users have remaining capacity for this task."

#     # 4. Save the verified data

# print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2))

# output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

# with open(output_file, "w", encoding="utf-8") as file:
#     writer = csv.DictWriter(file, fieldnames=["task_id", "status", "original_assignee", "reassigned_to", "reason", "suggestion"])
#     writer.writeheader()
#     writer.writerows(final_output)
# # print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2))

# # output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

# # with open(output_file, "w", encoding="utf-8") as file:
# #     writer = csv.DictWriter(file, fieldnames=[
# #         "task_id",
# #         "status",
# #         "original_assignee",
# #         "reassigned_to",
# #         "reason",
# #         "suggestion"
# #     ])

# #     writer.writeheader()
# #     writer.writerows(final_output)

# for row in final_output:
#     print("\nROWS :\n",row)




















# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []
# user_capacity = {}
# user_skills = {}
# user_total_hours = {}
# underutilized_per = 0.5

# def get_remaining(candidate):
#     return candidate["remaining"]


# # Load task assignments
# with open(assign_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         user_id = (row.get("user_id") or "0")
#         task_owner[row["task_id"]] = user_id
#         all_assigned_users.append(user_id)

# print("\nALL ASSIGNED USERS:\n",all_assigned_users)

# # Load user capacity
# with open(users_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         user_capacity[row["id"]] = float(row.get("weekly_capacity", 0))

# print("\nuser_capacity:\n",user_capacity)


# # Get the skill id and user id. Saves skill id as the key and user as the value
# with open(skill_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         skill = row["skill_id"]
#         user = row["user_id"]
#         if skill not in user_skills:
#             user_skills[skill] = []
#         user_skills[skill].append(user)
    
# print("\nuser_skills:\n",user_skills)


# # Count tasks users have
# user_task_count = Counter(all_assigned_users)

# # Load tasks
# with open(task_file, "r", encoding="utf-8") as file:
#     all_tasks = list(csv.DictReader(file))

# # WORKLOAD LOOP
# for row in all_tasks:
#     # Skip id task is completed or client approval is pending
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     # Get task id and the assignee
#     task_id = row["id"]
#     assignee = str(task_owner.get(task_id, "0"))
#     # Get estimated hours
#     hours = float(row.get("estimated_hours") or 0.0)

#     # assignee as the key , and value as the sum of tasks hours
#     user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

# print("\nuser_total_hours:\n",user_total_hours)


# ai_tasks = []

# # DECISION LOOP
# for row in all_tasks:
#     # Skip if tasks is completed or client approval is pending
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = int(row["id"])
#     deadline = row["date_deadline"]
#     required_skill = row.get("required_skill_id")
#     # description = row.get("name", "")
#     # print("DESCRIPTION:\n", description)

#     original_assignee =  str(task_owner.get(str(task_id), "0")).strip()
#     total_workload = user_total_hours.get(original_assignee, 0.0)
#     capacity = user_capacity.get(original_assignee, 0.0)

#     # Status logic
#     deadline_date = None
#     if deadline:
#         deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#     if deadline_date and today > deadline_date:
#         status = "DELAYED"
#         if original_assignee == "0":
#             status = "UNASSIGNED"
#         elif total_workload > capacity:
#             status = "OVERLOADED"
#         # check tasks hours are less than 50% of their capacity. check if user has some work.
#         elif 0 < total_workload < (capacity * underutilized_per):
#             status = "USER_UNDERUTILIZED_BUT_LATE"
#             print(f"USER : {original_assignee} , UNDERUTILISED : LOAD {total_workload}h CAPACITY: {capacity}")
#     else:
#         status = "ON_TIME"

#     # Candidates
#     candidates = []
#     for user in user_skills.get(required_skill, []):
#         user = str(user).strip()
#         load = user_total_hours.get(user,0)
#         user_cap = user_capacity.get(user,0)

#         if load < user_cap or user == original_assignee:
#             candidates.append({
#                 "user_id": int(user),
#                 "remaining": round(user_cap - load, 2),
#                 "task_count": user_task_count.get(user, 0),
#                 "capacity": user_cap,
#                 "current_load": load
#             })

#     # print("\ncandidates:\n",candidates)
#     listing = []
#     for candidate in candidates:
#         # print(candidate["user_id"])
#         listing.append(candidate["user_id"])
#     print("LISTING\n",listing)

#     candidates.sort(key=get_remaining, reverse=True)


#     ai_tasks.append({
#         "task_id": task_id,
#         "status": status,
#         "estimated_hours": hours,
#         # "task_description": description,
#         "required_skill": required_skill,
#         "original_assignee": int(original_assignee) if original_assignee.isdigit() else 0,
#         "candidates": candidates
#     })


# prompt = """
# You are an AI Resource Planner. Your objective is to optimize task distribution based on workload data.

# CORE CONSTRAINTS:
# 1. CAPACITY LIMIT: Never assign a task if (current_load + task_hours) > capacity. 
# 2. OPTIMAL SELECTION: Prioritize candidates with the highest remaining capacity (capacity - current_load).
# 3. SYSTEM OVERFLOW: If no candidate has sufficient remaining capacity, set reassigned_to = 0 and Suggestion: "ADD ANOTHER USER OR INCREASE TIMELINE".
# 4. DYNAMIC UPDATING: Treat load as cumulative. Update a candidate’s current_load immediately after a reassignment before evaluating the next task.

# REASSIGNMENT LOGIC:

# - ON_TIME: Maintain original_assignee. Reason: "On schedule." Suggestion: "Continue monitoring."
# - OVERLOADED: Move to candidate with the lowest load and task count. Reason: "Current user is over capacity." Suggestion: "Reassigned to balance workload."
# - DELAYED: If the assignee is under capacity, keep them. If overloaded, move to the best candidate. Reason: "Task delayed." Suggestion: "Consider additional support or timeline adjustment."
# - UNASSIGNED: Assign to candidate with lowest load/task count. Reason: "Task was unassigned." Suggestion: "Assigned to available skilled resource."
# - UNDERUTILIZED_BUT_LATE: Maintain original_assignee. Reason: "User has available capacity." Suggestion: "Focus on completing delayed task."

# OPERATIONAL RULES:
# - RETENTION: Ensure original users retain at least one task if they were managing multiple.
# - BALANCING: Distribute tasks evenly; avoid saturating a single resource.

# OUTPUT FORMAT:
# Return ONLY a valid JSON list. No text or markdown formatting.

# [
#   {
#     "task_id": int,
#     "reassigned_to": int,
#     "reason": string,
#     "suggestion": string
#   }
# ]

# """

# all_results = []
# size = 10

# for i in range(0, len(ai_tasks), size):
#     chunk = ai_tasks[i:i+size]
#     response = chat(
#         model = "llama3.2",
#         messages = [
#             {"role":"system", "content":prompt},
#             {"role":"user", "content":json.dumps(chunk)}
#         ],
#         options={"temperature": 0}
#     )

#     content = response.message.content

#     try:
#         result = json.loads(content)
#         all_results.extend(result)

#         for assignment in result:
#             # task_id = str(assignment["task_id"])
#             new_user = str(assignment.get("reassigned_to", "0")).strip()
#             if new_user == "0":
#                 continue            
#             # Find the task in your ai_tasks list to get its hours
#             task_data = next((item for item in ai_tasks if str(item["task_id"]) == task_id), None)

#             if task_data and new_user != str(task_data["original_assignee"]):
#                 task_hours = float(task_data.get("estimated_hours", 0))
#                 user_total_hours[new_user] = user_total_hours.get(new_user, 0.0) + task_hours
#                 user_task_count[new_user] = user_task_count.get(new_user, 0) + 1

#     except Exception as e:
#         print(f"Error parsing AI response: {e}")

# ai_map = {str(item["task_id"]): item for item in all_results}

# print("\nai_map:\n", json.dumps(ai_map, indent=2))

# final_output = []

# for task in ai_tasks:
#     task_id_str = str(task["task_id"])
#     ai_result = ai_map.get(task_id_str)
    
#     if ai_result:
#         reassigned_to = str(ai_result.get("reassigned_to","0"))
#         reason = ai_result.get("reason","")
#         suggestion = ai_result.get("suggestion","")
#     else:
#         reassigned_to = str(task["original_assignee"])
#         reason = "AI did not return a result for this task."
#         suggestion = "Manual review required."

#     final_output.append({
#         "task_id": task_id_str,
#         "status": status,
#         "original_assignee": task["original_assignee"],
#         "reassigned_to": reassigned_to,
#         "reason": reason,
#         "suggestion": suggestion
#     })
#     # clean_assignee = task["original_assignee"]
#     # status = task["status"]
#     # task_hours = float(task.get("estimated_hours") or 8.0)
    
#     # # 1. Get the AI's reason and suggestion
#     # reason = ai_result.get("reason", "Status unknown.")
#     # suggestion = ai_result.get("suggestion", "Manual review required.")
    
#     # # 2. DECIDE ASSIGNEE: If status is healthy, keep original
#     # if status in ["ON_TIME", "USER_UNDERUTILIZED_BUT_LATE"]:
#     #     reassigned_to = clean_assignee
#     # else:
#     #     # 3. CAPACITY ENFORCEMENT: Pick the best candidate with room
#     #     current_candidates = task.get("candidates", [])
        
#     #     # Sort so lowest load is at candidates[0]
#     #     current_candidates.sort(key=get_load)
        
#     #     found_user = False
#     #     for person in current_candidates:
#     #         if person['current_load'] + task_hours <= person['capacity']:
#     #             reassigned_to = person['user_id']
                
#     #             # UPDATE LOAD IMMEDIATELY so the next task sees this user is busy
#     #             person['current_load'] += task_hours
#     #             user_total_hours[str(reassigned_to)] = person['current_load']
                
#     #             found_user = True
#     #             break # Stop searching, we found a match
        
#     #     if not found_user:
#     #         reassigned_to = 0
#     #         reason = "Capacity Exhausted"
#     #         suggestion = "No available users have remaining capacity for this task."

#     # 4. Save the verified data

# print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2))

# output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

# with open(output_file, "w", encoding="utf-8") as file:
#     writer = csv.DictWriter(file, fieldnames=["task_id", "status", "original_assignee", "reassigned_to", "reason", "suggestion"])
#     writer.writeheader()
#     writer.writerows(final_output)
# # print("\nFINAL TASK REASSIGNMENTS:\n", json.dumps(final_output, indent=2))

# # output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

# # with open(output_file, "w", encoding="utf-8") as file:
# #     writer = csv.DictWriter(file, fieldnames=[
# #         "task_id",
# #         "status",
# #         "original_assignee",
# #         "reassigned_to",
# #         "reason",
# #         "suggestion"
# #     ])

# #     writer.writeheader()
# #     writer.writerows(final_output)

# for row in final_output:
#     print("\nROWS :\n",row)
















# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []
# user_capacity = {}
# user_skills = {}
# user_total_hours = {}
# underutilized_per = 0.5


# def get_remaining(candidate):
#     return candidate["remaining"]


# with open(assign_file, "r", encoding="utf-8") as f:
#     for row in csv.DictReader(f):
#         uid = row.get("user_id") or "0"
#         task_owner[row["task_id"]] = uid
#         all_assigned_users.append(uid)

# print("\nALL ASSIGNED USERS:\n",all_assigned_users)

# with open(users_file, "r", encoding="utf-8") as f:
#     for row in csv.DictReader(f):
#         user_capacity[row["id"]] = float(row.get("weekly_capacity") or 0)
# print("\nuser_capacity:\n",user_capacity)

# with open(skill_file, "r", encoding="utf-8") as f:
#     for row in csv.DictReader(f):
#         skill, user = row["skill_id"], row["user_id"]
#         user_skills.setdefault(skill, []).append(user)
# print("\nuser_skills:\n",user_skills)

# user_task_count = Counter(all_assigned_users)

# with open(task_file, "r", encoding="utf-8") as f:
#     all_tasks = list(csv.DictReader(f))

# # ─── WORKLOAD LOOP ────────────────────────────────────────────────────────────

# for row in all_tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue
#     task_id = row["id"]
#     assignee = str(task_owner.get(task_id, "0"))
#     hours = float(row.get("estimated_hours") or 0.0)
#     user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours
# print("\nuser_total_hours:\n",user_total_hours)

# # ─── DECISION LOOP ────────────────────────────────────────────────────────────

# ai_tasks = []

# for row in all_tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = row["id"]                          # keep as string consistently
#     hours = float(row.get("estimated_hours") or 0.0)   # FIX: read hours here too
#     deadline = row.get("date_deadline")
#     required_skill = row.get("required_skill_id")

#     original_assignee = str(task_owner.get(task_id, "0")).strip()
#     total_workload = user_total_hours.get(original_assignee, 0.0)
#     capacity = user_capacity.get(original_assignee, 0.0)

#     # Status logic
#     deadline_date = None
#     if deadline:
#         try:
#             deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
#         except ValueError:
#             pass

#     if deadline_date and today > deadline_date:
#         if original_assignee == "0":
#             status = "UNASSIGNED"
#         elif total_workload > capacity:
#             status = "OVERLOADED"
#         elif 0 < total_workload < (capacity * underutilized_per):
#             status = "USER_UNDERUTILIZED_BUT_LATE"
#         else:
#             status = "DELAYED"
#     else:
#         status = "ON_TIME"

#     # Build candidates list with LIVE load values
#     candidates = []
#     for user in user_skills.get(required_skill, []):
#         user = str(user).strip()
#         load = user_total_hours.get(user, 0)
#         cap = user_capacity.get(user, 0)
#         # Include original assignee always; others only if they have room
#         if user == original_assignee or load < cap:
#             candidates.append({
#                 "user_id": user,                        # string, consistent
#                 "capacity": cap,
#                 "current_load": load,
#                 "remaining": round(cap - load, 2),      # explicit for AI
#                 "task_count": user_task_count.get(user, 0)
#             })

#     # Sort candidates by remaining capacity descending so AI gets best options first
#     candidates.sort(key=get_remaining, reverse=True)


#     ai_tasks.append({
#         "task_id": task_id,
#         "status": status,
#         "estimated_hours": hours,
#         "required_skill": required_skill,
#         "original_assignee": original_assignee,
#         "candidates": candidates
#     })

# # ─── AI DECISION LOOP ─────────────────────────────────────────────────────────

# prompt = """
# You are an AI Resource Planner. Your objective is to optimize task distribution based on workload data.

# CORE CONSTRAINTS:
# 1. CAPACITY LIMIT: Never assign a task if (current_load + estimated_hours) > capacity for that candidate.
# 2. OPTIMAL SELECTION: Among valid candidates, pick the one with the highest `remaining` capacity.
# 3. SYSTEM OVERFLOW: If NO candidate has enough remaining capacity, set reassigned_to = "0" and suggest adding resources.
# 4. DYNAMIC UPDATING: Treat load as cumulative within the batch. If you reassign a task to a user, mentally add estimated_hours to their load before deciding the next task.

# REASSIGNMENT RULES BY STATUS:
# - ON_TIME → Keep original_assignee. Reason: "On schedule."
# - USER_UNDERUTILIZED_BUT_LATE → Keep original_assignee. Reason: "User has available capacity; focus on completing delayed task."
# - OVERLOADED → Reassign to best candidate (highest remaining, not the original). Reason: "Assignee over capacity."
# - DELAYED → If original_assignee has room (remaining >= estimated_hours), keep them. Otherwise reassign to best candidate.
# - UNASSIGNED → Assign to candidate with highest remaining capacity. Reason: "Task was unassigned."

# RULES:
# - reassigned_to must be a user_id string from the candidates list, or "0" if no one fits.
# - Never leave original_assignee overloaded if a valid candidate exists.
# - Distribute evenly — do not saturate one person.

# OUTPUT FORMAT:
# Return ONLY a valid JSON list. No explanation, no markdown.

# [
#   {
#     "task_id": string,
#     "reassigned_to": string,
#     "reason": string,
#     "suggestion": string
#   }
# ]
# """

# all_results = []
# size = 10

# for i in range(0, len(ai_tasks), size):
#     chunk = ai_tasks[i:i + size]

#     response = chat(
#         model="llama3.2",
#         messages=[
#             {"role": "system", "content": prompt},
#             {"role": "user", "content": json.dumps(chunk)}
#         ],
#         options={"temperature": 0}
#     )

#     content = response.message.content

#     # Strip markdown fences if model wraps output anyway
#     content = content.strip()
#     if content.startswith("```"):
#         content = content.split("```")[1]
#         if content.startswith("json"):
#             content = content[4:]
#     content = content.strip()

#     try:
#         result = json.loads(content)
#         all_results.extend(result)

#         # ── UPDATE LIVE LOADS after each chunk so next chunk is accurate ──
#         for assignment in result:
#             new_user = str(assignment.get("reassigned_to", "0")).strip()
#             if new_user == "0":
#                 continue
#             task_data = next(
#                 (t for t in ai_tasks if str(t["task_id"]) == str(assignment["task_id"])),
#                 None
#             )
#             if task_data and new_user != str(task_data["original_assignee"]):
#                 task_hours = float(task_data.get("estimated_hours") or 0)
#                 user_total_hours[new_user] = user_total_hours.get(new_user, 0.0) + task_hours
#                 user_task_count[new_user] = user_task_count.get(new_user, 0) + 1

#     except Exception as e:
#         print(f"Chunk {i//size + 1}: Error parsing AI response: {e}")
#         print("Raw response:", content)

# # ─── BUILD FINAL OUTPUT ───────────────────────────────────────────────────────

# ai_map = {str(item["task_id"]): item for item in all_results}

# final_output = []

# for task in ai_tasks:
#     task_id_str = str(task["task_id"])
#     ai_result = ai_map.get(task_id_str)

#     if ai_result:
#         # Trust AI completely
#         reassigned_to = str(ai_result.get("reassigned_to", "0"))
#         reason = ai_result.get("reason", "")
#         suggestion = ai_result.get("suggestion", "")
#     else:
#         # Fallback: AI missed this task
#         reassigned_to = str(task["original_assignee"])
#         reason = "AI did not return a result for this task."
#         suggestion = "Manual review required."

#     final_output.append({
#         "task_id": task_id_str,
#         "status": task["status"],
#         "original_assignee": task["original_assignee"],
#         "reassigned_to": reassigned_to,
#         "reason": reason,
#         "suggestion": suggestion
#     })

# # ─── SAVE OUTPUT ──────────────────────────────────────────────────────────────

# output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

# with open(output_file, "w", encoding="utf-8", newline="") as f:
#     writer = csv.DictWriter(f, fieldnames=[
#         "task_id", "status", "original_assignee", "reassigned_to", "reason", "suggestion"
#     ])
#     writer.writeheader()
#     writer.writerows(final_output)

# print(f"\nDone. {len(final_output)} tasks written to {output_file}")



















# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []
# user_capacity = {}
# user_skills = {}
# user_total_hours = {}
# underutilized_per = 0.5


# # Load task assignments
# with open(assign_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         user_id = (row.get("user_id") or "0")
#         task_owner[row["task_id"]] = user_id
#         all_assigned_users.append(user_id)
# # print("ALL ASSIGNED USERS :\n",all_assigned_users)

# # Load user capacity
# with open(users_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         user_capacity[row["id"]] = float(row.get("weekly_capacity", 0))

# # Get the skill id and user id. Saves skill id as the key and user as the value
# with open(skill_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         skill = row["skill_id"]
#         user = row["user_id"]
#         if skill not in user_skills:
#             user_skills[skill] = []
#         user_skills[skill].append(user)

# # print("USER SKILLS \n",user_skills)

# # Load user skills
# # with open(skill_file, "r", encoding="utf-8") as file:
# #     reader = csv.DictReader(file)
# #     for row in reader:
# #         skill = row["skill_id"]
# #         user = row["user_id"]
# #         user_skills.setdefault(skill, []).append(user)

# # print("\nFINAL USER SKILLS:", user_skills)


# # Count tasks users have
# user_task_count = Counter(all_assigned_users)

# # Load tasks
# with open(task_file, "r", encoding="utf-8") as file:
#     all_tasks = list(csv.DictReader(file))

# # WORKLOAD LOOP
# for row in all_tasks:
#     # Skip id task is completed or client approval is pending
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     # Get task id and the assignee
#     task_id = row["id"]
#     assignee = str(task_owner.get(task_id, "0"))
#     # Get estimated hours
#     hours = float(row.get("estimated_hours") or 0.0)

#     # assignee as the key , and value as the sum of tasks hours
#     user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours
# # print("\nUSER TOTAL HOURS :",user_total_hours)

# ai_tasks = []

# # DECISION LOOP
# for row in all_tasks:
#     # Skip if tasks is completed or client approval is pending
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = int(row["id"])
#     deadline = row["date_deadline"]
#     required_skill = row.get("required_skill_id")
#     # description = row.get("name", "")
#     # print("DESCRIPTION:\n", description)

#     original_assignee = str(task_owner.get(str(task_id), "0"))
#     total_workload = user_total_hours.get(original_assignee, 0.0)
#     capacity = user_capacity.get(original_assignee, 0.0)

#     # print("\nORIGINAL ASSIGNEE:",original_assignee)
#     # print("\nTOTAL WORKLOAD:",total_workload)
#     # print("\nCAPACITY:",capacity)

#     # Status logic
#     deadline_date = None
#     if deadline:
#         deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#     if deadline_date and today > deadline_date:
#         status = "DELAYED"
#         if original_assignee == "0":
#             status = "UNASSIGNED"
#         elif total_workload > capacity:
#             status = "OVERLOADED"
#         # check tasks hours are less than 50% of their capacity. check if user has some work.
#         elif 0 < total_workload < (capacity * underutilized_per):
#             status = "USER_UNDERUTILIZED_BUT_LATE"
#             print(f"USER : {original_assignee} , UNDERUTILISED : LOAD {total_workload}h CAPACITY: {capacity}")
#     else:
#         status = "ON_TIME"

#     # Candidates
#     candidates = []
#     for user in user_skills.get(required_skill, []):
#         candidates.append({
#             "user_id": int(user),
#             "task_count": user_task_count.get(user, 0),
#             "capacity": user_capacity.get(user, 0),
#             "current_load": user_total_hours.get(user, 0)
#         })

#     ai_tasks.append({
#         "task_id": task_id,
#         "status": status,
#         # "task_description": description,
#         "required_skill": required_skill,
#         "original_assignee": int(original_assignee),
#         "candidates": candidates
#     })

# # print("\nAI TASKS BEFORE LLM :\n",ai_tasks)

# prompt = """
# You are an intelligent Project Manager. 

# STRICT RULES for reassignment:
# 1. If status == "ON_TIME":
#    - Keep "reassigned_to" as the original_assignee.
#    - Reason: "On schedule."
#    - Suggestion: "Continue monitoring."

# 2. If status == "OVERLOADED":
#    - You MUST pick a new user from the "candidates" list.
#    - Choose the candidate with the lowest "current_load" and "task_count".
#    - Reason: "Current user is over capacity."
#    - Suggestion: "Reassigned to user <user_id> to balance workload."

# 3. If status == "DELAYED":
#    - Check the original_assignee's load. If they aren't overloaded but the task is late:
#    - KEEP the original_assignee (or pick a second one).
#    - Reason: "Not sufficient work done / Task past deadline."
#    - Suggestion: "Add more resources to this task or extend the project timeline."

# 4. If status == "UNASSIGNED":
#    - Pick the best candidate from the list.
#    - Reason: "Initial assignment missing."
#    - Suggestion: "Assigned to best available skilled resource."

# 5. If status == "USER_UNDERUTILIZED_BUT_LATE":
#    - Keep "reassigned_to" as the original_assignee.
#    - Reason: "Resource has remaining bandwidth."
#    - Suggestion: "Resource is available for additional tasks."

# 6.When reassigning tasks, maintain your standard logic for the majority, but ensure that the original user retains at least one of their tasks (e.g., if a user has 4 tasks, reassign 3 and leave 1).

# STRICT OUTPUT:
# Return ONLY a JSON list. No talk, no markdown.
# [
#   {
#     "task_id": int,
#     "reassigned_to": int,
#     "reason": string,
#     "suggestion": string
#   }
# ]
# """

# # response = chat(
# #     model="llama3",
# #     messages=[
# #         {"role": "system", "content": prompt},
# #         {"role": "user", "content": json.dumps(ai_tasks)}
# #     ],
# #     options={"temperature": 0}
# # )

# all_results = []
# size = 10

# for i in range(0, len(ai_tasks), size):
#     chunk = ai_tasks[i:i+size]
#     response = chat(
#         model = "llama3",
#         messages = [
#             {"role":"system", "content":prompt},
#             {"role":"user", "content":json.dumps(chunk)}
#         ]
#     )

#     try:
#         result = json.loads(response.message.content)
#         all_results.extend(result)
#     except:
#         pass

# # raw_content = response.message.content.strip()

# # if raw_content.startswith("```"):
# #     # Removes ```json at start and ``` at end
# #     raw_content = raw_content.split("```")[1]
# #     if raw_content.startswith("json"):
# #         raw_content = raw_content[4:]
# #     raw_content = raw_content.strip()

# # try :
# #     ai_output = json.loads(response.message.content)
# #     # print("\nAI OUTPUT:\n",ai_output)
# # except json.JSONDecodeError as e:
# #     # print(f"FAILED TO PARSE AI JSON: {e}")
# #     # print(f"RAW CONTENT: {raw_content}")
# #     ai_output = []

# ai_map = {str(item["task_id"]): item for item in ai_output}
# # print("\nAI MAP:\n",ai_map)

# final_output = []

# # for task in ai_tasks:
# #     # Look for a match in the AI results
# #     for item in ai_output:
# #         if item["task_id"] == task["task_id"]:
# #             ai_result = item
# #             break
# #     else:
# #         ai_result = {}

# for task in ai_tasks:
#     task_id = str(task["task_id"])
#     ai_result = ai_map.get(task_id, {})

#     reason = ai_result.get("reason")
#     suggestion = ai_result.get("suggestion")
    
#     if not reason:
#         if task["status"] == "ON_TIME":
#             reason = "On schedule."
#             suggestion = "Continue monitoring."
#         elif task["status"] == "OVERLOADED":
#             reason = "Resource overloaded."
#             suggestion = "Needs reassignment."
#         else:
#             reason = f"Status: {task['status']}"
#             suggestion = "Check manual workflow."

#     final_output.append({
#         "task_id": task_id,
#         "status": task["status"],
#         "original_assignee": task["original_assignee"],
#         "reassigned_to": ai_result.get("reassigned_to", task["original_assignee"]),
#         "reason": reason,
#         "suggestion": suggestion
#     })

# # print("\nFINAL OUTPUT :\n", final_output)

# output_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/ai_output/ai_smart_output.csv"

# with open(output_file, "w", encoding="utf-8") as file:
#     writer = csv.DictWriter(file, fieldnames=[
#         "task_id",
#         "status",
#         "original_assignee",
#         "reassigned_to",
#         "reason",
#         "suggestion"
#     ])

#     writer.writeheader()
#     writer.writerows(final_output)


# for row in final_output:
#     print("\nROWS :\n",row)



























# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []
# user_capacity = {}
# user_skills = {}
# user_total_hours = {}

# # Load task assignments
# with open(assign_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         user_id = (row.get("user_id") or "0").strip()
#         user_id = user_id if user_id and user_id != "" else "0"
#         task_owner[row["task_id"]] = user_id
#         all_assigned_users.append(user_id)

# # Load user weekly capacity
# with open(users_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         user_capacity[row["id"]] = float(row.get("weekly_capacity", 0) or 0)

# # Load user skills
# with open(skill_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         skill = row["skill_id"]
#         user = row["user_id"]
#         if skill not in user_skills:
#             user_skills[skill] = []
#         user_skills[skill].append(user)

# # Count how many tasks a person has
# user_task_count = Counter(all_assigned_users)

# ai_input = []

# with open(task_file, "r", encoding="utf-8") as file:
#     all_tasks = list(csv.DictReader(file))

# # Calculate total workload hours per user
# for row in all_tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = row["id"]
#     assignee = str(task_owner.get(task_id, "0"))
#     hours = float(row.get("estimated_hours") or 0.0)
#     user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

# # Process tasks
# for row in all_tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = int(row["id"])
#     deadline = row["date_deadline"]
#     required_skill = row.get("required_skill_id")

#     original_assignee_str = str(task_owner.get(str(task_id), "0"))
#     if not original_assignee_str or original_assignee_str == "":
#         original_assignee_str = "0"

#     original_assignee = int(original_assignee_str)

#     total_workload = user_total_hours.get(original_assignee_str, 0.0)
#     capacity = user_capacity.get(original_assignee_str, 0.0)

#     # is_overloaded = total_workload > capacity

#     deadline_date = None
#     if deadline:
#         deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#     if original_assignee == 0:
#         status = "UNASSIGNED"
#     elif total_workload > capacity:
#         print("TOTAL WORKLOAD :", total_workload,"\n CAPACITY :", capacity, "\n \n ")
#         status = "OVERLOADED"
#     elif deadline_date and today > deadline_date:
#         print("DEADLINE DATE:", deadline_date, "\n TODAY:", today , "\n \n")
#         status = "DELAYED"
#     else:
#         status = "ON_TIME"

#     candidates = []
#     # Get candidates for this task's skill
#     for user in user_skills.get(required_skill, []):
#         candidates.append({
#             "user_id": int(user),
#             "task_count": user_task_count.get(user, 0),
#             "capacity": user_capacity.get(user, 0)
#         })

#     reassigned_to = original_assignee

#     # if status in ["DELAYED", "OVERLOADED", "UNASSIGNED"]:
#     #     valid_candidates = []
#     #     for candidate in candidates:
#     #         if candidate["user_id"] != original_assignee:
#     #             valid_candidates.append(candidate)

#     #     if valid_candidates:
#     #         best_candidate = valid_candidates[0]
#     #         for candidate in valid_candidates:
#     #             if candidate["task_count"] < best_candidate["task_count"]:
#     #                 best_candidate = candidate
#     #         reassigned_to = best_candidate["user_id"]
#     #     else:
#     #         reassigned_to = 0

#     if status == "DELAYED" or status == "OVERLOADED" or status == "UNASSIGNED":
#         valid_candidates = []
        
#         # Filter out the original assignee
#         for current in candidates:
#             if current["user_id"] != original_assignee:
#                 valid_candidates.append(current)

#         # If we found valid people, find the one with the fewest tasks
#         if len(valid_candidates) > 0:
#             best_candidate = valid_candidates[0]
            
#             for current in valid_candidates:
#                 if current["task_count"] < best_candidate["task_count"]:
#                     best_candidate = current
            
#             reassigned_to = best_candidate["user_id"]
            
#             # Update status if it was unassigned
#         if status == "UNASSIGNED":
#             status = "OVERLOADED"
                
#     else:
#             reassigned_to = original_assignee

#     ai_input.append({
#         "task_id": task_id,
#         "status": status,
#         "original_assignee": original_assignee,
#         "reassigned_to": reassigned_to
#     })

# user_input = json.dumps(ai_input, indent=2)
# print("USER TOTAL HOURS :\n",user_total_hours)

# prompt = """
# You are a backend API that returns ONLY JSON. And a Project Manager.

# STRICT RULES:
# - ONLY JSON
# - NO explanation
# - NO markdown

# OUTPUT FORMAT:
# [
#   {
#     "task_id": <int>,
#     "status": "<string>",
#     "original_assignee": <int>,
#     "reassigned_to": <int>,
#     "reason": "<string>",
#     "suggestion": "<string>"
#   }
# ]

# RULES:
# - DO NOT change task_id
# - DO NOT change status
# - DO NOT change original_assignee
# - DO NOT change reassigned_to

# - If status == DELAYED:
#     reason = "Not sufficient work done"
#     suggestion = "Add resource or Extend timeline"

# - If status == OVERLOADED:
#     reason = "User Overloaded"
#     suggestion = "Reassigned to <user_id>" OR "Add resource or Extend timeline"

# # - If status == OVERLOADED:
# #     reason = "User overloaded"
# #     suggestion = "Reassigned to <user_id>" OR "Add resource or Extend timeline"

# - If status == "UNASSIGNED":
#     reason = "No user assigned"
#     suggestion = "Assign to available resource"

# - If status == ON_TIME:
#     reason = "On schedule"
#     suggestion = "Task has time."

# - Replace <user_id> with actual reassigned_to value
# """

# # Call LLM
# response = chat(
#     model="llama3.2",
#     messages=[
#         {"role": "system", "content": prompt},
#         {"role": "user", "content": user_input}
#     ],
#     # Reduce randomness and creativity of the LLM output:
#     options={"temperature": 0}
# )

# ai_output = response.message.content

# data = json.loads(ai_output)

# ai_file = "ai_data_new.csv"

# with open(ai_file, "w", newline="", encoding="utf-8") as file:
#     writer = csv.DictWriter(file, fieldnames=[
#         "task_id",
#         "status",
#         "original_assignee",
#         "reassigned_to",
#         "reason",
#         "suggestion"
#     ])
    
#     writer.writeheader()
#     writer.writerows(data)

# for row in data:
#     print("\nROW:\n", row)








































# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []
# user_capacity = {}
# user_skills = {}
# user_total_hours = {}


# # Load task assignments
# with open(assign_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         user_id = (row.get("user_id") or "0").strip() or "0"
#         task_owner[row["task_id"]] = user_id
#         all_assigned_users.append(user_id)

# # Load user capacity
# with open(users_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         user_capacity[row["id"]] = float(row.get("weekly_capacity", 0) or 0)

# # Load user skills
# with open(skill_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         skill = row["skill_id"]
#         user = row["user_id"]
#         user_skills.setdefault(skill, []).append(user)

# # Count tasks
# user_task_count = Counter(all_assigned_users)

# # Load tasks
# with open(task_file, "r", encoding="utf-8") as file:
#     all_tasks = list(csv.DictReader(file))


# for row in all_tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = row["id"]
#     assignee = str(task_owner.get(task_id, "0"))
#     hours = float(row.get("estimated_hours") or 0.0)

#     user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours


# ai_tasks = []

# for row in all_tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = int(row["id"])
#     deadline = row["date_deadline"]
#     required_skill = row.get("required_skill_id")
#     description = row.get("name", "")

#     original_assignee = str(task_owner.get(str(task_id), "0")) or "0"

#     total_workload = user_total_hours.get(original_assignee, 0.0)
#     capacity = user_capacity.get(original_assignee, 0.0)

#     # Status logic
#     deadline_date = None
#     if deadline:
#         deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#     if original_assignee == "0":
#         status = "UNASSIGNED"
#     elif total_workload > capacity:
#         status = "OVERLOADED"
#     elif deadline_date and today > deadline_date:
#         status = "DELAYED"
#     else:
#         status = "ON_TIME"

#     # Candidates
#     candidates = []
#     for user in user_skills.get(required_skill, []):
#         candidates.append({
#             "user_id": int(user),
#             "task_count": user_task_count.get(user, 0),
#             "capacity": user_capacity.get(user, 0),
#             "current_load": user_total_hours.get(user, 0)
#         })

#     ai_tasks.append({
#         "task_id": task_id,
#         "status": status,
#         "task_description": description,
#         "original_assignee": int(original_assignee),
#         "candidates": candidates
#     })


# prompt = """
# You are an intelligent project manager.

# Your job:
# 1. Decide best user for task (reassigned_to)
# 2. Give reason and suggestion

# Rules:
# - If status = ON_TIME → keep same user
# - If UNASSIGNED / OVERLOADED / DELAYED:
#     - Choose best candidate based on:
#         - lowest workload
#         - capacity
#         - balanced task count
# - Avoid overloaded users

# STRICT OUTPUT:
# Return ONLY JSON:
# [
#   {
#     "task_id": int,
#     "reassigned_to": int,
#     "reason": string,
#     "suggestion": string
#   }
# ]
# """

# response = chat(
#     model="llama3.2",
#     messages=[
#         {"role": "system", "content": prompt},
#         {"role": "user", "content": json.dumps(ai_tasks)}
#     ],
#     options={"temperature": 0}
# )

# ai_output = json.loads(response.message.content)
# print(ai_output)


# final_output = []

# # for task in ai_tasks:
# #     # Look for a match in the AI results
# #     for item in ai_output:
# #         if item["task_id"] == task["task_id"]:
# #             ai_result = item
# #             break
# #     else:
# #         ai_result = {}

# ai_map = {item["task_id"]: item for item in ai_output}
# print("AI TASKS:\n",ai_tasks)
# for task in ai_tasks:
#     task_id = task["task_id"]
#     ai_result = ai_map.get(task_id, {})

#     final_output.append({
#         "task_id": task_id,
#         "status": task["status"],
#         "original_assignee": task["original_assignee"],
#         "reassigned_to": ai_result.get("reassigned_to", task["original_assignee"]),
#         "reason": ai_result.get("reason", ""),
#         "suggestion": ai_result.get("suggestion", "")
#     })


# output_file = "ai_smart_output.csv"

# with open(output_file, "w", newline="", encoding="utf-8") as file:
#     writer = csv.DictWriter(file, fieldnames=[
#         "task_id",
#         "status",
#         "original_assignee",
#         "reassigned_to",
#         "reason",
#         "suggestion"
#     ])

#     writer.writeheader()
#     writer.writerows(final_output)


# print("\nFINAL OUTPUT:\n")
# for row in final_output:
#     print(row)























# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"
# formatted_csv = "latest_csv.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []
# user_capacity = {}
# user_skills = {}
# user_total_hours = {}

# # Load task assignments
# with open(assign_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         task_id = row["task_id"]
#         # user_id = user_id if user_id and user_id != "" else "0"
#         user_id = (row.get("user_id") or "0").strip()
#         if user_id == "":
#             user_id = "0"
#         task_owner[task_id] = user_id
#         all_assigned_users.append(user_id)

# # Load user weekly capacity
# with open(users_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         user_id = row["id"]
#         capacity = float(row.get("weekly_capacity", 0) or 0)
#         user_capacity[user_id] = capacity
#         # user_capacity[row["id"]] = float(row.get("weekly_capacity", 0) or 0)

# # Load user skills
# with open(skill_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         skill = row["skill_id"]
#         user = row["user_id"]
#         if skill not in user_skills:
#             user_skills[skill] = []
#         user_skills[skill].append(user)

# # Count how many tasks a person has
# user_task_count = Counter(all_assigned_users)

# ai_input = []

# with open(task_file, "r", encoding="utf-8") as file:
#     all_tasks = list(csv.DictReader(file))

# # Calculate total workload hours per user
# for row in all_tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = row["id"]
#     assignee = str(task_owner.get(task_id, "0"))
#     hours = float(row.get("estimated_hours") or 0.0)
#     user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

# # Process tasks
# for row in all_tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = int(row["id"])
#     deadline = row["date_deadline"]
#     required_skill = row.get("required_skill_id")

#     original_assignee_str = str(task_owner.get(str(task_id), "0"))
#     if not original_assignee_str or original_assignee_str == "":
#         original_assignee_str = "0"

#     original_assignee = int(original_assignee_str)

#     total_workload = user_total_hours.get(original_assignee_str, 0.0)
#     capacity = user_capacity.get(original_assignee_str, 0.0)

#     # is_overloaded = total_workload > capacity

#     deadline_date = None
#     if deadline:
#         deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#     if original_assignee == 0:
#         if deadline_date and today > deadline_date:
#             status = "DELAYED"
#         else:
#             status = "UNASSIGNED"
#     elif total_workload > capacity:
#         print("TOTAL WORKLOAD :", total_workload,"\n CAPACITY :", capacity, "\n \n ")
#         status = "OVERLOADED"
#     elif deadline_date and today > deadline_date:
#         print("DEADLINE DATE:", deadline_date, "\n TODAY:", today , "\n \n")
#         status = "DELAYED"
#     else:
#         status = "ON_TIME"

#     candidates = []
#     # Get candidates for this task's skill
#     for user in user_skills.get(required_skill, []):
#         candidates.append({
#             "user_id": int(user),
#             "task_count": user_task_count.get(user, 0),
#             "capacity": user_capacity.get(user, 0),
#             "workload": user_total_hours.get(user, 0)
#         })

#     reassigned_to = original_assignee

#     # if status in ["DELAYED", "OVERLOADED", "UNASSIGNED"]:
#     #     valid_candidates = []
#     #     for candidate in candidates:
#     #         if candidate["user_id"] != original_assignee:
#     #             valid_candidates.append(candidate)

#     #     if valid_candidates:
#     #         best_candidate = valid_candidates[0]
#     #         for candidate in valid_candidates:
#     #             if candidate["task_count"] < best_candidate["task_count"]:
#     #                 best_candidate = candidate
#     #         reassigned_to = best_candidate["user_id"]
#     #     else:
#     #         reassigned_to = 0

#     # if status == "DELAYED" or status == "OVERLOADED" or status == "UNASSIGNED":
#     #     valid_candidates = []
        
#     #     # Filter out the original assignee
#     #     for current in candidates:
#     #         if current["user_id"] != original_assignee:
#     #             valid_candidates.append(current)

#     #     # If we found valid people, find the one with the fewest tasks
#     #     if len(valid_candidates) > 0:
#     #         best_candidate = valid_candidates[0]
            
#     #         for current in valid_candidates:
#     #             if current["task_count"] < best_candidate["task_count"]:
#     #                 best_candidate = current
            
#     #         reassigned_to = best_candidate["user_id"]

#     # else:
#     #     reassigned_to = original_assignee


#     ai_input.append({
#         "task_id": task_id,
#         "status": status,
#         "original_assignee": original_assignee,
#         "candidates": candidates
#     })

# user_input = json.dumps(ai_input, indent=2)
# print("USER TOTAL HOURS :\n",user_total_hours)

# prompt = """
# You are a backend API that returns ONLY JSON. And a Project Manager.

# STRICT RULES:
# - ONLY JSON
# - NO explanation
# - NO markdown

# OUTPUT FORMAT:
# [
#   {
#     "task_id": <int>,
#     "status": "<string>",
#     "original_assignee": <int>,
#     "reassigned_to": <int>,
#     "reason": "<string>",
#     "suggestion": "<string>"
#   }
# ]

# RULES:
# - DO NOT change task_id
# - DO NOT change status
# - DO NOT change original_assignee
# - DO NOT change reassigned_to

# - If status == "DELAYED":
#     reason = "Not sufficient work done"
#     suggestion = "Add resource or Extend timeline"

# # - If status == "OVERLOADED":
# #     reason = "User Overloaded"
# #     suggestion = "Reassigned to <user_id>" OR "Add resource or Extend timeline"

# # - If status == OVERLOADED:
# #     reason = "User overloaded"
# #     suggestion = "Reassigned to <user_id>" OR "Add resource or Extend timeline"

# - If status == "OVERLOADED":
#     reason = "User overloaded"
#     suggestion = "Reassigned to <reassigned_to>" if reassigned_to > 0 else "Add resource or Extend timeline"

# - If status == "UNASSIGNED":
#     reason = "No user assigned"
#     suggestion = "Assign to available resource"

# - If status == "ON_TIME":
#     reason = "On schedule"
#     suggestion = "Task has time."


# - You must decide reassigned_to

# - If status == "DELAYED" or "OVERLOADED" or "UNASSIGNED":
#     - Choose best user from candidates
#     - Prefer:
#         - lowest task_count
#         - user with capacity

# - If no suitable candidate:
#     reassigned_to = original_assignee

# - If status == "ON_TIME":
#     reassigned_to = original_assignee

# - Replace <reassigned_to> with actual reassigned_to value
# - ALWAYS return valid JSON
# - DO NOT include trailing commas
# - DO NOT include comments
# """

# # Call LLM
# response = chat(
#     model="llama3.2",
#     messages=[
#         {"role": "system", "content": prompt},
#         {"role": "user", "content": user_input}
#     ],
#     # Reduce randomness and creativity of the LLM output:
#     options={"temperature": 0}
# )

# ai_output = response.message.content

# # data = json.loads(ai_output)

# try:
#     data = json.loads(ai_output)
# except json.JSONDecodeError:
#     print("Invalid JSON from model:\n", ai_output)
#     exit()


# ai_file = "ai_data_new.csv"

# with open(ai_file, "w", newline="", encoding="utf-8") as file:
#     writer = csv.DictWriter(file, fieldnames=[
#         "task_id",
#         "status",
#         "original_assignee",
#         "reassigned_to",
#         "reason",
#         "suggestion"
#     ])
    
#     writer.writeheader()
#     writer.writerows(data)


# with open(formatted_csv, "w", newline="", encoding="utf-8") as file:
#     writer = csv.DictWriter(file, fieldnames=[
#         "task_id",
#         "status",
#         "original_assignee",
#         "reassigned_to"
#     ])
    
#     writer.writeheader()

#     for row in data:
#         writer.writerow({
#             "task_id": row["task_id"],
#             "status": row["status"],
#             "original_assignee": row["original_assignee"],
#             "reassigned_to": row["reassigned_to"]
#         })

# print("\n Formatted CSV created successfully!")



















# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []
# user_capacity = {}
# user_skills = {}
# user_total_hours = {}


# with open(assign_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         task_id = row["task_id"]
#         user_id = (row.get("user_id") or "0").strip()
#         if user_id == "":
#             user_id = "0"
#         task_owner[task_id] = user_id
#         all_assigned_users.append(user_id)

# with open(users_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         user_id = row["id"]
#         capacity = float(row.get("weekly_capacity", 0) or 0)
#         user_capacity[user_id] = capacity

# with open(skill_file, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         skill = row["skill_id"]
#         user = row["user_id"]
#         if skill not in user_skills:
#             user_skills[skill] = []
#         user_skills[skill].append(user)

# user_task_count = Counter(all_assigned_users)

# with open(task_file, "r", encoding="utf-8") as file:
#     all_tasks = list(csv.DictReader(file))
# for row in all_tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = row["id"]
#     assignee = str(task_owner.get(task_id, "0"))
#     hours = float(row.get("estimated_hours") or 0.0)

#     user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours


# ai_input = []

# for row in all_tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = int(row["id"])
#     deadline = row["date_deadline"]
#     required_skill = row.get("required_skill_id")

#     original_assignee_str = str(task_owner.get(str(task_id), "0"))
#     if not original_assignee_str or original_assignee_str == "":
#         original_assignee_str = "0"

#     original_assignee = int(original_assignee_str)

#     total_workload = user_total_hours.get(original_assignee_str, 0.0)
#     capacity = user_capacity.get(original_assignee_str, 0.0)

#     deadline_date = None
#     if deadline:
#         deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#     if original_assignee == 0:
#         if deadline_date and today > deadline_date:
#             status = "DELAYED"
#         else:
#             status = "UNASSIGNED"
#     elif total_workload > capacity:
#         status = "OVERLOADED"
#     elif deadline_date and today > deadline_date:
#         status = "DELAYED"
#     else:
#         status = "ON_TIME"

#     # Only send candidates (no decision yet)
#     candidates = []
#     for user in user_skills.get(required_skill, []):
#         if int(user) != original_assignee:
#             candidates.append({
#                 "user_id": int(user),
#                 "task_count": user_task_count.get(user, 0),
#                 "capacity": user_capacity.get(user, 0)
#             })

#     ai_input.append({
#         "task_id": task_id,
#         "status": status,
#         "original_assignee": original_assignee,
#         "candidates": candidates
#     })

# user_input = json.dumps(ai_input, indent=2)

# prompt = """
# You are a backend API.

# For each task:
# - If DELAYED / OVERLOADED / UNASSIGNED:
#     - Reassign to best candidate if available
# - Else keep same

# Choose best candidate:
# - lowest task_count
# - within capacity

# Return ONLY JSON:

# [
#   {
#     "task_id": int,
#     "reassigned_to": int,
#     "reason": string
#   }
# ]


# STRICT RULES:
# - Output ONLY raw JSON
# - Do NOT use ```json or ```
# - Do NOT add explanation
# - Do NOT write anything before or after JSON
# """

# response = chat(
#     model="llama3.2",
#     messages=[
#         {"role": "system", "content": prompt},
#         {"role": "user", "content": user_input}
#     ],
#     options={"temperature": 0}
# )

# ai_output = response.message.content

# try:
#     data = json.loads(ai_output)
# except json.JSONDecodeError:
#     print("Invalid JSON from model:\n", ai_output)
#     exit()


# final_data = []

# for decision in data:
#     task_id = decision["task_id"]
#     reassigned_to = decision.get("reassigned_to", 0)

#     original_assignee = int(task_owner.get(str(task_id), "0"))

#     # get valid candidates
#     candidates = next(
#         (item["candidates"] for item in ai_input if item["task_id"] == task_id),
#         []
#     )

#     valid_ids = [c["user_id"] for c in candidates]

#     # safety check
#     if reassigned_to in valid_ids:
#         final_user = reassigned_to
#     else:
#         final_user = original_assignee

#     final_data.append({
#         "task_id": task_id,
#         "status": next(item["status"] for item in ai_input if item["task_id"] == task_id),
#         "original_assignee": original_assignee,
#         "reassigned_to": final_user,
#         "reason": decision["reason"],
#         "suggestion": f"Reassigned to {final_user}" if final_user != original_assignee else "No change"
#     })


# ai_file = "ai_data_new.csv"

# with open(ai_file, "w", newline="", encoding="utf-8") as file:
#     writer = csv.DictWriter(file, fieldnames=[
#         "task_id",
#         "status",
#         "original_assignee",
#         "reassigned_to",
#         "reason",
#         "suggestion"
#     ])

#     writer.writeheader()
#     writer.writerows(final_data)

# for row in final_data:
#     print("\nROW:\n", row)



















# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter


# task_file_path = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assignment_file_path = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file_path = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file_path = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# today_date = datetime.now().date()


# task_to_user_map = {}
# all_assigned_user_ids = []
# user_weekly_capacity = {}
# user_skills_map = {}
# user_total_workload_hours = {}


# with open(assignment_file_path, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         task_id = row["task_id"]
#         user_id = (row.get("user_id") or "0").strip()
#         if user_id == "":
#             user_id = "0"

#         task_to_user_map[task_id] = user_id
#         all_assigned_user_ids.append(user_id)


# with open(users_file_path, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         user_id = row["id"]
#         capacity = float(row.get("weekly_capacity", 0) or 0)
#         user_weekly_capacity[user_id] = capacity


# with open(skill_file_path, "r", encoding="utf-8") as file:
#     reader = csv.DictReader(file)
#     for row in reader:
#         skill_id = row["skill_id"]
#         user_id = row["user_id"]

#         if skill_id not in user_skills_map:
#             user_skills_map[skill_id] = []

#         user_skills_map[skill_id].append(user_id)


# user_task_count = Counter(all_assigned_user_ids)

# with open(task_file_path, "r", encoding="utf-8") as file:
#     all_tasks = list(csv.DictReader(file))


# for task in all_tasks:
#     if task["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = task["id"]
#     assigned_user = task_to_user_map.get(task_id, "0")

#     estimated_hours = float(task.get("estimated_hours") or 0)

#     user_total_workload_hours[assigned_user] = (
#         user_total_workload_hours.get(assigned_user, 0) + estimated_hours
#     )


# tasks_for_llm = []

# for task in all_tasks:
#     if task["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = int(task["id"])
#     required_skill = task.get("required_skill_id")
#     deadline_string = task.get("date_deadline")

#     original_user_id_str = task_to_user_map.get(str(task_id), "0")
#     original_user_id = int(original_user_id_str)

#     total_workload = user_total_workload_hours.get(original_user_id_str, 0)
#     capacity = user_weekly_capacity.get(original_user_id_str, 0)

#     status = "ON_TIME"

#     deadline_date = None
#     if deadline_string:
#         deadline_date = datetime.strptime(deadline_string, "%Y-%m-%d").date()

#     if original_user_id == 0:
#         status = "UNASSIGNED"

#     elif total_workload > capacity:
#         status = "OVERLOADED"

#     elif deadline_date and today_date > deadline_date:
#         status = "DELAYED"

#     elif capacity > 0 and total_workload < (0.5 * capacity):
#         status = "UNDERUTILIZED"

#     candidate_users = []

#     for user_id in user_skills_map.get(required_skill, []):
#         if user_id == original_user_id_str:
#             continue

#         candidate_users.append({
#             "user_id": int(user_id),
#             "task_count": user_task_count.get(user_id, 0),
#             "workload": user_total_workload_hours.get(user_id, 0),
#             "capacity": user_weekly_capacity.get(user_id, 0)
#         })


#     tasks_for_llm.append({
#         "task_id": task_id,
#         "status": status,
#         "original_assignee": original_user_id,
#         "candidates": candidate_users
#     })


# llm_input_json = json.dumps(tasks_for_llm, indent=2)

# prompt = """
# You are a smart project manager.

# For each task:
# - If status is OVERLOADED or DELAYED or UNASSIGNED:
#     Decide one:
#     - REASSIGN
#     - ADD_RESOURCE
#     - EXTEND

# - If REASSIGN:
#     Choose best candidate based on:
#     - lowest workload
#     - lowest task_count
#     - within capacity

# - If UNDERUTILIZED:
#     Assign new task if possible

# STRICT OUTPUT:
# Return ONLY JSON (no text)

# FORMAT:
# [
#   {
#     "task_id": int,
#     "action": "REASSIGN" | "ADD_RESOURCE" | "EXTEND" | "NONE",
#     "reassigned_to": int,
#     "reason": string
#   }
# ]
# """

# response = chat(
#     model="llama3.2",
#     messages=[
#         {"role": "system", "content": prompt},
#         {"role": "user", "content": llm_input_json}
#     ],
#     options={"temperature": 0}
# )

# llm_output_text = response.message.content


# try:
#     llm_output_data = json.loads(llm_output_text)
# except json.JSONDecodeError:
#     print("Invalid JSON from LLM:\n", llm_output_text)
#     exit()


# final_results = []

# for decision in llm_output_data:
#     task_id = decision["task_id"]
#     action = decision["action"]
#     reassigned_to = decision.get("reassigned_to", 0)

#     original_user = next(
#         (item["original_assignee"] for item in tasks_for_llm if item["task_id"] == task_id),
#         0
#     )

#     # Safety check: ensure reassigned user is valid
#     valid_user_ids = [
#         candidate["user_id"]
#         for item in tasks_for_llm if item["task_id"] == task_id
#         for candidate in item["candidates"]
#     ]

#     if action == "REASSIGN" and reassigned_to in valid_user_ids:
#         final_user = reassigned_to
#     else:
#         final_user = original_user

#     final_results.append({
#         "task_id": task_id,
#         "action": action,
#         "final_assignee": final_user,
#         "reason": decision["reason"]
#     })

# output_file = "final_ai_task_output.csv"

# with open(output_file, "w", newline="", encoding="utf-8") as file:
#     writer = csv.DictWriter(file, fieldnames=[
#         "task_id",
#         "action",
#         "final_assignee",
#         "reason"
#     ])
#     writer.writeheader()
#     writer.writerows(final_results)


# for row in final_results:
#     print("\nRESULT:", row)




















# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []
# user_capacity = {}
# user_skills = {}
# user_total_hours = {}

# # Load task assignments
# with open(assign_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# # Load user weekly capacity
# with open(users_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         user_capacity[row["id"]] = float(row.get("weekly_capacity", 0) or 0)

# # Load user skills
# with open(skill_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         skill = row["skill_id"]
#         user = row["user_id"]
#         if skill not in user_skills:
#             user_skills[skill] = []
#         user_skills[skill].append(user)

# # Count how many tasks a person has
# user_task_count = Counter(all_assigned_users)

# ai_input = []

# with open(task_file, "r", encoding="utf-8") as f:
#     all_tasks = list(csv.DictReader(f))

# # Calculate total workload hours per user
# for row in all_tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = row["id"]
#     assignee = str(task_owner.get(task_id, "0"))
#     hours = float(row.get("estimated_hours") or 0.0)
#     user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

# # Process tasks
# for row in all_tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = int(row["id"])
#     deadline = row["date_deadline"]
#     required_skill = row.get("required_skill_id")
    
#     original_assignee_str = str(task_owner.get(str(task_id), "0"))
#     original_assignee = int(original_assignee_str)

#     total_workload = user_total_hours.get(original_assignee_str, 0.0)
#     capacity = user_capacity.get(original_assignee_str, 0.0)
    
#     # is_overloaded = total_workload > capacity

#     deadline_date = None
#     if deadline:
#         deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#     if total_workload > capacity:
#         print("TOTAL WORKLOAD :", total_workload,"\n CAPACITY :", capacity, "\n \n ")
#         status = "OVERLOADED"
#     elif deadline_date and today > deadline_date:
#         print("DEADLINE DATE:", deadline_date, "\n TODAY:", today , "\n \n")
#         status = "DELAYED"
#     else:
#         status = "ON_TIME"

#     candidates = []
#     for user in user_skills.get(required_skill, []):
#         candidates.append({
#             "user_id": int(user),
#             "task_count": user_task_count.get(user, 0),
#             "capacity": user_capacity.get(user, 0)
#         })

#     reassigned_to = original_assignee

#     current_task_hours = float(row.get("estimated_hours") or 0.0)

#     if status in ["DELAYED", "OVERLOADED"]:
#         valid_candidates = []
#         for candidate in candidates:
#             cand_id_str = str(candidate["user_id"])
            
#             # Skip if it's the original owner
#             if candidate["user_id"] == original_assignee:
#                 continue
            
#             # Calculate if the candidate has room for this task
#             cand_current_workload = user_total_hours.get(cand_id_str, 0.0)
#             cand_capacity = user_capacity.get(cand_id_str, 0.0)
            
#             # RULE: Only add to valid_candidates if workload + new task <= capacity
#             if (cand_current_workload + current_task_hours) <= cand_capacity:
#                 valid_candidates.append(candidate)

#         if valid_candidates:
#             # Pick the candidate with the fewest tasks
#             best_candidate = valid_candidates[0]
#             for candidate in valid_candidates:
#                 if candidate["task_count"] < best_candidate["task_count"]:
#                     best_candidate = candidate
            
#             reassigned_to = best_candidate["user_id"]
            
#             # IMPORTANT: Update the candidate's workload and task count 
#             # so the NEXT loop knows they are now busier
#             user_total_hours[str(reassigned_to)] = user_total_hours.get(str(reassigned_to), 0.0) + current_task_hours
#             user_task_count[str(reassigned_to)] += 1
#         else:
#             # No one with the skill has enough free hours
#             reassigned_to = 0

#     ai_input.append({
#         "task_id": task_id,
#         "status": status,
#         "original_assignee": original_assignee,
#         "reassigned_to": reassigned_to
#     })

# user_input = json.dumps(ai_input, indent=2)
# print("USER TOTAL HOURS :\n",user_total_hours)

# prompt = """
# You are a backend API that returns ONLY JSON. And a Project Manager.

# STRICT RULES:
# - ONLY JSON
# - NO explanation
# - NO markdown

# OUTPUT FORMAT:
# [
#   {
#     "task_id": <int>,
#     "status": "<string>",
#     "original_assignee": <int>,
#     "reassigned_to": <int>,
#     "reason": "<string>",
#     "suggestion": "<string>"
#   }
# ]

# RULES:
# - DO NOT change task_id
# - DO NOT change status
# - DO NOT change original_assignee
# - DO NOT change reassigned_to

# - If status == DELAYED:
#     reason = "Not sufficient work done"
#     suggestion = "Add resource or Extend timeline"

# - If status = OVERLOADED:
#     reason = "User Overloaded"
#     suggestion = "Reassigned to <user_id>" OR "Add resource or Extend timeline"

# # - If status = OVERLOADED:
# #     reason = "User overloaded"
# #     suggestion = "Reassigned to <user_id>" OR "Add resource or Extend timeline"

# - If status = ON_TIME:
#     reason = "On schedule"
#     suggestion = "Task has time."

# - Replace <user_id> with actual reassigned_to value
# """

# # Call LLM
# response = chat(
#     model="llama3.2",
#     messages=[
#         {"role": "system", "content": prompt},
#         {"role": "user", "content": user_input}
#     ],
#     # Reduce randomness and creativity of the LLM output:
#     options={"temperature": 0}
# )

# ai_output = response.message.content

# data = json.loads(ai_output)


# ai_file = "ai_data_new.csv"

# with open(ai_file, "w", newline="", encoding="utf-8") as f:
#     writer = csv.DictWriter(f, fieldnames=[
#         "task_id",
#         "status",
#         "original_assignee",
#         "reassigned_to",
#         "reason",
#         "suggestion"
#     ])
    
#     writer.writeheader()
#     writer.writerows(data)

# for row in data:
#     print("\nROW:\n", row)




















# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []
# user_capacity = {}
# user_skills = {}
# user_total_hours = {}

# # Load task assignments
# with open(assign_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# # Load user weekly capacity
# with open(users_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         user_capacity[row["id"]] = float(row.get("weekly_capacity", 0) or 0)

# # Load user skills
# with open(skill_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         skill = row["skill_id"]
#         user = row["user_id"]
#         if skill not in user_skills:
#             user_skills[skill] = []
#         user_skills[skill].append(user)

# # Count how many tasks a person has
# user_task_count = Counter(all_assigned_users)

# ai_input = []

# # Prepare input - Fixed variable names and indentation here
# with open(task_file, "r", encoding="utf-8") as f:
#     all_tasks = list(csv.DictReader(f))

# # Calculate total workload hours per user
# for row in all_tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue
    
#     task_id = row["id"]
#     assignee = str(task_owner.get(task_id, "0"))
#     hours = float(row.get("estimated_hours") or 0.0)
    
#     user_total_hours[assignee] = user_total_hours.get(assignee, 0.0) + hours

# # Process tasks for AI input
# for row in all_tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = int(row["id"])
#     deadline = row["date_deadline"]
#     required_skill = row.get("required_skill_id")
    
#     original_assignee_str = str(task_owner.get(str(task_id), "0"))
#     original_assignee = int(original_assignee_str)

#     total_workload = user_total_hours.get(original_assignee_str, 0.0)
#     capacity = user_capacity.get(original_assignee_str, 0.0)
    
#     # is_overloaded = total_workload > capacity

#     deadline_date = None
#     if deadline:
#         try:
#             deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
#         except ValueError:
#             deadline_date = None

#     if total_workload > capacity:
#         status = "OVERLOADED"
#     elif deadline_date and today > deadline_date:
#         status = "DELAYED"
#     else:
#         status = "ON_TIME"

#     candidates = []
#     for user in user_skills.get(required_skill, []):
#         candidates.append({
#             "user_id": int(user),
#             "task_count": user_task_count.get(user, 0),
#             "capacity": user_capacity.get(user, 0)
#         })

#     reassigned_to = original_assignee

#     if status in ["DELAYED", "OVERLOADED"]:
#         valid_candidates = []
#         for candidate in candidates:
#             if candidate["user_id"] != original_assignee:
#                 valid_candidates.append(candidate)

#         if valid_candidates:
#             best_candidate = valid_candidates[0]
#             for candidate in valid_candidates:
#                 if candidate["task_count"] < best_candidate["task_count"]:
#                     best_candidate = candidate
#             reassigned_to = best_candidate["user_id"]
#         else:
#             reassigned_to = 0

#     ai_input.append({
#         "task_id": task_id,
#         "status": status,
#         "original_assignee": original_assignee,
#         "reassigned_to": reassigned_to
#     })

# user_input = json.dumps(ai_input, indent=2)

# prompt = """
# You are a backend API that returns ONLY JSON. And a Project Manager.

# STRICT RULES:
# - ONLY JSON
# - NO explanation
# - NO markdown

# OUTPUT FORMAT:
# [
#   {
#     "task_id": <int>,
#     "status": "<string>",
#     "original_assignee": <int>,
#     "reassigned_to": <int>,
#     "reason": "<string>",
#     "suggestion": "<string>"
#   }
# ]

# RULES:
# - DO NOT change task_id
# - DO NOT change status
# - DO NOT change original_assignee
# - DO NOT change reassigned_to

# - If status == DELAYED:
#     reason = "Not sufficient work done"
#     suggestion = "Add resource or Extend timeline"

# - If status = OVERLOADED:
#     reason = "Task missed deadline"
#     suggestion = "Reassigned to <user_id>" OR "Add resource or Extend timeline"

# # - If status = OVERLOADED:
# #     reason = "User overloaded"
# #     suggestion = "Reassigned to <user_id>" OR "Add resource or Extend timeline"

# - If status = ON_TIME:
#     reason = "On schedule"
#     suggestion = "Task has time."

# - Replace <user_id> with actual reassigned_to value
# """

# # Call LLM
# response = chat(
#     model="llama3.2",
#     messages=[
#         {"role": "system", "content": prompt},
#         {"role": "user", "content": user_input}
#     ],
#     # Reduce randomness and creativity of the LLM output:
#     options={"temperature": 0}
# )

# ai_output = response.message.content

# data = json.loads(ai_output)


# ai_file = "ai_data_new.csv"

# with open(ai_file, "w", newline="", encoding="utf-8") as f:
#     writer = csv.DictWriter(f, fieldnames=[
#         "task_id",
#         "status",
#         "original_assignee",
#         "reassigned_to",
#         "reason",
#         "suggestion"
#     ])
    
#     writer.writeheader()
#     writer.writerows(data)

# for row in data:
#     print("\nROW:\n", row)

















# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []
# user_capacity = {}
# # users with same skill id
# user_skills = {}
# # sum estimated hours assigned to each user 
# user_total_hours = {}

# # Load task assignments
# with open(assign_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])


# # Load user weekly capacity
# with open(users_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         user_capacity[row["id"]] = float(row.get("weekly_capacity", 0) or 0)


# # Load user skills
# with open(skill_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         skill = row["skill_id"]
#         user = row["user_id"]
#         # user_skills.setdefault(skill, []).append(user)
#         if skill not in user_skills:
#             # If it is a new skill, create an empty list for it
#             user_skills[skill] = []
#         # add user to the list of this skill
#         user_skills[skill].append(user)


# # Count how many tasks a person has
# user_task_count = Counter(all_assigned_users)

# ai_input = []

# # Prepare input
# with open(task_file, "r", encoding="utf-8") as f:
#     tasks = list(csv.DictReader(f))

#     for row in tasks:
#         # Skip completed tasks
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = int(row["id"])
#         deadline = row["date_deadline"]
#         required_skill = row.get("required_skill_id")
#         estimated_hours = row.get("estimated_hours")

#         original_assignee = task_owner.get(str(task_id), "0")
#         if original_assignee in ["", None]:
#             original_assignee = "0"

#         original_assignee = int(original_assignee)

#         hours = float(estimated_hours) if estimated_hours else 0.0
#         print("USER TOTAL HOURS :\n", user_total_hours)
#         # if user exists in the dictionary
#         if original_assignee not in user_total_hours:
#             user_total_hours[original_assignee] = 0.0
#         # add hours of the user's tasks
#         user_total_hours[original_assignee] += hours

#         deadline_date = None
#         if deadline:
#                 deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#         if deadline_date and today > deadline_date:
#             status = "DELAYED"
#             if user_task_count.get(original_assignee, 0) > 2:
#                 status = "OVERLOADED"
#                 action = "REASSIGN_TASKS_KEEP_ONE"
#             else:
#                 action = "EXTEND_DEADLINE_OR_ADD_RESOURCE"
#         # elif user_task_count.get(original_assignee, 0) > 2:
#         #     status = "OVERLOADED"
#         #     action = "REDISTRIBUTE_TASKS"
#         else:
#             status = "ON_TIME"
#             action = "NONE"

#         candidates = []
#         for user in user_skills.get(required_skill, []):
#             candidates.append({
#                 "user_id": int(user),
#                 "task_count": user_task_count.get(user, 0),
#                 "capacity": user_capacity.get(user, 0)
#             })

#         reassigned_to = original_assignee

#         if status in ["DELAYED", "OVERLOADED"]:
#             valid_candidates = []

#             if status == "DELAYED" or status == "OVERLOADED":
                
#                 for candidate in candidates:
                    
#                     if candidate["user_id"] != original_assignee:
#                         valid_candidates.append(candidate)


#             reassigned_to = 0

#             if valid_candidates:
#                 # Start by assuming the first person is the "best"
#                 best_candidate = valid_candidates[0]
                
#                 for candidate in valid_candidates:
#                     # If this candidate has fewer tasks than our current best, update it
#                     if candidate["task_count"] < best_candidate["task_count"]:
#                         best_candidate = candidate
                        
#                 reassigned_to = best_candidate["user_id"]


#         ai_input.append({
#             "task_id": task_id,
#             "status": status,
#             "original_assignee": original_assignee,
#             "reassigned_to": reassigned_to
#         })

# # Convert to JSON
# user_input = json.dumps(ai_input, indent=2)

# # Prompt (LLM only for text generation)
# prompt = """
# You are a backend API that returns ONLY JSON. And a Project Manager.

# STRICT RULES:
# - ONLY JSON
# - NO explanation
# - NO markdown

# OUTPUT FORMAT:
# [
#   {
#     "task_id": <int>,
#     "status": "<string>",
#     "original_assignee": <int>,
#     "reassigned_to": <int>,
#     "reason": "<string>",
#     "suggestion": "<string>"
#   }
# ]

# RULES:
# - DO NOT change task_id
# - DO NOT change status
# - DO NOT change original_assignee
# - DO NOT change reassigned_to

# - If status == DELAYED:
#     reason = "Not sufficient work done"
#     suggestion = "Add resource or Extend timeline"

# - If status = OVERLOADED:
#     reason = "Task missed deadline"
#     suggestion = "Reassigned to <user_id>" OR "Add resource or Extend timeline"

# # - If status = OVERLOADED:
# #     reason = "User overloaded"
# #     suggestion = "Reassigned to <user_id>" OR "Add resource or Extend timeline"

# - If status = ON_TIME:
#     reason = "On schedule"
#     suggestion = "Task has time."

# - Replace <user_id> with actual reassigned_to value
# """

# # Call LLM
# response = chat(
#     model="llama3.2",
#     messages=[
#         {"role": "system", "content": prompt},
#         {"role": "user", "content": user_input}
#     ],
#     options={"temperature": 0}
# )

# ai_output = response.message.content

# # Parse JSON
# try:
#     data = json.loads(ai_output)
# except Exception as e:
#     print("JSON ERROR:", e)
#     print("RAW OUTPUT:\n", ai_output)
#     exit()

# ai_file = "ai_data_new.csv"

# with open(ai_file,"w",encoding="utf-8") as file:
#     file.write(ai_output)

# # Print result
# for row in data:
#     print("\nROW:\n", row)










# import csv
# import json
# from datetime import datetime
# from collections import defaultdict
# from ollama import chat


# # ==============================
# # CONFIG
# # ==============================
# TASK_FILE = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# ASSIGN_FILE = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# SKILL_FILE = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# USERS_FILE = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# TODAY = datetime.now().date()


# # ==============================
# # LOADERS
# # ==============================
# def load_task_owners(assign_file):
#     task_owner = {}
#     with open(assign_file, "r", encoding="utf-8") as f:
#         for row in csv.DictReader(f):
#             task_owner[row["task_id"]] = row["user_id"]
#     return task_owner


# def load_user_capacity(users_file):
#     capacity = {}
#     with open(users_file, "r", encoding="utf-8") as f:
#         for row in csv.DictReader(f):
#             capacity[row["id"]] = float(row.get("weekly_capacity", 0) or 0)
#     return capacity


# def load_user_skills(skill_file):
#     skills = defaultdict(list)
#     with open(skill_file, "r", encoding="utf-8") as f:
#         for row in csv.DictReader(f):
#             skills[row["skill_id"]].append(row["user_id"])
#     return skills


# def load_tasks(task_file):
#     with open(task_file, "r", encoding="utf-8") as f:
#         return list(csv.DictReader(f))


# # ==============================
# # BUSINESS LOGIC
# # ==============================
# def calculate_user_hours(tasks, task_owner):
#     user_hours = defaultdict(float)

#     for row in tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = row["id"]
#         planned_hours = float(row.get("planned_hours", 0) or 0)

#         user = task_owner.get(task_id)
#         if user:
#             user_hours[user] += planned_hours

#     return user_hours


# def get_task_status(row, task_owner, user_hours, user_capacity):
#     task_id = row["id"]
#     deadline = row["date_deadline"]

#     user = task_owner.get(task_id, "0")

#     deadline_date = None
#     if deadline:
#         try:
#             deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
#         except:
#             pass

#     if deadline_date and TODAY > deadline_date:
#         if user_hours.get(user, 0) > user_capacity.get(user, 0):
#             return "OVERLOADED"
#         return "DELAYED"

#     return "ON_TIME"


# def find_best_candidate(original_user, candidates, user_hours, user_capacity):
#     best_user = None
#     best_remaining = float("-inf")

#     for user in candidates:
#         if user == original_user:
#             continue

#         remaining = user_capacity.get(user, 0) - user_hours.get(user, 0)

#         if remaining > best_remaining:
#             best_remaining = remaining
#             best_user = user

#     return best_user if best_user else original_user


# def process_tasks(tasks, task_owner, user_capacity, user_skills):
#     user_hours = calculate_user_hours(tasks, task_owner)

#     results = []

#     for row in tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = int(row["id"])
#         required_skill = row.get("required_skill_id")

#         original_user = task_owner.get(str(task_id), "0")

#         status = get_task_status(row, task_owner, user_hours, user_capacity)

#         reassigned_to = original_user

#         if status in ["DELAYED", "OVERLOADED"]:
#             candidates = user_skills.get(required_skill, [])
#             best_user = find_best_candidate(
#                 original_user,
#                 candidates,
#                 user_hours,
#                 user_capacity
#             )

#             reassigned_to = best_user

#         results.append({
#             "task_id": task_id,
#             "status": status,
#             "original_assignee": int(original_user),
#             "reassigned_to": int(reassigned_to)
#         })

#     return results


# # ==============================
# # LLM CALL
# # ==============================
# def generate_ai_response(ai_input):
#     prompt = """
# You are a backend API that returns ONLY JSON.

# STRICT RULES:
# - ONLY JSON
# - NO explanation
# - NO markdown

# OUTPUT FORMAT:
# [
#   {
#     "task_id": <int>,
#     "status": "<string>",
#     "original_assignee": <int>,
#     "reassigned_to": <int>,
#     "reason": "<string>",
#     "suggestion": "<string>"
#   }
# ]

# RULES:
# - DO NOT change task_id
# - DO NOT change status
# - DO NOT change original_assignee
# - DO NOT change reassigned_to

# - If status == OVERLOADED:
#     reason = "User overloaded"
#     suggestion = "Reassigned to <user_id>"

# - If status == DELAYED:
#     reason = "Task missed deadline"
#     suggestion = "Reassigned to <user_id> or Extend timeline"

# - If status == ON_TIME:
#     reason = "On schedule"
#     suggestion = "Task has time"
# """

#     response = chat(
#         model="llama3.2",
#         messages=[
#             {"role": "system", "content": prompt},
#             {"role": "user", "content": json.dumps(ai_input)}
#         ],
#         options={"temperature": 0}
#     )

#     return response.message.content


# # ==============================
# # MAIN
# # ==============================
# def main():
#     task_owner = load_task_owners(ASSIGN_FILE)
#     user_capacity = load_user_capacity(USERS_FILE)
#     user_skills = load_user_skills(SKILL_FILE)
#     tasks = load_tasks(TASK_FILE)

#     ai_input = process_tasks(tasks, task_owner, user_capacity, user_skills)

#     ai_output = generate_ai_response(ai_input)

#     try:
#         data = json.loads(ai_output)
#     except Exception as e:
#         print("JSON ERROR:", e)
#         print(ai_output)
#         return

#     # Save output
#     with open("ai_output.csv", "w", encoding="utf-8") as f:
#         f.write(ai_output)

#     # Print
#     for row in data:
#         print(row)


# if __name__ == "__main__":
#     main()
















# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []
# user_capacity = {}
# user_skills = {}

# # Load task assignments
# with open(assign_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# # Load user capacity
# with open(users_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         user_capacity[row["id"]] = float(row.get("weekly_capacity", 0) or 0)

# # Load user skills
# with open(skill_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         skill = row["skill_id"]
#         user = row["user_id"]
#         user_skills.setdefault(skill, []).append(user)

# # Count workload
# user_task_count = Counter(all_assigned_users)

# ai_input = []

# # Prepare AI input
# with open(task_file, "r", encoding="utf-8") as f:
#     tasks = list(csv.DictReader(f))

#     for row in tasks:

#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = int(row["id"])
#         deadline = row["date_deadline"]
#         progress = float(row.get("progress", 0) or 0)
#         estimated_hours = float(row.get("estimated_hours", 0) or 0)

#         task_starting = row.get("jj_cockpit_timer_hours")
#         actual_hours = float(task_starting) if task_starting and str(task_starting).upper() != "NULL" else 0.0

#         required_skill = row.get("required_skill_id")

#         original_assignee = task_owner.get(str(task_id), "0")
#         if original_assignee in ["", None]:
#             original_assignee = "0"

#         # Candidates
#         candidates = []
#         for user in user_skills.get(required_skill, []):
#             candidates.append({
#                 "user_id": int(user),
#                 "task_count": user_task_count.get(user, 0),
#                 "capacity": user_capacity.get(user, 0)
#             })

#         ai_input.append({
#             "task_id": task_id,
#             "deadline": deadline,
#             "today": str(today),
#             "progress": progress,
#             "estimated_hours": estimated_hours,
#             "actual_hours": actual_hours,
#             "original_assignee": int(original_assignee),
#             "original_user_task_count": user_task_count.get(original_assignee, 0),
#             "original_user_capacity": user_capacity.get(original_assignee, 0),
#             "required_skill": required_skill,
#             "candidates": candidates
#         })

# # Convert to JSON
# user_input = json.dumps(ai_input, indent=2)

# # Prompt
# prompt = """
# You are a backend API that returns ONLY JSON.

# STRICT RULES:
# - ONLY JSON
# - NO explanation
# - NO markdown
# - Output must start with [ and end with ]

# OUTPUT FORMAT [STRICT]:
# [
#   {
#     "task_id": <int>,
#     "status": "ON_TIME | DELAYED | OVERLOADED",
#     "original_assignee": <int>,
#     "reassigned_to": <int>,
#     "reason": "<string>",
#     "suggestion": "<string>"
#   }
# ]

# LOGIC:
# - If today > deadline → DELAYED
# - Else if original_user_task_count > 2 → OVERLOADED
# - Else → ON_TIME

# - If DELAYED or OVERLOADED:
#     → pick candidate with lowest task_count
#     → if exists:
#         reassigned_to = user_id
#         reason = "Overloaded"
#         suggestion = "Reassigned to <user_id>"
#     → else:
#         reassigned_to = 0
#         reason = "No resource"
#         suggestion = "Add resource or Extend timeline"

# - If ON_TIME:
#     reason = "On schedule"
#     suggestion = "Task has time."
# """

# # Call LLM
# response = chat(
#     model="llama3.2",
#     messages=[
#         {"role": "system", "content": prompt},
#         {"role": "user", "content": user_input}
#     ],
#     options={"temperature": 0}
# )

# ai_output = response.message.content

# # Parse JSON
# try:
#     data = json.loads(ai_output)
# except Exception as e:
#     print("JSON ERROR:", e)
#     print("RAW OUTPUT:\n", ai_output)
#     exit()

# # Print result
# for row in data:
#     print("\nROW:\n", row)






























# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter


# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"


# today = datetime.now().date()
# task_owner = {}
# all_assigned_users = []
# results_list = []
# user_capacity = {}
# threshold = 2


# def safe_float(value):
#     if value in [None, "", "NULL"]:
#         return 0.0
#     return float(value)


# # ===============================
# # LOAD ASSIGNED TASKS
# # ===============================
# with open(assign_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])


# # ===============================
# # LOAD USER CAPACITY
# # ===============================
# with open(users_file, "r", encoding="utf-8") as file:
#     users = csv.DictReader(file)
#     for row in users:
#         user_capacity[row["id"]] = safe_float(row.get("weekly_capacity"))


# # ===============================
# # LOAD SKILLS (OPTIMIZED)
# # ===============================
# with open(skill_file, "r", encoding="utf-8") as f_skill:
#     skills_data = list(csv.DictReader(f_skill))


# # ===============================
# # LOAD TASKS
# # ===============================
# with open(task_file, "r", encoding="utf-8") as f:
#     tasks = list(csv.DictReader(f))


# print("ALL ASSIGNED USERS:\n", all_assigned_users)

# # Count tasks per user
# user_tasks_count = Counter(all_assigned_users)
# print("USER TASKS COUNT:\n", user_tasks_count)


# # ===============================
# # CALCULATE USER WORKLOAD
# # ===============================
# user_workload_hours = Counter()

# for row in tasks:
#     if row["state"] not in ["completed", "client_approval_pending"]:
#         assignee = task_owner.get(row["id"], "0")

#         if assignee != "0":
#             estimate_hours = safe_float(row.get("estimated_hours"))
#             user_workload_hours[assignee] += estimate_hours

# print("USER WORKLOAD HOURS:\n", user_workload_hours)


# # ===============================
# # MAIN PROCESSING
# # ===============================
# for row in tasks:

#     # Skip completed tasks
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = row["id"]
#     deadline_str = row.get("date_deadline")
#     progress = row.get("progress")
#     required_skill = row.get("required_skill_id")

#     estimated_hours = safe_float(row.get("estimated_hours"))
#     user_actual_hours = safe_float(row.get("effective_hours"))

#     # Assignee
#     original_assignee = task_owner.get(task_id, "0")
#     if original_assignee in ["", None]:
#         original_assignee = "0"

#     capacity_value = user_capacity.get(original_assignee, 0.0)
#     current_assignee_load = user_tasks_count.get(original_assignee, 0)

#     # ===============================
#     # STATUS LOGIC
#     # ===============================
#     status = "ON_TIME"

#     if deadline_str and deadline_str not in ["", "NULL"]:
#         deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()

#         if today > deadline_date or user_actual_hours < estimated_hours:
#             status = "DELAYED"

#         elif current_assignee_load > threshold:
#             status = "OVERLOADED"

#     # ===============================
#     # DEFAULT VALUES
#     # ===============================
#     reassigned_to = "0"
#     reason = "On schedule"
#     suggestion = "Task has time."

#     # ===============================
#     # REASSIGNMENT LOGIC
#     # ===============================
#     if status == "DELAYED" or current_assignee_load > threshold:

#         suggest_employees = []

#         for skill_row in skills_data:
#             if (
#                 str(skill_row["skill_id"]) == str(required_skill)
#                 and skill_row["user_id"] != original_assignee
#             ):
#                 suggest_employees.append(skill_row["user_id"])

#         if suggest_employees:

#             least_loaded_user = min(
#                 suggest_employees,
#                 key=lambda user: user_tasks_count.get(user, 0)
#             )

#             reassigned_to = least_loaded_user

#             # Update counts
#             user_tasks_count[reassigned_to] += 1
#             if original_assignee != "0":
#                 user_tasks_count[original_assignee] -= 1

#             task_owner[task_id] = reassigned_to

#             # ===============================
#             # REASON LOGIC
#             # ===============================
#             if current_assignee_load > threshold:
#                 reason = "Overloaded User"
#             elif estimated_hours > user_actual_hours:
#                 reason = "Insufficient work done"
#             else:
#                 reason = "Delayed"

#             suggestion = f"Reassigned to {reassigned_to}"

#         else:
#             suggestion = "No skilled employee found"

#     # ===============================
#     # LOW PROGRESS CHECK
#     # ===============================
#     if (
#         status == "DELAYED"
#         and reassigned_to == "0"
#         and progress
#         and safe_float(progress) <= 50
#     ):
#         reason = "Low Progress"
#         suggestion = "Add resource or Extend timeline."

#     # ===============================
#     # STORE RESULT
#     # ===============================
#     results_list.append({
#         "Task ID": task_id,
#         "Status": status,
#         "Original Assignee": original_assignee,
#         "Reassigned To": reassigned_to,
#         "Reason": reason,
#         "Suggestion": suggestion,
#     })


# # ===============================
# # SORT RESULTS
# # ===============================
# def get_task_id(item):
#     try:
#         return int(item["Task ID"])
#     except:
#         return 0


# results_list.sort(key=get_task_id)

# print("\nRESULTS LIST:\n", results_list)


# # ===============================
# # AI INPUT
# # ===============================
# user_input = json.dumps(results_list, indent=2)


# # ===============================
# # PROMPT
# # ===============================
# prompt = """
# You are a Project Manager AI. 
# TASK: Generate a CSV report from JSON input.

# STRICT RULES:
# - Output ONLY CSV
# - No explanations
# - No markdown

# HEADER:
# task_id,status,original_assignee,reassigned_to,reason,suggestion
# """


# # ===============================
# # AI CALL
# # ===============================
# response = chat(
#     model="llama3.2",
#     messages=[
#         {"role": "system", "content": prompt},
#         {"role": "user", "content": user_input}
#     ]
# )

# ai_output = response.message.content


# # ===============================
# # SAVE CSV
# # ===============================
# ai_file = "ai_data_new.csv"

# with open(ai_file, "w", encoding="utf-8") as file:
#     file.write(ai_output)


# # ===============================
# # READ OUTPUT
# # ===============================
# with open(ai_file, "r", encoding="utf-8") as f_read:
#     final_reader = csv.DictReader(f_read)
#     for row in final_reader:
#         print("\nROWS:\n", row)






















# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []
# results_list = []
# user_capacity = {}
# threshold = 2

# def safe_float(value):
#     try:
#         if value is None or str(value).upper() == "NULL" or str(value).strip() == "":
#             return 0.0
#         return float(value)
#     except:
#         return 0.0

# with open(assign_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# with open(users_file, "r", encoding="utf-8") as file:
#     users = csv.DictReader(file)
#     for row in users:
#         user_capacity[row["id"]] = safe_float(row.get("weekly_capacity"))

# with open(task_file, "r", encoding="utf-8") as f:
#     tasks = list(csv.DictReader(f))

# user_tasks_count = Counter(all_assigned_users)

# user_workload_hours = Counter()

# for row in tasks:
#     if row["state"] not in ["completed", "client_approval_pending"]:
#         assignee = task_owner.get(row["id"], "0")
#         if assignee != "0":
#             estimated_hours = safe_float(row.get("estimated_hours"))
#             user_workload_hours[assignee] += estimated_hours

# for row in tasks:

#     # Skip completed
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = row["id"]
#     deadline_str = row.get("date_deadline")
#     progress = safe_float(row.get("progress"))
#     required_skill = row.get("required_skill_id")

#     estimated_hours = safe_float(row.get("estimated_hours"))
#     user_actual_hours = safe_float(row.get("jj_cockpit_timer_hours"))

#     original_assignee = task_owner.get(task_id, "0")
#     if original_assignee in ["", None]:
#         original_assignee = "0"

#     capacity_value = user_capacity.get(original_assignee, 40.0)
#     total_user_hours = user_workload_hours.get(original_assignee, 0)
#     current_task_count = user_tasks_count.get(original_assignee, 0)

#     status = "ON_TIME"

#     if deadline_str and deadline_str.upper() != "NULL" and deadline_str.strip() != "":
#         deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()

#         if today > deadline_date or user_actual_hours < estimated_hours:
#             status = "DELAYED"

#     if total_user_hours > capacity_value:
#         status = "OVERLOADED"

#     reassigned_to = "0"
#     reason = "On schedule"
#     suggestion = "Task has time."

#     if status == "DELAYED":
#         if total_user_hours > capacity_value:
#             reason = "Overloaded user"
#         elif estimated_hours > user_actual_hours:
#             reason = "Insufficient work done"
#         else:
#             reason = "Delayed"

#     if original_assignee == "0" or total_user_hours > capacity_value:

#         suggest_employees = []

#         with open(skill_file, "r", encoding="utf-8") as f_skill:
#             skills = csv.DictReader(f_skill)

#             for skill_row in skills:
#                 if (
#                     str(skill_row["skill_id"]).strip() == str(required_skill).strip()
#                     and skill_row["user_id"] != original_assignee
#                 ):
#                     suggest_employees.append(skill_row["user_id"])

#         if suggest_employees:
#             # pick least loaded user
#             reassigned_to = min(
#                 suggest_employees,
#                 key=lambda u: user_tasks_count.get(u, 0)
#             )

#             # update counts
#             user_tasks_count[reassigned_to] += 1
#             if original_assignee != "0":
#                 user_tasks_count[original_assignee] -= 1

#             task_owner[task_id] = reassigned_to

#             if original_assignee == "0":
#                 reason = "No assignee"
#                 suggestion = "Assign task to available employee"
#             else:
#                 reason = "Overloaded"
#                 suggestion = f"Reassigned to {reassigned_to}"
#         else:
#             suggestion = "No skilled employee found"

#     if status == "DELAYED" and reassigned_to == "0" and progress <= 50:
#         if reason == "Delayed":
#             reason = "Low Progress"
#         suggestion = "Add resource or extend timeline"

#     results_list.append({
#         "task_id": task_id,
#         "status": status,
#         "original_assignee": original_assignee,
#         "reassigned_to": reassigned_to,
#         "reason": reason,
#         "suggestion": suggestion,
#     })

# def get_task_id(item):
#     try:
#         return int(item["task_id"])
#     except:
#         return 0

# results_list.sort(key=get_task_id)

# user_input = json.dumps(results_list, indent=2)

# prompt = """
# You are a Project Manager AI.
# Return ONLY CSV.

# HEADER:
# task_id,status,original_assignee,reassigned_to,reason,suggestion

# RULES:
# - Keep 6 columns exactly
# - No explanation
# """

# response = chat(
#     model="llama3.2",
#     messages=[
#         {"role": "system", "content": prompt},
#         {"role": "user", "content": user_input}
#     ]
# )

# ai_output = response.message.content

# ai_file = "ai_data_new.csv"

# with open(ai_file, "w", encoding="utf-8") as file:
#     file.write(ai_output)

# with open(ai_file, "r", encoding="utf-8") as f_read:
#     final_reader = csv.DictReader(f_read)
#     for row in final_reader:
#         print(row)



















# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter


# def safe_float(value):
#     if value in [None, "", "NULL", "null", "None"]:
#         return 0.0
#     try:
#         return float(value)
#     except:
#         return 0.0


# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# today = datetime.now().date()


# task_owner = {}
# all_assigned_users = []

# with open(assign_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# # Count tasks per user
# user_tasks_count = Counter(all_assigned_users)


# task_data = {}
# user_total_estimated = Counter()
# user_total_actual = Counter()

# with open(task_file, "r", encoding="utf-8") as f:
#     tasks = list(csv.DictReader(f))

#     for row in tasks:
#         task_id = row["id"]

#         # estimated hours
#         estimated_hours = safe_float(row.get("planned_hours")) or safe_float(row.get("estimated_hours"))
#         actual_hours = safe_float(row.get("effective_hours"))

#         start_date = row.get("create_date") or row.get("date_assign")
#         if start_date and start_date != "NULL":
#             start_date = datetime.strptime(start_date.split(" ")[0], "%Y-%m-%d")

#         task_data[task_id] = {
#             "estimated_hours": estimated_hours,
#             "actual_hours": actual_hours,
#             "start_date": start_date,
#             "deadline": row.get("date_deadline"),
#             "progress": float(row.get("progress") or 0),
#             "required_skill": row.get("required_skill_id"),
#             "state": row.get("state")
#         }

#         user_id = task_owner.get(task_id, "0")
#         if user_id != "0":
#             user_total_estimated[user_id] += estimated_hours
#             user_total_actual[user_id] += actual_hours


# results_list = []
# THRESHOLD = 2

# for task_id, data in task_data.items():

#     # Skip completed / approval pending
#     if data["state"] in ["completed", "client_approval_pending"]:
#         continue

#     original_assignee = task_owner.get(task_id, "0")
#     if not original_assignee:
#         original_assignee = "0"

#     user_task_count = user_tasks_count.get(original_assignee, 0)

#     estimated = data["estimated_hours"]
#     actual = data["actual_hours"]
#     deadline = data["deadline"]

#     status = "ON_TIME"


#     if deadline and deadline != "NULL":
#         deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

#         if today > deadline_date or actual < estimated:
#             status = "DELAYED"


#     reassigned_to = "0"
#     reason = "On schedule"
#     suggestion = "No change"

#     if original_assignee == "0":
#         reason = "No assignee"
#         suggestion = "Assign task to available employee"


#     elif status == "DELAYED":

#         if actual < estimated:
#             reason = "Insufficient work done"

#         if user_task_count > THRESHOLD:
#             reason = "Overloaded user"

#         suggest_employees = []

#         with open(skill_file, "r", encoding="utf-8") as f_skill:
#             skills = csv.DictReader(f_skill)

#             for skill_row in skills:
#                 if (
#                     skill_row["skill_id"] == data["required_skill"]
#                     and skill_row["user_id"] != original_assignee
#                 ):
#                     suggest_employees.append(skill_row["user_id"])

#         if suggest_employees:
#             suggest_employees.sort(key=lambda u: user_tasks_count.get(u, 0))
#             reassigned_to = suggest_employees[0]
#             suggestion = "Reassign to employee with fewer tasks"
#         else:
#             suggestion = "Extend timeline or add resource"


#     elif user_task_count > THRESHOLD:

#         reason = "Overloaded user"

#         suggest_employees = []

#         with open(skill_file, "r", encoding="utf-8") as f_skill:
#             skills = csv.DictReader(f_skill)

#             for skill_row in skills:
#                 if (
#                     skill_row["skill_id"] == data["required_skill"]
#                     and skill_row["user_id"] != original_assignee
#                 ):
#                     suggest_employees.append(skill_row["user_id"])

#         if suggest_employees:
#             suggest_employees.sort(key=lambda user: user_tasks_count.get(user, 0))
#             reassigned_to = suggest_employees[0]
#             suggestion = "Redistribute workload"


#     results_list.append({
#         "Task ID": task_id,
#         "Status": status,
#         "Original Assignee": original_assignee,
#         "Reassigned To": reassigned_to,
#         "Reason": reason,
#         "Suggestion": suggestion,
#     })

# print(results_list)

# def get_task_id(item):
#     try:
#         return int(item["Task ID"])
#     except:
#         return 0

# results_list.sort(key=get_task_id)

# user_input = json.dumps(results_list, indent=2)


# prompt = """
# You are a Project Manager AI. 
# TASK: Generate a CSV report from JSON input.
# OUTPUT: Return ONLY the raw CSV text.

# HEADER:
# task_id,status,original_assignee,reassigned_to,reason,suggestion
# """

# response = chat(
#     model="llama3.2",
#     messages=[
#         {"role": "system", "content": prompt},
#         {"role": "user", "content": user_input}
#     ]
# )

# ai_output = response.message.content

# ai_file = "ai_data_new.csv"

# with open(ai_file, "w", encoding="utf-8") as file:
#     file.write(ai_output)

# with open(ai_file, "r", encoding="utf-8") as f_read:
#     reader = csv.DictReader(f_read)
#     for row in reader:
#         print(row)













# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# users_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/res_users.csv"

# today = datetime.now().date()
# task_owner = {}
# all_assigned_users = []
# results_list = [] 

# with open(assign_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# user_capacity = {}
# with open(users_file, "r", encoding="utf-8") as file:
#     users = csv.DictReader(file)
#     for row in users:
#         user_capacity[row["id"]] = float(row.get("weekly_capacity", 0) or 0)

# user_total_hours = Counter()
# with open(task_file, "r", encoding="utf-8") as f:
#     tasks_data = list(csv.DictReader(f))
#     for row in tasks_data:
#         t_id = row["id"]
#         u_id = task_owner.get(t_id, "0")
#         est_h = float(row.get("estimated_hours", 0) or 0)
#         if u_id != "0":
#             user_total_hours[u_id] += est_h

# user_tasks_count = Counter(all_assigned_users)

# for row in tasks_data:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = row["id"]
#     deadline_str = row["date_deadline"]
#     progress = row["progress"]
#     required_skill = row.get("required_skill_id")
#     original_assignee = task_owner.get(task_id, "0")
    
#     if original_assignee in ["", "0", None]:
#         original_assignee = "0"

#     status = "ON_TIME"
#     # Check Deadline
#     if deadline_str and deadline_str.upper() != "NULL" and deadline_str.strip() != "":
#         deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
#         if today > deadline_date:
#             status = "DELAYED"

#     # Check Overload Logic: Total assigned hours vs Weekly Capacity
#     user_cap = user_capacity.get(original_assignee, 0)
#     user_load = user_total_hours.get(original_assignee, 0)
#     if original_assignee != "0" and user_load > user_cap:
#         status = "OVERLOADED"

#     reassigned_to = "0"
#     reason = "On schedule"
#     suggestion = "Task has time."

#     # Reassignment Logic
#     if original_assignee == "0" or status == "OVERLOADED" or user_tasks_count[original_assignee] >= 2:
#         suggest_employees = []
#         with open(skill_file, "r", encoding="utf-8") as f_skill:
#             skills = csv.DictReader(f_skill)
#             for skill_row in skills:
#                 cand_id = skill_row["user_id"]
#                 if skill_row["skill_id"] == required_skill and cand_id != original_assignee:
#                     # Only suggest if candidate has capacity
#                     if user_total_hours[cand_id] < user_capacity.get(cand_id, 0):
#                         suggest_employees.append(cand_id)

#         if suggest_employees:
#             reassigned_to = suggest_employees[0]
#             # Update counters
#             user_tasks_count[reassigned_to] += 1
#             if original_assignee != "0":
#                 user_tasks_count[original_assignee] -= 1
            
#             reason = "No assignee" if original_assignee == "0" else "Overloaded"
#             suggestion = f"Reassigned to {reassigned_to}"
#         else:
#             suggestion = "No skilled employee with capacity found"

#     results_list.append({
#         "Task ID": task_id,
#         "Status": status,
#         "Original Assignee": original_assignee,
#         "Reassigned To": reassigned_to, 
#         "Reason": reason,
#         "Suggestion": suggestion,
#     }) 

# results_list.sort(key=lambda x: int(x["Task ID"]) if x["Task ID"].isdigit() else 0)
# user_input = json.dumps(results_list, indent=2)



# print("USER INPUT:\n",user_input)

# # if results_list:
# #     keys = results_list[0].keys()
# #     with open(output_csv, "w", newline="") as f_output:
# #         writer = csv.DictWriter(f_output, fieldnames=keys)
# #         writer.writeheader()
# #         writer.writerows(results_list)
# #     print(f"File '{output_csv}' created successfully.\n")

# # print("Reading Data from Created CSV")
# # with open(output_csv, "r") as f_read:
# #     final_reader = csv.DictReader(f_read)
# #     for row in final_reader:
# #         print(f"Task {row['Task ID']} \nFrom: {row['Original Assignee']} To: {row['Reassigned To']}")


# prompt = """
# You are a Project Manager AI. 
# TASK: Generate a CSV report from JSON input.
# OUTPUT: Return ONLY the raw CSV text. No markdown backticks (```), no preamble, no chatter.

# [HEADER]
# task_id,status,original_assignee,reassigned_to,reason,suggestion

# [DATA NORMALIZATION]
# - task_id: Keep original.
# - status: Convert "On Time" to ON_TIME; convert "Late" to DELAYED.
# - original_assignee: If 0 or "No one assigned", treat as 0.
# - reassigned_to: Use provided integer; if null/none, use 0.

# [DETERMINISTIC LOGIC]
# 1. IF original_assignee == 0:
#    reason = "No assignee"
#    suggestion = "Assign task to available employee"
   
# 2. IF status == ON_TIME (and original_assignee != 0):
#    reason = "On schedule"
#    suggestion = "No change"
   
# 3. IF status == DELAYED (and original_assignee != 0):
#    IF reassigned_to != 0:
#       reason = "Overloaded"
#       suggestion = "Reassign to employee with fewer tasks"
#    ELSE:
#       reason = "Low Progress"
#       suggestion = "Add another resource or Extend Timeline"

# [CONSTRAINTS]
# - 6 columns exactly.
# - No duplicate rows.
# - No invented IDs.
# - No explanations.

# [FINAL OUTPUT]
# (Output CSV starting with header)
# """

# response = chat(
#     model = "llama3.2",
#     messages = [
#         {"role":"system","content":prompt,},
#         {"role":"user","content":user_input}]
# )
# ai_output = response.message.content

# ai_file = "ai_data_new.csv"

# with open(ai_file,"w",encoding="utf-8") as file:
#     file.write(ai_output)

# with open(ai_file, "r", encoding="utf-8") as f_read:
#     final_reader = csv.DictReader(f_read)
#     for row in final_reader:
#         print("\nROWS:\n",row)





















# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter


# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (2).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"


# today = datetime.now().date()
# task_owner = {}
# all_assigned_users = []
# results_list = [] 


# # Load assigned tasks
# with open(assign_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# print("ALL ASSIGNED USERS:\n", all_assigned_users)

# # Count users
# user_tasks_count = Counter(all_assigned_users)

# # Process tasks
# with open(task_file, "r", encoding="utf-8") as f:
#     tasks = list(csv.DictReader(f))

# for row in tasks:
#     # Skip if tasks is completed or need client approval pending
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = row["id"]
#     deadline_str = row["date_deadline"]
#     progress = row["progress"]
#     required_skill = row.get("required_skill_id")

#     # Normalize original assignee
#     original_assignee = task_owner.get(task_id, "0")
#     if original_assignee in ["", "0", None]:
#         original_assignee = "0"

#     user_task_count = user_tasks_count.get(original_assignee, 0)

#     status = "ON_TIME"
#     if deadline_str and deadline_str.upper() != "NULL":
#         try:
#             deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
#             if today > deadline_date:
#                 status = "DELAYED"
#         except ValueError:
#             # Handle cases where the date format might be wrong
#             status = "INVALID_DATE" 
#     else:
#         status = "NO_DEADLINE" # Or "ON_TIME" depending on your preference


#     reassigned_to = "0"
#     reason = "On schedule"
#     suggestion = "Task has time."

#     if original_assignee == "0" or user_task_count >= 2:
#         suggest_employees = []

#         with open(skill_file, "r",encoding="utf-8") as f_skill:
#             skills = csv.DictReader(f_skill)

#             for skill_row in skills:
#                 # Find someone with skill who isn't the current overloaded person
#                 if skill_row["skill_id"] == required_skill and skill_row["user_id"] != original_assignee:
#                     suggest_employees.append(skill_row["user_id"])

#         if suggest_employees:
#             f_employee = suggest_employees[0]
#             f_employee_load = user_tasks_count.get(f_employee,0)

#             if f_employee_load >= 2 and len(suggest_employees) > 1:
#                 reassigned_to = suggest_employees[1]
#             else:
#                 reassigned_to = f_employee

#             print("SUGGEST EMPLOYEES:\n", suggest_employees)

#             # Update counters and owner
#             user_tasks_count[reassigned_to] += 1
#             if original_assignee != "0":
#                 user_tasks_count[original_assignee] -= 1

#             task_owner[task_id] = reassigned_to

#             if original_assignee == "0":
#                 reason = "No assignee"
#                 suggestion = "Assign task to available employee"
#             else:
#                 reason = "Overloaded"
#                 suggestion = f"Reassigned to {reassigned_to}"
#         else:
#             suggestion = "No skilled employee found"

#     # Additional check for Low Progress on Delayed tasks
#     if status == "DELAYED" and reassigned_to == "0":
#         if progress and float(progress) <= 50:
#             reason = "Low Progress"
#             suggestion = "Add another resource or Extend Timeline."

#     results_list.append({
#         "Task ID": task_id,
#         "Status": status,
#         "Original Assignee": original_assignee,
#         "Reassigned To": reassigned_to, 
#         "Reason": reason,
#         "Suggestion": suggestion,
#     })

# # Final Sort by Task ID
# # results_list.sort(key=lambda x: int(x["Task ID"]))
# def get_task_id(item):
#     task_id_str = item["Task ID"]
#     if task_id_str == "" or task_id_str == None:
#         return 0
#     return int(task_id_str)

# results_list.sort(key=get_task_id)
# print("\nRESULTS LIST:\n",results_list)

# user_input = json.dumps(results_list, indent=2)

# print("USER INPUT:\n",user_input)

# # if results_list:
# #     keys = results_list[0].keys()
# #     with open(output_csv, "w", newline="") as f_output:
# #         writer = csv.DictWriter(f_output, fieldnames=keys)
# #         writer.writeheader()
# #         writer.writerows(results_list)
# #     print(f"File '{output_csv}' created successfully.\n")

# # print("Reading Data from Created CSV")
# # with open(output_csv, "r") as f_read:
# #     final_reader = csv.DictReader(f_read)
# #     for row in final_reader:
# #         print(f"Task {row['Task ID']} \nFrom: {row['Original Assignee']} To: {row['Reassigned To']}")


# prompt = """
# You are a Project Manager AI. 
# TASK: Generate a CSV report from JSON input.
# OUTPUT: Return ONLY the raw CSV text. No markdown backticks (```), no preamble, no chatter.

# [HEADER]
# task_id,status,original_assignee,reassigned_to,reason,suggestion

# [DATA NORMALIZATION]
# - task_id: Keep original.
# - status: Convert "On Time" to ON_TIME; convert "Late" to DELAYED.
# - original_assignee: If 0 or "No one assigned", treat as 0.
# - reassigned_to: Use provided integer; if null/none, use 0.

# [DETERMINISTIC LOGIC]
# 1. IF original_assignee == 0:
#    reason = "No assignee"
#    suggestion = "Assign task to available employee"
   
# 2. IF status == ON_TIME (and original_assignee != 0):
#    reason = "On schedule"
#    suggestion = "No change"
   
# 3. IF status == DELAYED (and original_assignee != 0):
#    IF reassigned_to != 0:
#       reason = "Overloaded"
#       suggestion = "Reassign to employee with fewer tasks"
#    ELSE:
#       reason = "Low Progress"
#       suggestion = "Add another resource or Extend Timeline"

# [CONSTRAINTS]
# - 6 columns exactly.
# - No duplicate rows.
# - No invented IDs.
# - No explanations.

# [FINAL OUTPUT]
# (Output CSV starting with header)
# """

# response = chat(
#     model = "llama3.2",
#     messages = [
#         {"role":"system","content":prompt,},
#         {"role":"user","content":user_input}]
# )
# ai_output = response.message.content

# ai_file = "ai_data_new.csv"

# with open(ai_file,"w",encoding="utf-8") as file:
#     file.write(ai_output)

# with open(ai_file, "r", encoding="utf-8") as f_read:
#     final_reader = csv.DictReader(f_read)
#     for row in final_reader:
#         print("\nROWS:\n",row)

























# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter


# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"


# today = datetime.now().date()
# task_owner = {}
# all_assigned_users = []
# results_list = [] 


# # Load assigned tasks
# with open(assign_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# # Count users
# user_tasks_count = Counter(all_assigned_users)


# # Process tasks
# with open(task_file, "r", encoding="utf-8") as f:
#     tasks = list(csv.DictReader(f))

# for row in tasks:
#     # Skip if tasks is completed or need client approval pending
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = row["id"]
#     deadline_str = row["date_deadline"]
#     progress = row["progress"]
#     required_skill = row.get("required_skill_id")

#     # Normalize original assignee
#     original_assignee = task_owner.get(task_id, "0")
#     if original_assignee in ["", "0", None]:
#         original_assignee = "0"

#     user_task_count = user_tasks_count.get(original_assignee, 0)

#     status = "ON_TIME"
#     if deadline_str:
#         deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
#         if today > deadline_date:
#             status = "DELAYED"

#     reassigned_to = "0"
#     reason = "On schedule"
#     suggestion = "Task has time."

#     if original_assignee == "0" or user_task_count >= 2:
#         suggest_employees = []

#         with open(skill_file, "r",encoding="utf-8") as f_skill:
#             skills = csv.DictReader(f_skill)

#             for skill_row in skills:
#                 # Find someone with skill who isn't the current overloaded person
#                 if skill_row["skill_id"] == required_skill and skill_row["user_id"] != original_assignee:
#                     suggest_employees.append(skill_row["user_id"])

#         if suggest_employees:
#             f_employee = suggest_employees[0]
#             f_employee_load = user_tasks_count.get(f_employee,0)

#             if f_employee_load >= 2 and len(suggest_employees) > 1:
#                 reassigned_to = suggest_employees[1]
#             else:
#                 reassigned_to = f_employee

#             # Update counters and owner
#             user_tasks_count[reassigned_to] += 1
#             if original_assignee != "0":
#                 user_tasks_count[original_assignee] -= 1

#             task_owner[task_id] = reassigned_to

#             if original_assignee == "0":
#                 reason = "No assignee"
#                 suggestion = "Assign task to available employee"
#             else:
#                 reason = "Overloaded"
#                 suggestion = f"Reassigned to {reassigned_to}"
#         else:
#             suggestion = "No skilled employee found"

#     # Additional check for Low Progress on Delayed tasks
#     if status == "DELAYED" and reassigned_to == "0":
#         if progress and float(progress) <= 50:
#             reason = "Low Progress"
#             suggestion = "Add another resource or Extend Timeline."

#     results_list.append({
#         "Task ID": task_id,
#         "Status": status,
#         "Original Assignee": original_assignee,
#         "Reassigned To": reassigned_to, 
#         "Reason": reason,
#         "Suggestion": suggestion,
#     })

# # Final Sort by Task ID
# # results_list.sort(key=lambda x: int(x["Task ID"]))
# def get_task_id(item):
#     task_id_str = item["Task ID"]
#     if task_id_str == "" or task_id_str == None:
#         return 0
#     return int(task_id_str)

# results_list.sort(key=get_task_id)
# print("\nRESULTS LIST:\n",results_list)

# user_input = json.dumps(results_list, indent=2)

# # if results_list:
# #     keys = results_list[0].keys()
# #     with open(output_csv, "w", newline="") as f_output:
# #         writer = csv.DictWriter(f_output, fieldnames=keys)
# #         writer.writeheader()
# #         writer.writerows(results_list)
# #     print(f"File '{output_csv}' created successfully.\n")

# # print("Reading Data from Created CSV")
# # with open(output_csv, "r") as f_read:
# #     final_reader = csv.DictReader(f_read)
# #     for row in final_reader:
# #         print(f"Task {row['Task ID']} \nFrom: {row['Original Assignee']} To: {row['Reassigned To']}")


# prompt = """
# You are a Project Manager AI. 
# TASK: Generate a CSV report from JSON input.
# OUTPUT: Return ONLY the raw CSV text. No markdown backticks (```), no preamble, no chatter.

# [HEADER]
# task_id,status,original_assignee,reassigned_to,reason,suggestion

# [DATA NORMALIZATION]
# - task_id: Keep original.
# - status: Convert "On Time" to ON_TIME; convert "Late" to DELAYED.
# - original_assignee: If 0 or "No one assigned", treat as 0.
# - reassigned_to: Use provided integer; if null/none, use 0.

# [DETERMINISTIC LOGIC]
# 1. IF original_assignee == 0:
#    reason = "No assignee"
#    suggestion = "Assign task to available employee"
   
# 2. IF status == ON_TIME (and original_assignee != 0):
#    reason = "On schedule"
#    suggestion = "No change"
   
# 3. IF status == DELAYED (and original_assignee != 0):
#    IF reassigned_to != 0:
#       reason = "Overloaded"
#       suggestion = "Reassign to employee with fewer tasks"
#    ELSE:
#       reason = "Low Progress"
#       suggestion = "Add another resource or Extend Timeline"

# [CONSTRAINTS]
# - 6 columns exactly.
# - No duplicate rows.
# - No invented IDs.
# - No explanations.

# [FINAL OUTPUT]
# (Output CSV starting with header)
# """

# response = chat(
#     model = "llama3.2",
#     messages = [
#         {"role":"system","content":prompt,},
#         {"role":"user","content":user_input}]
# )
# ai_output = response.message.content

# ai_file = "ai_data_new.csv"

# with open(ai_file,"w",encoding="utf-8") as file:
#     file.write(ai_output)

# with open(ai_file, "r", encoding="utf-8") as f_read:
#     final_reader = csv.DictReader(f_read)
#     for row in final_reader:
#         print("\nROWS:\n",row)
























# import pandas as pd

# tasks_path = "/home/lavanya/Desktop/Lavanya/ai/project_task.csv"
# df = pd.read_csv(tasks_path)

# columns = [
#     'id',
#     'name',
#     'project_id',
#     'date_assign',
#     'date_deadline',
#     'date_end',
#     'estimated_hours',
#     'effective_hours',
#     'required_skill_id',
#     'progress',
#     'is_closed',
#     'is_blocked'
# ]

# tasks = df[columns].copy()

# tasks['date_deadline'] = pd.to_datetime(tasks['date_deadline'])
# tasks['date_end'] = pd.to_datetime(tasks['date_end'])

# tasks = tasks.dropna(subset=['date_deadline'])

# def check_task_status(task):
#     now = pd.Timestamp.now()

#     if task['is_closed'] == True:
#         if pd.notna(task['date_end']) <= task['date_deadline']:
#             return "On Time"
#         else:
#             return "Completed Late"

#     if now > task['date_deadline']:
#         return "Delayed"

#     return "not Delayed"


# for index, row in tasks.iterrows():
#     status = check_task_status(row)

#     print("TASK ID :", row['id'])
#     print("TASK NAME :", row['name'])
#     print("STATUS :", status)
    # print("----------------------")








# import csv
# from datetime import datetime

# task_csv = "/home/lavanya/Desktop/Lavanya/ai/project_task (1).csv"
# today = datetime.now().date()

# with open(task_csv, "r", encoding="utf-8") as task_file:
#     reader = csv.DictReader(task_file)
#     all_tasks = list(reader)

# for row in all_tasks:
#     if row["state"] == "completed" or row["state"] == "client_approval_pending":
#         continue
    
#     deadline_str = row["date_deadline"]
#     deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()

#     if today < deadline_date:
#         print(f"Task: {row['name']} have time")
#     else:
#         print(f"Task: {row['name']} overdue")






# # COLUMNS:
# task_columns = [
# "id",
# "project_id",
# "name",
# "date_deadline",
# "estimated_hours",
# "required_skill_id",
# "access_token",
# "partner_email",
# "state",
# "task_time"]

# project_columns = [
# "id",
# "name",
# "date_start",
# "partner_email",
# "project_status"]

# employee_columns = [
# "id",
# "name",
# "job_title",
# "work_email"]








# all_assigned_users = []
# with open(assign_file, "r") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# user_task_counts = Counter(all_assigned_users)

# for user_id, count in user_task_counts.items():
#     if count >= 2:
#         print(f"yess (User {user_id} has {count} tasks)")


#         print(f"Task {task_id} :\n  status: {status}\n  Assigned to: {assigned_to}\n  Reason: {reason}\n  Suggestion: {suggestion}")








# import csv
# from datetime import datetime
# from collections import Counter

# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []

# with open(assign_file, "r") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# user_tasks_count = Counter(all_assigned_users)

# with open(task_file, "r") as f:
#     tasks = csv.DictReader(f)
#     for row in tasks:
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = row["id"]
#         deadline_str = row["date_deadline"]
#         progress = float(row.get("progress", 0) or 0) # Handle empty/null progress
#         assigned_to = task_owner.get(task_id, "No one assigned")
        
#         current_user_task_count = user_tasks_count.get(assigned_to, 0)

#         reason = ""
#         suggestion = ""
#         status = "Unknown"

#         if deadline_str:
#             deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
#             status = "On Time" if today <= deadline_date else "Late"

#         if status == "Late":
#             if assigned_to == "No one assigned":
#                 reason = "No Employee Assigned"
#                 suggestion = "Assign task to Employee"
#             elif progress < 50:
#                 reason = "Low Progress"
#                 suggestion = "Add another resource."
#         else:
#             reason = "Within deadline"
#             suggestion = "Task has time."

#         print(f"Task {task_id}:")
#         print(f"  Status: {status}")
#         print(f"  Assigned to: {assigned_to} (Total User Tasks: {current_user_task_count})")
#         print(f"  Reason: {reason}")
#         print(f"  Suggestion: {suggestion}\n")





# ================================================================================================

# ---------------------------------CODE WITH FUNCTION --------------------------------------------

# ================================================================================================


# import csv
# from datetime import datetime
# from collections import Counter

# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"

# today = datetime.now().date()


# def load_task_owners(assign_file):
#     task_owner = {}
#     all_assigned_users = []

#     with open(assign_file, "r") as f:
#         reader = csv.DictReader(f)
#         for row in reader:
#             task_owner[row["task_id"]] = row["user_id"]
#             all_assigned_users.append(row["user_id"])

#     user_tasks_count = Counter(all_assigned_users)
#     return task_owner, user_tasks_count


# def get_status(deadline_str, today):
#     if deadline_str:
#         deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
#         if today <= deadline_date:
#             return "On Time"
#         else:
#             return "Late"
#     return "No Deadline"


# def get_skill_suggestions(required_skill):
#     suggest_employees = []

#     with open(skill_file, "r", encoding="utf-8") as f:
#         skills = csv.DictReader(f)
#         for skill_row in skills:
#             if skill_row["skill_id"] == required_skill:
#                 suggest_employees.append(skill_row["user_id"])

#     return suggest_employees


# def process_tasks(task_file, task_owner, user_tasks_count):
#     with open(task_file, "r") as f:
#         tasks = csv.DictReader(f)

#         for row in tasks:
#             if row["state"] == "completed" or row["state"] == "client_approval_pending":
#                 continue

#             task_id = row["id"]
#             deadline_str = row["date_deadline"]
#             progress = row["progress"]
#             assigned_to = task_owner.get(task_id, "No one assigned")

#             reason = ""
#             suggestion = ""
#             user_task_count = user_tasks_count.get(assigned_to, 0)

#             status = get_status(deadline_str, today)

#             if status == "On Time":
#                 reason = "within deadline"
#                 suggestion = "Task has time."

#             elif status == "Late":

#                 if assigned_to == "No one assigned":
#                     reason = "No Employee Assigned"
#                     suggestion = "Assign task to Employee"

#                 elif progress:
#                     progress_val = float(progress)

#                     if progress_val <= 50:
#                         reason = "Low Progress"
#                         suggestion = "Add another resource."

#                         if user_task_count >= 2:
#                             required_skill = row.get("required_skill_id")
#                             suggest_employees = get_skill_suggestions(required_skill)

#                             if suggest_employees:
#                                 suggestion += f"\n  user suggestions: {suggest_employees}"
#                             else:
#                                 suggestion += " No user with same skill"

#             print(f"\nTask {task_id} :\n  status: {status}\n  Assigned to: {assigned_to}\n  Reason: {reason}\n  Suggestion: {suggestion}\n  Counts: {user_task_count}")


# task_owner, user_tasks_count = load_task_owners(assign_file)
# process_tasks(task_file, task_owner, user_tasks_count)





















# ===========================================================================================

#------------------------------- REFINED CODE -----------------------------------------------

# ===========================================================================================


# import csv
# from datetime import datetime
# from collections import Counter

# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"

# today = datetime.now().date()


# task_owner = {}
# all_assigned_users = []

# with open(assign_file, "r") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# user_tasks_count = Counter(all_assigned_users)

# skill_map = {}

# with open(skill_file, "r", encoding="utf-8") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         skill_map.setdefault(row["skill_id"], []).append(row["user_id"])


# with open(task_file, "r") as f:
#     tasks = csv.DictReader(f)

#     for row in tasks:
#         state = row["state"]

#         if state in ["completed", "client_approval_pending"]:
#             continue

#         task_id = row["id"]
#         deadline_str = row["date_deadline"]
#         progress = row["progress"]
#         required_skill = row.get("required_skill_id")

#         assigned_to = task_owner.get(task_id, "No one assigned")
#         user_task_count = user_tasks_count.get(assigned_to, 0)


#         status = "No Deadline"

#         if deadline_str:
#             deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
#             status = "On Time" if today <= deadline_date else "Late"

#         reason = "N/A"
#         suggestion = "N/A"


#         if status == "On Time":
#             reason = "Within deadline"
#             suggestion = "Task has sufficient time"

#         elif status == "Late":

#             if assigned_to == "No one assigned":
#                 reason = "No Employee Assigned"
#                 suggestion = "Assign task to an employee"

#             elif progress:
#                 progress_val = float(progress)

#                 if progress_val <= 50:
#                     reason = "Low Progress"
#                     suggestion = "Consider adding another resource"

#                     if user_task_count >= 2:
#                         suggested_users = skill_map.get(required_skill, [])

#                         if suggested_users:
#                             suggestion += f"\n  Suggested users: {suggested_users}"
#                         else:
#                             suggestion += "\n  No users found with required skill"

#         print(
#             f"\nTask {task_id}:\n"
#             f"  Status: {status}\n"
#             f"  Assigned to: {assigned_to}\n"
#             f"  Reason: {reason}\n"
#             f"  Suggestion: {suggestion}\n"
#             f"  Task Count: {user_task_count}"
#         )
















# import csv
# from datetime import datetime
# from collections import Counter

# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []

# # ---------------- LOAD ASSIGNMENTS ----------------
# with open(assign_file, "r") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# user_tasks_count = Counter(all_assigned_users)

# # ---------------- LOAD SKILLS (OPTIMIZED) ----------------
# skill_map = {}

# with open(skill_file, "r", encoding="utf-8") as f:
#     skills = csv.DictReader(f)
#     for row in skills:
#         skill_map.setdefault(row["skill_id"], []).append(row["user_id"])

# # ---------------- PROCESS TASKS ----------------
# with open(task_file, "r") as f:
#     tasks = list(csv.DictReader(f))   # convert to list for reuse

# for row in tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = row["id"]
#     deadline_str = row["date_deadline"]
#     progress = row["progress"]
#     assigned_to = task_owner.get(task_id, "No one assigned")
#     required_skill = row.get("required_skill_id")

#     reason = ""
#     suggestion = ""
#     user_task_count = user_tasks_count.get(assigned_to, 0)

#     # ---------------- DEADLINE CHECK ----------------
#     if deadline_str:
#         deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
#         status = "On Time" if today <= deadline_date else "Late"
#     else:
#         status = "No Deadline"

#     # ---------------- LOGIC ----------------
#     if status == "On Time":
#         reason = "within deadline"
#         suggestion = "Task has time."

#     elif status == "Late":

#         if assigned_to == "No one assigned":
#             reason = "No Employee Assigned"
#             suggestion = "Assign task to Employee"

#         elif progress:
#             if float(progress) <= 50:
#                 reason = "Low Progress"
#                 suggestion = "Add another resource."

#                 if user_task_count >= 2:
#                     suggest_employees = [
#                         user for user in skill_map.get(required_skill, [])
#                         if user != assigned_to
#                     ]

#                     if suggest_employees:
#                         # --------- FIND BEST USER (LEAST TASKS) ----------
#                         best_user = None
#                         min_task_count = float("inf")

#                         for user in suggest_employees:
#                             count = user_tasks_count.get(user, 0)

#                             if count < min_task_count:
#                                 min_task_count = count
#                                 best_user = user

#                         suggestion += f"\n  Suggested user for reassignment: {best_user}"

#                         # OPTIONAL: simulate reassignment
#                         task_owner[task_id] = best_user
#                         user_tasks_count[best_user] += 1

#                     else:
#                         suggestion += "\n  No user with same skill"

#     # ---------------- OUTPUT ----------------
#     print(f"Task {task_id} :")
#     print(f"  Status       : {status}")
#     print(f"  Assigned to  : {assigned_to}")
#     print(f"  Reason       : {reason}")
#     print(f"  Suggestion   : {suggestion}")
#     print(f"  Task Count   : {user_task_count}")
#     print("-" * 50)








# import csv
# from datetime import datetime
# from collections import Counter


# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"

# today = datetime.now().date()

# task_owner = {}
# all_assigned_users = []

# with open(assign_file, "r") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

#         # for user_id, count in user_tasks_count.items():
#         #     if count >= 2:
#         #         print(f"User : {user_id}  Count : {count}")

# user_tasks_count = Counter(all_assigned_users)

# employee_skills = {}


# with open(task_file, "r") as f:
#     tasks = csv.DictReader(f)
#     for row in tasks:
#         suggest_emp_hours = []

#         if row["state"] == "completed" or row["state"] == "client_approval_pending":
#             continue

#         task_id = row["id"]
#         deadline_str = row["date_deadline"]
#         estimated_hours = row["estimated_hours"]
#         # required_skill = row["required_skill_id"]
#         progress = row["progress"]
#         # is_blocked = row["is_blocked"]
#         assigned_to = task_owner.get(task_id, "No one assigned")
        
#         reason = ""
#         suggestion = ""
#         user_task_count = user_tasks_count.get(assigned_to,0)

#         if deadline_str:
#             deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()

#             if today <= deadline_date:
#                 status = "On Time"
#             else:
#                 status = "Late"

#         if status == "On Time":
#             reason = "within deadline"
#             suggestion = "Task has time."

#         elif status == "Late":

#             if assigned_to == "No one assigned":
#                 reason = "No Employee Assigned"
#                 suggestion = "Assign task to Employee"

#             # elif is_blocked == "True":
#             #     reason = "Task Blocked"
#             #     suggestion = "Blocked task. Reassign or Extend Timeline."

#             elif progress:
#                 # progress_val = float(progress)
#                 if float(progress) <= 50:
#                     reason = "Low Progress"
#                     suggestion = "Add another resource."
#                     if user_task_count >= 2:
#                         required_skill = row.get("required_skill_id")
#                         suggest_employees = []

#                         with open(skill_file,"r",encoding="utf-8") as f:
#                             skills = csv.DictReader(f)

#                             for skill_row in skills:
#                                 if skill_row["skill_id"] == required_skill and skill_row["user_id"] != assigned_to:
#                                     suggest_employees.append(skill_row["user_id"])
#                         if suggest_employees:
#                             hours_val = float(estimated_hours) if estimated_hours else 0.0
#                             suggest_emp_hours.append(hours_val)
#                         else:
#                             print("[ERROR]: Getting some error.")

#                         if suggest_emp_hours:
#                             min_suggest_emp_hours = min(suggest_emp_hours)

#                         if suggest_employees:
#                             suggestion += f"\n  user suggestions: {suggest_employees}"
#                             # print("TASK ID :",task_id)
#                             # print("REQUIRED SKILL :",required_skill)
#                             # print("ESTIMATED HOURS:",estimated_hours)
#                             # print("SUGGESTED EMPLOYEES :",suggest_employees)

#                             # all_estimated_hours.append(float(estimated_hours))
#                             # min_estimated_hour = min(all_estimated_hours)
#                             # print(min_estimated_hour)
                            

#                         else:
#                             suggestion += "No user with same skill"
                        
# # current_min = min(suggest_emp_hours) if suggest_emp_hours else "Empty List"
#         print(f"Task {task_id} :\n  status: {status}\n  Assigned to: {assigned_to}\n  Reason: {reason}\n  Suggestion: {suggestion}\n  Counts: {user_task_count}\n")














# import csv
# from datetime import datetime
# from collections import Counter

# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"

# today = datetime.now().date()
# task_data = []

# task_owner = {}
# all_assigned_users = []

# with open(assign_file, "r") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# user_tasks_count = Counter(all_assigned_users)


# employee_skills = {}

# with open(skill_file, "r", encoding="utf-8") as f:
#     skills = csv.DictReader(f)
#     for row in skills:
#         user_id = row["user_id"]
#         skill_id = row["skill_id"]

#         if user_id not in employee_skills:
#             employee_skills[user_id] = []

#         employee_skills[user_id].append(skill_id)


# with open(task_file, "r") as f:
#     tasks = csv.DictReader(f)

#     for row in tasks:

#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         suggest_employees = []

#         task_id = row["id"]
#         deadline_str = row["date_deadline"]
#         estimated_hours = row.get("estimated_hours")
#         required_skill = row.get("required_skill_id")
#         progress = row.get("progress")

#         assigned_to = task_owner.get(task_id, "No one assigned")
#         user_task_count = user_tasks_count.get(assigned_to, 0)

#         reason = ""
#         actions = []

#         if deadline_str:
#             deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()

#             if today <= deadline_date:
#                 status = "On Time"
#             else:
#                 status = "Late"
#         else:
#             status = "No Deadline"

#         progress_val = float(progress) if progress else 0

#         if status == "Late":

#             if assigned_to == "No one assigned":
#                 reason = "No Employee Assigned"
#                 actions.append("Assign employee")

#             elif user_task_count >= 3:
#                 reason = "Overloaded Employee"
#                 actions.append("Reassign task")

#             elif progress_val <= 50:
#                 reason = "Low Progress"
#                 actions.append("Add another resource")
#                 actions.append("Extend timeline")

#                 # find employees with same skill
#                 for user_id, skill_list in employee_skills.items():
#                     if required_skill in skill_list and user_id != assigned_to:
#                         if user_tasks_count.get(user_id, 0) < 2:
#                             suggest_employees.append(user_id)

#                 if suggest_employees:
#                     actions.append(f"Reassign to {suggest_employees[0]}")

#             else:
#                 reason = "Needs Review"
#                 actions.append("Manual check")

#         else:
#             reason = "Within Deadline"
#             actions.append("No action needed")

#         task_data.append({
#             "task_id": task_id,
#             "status": status,
#             "assigned_to": assigned_to,
#             "required_skill": required_skill,
#             "progress": progress_val,
#             "user_task_count": user_task_count,
#             "reason": reason,
#             "actions": actions
#         })


# overloaded_users = [user_id for user_id, task_count in user_tasks_count.items() if task_count >= 3]

# for overloaded_user in overloaded_users:
#     print(f"\n[OVERLOADED] User {overloaded_user} → Redistributing tasks")

#     for task in task_data:
#         if task["assigned_to"] == overloaded_user:

#             required_skill = task["required_skill"]

#             for candidate_user, skill_list in employee_skills.items():
#                 if required_skill in skill_list and user_tasks_count.get(candidate_user, 0) < 2:

#                     print(f"Reassign Task {task['task_id']} → {candidate_user}")

#                     task["assigned_to"] = candidate_user
#                     user_tasks_count[candidate_user] += 1
#                     user_tasks_count[overloaded_user] -= 1
#                     break


# underutilized_users = [user_id for user_id, task_count in user_tasks_count.items() if task_count <= 1]

# unassigned_tasks = [task for task in task_data if task["assigned_to"] == "No one assigned"]

# for task in unassigned_tasks:
#     for available_user in underutilized_users:

#         if task["required_skill"] in employee_skills.get(available_user, []):

#             print(f"Assign Task {task['task_id']} → {available_user}")

#             task["assigned_to"] = available_user
#             user_tasks_count[available_user] += 1
#             break


# for task in task_data:
#     print(task)
















# import csv
# from datetime import datetime
# from collections import Counter

# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"

# today = datetime.now().date()
# task_owner = {}
# all_assigned_users = []
# task_data = []
# employee_skills = {}


# # Load assigned tasks
# with open(assign_file, "r") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# user_tasks_count = Counter(all_assigned_users)

# # Process tasks
# with open(task_file, "r") as f:
#     tasks = csv.DictReader(f)
#     for row in tasks:
#         if row["state"] == "completed" or row["state"] == "client_approval_pending":
#             continue
        
#         suggest_emp_hours = []
#         suggest_employees = []
#         actions = []

#         task_id = row["id"]
#         deadline_str = row["date_deadline"]
#         estimated_hours = row["estimated_hours"]
#         progress = row["progress"]
        
#         assigned_to = task_owner.get(task_id, "No one assigned")
#         reason = ""
#         suggestion = ""
#         user_task_count = user_tasks_count.get(assigned_to, 0)
        
#         if deadline_str:
#             deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
#             if today <= deadline_date:
#                 status = "On Time"
#             else:
#                 status = "Late"

#         progress_val = float(progress) if progress else 0

#         if status == "On Time":
#             reason = "within deadline"
#             suggestion = "Task has time."
#         elif status == "Late":
#             if assigned_to == "No one assigned":
#                 reason = "No Employee Assigned"
#                 suggestion = "Assign task to Employee"
#             elif progress:
#                 if float(progress) <= 50:
#                     reason = "Low Progress"
#                     suggestion = "Add another resource."
                        
#         if user_task_count >= 2:
#             required_skill = row.get("required_skill_id")
#             suggest_employees = []
            
#             with open(skill_file, "r", encoding="utf-8") as f_skill:
#                 skills = csv.DictReader(f_skill)
#                 for skill_row in skills:
#                     if skill_row["skill_id"] == required_skill and skill_row["user_id"] != assigned_to:
#                         suggest_employees.append(skill_row["user_id"])
            
#             if suggest_employees:
#                 suggestion += f"\n user suggestions: {suggest_employees}"
#                 suggestion += f"\n  Assigned To: {new_user}"

#                         # print("TASK ID :",task_id)
#                         # print("REQUIRED SKILL :",required_skill)
#                         # print("ESTIMATED HOURS:",estimated_hours)
#                         # print("SUGGESTED EMPLOYEES :",suggest_employees))

#                         # Updates task_owner and users_task_count
#                 if assigned_to != "No one assigned":
#                     print("SOMETHING")
#                     user_tasks_count[assigned_to] -= 1


#                 user_tasks_count[new_user] += 1
#                 task_owner[task_id] = new_user
#                 user_id = task_owner.get("user_id")

#                 print(f"TASK {task_id} REASSIGNED: {assigned_to} to {new_user}")


#             else:
#                 suggestion += "\n  No employee found with the same skill"

#         print(f"Task {task_id} :\n status: {status}\n Assigned to: {assigned_to}\n Reason: {reason}\n Suggestion: {suggestion}\n Counts: {user_task_count}\n")


















# import csv
# from datetime import datetime
# from collections import Counter

# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"

# today = datetime.now().date()
# task_owner = {}
# all_assigned_users = []
# task_data = []
# employee_skills = {}

# # Load assigned tasks
# with open(assign_file, "r") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# user_tasks_count = Counter(all_assigned_users)

# # Process tasks
# with open(task_file, "r") as f:
#     tasks = csv.DictReader(f)
#     for row in tasks:
#         if row["state"] == "completed" or row["state"] == "client_approval_pending":
#             continue
        
#         suggest_emp_hours = []
#         suggest_employees = []
#         actions = []

#         task_id = row["id"]
#         deadline_str = row["date_deadline"]
#         estimated_hours = row["estimated_hours"]
#         progress = row["progress"]
        
#         assigned_to = task_owner.get(task_id, "No one assigned")
#         reason = ""
#         suggestion = ""
#         user_task_count = user_tasks_count.get(assigned_to, 0)
        
#         status = "Unknown"
#         if deadline_str:
#             deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
#             if today <= deadline_date:
#                 status = "On Time"
#             else:
#                 status = "Late"

#         progress_val = float(progress) if progress else 0

#         if status == "On Time":
#             reason = "within deadline"
#             suggestion = "Task has time."
#         elif status == "Late":
#             if assigned_to == "No one assigned":
#                 reason = "No Employee Assigned"
#                 suggestion = "Assign task to Employee"
#             elif progress:
#                 if float(progress) <= 50:
#                     reason = "Low Progress"
#                     suggestion = "Add another resource."
                        
#         if user_task_count >= 2:
#             required_skill = row.get("required_skill_id")
#             suggest_employees = []
            
#             with open(skill_file, "r", encoding="utf-8") as f_skill:
#                 skills = csv.DictReader(f_skill)
#                 for skill_row in skills:
#                     if skill_row["skill_id"] == required_skill and skill_row["user_id"] != assigned_to:
#                         suggest_employees.append(skill_row["user_id"])
            
#             if suggest_employees:
#                 new_user = suggest_employees[0] # Assuming first suggestion is chosen
#                 suggestion += f"\n user suggestions: {suggest_employees}"
#                 suggestion += f"\n Assigned To: {new_user}"

#                 # Updates task_owner and users_task_count
#                 if assigned_to != "No one assigned":
#                     user_tasks_count[assigned_to] -= 1

#                 user_tasks_count[new_user] += 1
#                 task_owner[task_id] = new_user
                
#                 print(f"TASK {task_id} REASSIGNED: {assigned_to} to {new_user}")
#             else:
#                 suggestion += "\n No employee found with the same skill"

#         print(f"Task {task_id} :\n status: {status}\n Assigned to: {assigned_to}\n Reason: {reason}\n Suggestion: {suggestion}\n Counts: {user_task_count}\n")




















# import csv
# from datetime import datetime
# from collections import Counter

# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# output_csv = "task_analysis_results.csv"

# today = datetime.now().date()
# task_owner = {}
# all_assigned_users = []
# results_list = [] 

# # Load assigned tasks
# with open(assign_file, "r") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# user_tasks_count = Counter(all_assigned_users)

# # Process tasks
# with open(task_file, "r") as f:
#     tasks = csv.DictReader(f)
#     for row in tasks:
#         if row["state"] == "completed" or row["state"] == "client_approval_pending":
#             continue
        
#         task_id = row["id"]
#         deadline_str = row["date_deadline"]
#         progress = row["progress"]
#         original_assignee = task_owner.get(task_id, "No one assigned")
#         user_task_count = user_tasks_count.get(original_assignee, 0)
        
#         status = "Unknown"
#         reason = ""
#         suggestion = ""
#         reassigned_to = "N/A" # Default if no reassignment happens

#         if deadline_str:
#             deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
#             status = "On Time" if today <= deadline_date else "Late"

#         if status == "On Time":
#             reason = "within deadline"
#             suggestion = "Task has time."
#         elif status == "Late":
#             if original_assignee == "No one assigned":
#                 reason = "No Employee Assigned"
#                 suggestion = "Assign task to Employee"
#             elif progress and float(progress) <= 50:
#                 reason = "Low Progress"
#                 suggestion = "Add another resource."
                        
#         if user_task_count >= 2:
#             required_skill = row.get("required_skill_id")
#             suggest_employees = []
#             with open(skill_file, "r", encoding="utf-8") as f_skill:
#                 skills = csv.DictReader(f_skill)
#                 for skill_row in skills:
#                     if skill_row["skill_id"] == required_skill and skill_row["user_id"] != original_assignee:
#                         suggest_employees.append(skill_row["user_id"])
            
#             if suggest_employees:
#                 reassigned_to = suggest_employees[0]
#                 suggestion += f" | Suggestions: {suggest_employees}"
                
#                 # Update counters
#                 if original_assignee != "No one assigned":
#                     user_tasks_count[original_assignee] -= 1
#                 user_tasks_count[reassigned_to] += 1
#                 task_owner[task_id] = reassigned_to
#             else:
#                 suggestion += " | No employee found with same skill"

#         # SAVE TO VARIABLE WITH NEW COLUMN
#         results_list.append({
#             "Task ID": task_id,
#             "Status": status,
#             "Original Assignee": original_assignee,
#             "Reassigned To": reassigned_to, # NEW COLUMN
#             "Reason": reason,
#             "Suggestion": suggestion.replace("\n", " "),
#             "Original User Task Count": user_task_count
#         })

# # CREATE THE CSV FILE
# if results_list:
#     keys = results_list[0].keys()
#     with open(output_csv, "w", newline="") as f_output:
#         writer = csv.DictWriter(f_output, fieldnames=keys)
#         writer.writeheader()
#         writer.writerows(results_list)
#     print(f"File '{output_csv}' created successfully.\n")

# # READ THE CSV FILE BACK
# print("--- Reading Data from Created CSV ---")
# with open(output_csv, "r") as f_read:
#     final_reader = csv.DictReader(f_read)
#     for row in final_reader:
#         print(f"Task {row['Task ID']} | From: {row['Original Assignee']} -> To: {row['Reassigned To']}")











# import csv
# import json
# import ollama  # Import the local Ollama library
# from datetime import datetime
# from collections import Counter, defaultdict

# # Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"

# def get_ai_recommendation(task_info, candidates):
#     """Uses local Ollama to decide on reassignment."""
#     if not candidates:
#         return {"reassign": False, "new_user": None, "reason": "No candidates available"}
    
#     prompt = f"""
#     Task Details: {task_info}
#     Available Employees (ID: current_load): {candidates}
    
#     Decide:
#     1. Should this task be reassigned?
#     2. Who is the best person for it (lowest load/best fit)?
#     3. What is the reason?
    
#     Return ONLY a JSON object with this structure: 
#     {{"reassign": boolean, "new_user": "id", "reason": "text"}}
#     """
    
#     try:
#         # Using ollama.chat with structured output format
#         response = ollama.chat(
#             model='llama3', # Or your preferred local model like 'mistral'
#             messages=[{'role': 'user', 'content': prompt}],
#             format='json'  # Forces the model to respond in JSON
#         )
#         return json.loads(response['message']['content'])
#     except Exception as e:
#         return {"reassign": False, "new_user": None, "reason": f"Ollama Error: {str(e)}"}

# # --- Data Loading Logic ---
# today = datetime.now().date()
# task_owner = {}
# all_assigned_users = []

# # Load current assignments
# with open(assign_file, "r") as f:
#     for row in csv.DictReader(f):
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# user_tasks_count = Counter(all_assigned_users)

# # Load skills into a map {skill_id: [user_ids]}
# skill_map = defaultdict(list)
# with open(skill_file, "r", encoding="utf-8") as f:
#     for row in csv.DictReader(f):
#         skill_map[row["skill_id"]].append(row["user_id"])

# # --- Main Processing Loop ---
# task_data = []
# with open(task_file, "r") as f:
#     tasks = list(csv.DictReader(f))

# for row in tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = row["id"]
#     req_skill = row.get("required_skill_id")
#     assigned_to = task_owner.get(task_id, "No one assigned")
#     user_task_count = user_tasks_count.get(assigned_to, 0)
    
#     # Check deadline
#     status = "Unknown"
#     deadline_str = row.get("date_deadline")
#     if deadline_str:
#         deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
#         status = "On Time" if today <= deadline_date else "Late"

#     reassigned_user = assigned_to
#     reason = "Late" if status == "Late" else "Within deadline"
#     suggestion = ""

#     # Reassignment check
#     if status == "Late" or user_task_count >= 2:
#         potential_ids = skill_map.get(req_skill, [])
#         candidates = {u: user_tasks_count[u] for u in potential_ids if u != assigned_to}
        
#         ai_decision = get_ai_recommendation(row, candidates)
        
#         if ai_decision.get('reassign') and ai_decision.get('new_user'):
#             new_user = ai_decision['new_user']
#             suggestion = ai_decision['reason']
            
#             # Update workload counts
#             if assigned_to != "No one assigned":
#                 user_tasks_count[assigned_to] -= 1
#             user_tasks_count[new_user] += 1
#             task_owner[task_id] = new_user
#             reassigned_user = new_user

#     task_data.append({
#         "Task": task_id,
#         "Status": status,
#         "Assigned_to": reassigned_user,
#         "Reason": reason,
#         "Suggest": suggestion,
#         "Counts": user_tasks_count.get(reassigned_user, 0),
#     })

# # --- Export ---
# if task_data:
#     keys = task_data[0].keys()
#     with open("ollama_data.csv", "w", newline="") as output_file:
#         writer = csv.DictWriter(output_file, fieldnames=keys)
#         writer.writeheader()
#         writer.writerows(task_data)
#     print("\nSuccessfully processed tasks with local Ollama.")





# import csv
# import json
# import ollama
# from datetime import datetime
# from collections import Counter, defaultdict

# TASK_DATA_SOURCE = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# ASSIGNMENT_RELATION_SOURCE = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# EMPLOYEE_SKILLS_SOURCE = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"

# TODAY_DATE = datetime.now().date()

# def get_ai_manager_decision(task_details, candidate_pool):
#     decision_prompt = f"""
#     ### Context
#     - Task ID: {task_details['id']} | Status: {task_details['status']} | Progress: {task_details['progress']}%
#     - Current Assignee: {task_details['current_user']}
#     - Required Skill: {task_details['skill_needed']}
    
#     ### Available Backup Employees (Skill Match & Current Task Load)
#     {json.dumps(candidate_pool)}

#     ### AI Logic Rules:
#     1. Case 1 (Delay): If Late & progress < 50%, find a replacement.
#     2. Case 2 (Overload): If current assignee has > 2 tasks, reassign to an idle resource (0 tasks).
#     3. Case 3 (Underutilized): Prioritize employees with 0 tasks.

#     Return ONLY a JSON object: {{"reassign": true, "new_user": "ID", "reason": "Explain Case 1, 2, or 3"}}
#     """
    
#     ai_response = ollama.chat(
#         model="llama3.2",
#         format="json",
#         messages=[
#             {"role": "system", "content": "You are an AI Project Manager. Respond only in JSON."},
#             {"role": "user", "content": decision_prompt}
#         ]
#     )
#     return json.loads(ai_response["message"]["content"])

# task_to_user_map = {}
# all_active_assignments = []

# with open(ASSIGNMENT_RELATION_SOURCE, "r") as file:
#     for row in csv.DictReader(file):
#         task_to_user_map[row["task_id"]] = row["user_id"]
#         all_active_assignments.append(row["user_id"])

# employee_workload_counts = Counter(all_active_assignments)

# skill_to_employee_map = defaultdict(list)
# with open(EMPLOYEE_SKILLS_SOURCE, "r") as file:
#     for row in csv.DictReader(file):
#         skill_to_employee_map[row["skill_id"]].append(row["user_id"])

# processed_task_results = []

# with open(TASK_DATA_SOURCE, "r") as file:
#     all_tasks = csv.DictReader(file)

#     for task in all_tasks:
#         if task["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = task["id"]
#         current_user = task_to_user_map.get(task_id, "Unassigned")
#         required_skill = task.get("required_skill_id")
        
#         deadline_str = task.get("date_deadline")
#         status = "Late"
#         if deadline_str:
#             deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
#             status = "On Time" if TODAY_DATE <= deadline_date else "Late"

#         backups_with_load = {
#             emp_id: employee_workload_counts[emp_id] 
#             for emp_id in skill_to_employee_map.get(required_skill, []) 
#             if emp_id != current_user
#         }

#         task_summary = {
#             "id": task_id, 
#             "status": status, 
#             "progress": task.get("progress", 0), 
#             "current_user": current_user, 
#             "skill_needed": required_skill
#         }
        
#         ai_recommendation = get_ai_manager_decision(task_summary, backups_with_load)

#         processed_task_results.append({
#             "Task_ID": task_id,
#             "Current_Status": status,
#             "Final_Assignee": ai_recommendation["new_user"] if ai_recommendation["reassign"] else current_user,
#             "AI_Reasoning": ai_recommendation["reason"],
#             "Workload_at_Time": employee_workload_counts.get(current_user, 0)
#         })

# if processed_task_results:
#     with open("ai_task_report.csv", "w", newline="") as output_file:
#         writer = csv.DictWriter(output_file, fieldnames=processed_task_results[0].keys())
#         writer.writeheader()
#         writer.writerows(processed_task_results)
#     print("AI Analysis complete. Saved to ai_task_report.csv.")



# import csv
# import json
# import ollama
# from datetime import datetime
# from collections import Counter, defaultdict

# TASK_FILE = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# ASSIGN_FILE = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# SKILL_FILE = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# TODAY = datetime.now().date()

# task_owners = {}
# all_assigned = []
# with open(ASSIGN_FILE, "r") as f:
#     for row in csv.DictReader(f):
#         task_owners[row["task_id"]] = row["user_id"]
#         all_assigned.append(row["user_id"])

# workload = Counter(all_assigned)

# skill_map = defaultdict(list)
# with open(SKILL_FILE, "r") as f:
#     for row in csv.DictReader(f):
#         skill_map[row["skill_id"]].append(row["user_id"])

# def ask_ai_manager(task_info, backups):
#     prompt = f"""
#     Task {task_info['id']} is {task_info['status']} ({task_info['progress']}% done).
#     Current User: {task_info['user']} (has {task_info['load']} tasks).
#     Qualified Backups & their current loads: {backups}

#     Rules(STRICT):
#     1: If task is late and user has other tasks too. asign one of them to other with less tasks and same skill.
#     2: Create CSV only.
    

#     Return JSON: {{"reassign": true/false, "new_user": "ID", "reason": "why"}}
#     """
#     response = ollama.chat(
#         model="llama3.2",
#         format="json",
#         messages=[{"role": "user", "content": prompt}]
#     )
#     return json.loads(response["message"]["content"])

# results = []

# with open(TASK_FILE, "r") as f:
#     for task in csv.DictReader(f):
#         if task["state"] in ["completed", "client_approval_pending"]:
#             continue

#         t_id = task["id"]
#         curr_user = task_owners.get(t_id, "None")
#         skill_needed = task.get("required_skill_id")
        
#         deadline = task.get("date_deadline")
#         status = "Late"
#         if deadline:
#             status = "On Time" if TODAY <= datetime.strptime(deadline, "%Y-%m-%d").date() else "Late"

#         backups = {u: workload[u] for u in skill_map[skill_needed] if u != curr_user}

#         summary = {
#             "id": t_id, "status": status, "progress": task.get("progress", 0),
#             "user": curr_user, "load": workload.get(curr_user, 0)
#         }
#         decision = ask_ai_manager(summary, backups)

#         results.append({
#             "Task_ID": t_id,
#             "Status": status,
#             "Original_User": curr_user,
#             "Final_User": decision["new_user"] if decision["reassign"] else curr_user,
#             "AI_Reason": decision["reason"]
#         })

# if results:
#     with open("ai_task_report.csv", "w", newline="") as f:
#         writer = csv.DictWriter(f, fieldnames=results[0].keys())
#         writer.writeheader()
#         writer.writerows(results)
#     print(f"Done! Processed {len(results)} tasks into ai_task_report.csv")






# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # Read CSV
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# output_csv = "task_analysis_results.csv"


# today = datetime.now().date()
# task_owner = {}
# all_assigned_users = []
# results_list = [] 


# # Load assigned tasks
# with open(assign_file, "r") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# # Count employee tasks
# user_tasks_count = Counter(all_assigned_users)


# # Process tasks
# with open(task_file, "r") as f:
#     tasks = csv.DictReader(f)

#     # Ignore is task status is completed or client approval pending.
#     for row in tasks:
#         if row["state"] == "completed" or row["state"] == "client_approval_pending":
#             continue
        
#         task_id = row["id"]
#         deadline_str = row["date_deadline"]
#         progress = row["progress"]
#         original_assignee = task_owner.get(task_id, "0")
#         user_task_count = user_tasks_count.get(original_assignee, 0)
        
#         status = "Unknown"
#         reason = ""
#         suggestion = ""
#         reassigned_to = "0"

#         # Check if task is On Time or Late
#         if deadline_str:
#             deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
#             status = "ON_TIME" if today <= deadline_date else "DELAYED"

#         if status == "ON_TIME":
#             reason = "within deadline"
#             suggestion = "Task has time."

#         elif status == "DELAYED":
#             if original_assignee == "0":
#         required_skill = row.get("required_skill_id")
#         suggest_employees = []

#         with open(skill_file, "r", encoding="utf-8") as f_skill:
#             skills = csv.DictReader(f_skill)

#             for skill_row in skills:
#                 if skill_row["skill_id"] == required_skill:
#                     suggest_employees.append(skill_row["user_id"])

#         if suggest_employees:
#             reassigned_to = suggest_employees[0]
#             reason = "No Employee Assigned"
#             suggestion = f"Assigned to employee with same skill: {reassigned_to}"

#             # update tracking
#             user_tasks_count[reassigned_to] += 1
#             task_owner[task_id] = reassigned_to
#         else:
#             reason = "No Employee Assigned"
#             suggestion = "No employee found with required skill"

#     elif progress and float(progress) <= 50:
#         reason = "Low Progress"
#         suggestion = "Add another resource or Extend Timeline."
#         results_list.append({
#             "Task ID": task_id,
#             "Status": status,
#             "Original Assignee": original_assignee,
#             "Reassigned To": reassigned_to, 
#             "Reason": reason,
#             "Suggestion": suggestion.replace("\n", " "),
#         })

# print("RESULTS LIST:\n", results_list)

# user_input = json.dumps(results_list,indent=2)
# # if results_list:
# #     keys = results_list[0].keys()
# #     with open(output_csv, "w", newline="") as f_output:
# #         writer = csv.DictWriter(f_output, fieldnames=keys)
# #         writer.writeheader()
# #         writer.writerows(results_list)
# #     print(f"File '{output_csv}' created successfully.\n")

# # print("Reading Data from Created CSV")
# # with open(output_csv, "r") as f_read:
# #     final_reader = csv.DictReader(f_read)
# #     for row in final_reader:
# #         print(f"Task {row['Task ID']} \nFrom: {row['Original Assignee']} To: {row['Reassigned To']}")

# prompt = """
# You are a Project Manager. You will receive structured task data in JSON.

# Your job is to generate a CSV with decisions based ONLY on the given data.

# STRICT OUTPUT FORMAT:
# - Output ONLY valid CSV. No explanation.
# - FIRST ROW MUST be EXACTLY:
# task_id,status,original_assignee,reassigned_to,reason,suggestion
# - Do NOT skip header
# - EXACTLY 6 columns per row
# - Use comma (,) only
# - No extra lines, no duplicate rows

# DATA NORMALIZATION RULES:
# - task_id: keep unchanged
# - status:
#   "On Time" → ON_TIME
#   "Late" → DELAYED
# - original_assignee:
#   if original_assignee → 0 or "No one assigned". Assign to other employee
# - If original_assignee = 0 . reason should be "No one assigned"
# - reassigned_to:
#   keep given value or use 0 if none
# - reason: short (Low Progress, On schedule, Overloaded, No assignee)
# - suggestion: ONE line only


# DECISION RULES (DETERMINISTIC — NO RANDOMNESS):

# 1. DELAYED TASK:
#    IF status = DELAYED:
#       IF reassigned_to != 0:
#          suggestion = Reassign to employee with fewer tasks
#          reason = Overloaded
#       ELSE:
#          suggestion = Add another resource or Extend Timeline.
#          reason = Low Progress

# 2. NO ASSIGNEE:
#    IF original_assignee = 0:
#       suggestion = Assign task to available employee
#       reason = No assignee

# 3. ON TIME:
#    IF status = ON_TIME:
#       suggestion = No change
#       reason = On schedule

# 4. DO NOT:
#    - Do NOT create new employee IDs
#    - Do NOT pick random employees
#    - Do NOT change reassigned_to unless already provided
#    - Do NOT infer new data

# CONSISTENCY RULES:
# - Same input → same output
# - Do not vary wording
# - Follow exact phrases used above

# Return ONLY the CSV.
# """

# response = chat(
#     model = "llama3.2",
#     messages = [{
#         "role":"system",
#         "content":prompt,
#         },
#         {
#         "role":"user",
#         "content":user_input
#         }]
# )
# ai_output = response.message.content
# ai_file = "ai_data_new.csv"
# with open(ai_file,"w",encoding="utf-8") as file:
#     file.write(ai_output)

# with open(ai_file, "r") as f_read:
#     final_reader = csv.DictReader(f_read)
#     for row in final_reader:
#         print(row)









# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # Read CSV
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"
# output_csv = "task_analysis_results.csv"

# today = datetime.now().date()
# task_owner = {}
# all_assigned_users = []
# results_list = []

# # Load assigned tasks
# with open(assign_file, "r") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# # Count employee tasks
# user_tasks_count = Counter(all_assigned_users)

# # Process tasks
# with open(task_file, "r") as f:
#     tasks = csv.DictReader(f)

#     for row in tasks:
#         # Ignore completed / client approval pending
#         if row["state"] in ["completed", "client_approval_pending"]:
#             continue

#         task_id = row["id"]
#         task_name = row["name"]
#         deadline_str = row["date_deadline"]
#         progress = row["progress"]
#         required_skill = row.get("required_skill_id")

#         original_assignee = task_owner.get(task_id, "0")
#         user_task_count = user_tasks_count.get(original_assignee, 0)

#         status = "Unknown"
#         reason = ""
#         suggestion = ""
#         reassigned_to = "0"

#         # Check deadline
#         if deadline_str:
#             deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
#             status = "ON_TIME" if today <= deadline_date else "DELAYED"

#         if status == "ON_TIME":
#             reason = "within deadline"
#             suggestion = "Task has time or add another employee"

#         elif status == "DELAYED":

#             # CASE 1: No assignee
#             if original_assignee == "0":
#                 suggest_employees = []

#                 with open(skill_file, "r", encoding="utf-8") as f_skill:
#                     skills = csv.DictReader(f_skill)

#                     for skill_row in skills:
#                         if skill_row["skill_id"] == required_skill:
#                             suggest_employees.append(skill_row["user_id"])

#                 if suggest_employees:
#                     reassigned_to = suggest_employees[0]
#                     reason = "No Employee Assigned"
#                     suggestion = f"Assigned to employee with same skill: {reassigned_to}"

#                     user_tasks_count[reassigned_to] += 1
#                     task_owner[task_id] = reassigned_to
#                 else:
#                     reason = "No Employee Assigned"
#                     suggestion = "No employee found with required skill"

#             # CASE 2: Overloaded user (>2 tasks)
#             elif user_task_count > 2:
#                 suggest_employees = []

#                 with open(skill_file, "r", encoding="utf-8") as f_skill:
#                     skills = csv.DictReader(f_skill)

#                     for skill_row in skills:
#                         if (
#                             skill_row["skill_id"] == required_skill
#                             and skill_row["user_id"] != original_assignee
#                         ):
#                             suggest_employees.append(skill_row["user_id"])

#                 if suggest_employees:
#                     reassigned_to = min(
#                         suggest_employees,
#                         key=lambda u: user_tasks_count.get(u, 0)
#                     )

#                     reason = "Overloaded"
#                     suggestion = f"Reassigned to less loaded employee: {reassigned_to}"

#                     user_tasks_count[original_assignee] -= 1
#                     user_tasks_count[reassigned_to] += 1
#                     task_owner[task_id] = reassigned_to
#                 else:
#                     reason = "Overloaded"
#                     suggestion = "No alternative employee with same skill"

#             # CASE 3: Low progress
#             elif progress and float(progress) <= 50:
#                 reason = "Low Progress"
#                 suggestion = "Add another resource or Extend Timeline."

#         results_list.append({
#             "Task ID": task_id,
#             "Task Name": task_name,
#             "Status": status,
#             "Original Assignee": original_assignee,
#             "Reassigned To": reassigned_to,
#             "Reason": reason,
#             "Suggestion": suggestion.replace("\n", " "),
#         })

# print("RESULTS LIST:\n", results_list)

# user_input = json.dumps(results_list, indent=2)

# prompt = """
# You are a Project Manager. You will receive structured task data in JSON.

# Your job is to generate a CSV with decisions based ONLY on the given data.

# STRICT OUTPUT FORMAT:
# - Output ONLY valid CSV. No explanation.
# - FIRST ROW MUST be EXACTLY:
# task_id,status,original_assignee,reassigned_to,reason,suggestion
# - Do NOT skip header
# - EXACTLY 6 columns per row
# - Use comma (,) only
# - No extra lines, no duplicate rows

# DATA NORMALIZATION RULES:
# - task_id: keep unchanged
# - status:
#   "On Time" → ON_TIME
#   "Late" → DELAYED
# - original_assignee:
#   if original_assignee → 0 or "No one assigned". Assign to other employee
# - If original_assignee = 0 . reason should be "No one assigned"
# - reassigned_to:
#   keep given value or use 0 if none
# - reason: short (Low Progress, On schedule, Overloaded, No assignee)
# - suggestion: ONE line only

# DECISION RULES:

# 1. DELAYED TASK:
#    IF status = DELAYED:
#       IF reassigned_to != 0:
#          suggestion = Reassign to employee with fewer tasks
#          reason = Overloaded
#       ELSE:
#          suggestion = Add another resource or Extend Timeline.
#          reason = Low Progress

# 2. NO ASSIGNEE:
#    IF original_assignee = 0:
#       suggestion = Assign task to available employee
#       reason = No assignee

# 3. ON TIME:
#    IF status = ON_TIME:
#       suggestion = No change
#       reason = On schedule

# Return ONLY the CSV.
# """

# response = chat(
#     model="llama3.2",
#     messages=[
#         {"role": "system", "content": prompt},
#         {"role": "user", "content": user_input}
#     ]
# )

# ai_output = response.message.content
# ai_file = "ai_data_new.csv"

# with open(ai_file, "w", encoding="utf-8") as file:
#     file.write(ai_output)

# with open(ai_file, "r") as f_read:
#     final_reader = csv.DictReader(f_read)
#     for row in final_reader:
#         print(row)














# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter

# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"

# today = datetime.now().date()
# task_owner = {}
# all_assigned_users = []
# results_list = []

# # Load assigned tasks
# with open(assign_file, "r") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# user_tasks_count = Counter(all_assigned_users)

# # Process tasks
# with open(task_file, "r") as f:
#     tasks = list(csv.DictReader(f))

# for row in tasks:
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = row["id"]
#     deadline_str = row["date_deadline"]
#     progress = row["progress"]
#     required_skill = row.get("required_skill_id")

#     # Normalize original assignee
#     original_assignee = task_owner.get(task_id, "0")
#     if original_assignee in ["", "0", None]:
#         original_assignee = "0"

#     user_task_count = user_tasks_count.get(original_assignee, 0)

#     status = "ON_TIME"
#     if deadline_str:
#         deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
#         if today > deadline_date:
#             status = "DELAYED"

#     reassigned_to = "0"
#     reason = "On schedule"
#     suggestion = "Task has time."

#     if original_assignee == "0" or user_task_count >= 2:
#         suggest_employees = []

#         with open(skill_file, "r", encoding="utf-8") as f_skill:
#             skills = csv.DictReader(f_skill)
#             for skill_row in skills:
#                 if (
#                     skill_row["skill_id"] == required_skill
#                     and skill_row["user_id"] != original_assignee
#                 ):
#                     suggest_employees.append(skill_row["user_id"])

#         if suggest_employees:
#             # Take first employee to reassign
#             first_candidate = suggest_employees[0]
#             first_candidate_load = user_tasks_count.get(first_candidate, 0)

#             # Take second employee to reassign
#             if first_candidate_load >= 2 and len(suggest_employees) > 1:
#                 reassigned_to = suggest_employees[1]
#             else:
#                 reassigned_to = first_candidate

#             # Update counters and owner
#             user_tasks_count[reassigned_to] += 1
#             if original_assignee != "0":
#                 user_tasks_count[original_assignee] -= 1

#             task_owner[task_id] = reassigned_to

#             if original_assignee == "0":
#                 reason = "No assignee"
#                 suggestion = "Assign task to available employee"
#             else:
#                 reason = "Overloaded"
#                 suggestion = f"Reassigned to {reassigned_to}"
#         else:
#             suggestion = "No skilled employee found"

#     # Additional check for Low Progress on Delayed tasks
#     if status == "DELAYED" and reassigned_to == "0":
#         if progress and float(progress) <= 50:
#             reason = "Low Progress"
#             suggestion = "Add another resource or Extend Timeline."

#     results_list.append({
#         "Task ID": task_id,
#         "Status": status,
#         "Original Assignee": original_assignee,
#         "Reassigned To": reassigned_to,
#         "Reason": reason,
#         "Suggestion": suggestion,
#     })


# # Sorting
# def get_task_id(item):
#     task_id_str = item["Task ID"]
#     if task_id_str == "" or task_id_str is None:
#         return 0
#     return int(task_id_str)


# results_list.sort(key=get_task_id)

# print("\nRESULTS LIST:\n", results_list)

# # if results_list:
# #     keys = results_list[0].keys()
# #     with open(output_csv, "w", newline="") as f_output:
# #         writer = csv.DictWriter(f_output, fieldnames=keys)
# #         writer.writeheader()
# #         writer.writerows(results_list)
# #     print(f"File '{output_csv}' created successfully.\n")

# # print("Reading Data from Created CSV")
# # with open(output_csv, "r") as f_read:
# #     final_reader = csv.DictReader(f_read)
# #     for row in final_reader:
# #         print(f"Task {row['Task ID']} \nFrom: {row['Original Assignee']} To: {row['Reassigned To']}")



# user_input = json.dumps(results_list, indent=2)

# prompt = """
# You are a Project Manager. You will receive structured task data in JSON.

# Your job is to generate a CSV with decisions based ONLY on the given data.

# STRICT OUTPUT FORMAT:
# - Output ONLY valid CSV. No explanation.
# - FIRST ROW MUST be EXACTLY:
# task_id,status,original_assignee,reassigned_to,reason,suggestion
# - Do NOT skip header
# - EXACTLY 6 columns per row
# - Use comma (,) only
# - No extra lines, no duplicate rows

# DATA NORMALIZATION RULES:
# - task_id: keep unchanged
# - status:
#   "On Time" → ON_TIME
#   "Late" → DELAYED
# - original_assignee:
#   if original_assignee → 0 or "No one assigned". Assign to other employee
# - If original_assignee = 0 . reason should be "No one assigned"
# - reassigned_to:
#   keep given value or use 0 if none
# - reason: short (Low Progress, On schedule, Overloaded, No assignee)
# - suggestion: ONE line only

# DECISION RULES (DETERMINISTIC — NO RANDOMNESS):

# 1. DELAYED TASK:
#    IF status = DELAYED:
#       IF reassigned_to != 0:
#          suggestion = Reassign to employee with fewer tasks
#          reason = Overloaded
#       ELSE:
#          suggestion = Add another resource or Extend Timeline.
#          reason = Low Progress

# 2. NO ASSIGNEE:
#    IF original_assignee = 0:
#       suggestion = Assign task to available employee
#       reason = No assignee

# 3. ON TIME:
#    IF status = ON_TIME:
#       suggestion = No change
#       reason = On schedule

# 4. DO NOT:
#    - Do NOT create new employee IDs
#    - Do NOT pick random employees
#    - Do NOT change reassigned_to unless already provided
#    - Do NOT infer new data

# CONSISTENCY RULES:
# - Same input → same output
# - Do not vary wording
# - Follow exact phrases used above
# - If original_assignee == '0' ,reassign that task

# Return ONLY the CSV.
# """

# response = chat(
#     model="llama3.2",
#     messages=[
#         {"role": "system", "content": prompt},
#         {"role": "user", "content": user_input},
#     ],
# )

# ai_output = response.message.content

# ai_file = "ai_data_new.csv"
# with open(ai_file, "w", encoding="utf-8") as file:
#     file.write(ai_output)

# with open(ai_file, "r") as f_read:
#     final_reader = csv.DictReader(f_read)
#     for row in final_reader:
#         print("\nROWS:\n", row)












# import csv
# import json
# from ollama import chat
# from datetime import datetime
# from collections import Counter


# # File Paths
# task_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task (1).csv"
# assign_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/project_task_assigned_agent_rel.csv"
# skill_file = "/home/lavanya/Desktop/Lavanya/jjungles/data/employee_skill_level.csv"


# today = datetime.now().date()
# task_owner = {}
# all_assigned_users = []
# results_list = [] 


# # Load assigned tasks
# with open(assign_file, "r") as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         task_owner[row["task_id"]] = row["user_id"]
#         all_assigned_users.append(row["user_id"])

# # Count users
# user_tasks_count = Counter(all_assigned_users)


# # Process tasks
# with open(task_file, "r") as f:
#     tasks = list(csv.DictReader(f))

# for row in tasks:
#     # Skip if tasks is completed or need client approval pending
#     if row["state"] in ["completed", "client_approval_pending"]:
#         continue

#     task_id = row["id"]
#     deadline_str = row["date_deadline"]
#     progress = row["progress"]
#     required_skill = row.get("required_skill_id")

#     # Normalize original assignee
#     original_assignee = task_owner.get(task_id, "0")
#     if original_assignee in ["", "0", None]:
#         original_assignee = "0"

#     user_task_count = user_tasks_count.get(original_assignee, 0)

#     status = "ON_TIME"
#     if deadline_str:
#         deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
#         if today > deadline_date:
#             status = "DELAYED"

#     reassigned_to = "0"
#     reason = "On schedule"
#     suggestion = "Task has time."

#     if original_assignee == "0" or user_task_count >= 2:
#         suggest_employees = []

#         with open(skill_file, "r", encoding="utf-8") as f_skill:
#             skills = csv.DictReader(f_skill)

#             for skill_row in skills:
#                 # Find someone with skill who isn't the current overloaded person
#                 if skill_row["skill_id"] == required_skill and skill_row["user_id"] != original_assignee:
#                     suggest_employees.append(skill_row["user_id"])

#         if suggest_employees:
#             f_employee = suggest_employees[0]
#             f_employee_load = user_tasks_count.get(f_employee,0)

#             if f_employee_load >= 2 and len(suggest_employees) > 1:
#                 reassigned_to = suggest_employees[1]
#             else:
#                 reassigned_to = f_employee

#             # Update counters and owner
#             user_tasks_count[reassigned_to] += 1
#             if original_assignee != "0":
#                 user_tasks_count[original_assignee] -= 1

#             task_owner[task_id] = reassigned_to

#             if original_assignee == "0":
#                 reason = "No assignee"
#                 suggestion = "Assign task to available employee"
#             else:
#                 reason = "Overloaded"
#                 suggestion = f"Reassigned to {reassigned_to}"
#         else:
#             suggestion = "No skilled employee found"

#     # Additional check for Low Progress on Delayed tasks
#     if status == "DELAYED" and reassigned_to == "0":
#         if progress and float(progress) <= 50:
#             reason = "Low Progress"
#             suggestion = "Add another resource or Extend Timeline."

#     results_list.append({
#         "Task ID": task_id,
#         "Status": status,
#         "Original Assignee": original_assignee,
#         "Reassigned To": reassigned_to, 
#         "Reason": reason,
#         "Suggestion": suggestion,
#     })

# # Final Sort by Task ID
# # results_list.sort(key=lambda x: int(x["Task ID"]))
# def get_task_id(item):
#     task_id_str = item["Task ID"]
#     if task_id_str == "" or task_id_str == None:
#         return 0
#     return int(task_id_str)

# results_list.sort(key=get_task_id)
# print("\nRESULTS LIST:\n",results_list)

# user_input = json.dumps(results_list, indent=2)

# # if results_list:
# #     keys = results_list[0].keys()
# #     with open(output_csv, "w", newline="") as f_output:
# #         writer = csv.DictWriter(f_output, fieldnames=keys)
# #         writer.writeheader()
# #         writer.writerows(results_list)
# #     print(f"File '{output_csv}' created successfully.\n")

# # print("Reading Data from Created CSV")
# # with open(output_csv, "r") as f_read:
# #     final_reader = csv.DictReader(f_read)
# #     for row in final_reader:
# #         print(f"Task {row['Task ID']} \nFrom: {row['Original Assignee']} To: {row['Reassigned To']}")


# prompt = """
# You are a Project Manager. You will receive structured task data in JSON.

# Your job is to generate a CSV with decisions based ONLY on the given data.

# STRICT OUTPUT FORMAT:
# - Output ONLY valid CSV. No explanation.
# - FIRST ROW MUST be EXACTLY:
# task_id,status,original_assignee,reassigned_to,reason,suggestion
# - Do NOT skip header
# - EXACTLY 6 columns per row
# - Use comma (,) only
# - No extra lines, no duplicate rows

# DATA NORMALIZATION RULES:
# - task_id: keep unchanged
# - status:
#   "On Time" → ON_TIME
#   "Late" → DELAYED
# - original_assignee:
#   if original_assignee → 0 or "No one assigned". Assign to other employee
# - If original_assignee = 0 . reason should be "No one assigned"
# - reassigned_to:
#   keep given value or use 0 if none
# - reason: short (Low Progress, On schedule, Overloaded, No assignee)
# - suggestion: ONE line only


# DECISION RULES (DETERMINISTIC — NO RANDOMNESS):

# 1. DELAYED TASK:
#    IF status = DELAYED:
#       IF reassigned_to != 0:
#          suggestion = Reassign to employee with fewer tasks
#          reason = Overloaded
#       ELSE:
#          suggestion = Add another resource or Extend Timeline.
#          reason = Low Progress

# 2. NO ASSIGNEE:
#    IF original_assignee = 0:
#       suggestion = Assign task to available employee
#       reason = No assignee

# 3. ON TIME:
#    IF status = ON_TIME:
#       suggestion = No change
#       reason = On schedule

# 4. DO NOT:
#    - Do NOT create new employee IDs
#    - Do NOT pick random employees
#    - Do NOT change reassigned_to unless already provided
#    - Do NOT infer new data

# CONSISTENCY RULES:
# - Same input → same output
# - Do not vary wording
# - Follow exact phrases used above
# - If original_assignee == '0' ,reassign that task

# Return ONLY the CSV.
# """

# response = chat(
#     model = "llama3.2",
#     messages = [
#         {"role":"system","content":prompt,},
#         {"role":"user","content":user_input}]
# )
# ai_output = response.message.content

# ai_file = "ai_data_new.csv"

# with open(ai_file,"w",encoding="utf-8") as file:
#     file.write(ai_output)

# with open(ai_file, "r") as f_read:
#     final_reader = csv.DictReader(f_read)
#     for row in final_reader:
#         print("\nROWS:\n",row)














