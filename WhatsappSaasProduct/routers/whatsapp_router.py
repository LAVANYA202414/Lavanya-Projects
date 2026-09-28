from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from core.config import settings
from services.whatsapp_service import WhatsAppService
from utils.logger import get_logger
from schemas.api_schemas import(
    whatsapp_api_schemas
)

# Initialize logger
logger = get_logger(__name__)   

# Configure Router
router = APIRouter(prefix="/whatsapp" , tags=["WhatsApp"])

# Configure whatsapp service
service = WhatsAppService()


# webhook verification 
@router.get("/webhook")
async def verify_webhook(request : Request):

    try:
        params = request.query_params
        verify_token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")

        if verify_token == settings.WHATSAPP_VERIFY_TOKEN:
            logger.info("Webhook verified successfully")
            return PlainTextResponse(content=challenge, status_code=200)
        
        logger.error("Invalid verify token")
        return PlainTextResponse(content="Invalid token", status_code=403)
    
    except Exception as e:
        logger.error("Webhook verification error: %s", str(e))
        return PlainTextResponse(content="Error", status_code=500)
    

# Recieve Incoming Message
@router.post("/webhook")
async def recieve_message(request: Request):
    try:
        
        body = await request.json()
        logger.info("Incoming webhook: %s", body)
        
        entry = body.get("entry", [])

        if not entry:
            return {"status": "ignored"}

        changes = entry[0].get("changes", [])

        if not changes:
            return {"status": "ignored"}

        value = changes[0].get("value", {})

        messages = value.get("messages")

        if not messages:
            logger.info("No incoming messages")
            return {"status": "ignored"}

        message = messages[0]

        sender = message.get("from")

        message_id = message.get("id")

        message_type = message.get("type")

        logger.info("Sender : %s", sender)
        logger.info("Message ID : %s", message_id)
        logger.info("Message Type : %s", message_type)

        text = ""

        if message_type == "text":
            text = message["text"]["body"]

        logger.info("Message : %s", text)

        # Reply back
        service.reply_message(
            sender,
            f"Thanks for messaging....."
        )

        return {
            "status": "success"
        }

    except Exception as e:
        logger.error("Webhook processing error: %s", str(e))

        return {
            "status": "failed",
            "data": "Processing failed"
        }

# Send Message API
@router.post("/send-message")
def send_message(to: str, message: str):
    try:
        result = service.send_message(to, message)
        return result

    except Exception as e:
        logger.error("Send message API error: %s", str(e))

        return {
            "status": "failed",
            "data": "Send message failed"
        }
    

# Get Whatsapp Message Templates
@router.get("/get-message-templates")
async def whatsapp_message_templates():
    try:

        result = service.get_message_templates()
        return result


    except Exception as e:
        logger.error("Get whatsapp Template API error: %s", str(e))

        return {
            "status": "failed",
            "data": "Get whatsapp Template"
        }
    

# Send Whatsapp Template Message API
@router.post("/send-template-message")
def send_whatsapp_message_template(req: whatsapp_api_schemas.SendTemplateRequest):
    try:
        if "string" in req.body_params:
            req.body_params = []

        result = service.send_template(
            to=req.to,
            template_name=req.template_name,
            language_code=req.language_code,
            body_params=req.body_params
        )
        return result

    except Exception as e:
        logger.error("Send whatsapp template API error: %s", str(e))
        return {
            "status": "failed",
            "data": "Send whatsapp template failed"
        }