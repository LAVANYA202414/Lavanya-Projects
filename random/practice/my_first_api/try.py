from fastapi import FastAPI, Depends, status, HTTPException
from sqlalchemy.orm import Session
from database import engine, Base, get_db
from models import TodoTable

# Physically builds the file and tables on your computer
Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/")
def home():
    return {"message": "Hello World! This is my first API."}


@app.get("/todos")
def get_all_todos(db: Session = Depends(get_db)):
    return db.query(TodoTable).all()


@app.get("/todos/{todo_id}")
def get_single_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = db.query(TodoTable).filter(TodoTable.id == todo_id).first()
    if todo:
        return todo
    raise HTTPException(status_code=404, detail="Task Not Found...")


@app.post("/create-todo", status_code=status.HTTP_201_CREATED)
def create_todo(task_name:str, db: Session = Depends(get_db)):
    new_todo = TodoTable(task= task_name, completed = False)
    db.add(new_todo)
    db.commit()
    db.refresh(new_todo)
    # new_item = {"id":new_id, "task": task_name, "completed":False}
    # todo_db.append(new_item)
    return {"message": "Success", "added_data": new_todo}


@app.delete("/delete-todo/{todo_id}")
def delete_todo(todo_id:int, db: Session = Depends(get_db)):
    todo = db.query(TodoTable).filter(TodoTable.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail = "Task Not Found")

    db.delete(todo)
    db.commit()
    # for index, item in enumerate(todo_db):
    #     if item["id"] == todo_id:
    #         deleted_item = todo_db.pop(index)
    #         return {"message":"Deleted!", "removed_data":deleted_item}
    return {"message":"Deleted!", "removed_id": todo_id}


@app.put("/update-todo/{todo_id}")
def update_todo(todo_id:int, db:Session = Depends(get_db)):
    todo = db.query(TodoTable).filter(TodoTable.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail = "Task Not Found.")

    # This dynamically flips True to False, or False to True
    todo.completed = not todo.completed
    db.commit()
    db.refresh(todo)

    return {"message":"Updated Seccessfully!", "updated_todo": todo}