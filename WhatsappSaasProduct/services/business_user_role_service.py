import sys
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from utils.logger import get_logger
from models import (
    translation,
    tenant,
    business
)

from schemas.models_schemas.tenant_schema import (
    TenantAllResponse,
    TenantResponse
)

from schemas.models_schemas.business_schemas import AllBusinessResponse
from utils.helper import (
    success_response,
    normalize_string
)

# Initialize logger
logger = get_logger(__name__)



class BusinessUserRoleService:

    pass