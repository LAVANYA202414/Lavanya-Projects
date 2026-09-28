import requests
import sys
from fastapi import HTTPException
from core.config import settings

from utils.helper import (
    count_template_parameter,
    get_template_parameter_count,
    success_response,
)

from utils.logger import get_logger 


# Initialize logger
logger = get_logger(__name__)


class WhatsAppService:
    def __init__(self):
        self.token = settings.WHATSAPP_ACCESS_TOKEN
        self.phone_id = settings.PHONE_NUMBER_ID
        self.base_url = settings.BASE_URL
        self.wabd_ID = settings.WABA_ID


    def send_message(self, to: str, message: str):
        try:
            url = f"{self.base_url}/{self.phone_id}/messages"

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            payload = {
                "messaging_product": "whatsapp",
                "to": str(to),
                "type": "text",
                "text": {"body": message}
            }

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                resp_json = response.json()
                message_id = resp_json.get("messages", [{}])[0].get("id")

                logger.info(
                    "Message sent to %s | Message ID: %s",
                    to,
                    message_id
                )

                return success_response(
                    detail="Message send successfully",
                    status_code=200,
                    data= {"response": resp_json}
                )

            else:
                logger.error(
                    "WhatsApp API Error for %s | Status: %s | Response: %s",
                    to,
                    response.status_code,
                    response.text
                )

                raise HTTPException(
                    status_code = response.status_code,
                    detail= response.text
                )
            
        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]
            logger.error(
                "Exception while sending message to %s: %s at line: %s",
                to,
                str(e),
                exc_tb.tb_lineno,
            )

            raise HTTPException(
                status_code = 500,
                detail= f"Message sending failed. Error : {str(e)}, Line :{exc_tb.tb_lineno}"
            )


    # Function for reply message
    def reply_message(self, to: str, message: str):
        return self.send_message(to, message)
    

    # Function to get message templates from the whatsapp cloud
    def get_message_templates(self):
        try:
            url = f"{self.base_url}/{self.wabd_ID}/message_templates"

            headers = {
                "Authorization": f"Bearer {self.token}"
            }

            response = requests.get(
                url,
                headers=headers,
                timeout=10
            )

            if response.status_code ==200:
                records =[]
                data = response.json().get("data", [])
                data = [rec for rec in data if not rec["name"].startswith("3p_")]
                count_template_parameter(data)


                for rec in data:
                    id = rec.get("id")     
                    name = rec.get("name")
                    status = rec.get("status")
                    category= rec.get("category")
                    components = rec.get("components")
                    resp_json = {
                        "id": id,
                        "name": name,
                        "status": status, 
                        "category": category,
                        "message_text":' '.join([t['text'] for t in components if t["type"] =="BODY"])
                    }
                    records.append(resp_json)

                logger.info(
                    "Whatsapp Messsage Template Get Successfully : %s",
                    records,
                )

                return success_response(
                    detail="Message Template get successfully.",
                    status_code= 200,
                    data={"response": records}

                )
            
            else:
                logger.error(
                    "WhatsApp Message Template API Error Status: %s | Response: %s",
                    response.status_code,
                    response.text
                )
                
                raise HTTPException(
                    status_code =response.status_code,
                    detail =  response.text
                )
            
        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]
            logger.error(
                "Exception while getting whatsapp templates : %s at line: %s",
                str(e),
                exc_tb.tb_lineno,
            )

            raise HTTPException(
                status_code =500,
                detail =f"Failed to fetching template. Error : {str(e)}, Line: {exc_tb.tb_lineno}"
            )
    
    # Function to send whatsapp message template
    def send_template(
            self, 
            to: str, 
            template_name: str , 
            language_code: str = "en_US",
            body_params: list = None
    ):
        try:
            url = f"{self.base_url}/{self.phone_id}/messages"

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            template_data = {
                "name": template_name,
                "language": {
                    "code": language_code
                }
            }

            total_parameters = get_template_parameter_count(template_name)
            received_parameters = len(body_params or [])

            if received_parameters != total_parameters:
                raise HTTPException(status_code= 400 , detail= "Failed to send template" )
                
            if total_parameters > 0:
                template_data["components"] = [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": str(param)}
                            for param in body_params
                        ]
                    }
                ]

            payload = {
                "messaging_product": "whatsapp",
                "to": str(to),
                "type": "template",
                "template": template_data
            }

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                resp_json = response.json()
                message_id = resp_json.get("messages", [{}])[0].get("id")

                logger.info(
                    "Message Template sent to %s | Message ID: %s",
                    to,
                    message_id
                )

                return success_response(
                    detail="Template send successfully.",
                    status_code=200,
                    data={"response": resp_json}
                )
                
            else:
                logger.error(
                    "Send WhatsApp Message Template API Error for %s | Status: %s | Response: %s",
                    to,
                    response.status_code,
                    response.text
                )

                raise HTTPException(
                    status_code=response.status_code, 
                    detail= response.text
                )

        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]
            logger.error(
                "Exception while sending whatsapp template message to %s: %s at line: %s",
                to,
                str(e),
                exc_tb.tb_lineno,
            )

            raise HTTPException(
                status_code=500, 
                detail= "Failed to send template."
            )

          