import datetime
import parsedatetime
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:postgr23@localhost:5432/salon_bot"
cal = parsedatetime.Calendar()
engine = create_engine(DATABASE_URL)

def booking_appointment(intent, entities):
    # 1. Extract raw entity strings
    raw_service = entities.get("service")
    raw_date = entities.get("date")
    raw_time = entities.get("time")

    # 2. Parse relative natural language into datetime structs
    date_struct, _ = cal.parse(raw_date)
    time_struct, _ = cal.parse(raw_time)

    # 3. Convert structs to standard python date and time objects
    parsed_date = datetime.date(*date_struct[:3])      # Result: 2026-07-27
    parsed_time = datetime.time(*time_struct[3:6])     # Result: 10:00:00

    print(f"Parsed -> Service: {raw_service}, Date: {parsed_date}, Time: {parsed_time}")

    # 4. Insert into PostgreSQL using SQLAlchemy Textual SQL
    # Ensure your table column types are 'DATE' and 'TIME'
    query = text("""
        INSERT INTO appointments (service, appointment_date, appointment_time, intent)
        VALUES (:service, :date, :time, :intent);
    """)

    try:
        with engine.begin() as connection:  # Automatically commits or rolls back
            connection.execute(query, {
                "service": raw_service,
                "date": parsed_date,
                "time": parsed_time,
                "intent": intent
            })
        print("Successfully saved appointment to the database!")
    except Exception as e:
        print(f"Database insertion failed: {e}")


intent = "book_appointment"
entities = {
    "service": "haircut",
    "date": "this monday",
    "time": "10am"
}

booking_appointment(intent, entities)
