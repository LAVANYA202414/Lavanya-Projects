import datetime
from sqlalchemy import create_engine, text
from datetime import datetime

DATABASE_URL = "postgresql://postgres:postgres123@localhost:5432/salon_bot"
now = datetime.now()

engine = create_engine(DATABASE_URL)
with engine.connect() as conn:
    print("Connection successful")

def booking_appointment(intent,entities):
    if intent == "book_appointment":
        tenant_id = entities.get("tenant_id")
        business_id = entities.get("business_id")
        service_id = entities.get("service_id")
        staff_id = entities.get("staff_id")
        start_time = entities.get("start_time")
        end_time = entities.get("end_time")
        created_date = now

        print(f"Input -> Tenant: {tenant_id}, Service: {service_id}, Date: {date_str}, Time: {time_str}, Staff_id: {staff_id}")
        
        with engine.begin() as conn:
            query = text("INSERT INTO bookings (tenant_id, service_id, staff_id, start_time, end_time) VALUES (:tenant_id, :service_id, :staff_id), :start_time, :end_time")
            conn.execute(query,{
            "tenant_id":tenant_id,
            "service":service_str,
            "staff_id": staff_id,
            "start_time" : start_time,
            "end_time": end_time
        })
        print("Booking success")

intent = "book_appointment"
entities = {
    "tenant_id" : "1",
    "service_id": "2",
    "date": "27-07-2005",
    "time": "10am",
    "staff_id" : "1"
}

booking_appointment(intent, entities)   
