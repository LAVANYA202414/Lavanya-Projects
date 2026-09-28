from pydantic import BaseModel, Field
from typing import Optional , List

class SendTemplateRequest(BaseModel):
    to: str
    template_name: str
    language_code: str = "en_US"
    body_params: Optional[List[str]] = Field(default=None, example=[])
