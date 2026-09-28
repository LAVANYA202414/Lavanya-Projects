from fastapi import FastAPI, Depends, status, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session


DATABASE_URL = "sqlite:///.todos.db"
engine = create_engine(DATABASE_URL,connect_args = {"check_same_thread": False})
SessionLocal = sessionmaker(autocommit = False, autoflush = False, bind = engine)
Base = declarative_base()


class TodoTable(Base):
    __tablename__ = "todos"

    id = Column(Integer, primary_key=True, index=True)
    task = Column(String, index=True)
    completed = Column(Boolean, default=False)


# This command physically builds the file and tables on your computer
Base.metadata.create_all(bind=engine)

# This line initializes the FastAPI framework
app = FastAPI()

# # Simulated Database (A simple Python list of dictionaries)
# todo_db = [
#     {"id": 1, "task": "Learn basic Python", "completed": True},
#     {"id": 2, "task": "Build a FastAPI server", "completed": False}
# ]


def get_db():
    # Creates a new isolated database
    db = SessionLocal()
    try:
        # The yield keyword temporarily pauses the function and hands the active database session (db) 
        # to your API endpoint. The code inside your endpoint executes using this session.
        yield db
    finally:
        # The finally block guarantees execution, even if your API endpoint encounters an error. 
        # It safely closes the database connection.
        db.close()


# This is a normal Python function, but the '@app.get' tells FastAPI 
# to show this function's return message to anyone who visits '/'
@app.get("/")
def home():
    return {"message": "Hello World! This is my first API."}


@app.get("/todos")
def get_all_todos(db: Session = Depends(get_db)):
    return db.query(TodoTable).all()


@app.get("/todos/{todo_id}")
def get_single_todo(todo_id:int, db:Session = Depends(get_db)):
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