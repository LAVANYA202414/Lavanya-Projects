# # Your dataset
# student_data = {
#     "Alice": 85,
#     "Bob": 42,
#     "Charlie": 78,
#     "David": 92
# }
# turns = len(student_data)

# def calculate_average(grades_dict):
#     marks = 0
#     for name,grade in grades_dict.items():
#         marks += grade
#     return marks / turns

# def remove_student(grades_dict,name):
#     grades_dict.pop(name, None) 
#     print(grades_dict)
#     return grades_dict

# def get_honor_roll(grades_dict):
#     scores = {}
#     for name,grade in grades_dict.items():
#         if grade < 80:
#             scores[name] = grade
#     return scores

# # Test 1: Calculate average
# current_average = calculate_average(student_data)
# print(f"Initial Average: {current_average}")

# # Test 2: Remove Bob
# updated_data = remove_student(student_data, "Bob")
# print(f"Data after removing Bob: {updated_data}")

# # Test 3: Get honor roll
# honor_group = get_honor_roll(updated_data)
# print(f"Honor Roll: {honor_group}")


# This code is supposed to find the average score and list players with 100+ points.
# Identify and fix the 3 errors.

players = {"Player1": 120, "Player2": 80, "Player3": 105}

total_points = 0
for name, score in players.items():  # Error 1
    total_points += score

average = total_points / 3
print(average)

pro_players = {}
for name, score in players.items():
    if score > 100:
        pro_players[name] = score  # Error 2

print(pro_players)  # Error 3
