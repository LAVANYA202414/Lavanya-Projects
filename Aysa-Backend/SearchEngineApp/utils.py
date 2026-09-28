from textblob import TextBlob
import re
from .models import *
from django.utils.timezone import now
import sys
import os
import pandas as pd
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError


PRODUCT_DATA_COLUMNS = ["Brand", "Product Name", "Category", "Gender", "Production Year","Link to Product Pictures" ,"Release Price", "Profit Made",  "Profit Margin", "Product Type"]

TAX_DATA_COLUMNS = ['Company Name', 'Year', 'Taxes Paid', 'Taxes Avoided']

PHONE_CEO_WORKER_DATA_COLUMNS = ['Company Name', 'Year', 'CEO Name', 'CEO Total Compensation', 'Frontline Worker Salary', 'Pay Ratio']

WEBSITE_CEO_WORKER_DATA_COLUMNS = ['Company Name', 'Year', 'CEO Name', 'CEO Total Compensation', 'Frontline Worker Salary', 'Pay Ration']

# function to convert data into list 
def ListToDict(input_list):
    data_dict ={}
    for item in input_list :
        split_item=  item.split(":", 1)
        data_dict[split_item[0]] =split_item[1]
    return data_dict

# Function to check response dict has all rows data
def is_valid_product(data, required_keys):
    return all(key in data and data[key].strip() != '' for key in required_keys)

# function to check grammer corrector
def SpellCorrector(input_str:str) -> str:
    correct_string = TextBlob(input_str)
    return str(correct_string.correct()).lower()


# function to remove preprocessing
def preprocess_text(text):
    text = str(text).lower()                          # Lowercase
    # text = re.sub(r'[^\w\s]', '', text)               # Remove punctuation
    text = re.sub(r'\s+', ' ', text).strip()          # Remove extra spaces
    return text

# Function To Format Profit Margin API
def format_profit_margin(x):
    if pd.isnull(x):
        return ""
    
    s = str(x).strip()
    
    # If already has $ → format as currency
    if "$" in s:
        # Remove commas, $, then format again
        try:
            val = float(s.replace("$", "").replace(",", ""))
            return f"${val:,.2f}"
        except:
            return s
    
    # If has % → normalize to 2 decimals
    if "%" in s:
        try:
            val = float(s.replace("%", ""))
            return f"{val:.2f}%"
        except:
            return s
    
    # If pure number → decide if % or $
    try:
        val = float(s)
        # If it's > 1000 → assume it's money
        if val > 1000:
            return f"${val:,.2f}"
        else:
            return f"{val:.2f}%"
    except:
        return s


# function to filter year from the user query
def get_year(text: str) -> str:
    match = re.search(r"(19|20)\d{2}", text)  # no word boundaries
    return match.group(0) if match else "None"


# function to update track count of Product
def ProductSearch_Object_create_func(
    brand_name: str,
    product_name: str,
    tab_type: str,
    weight: int = 1
):
    try:
        today = now().date()

        # clamp weight
        weight = max(1, min(int(weight), 10))
        
        visit_model_obj, created = ProductSearchTrack.objects.get_or_create(
            brand_name=brand_name,
            product_name=product_name,
            tab_type=tab_type,
            track_date=today,   
            defaults={"search_count": 0},
        )

        visit_model_obj.search_count += weight
        visit_model_obj.save()

        total_count = ProductSearchTrack.objects.aggregate(
            total=models.Sum("search_count")
        )["total"] or 0

        
        return {
            "message": f"Search count increased by {weight}",
            "count": int(total_count),
            "object": visit_model_obj
        }

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        error_message = (
            f"[ERROR] Failed to get track count value, "
            f"error: {str(e)} in line {exc_tb.tb_lineno}"
        )
        return error_message


# function to validate token
def validate_token(token: str):
    secret_key = os.getenv("SECRET_KEY", "default_secret")
    algorithm = os.getenv("ALGORITHM", "HS256")

    try:
        # Decode and verify token
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return {"valid": True, "payload": payload}

    except ExpiredSignatureError:
        return {"valid": False, "error": "Token expired"}
    except InvalidTokenError:
        return {"valid": False, "error": "Invalid token"}


# function to check file suffix means check file type
def check_suffix(file) -> bool:
        
    suffix_status = False

    file_name = file.name

    if file_name.endswith(".csv"):
        suffix_status= True
    
    return suffix_status

# function to check uploaded csv file has same columns
def check_columns(tab_type: str, dataframe: pd.DataFrame) -> bool:
    columns_status = True

    # Normalize dataframe column names
    dataframe_columns = dataframe.columns.str.strip().tolist()

    # Select expected columns
    expected_columns = PRODUCT_DATA_COLUMNS
    if tab_type == "tax":
        expected_columns = TAX_DATA_COLUMNS
    elif tab_type == "mobile":
        expected_columns = PHONE_CEO_WORKER_DATA_COLUMNS
    elif tab_type == "desktop":
        expected_columns = WEBSITE_CEO_WORKER_DATA_COLUMNS

    # Normalize expected columns too
    expected_columns = [col.strip() for col in expected_columns]

   

    # Check if expected columns match exactly
    if set(expected_columns) != set(dataframe_columns):
        columns_status = False

    return columns_status , expected_columns


