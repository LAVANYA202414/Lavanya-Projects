from app import app, db, Event
with app.app_context():
    events = db.session.execute(db.select(Event)).scalars().all()
    for e in events:
        print(f"ID: {e.id} | Date: {e.date} | Event: {e.event}")
