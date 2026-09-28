from fastapi import FastAPI 
from routers import (
    whatsapp_router,
    business_routers,
    subscription_routers,
    business_subscription_router,
    users_router,
    onboarding_router,
    auth_router,
    admin_router,
    staff_router,
    ollama_router
)
import uvicorn
from server.database import Base , engine


# Create ALL Tables
Base.metadata.create_all(bind=engine)


# make a app object 
app = FastAPI(
    title = "Whatsapp Automation Platform",
    description= "B2B Saas Whatsapp Platform for Multiple Business",
    version="1.0.0"

)

# Add router path in app object
app.include_router(ollama_router.router)
app.include_router(admin_router.router)
app.include_router(onboarding_router.router)
app.include_router(auth_router.router)
app.include_router(whatsapp_router.router)
app.include_router(business_routers.router)
app.include_router(staff_router.router)

# app.include_router(subscription_routers.router)
# app.include_router(business_subscription_router.router)

if __name__ =="__main__":
    uvicorn.run("main:app", host="127.0.0.1" , port=8000 , reload= True)