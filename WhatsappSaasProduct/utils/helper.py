import re
import json
import os
from fastapi.responses import JSONResponse

json_file_path = f"{os.getcwd()}/core/template_parameter_count.json"


# Function to extract template name and parameter count value.
def count_template_parameter(templates : list) -> dict:
          
    template_cache = {}

    for template in templates:
        count = 0

        for component in template.get("components", []):

            if component["type"] == "BODY":
                count = len(re.findall(r"\{\{\d+\}\}", component.get("text", "")))

        template_cache[template["name"]] = count

    with open(json_file_path, "w") as file:
        json.dump(template_cache, file, indent=4)

    return template_cache

# Check template has parameters or not 
def get_template_parameter_count(template_name: str) -> int:
    
    with open(json_file_path, "r") as f:
        json_data = json.load(f)

    return int(json_data.get(template_name.lower().strip(), 0))


def is_valid_value(value):
    if value is None:
        return False
    if isinstance(value, str) and value.strip().lower() in ["", "string", "none"]:
        return False
    if isinstance(value, int) and value==0:
        return False
    return True


def deep_clean(data):
    """
    Recursively remove empty / invalid values from dict
    """
    if isinstance(data, dict):
        cleaned_dict = {}

        for k, v in data.items():
            cleaned_value = deep_clean(v)

            # skip invalid values
            if not is_valid_value(cleaned_value):
                continue

            # skip empty dicts after cleaning
            if isinstance(cleaned_value, dict) and not cleaned_value:
                continue

            cleaned_dict[k] = cleaned_value

        return cleaned_dict

    return data


def normalize_string(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().lower()


def normalize_dict_data(data: dict, exclude_fields: set = None) -> dict:
    """
    Convert all string values in dict to lowercase,
    except fields in exclude_fields.
    """
    if exclude_fields is None:
        exclude_fields = {"password", "owner_password"}

    normalized_data = {}

    for key, value in data.items():

        if isinstance(value, str) and key not in exclude_fields: 
            normalized_data[key] = value.lower()
        else:
            normalized_data[key] = value

    return normalized_data


def success_response(detail, data=None, status_code=200, meta=None):
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "status_code": status_code,
            "detail": detail,
            "data": data,
            "meta": meta or {}
        }
    )


def error_response(message, status_code=400):
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "status_code": status_code,
            "message": message,
            "data": None
        }
    )

    
