from fastapi import FastAPI, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List # Import this to handle lists of schemas
from database import engine, Base, get_db
from models import TodoTable
import schemas # Import your brand new schemas file

Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/")
def home():
    return {"message": "Hello World! This is my first API."}


# Upgrade 1: Filters the outgoing list to strictly match the TodoResponse schema
@app.get("/todos", response_model=List[schemas.TodoResponse])
def get_all_todos(db: Session = Depends(get_db)):
    return db.query(TodoTable).all()


# Upgrade 2: Filters a single outgoing todo safely
@app.get("/todos/{todo_id}", response_model=schemas.TodoResponse)
def get_single_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = db.query(TodoTable).filter(TodoTable.id == todo_id).first()
    if todo:
        return todo
    raise HTTPException(status_code=404, detail="Task Not Found...")


# Upgrade 3: Accepts a clean JSON Request Body instead of a query parameter
@app.post("/create-todo", response_model=schemas.TodoResponse, status_code=status.HTTP_201_CREATED)
def create_todo(todo_input: schemas.TodoCreate, db: Session = Depends(get_db)):
    # todo_input.task reads directly from the incoming JSON payload
    new_todo = TodoTable(task=todo_input.task, completed=False)
    db.add(new_todo)
    db.commit()
    db.refresh(new_todo)
    return new_todo


@app.delete("/delete-todo/{todo_id}")
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = db.query(TodoTable).filter(TodoTable.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Task Not Found")

    db.delete(todo)
    db.commit()
    return {"message": "Deleted!", "removed_id": todo_id}


# Upgrade 4: Formats the updated task response safely
@app.put("/update-todo/{todo_id}", response_model=schemas.TodoResponse)
def update_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = db.query(TodoTable).filter(TodoTable.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Task Not Found.")

    todo.completed = not todo.completed
    db.commit()
    db.refresh(todo)
    return todo