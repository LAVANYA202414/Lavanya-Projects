import datetime
from app import db
from sqlalchemy.orm import DeclarativeBase

class Event(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    date = db.Column(db.DateTime, default = datetime.datetime.utcnow)
    event = db.Column(db.String, nullable = False)


def add_event(event_description):
    new_event = Event(event = event_description)
    db.session.add(new_event)
    db.session.commit()


# creates a base class for defining ORM database models
class Base(DeclarativeBase):
    pass    