import sys
from fastapi import HTTPException
from core.config import settings
from ai.prompt_builder import system_prompt
from ai.llm_configure import (LLMIntegration)
from utils.helper import (success_response)
from utils.logger import get_logger

logger = get_logger(__name__)

class AIResponseService:

    def user_query_response(self, user_message):
        try:

            logger.info("user message recieved : %s",user_message)

            print("="*70)
            print(f"Step 1 - User Message Recieve {user_message}")
            print("="*70)
            print()


            print("="*70)
            print(f"Step 2 - Calling LLM Model : {settings.OLLAMA_DEFAULT_MODEL}")
            print("="*70)
            print()

            response = LLMIntegration.call_ollama_model(
                ollama_model_name= settings.OLLAMA_DEFAULT_MODEL,
                system_prompt= system_prompt,
                user_message= user_message,
            )

            print("="*70)
            print(f"AI Response : {response}")
            print("="*70)
            print()

            return success_response(
                detail="User Intent get successfully...",
                data=response,
                status_code=200
            )
            

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to get ai response. Error %s, Line %s",
                str(e),
                exc_tb.tb_lineno
            )


            raise HTTPException(
                status_code = 500,
                detail = f"Failed to get ai response. Error {str(e)} , Line {exc_tb.tb_lineno}"
            )
