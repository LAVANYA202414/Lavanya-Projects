# Starting Student Data
student_grades = {
    "Alice": 85,
    "Bob": 42,
    "Charlie": 78
}

student_grades["David"] = 92
# student_grades["Bob"] = 65
marks = 0
turn = len(student_grades)
for name,grade in student_grades.items():
    if grade >= 60:
        print("Passes")
    else:
        print("Failed")


for name,grades in student_grades.items():
    marks += grades

average = marks / turn
print(average)

deleted_student = student_grades.pop("Bob")

honor_roll = {}

for name,grades in student_grades.items():
    print(name,grade)
    if grades >= 80:
        honor_roll[name] = grades

print(honor_roll)