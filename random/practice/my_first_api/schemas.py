# schemas.py
from pydantic import BaseModel

# 1. Used when creating a new Todo (Incoming Request)
class TodoCreate(BaseModel):
    task: str

# 2. Used when sending Todo data back to the client (Outgoing Response)
class TodoResponse(BaseModel):
    id: int
    task: str
    completed: bool

    class Config:
        # This crucial line tells Pydantic to read data directly 
        # from your SQLAlchemy database object models smoothly.
        from_attributes = True 
