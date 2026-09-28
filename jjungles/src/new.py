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
            #             suggestion = f"Original assignee {original_assignee} is over capacity; reassigned to user {reassigned_to}.

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