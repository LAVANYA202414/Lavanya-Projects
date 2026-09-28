from twilio.rest import Client
from twilio.base.exceptions import TwilioException
import pandas as pd
from rest_framework.views import APIView
import os
from dotenv import load_dotenv
from rest_framework.response import Response

load_dotenv()

class Send_sms_twilio(APIView):
    
    # function to connect twilio account
    def config_twilio_client(self):
        try:
            account_sid = os.getenv("twilio_account_sid")
            auth_token = os.getenv("twilio_auth_token")
            client = Client(account_sid, auth_token)
            return client
        

        except TwilioException as e:
            error_message = f"[ERROR] Failed to connect twilio client. error occur : {str(e)}"
            return error_message


    def send_twilio_sms(self , **kwargs):
        try:
            client = self.config_twilio_client()

            # FIX: never use "ERROR" in client
            if isinstance(client, dict) and client.get("ERROR"):
                return client

            body_content = kwargs.get("body_content")
            customer_num = kwargs.get("customer_num")
            twilio_num = os.getenv("twilio_phone_number")

            message = client.messages.create(
                body=body_content,
                from_=twilio_num,
                to=customer_num
            )

            return "success"

        except TwilioException as e:
            error_message = f"[ERROR] Failed to send sms. error occur : {str(e)}"
            return error_message


    def post(self, request, format=None):
        
        try:
            # Get payload data
            payload = request.data

            # Handle payload data
            required_fields =["file" , "sms_content"]
            missing_fields = [field for field in required_fields if not payload.get(field) or field in ["" , None]]

            if missing_fields:
                return Response({
                    "message": f"{', '.join(missing_fields)} key is required",
                    "status": 400
                }, status=400)

            # Handle File type
            uploaded_file = payload.get("file")
            filename, file_extension = os.path.splitext(uploaded_file.name)

            if file_extension.lower() != ".csv":
                return Response({"error": "Only CSV files are allowed." , "status": 400}, status=400)

            # Read CSV

            df = pd.read_csv(
                uploaded_file,
                dtype=str,               # forces ALL columns to string (safest)
                keep_default_na=False    # prevents NaN conversion → keeps empty as ""
            )

            # Normalize column names
            df.columns = df.columns.str.strip().str.lower()

            # Required columns
            required_columns = ["phone number", "email", "first name", "last name"]
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                return Response({
                    "error": "Only Acceptable column is : Phone Number, Email, First Name, Last Name",
                    "status": 400
                }, status=400)

            res_data = []
            for idx , row_data in df.iterrows():

                number = row_data["phone number"]
                 # skip invalid numbers
                if not number or number.lower() == "none" :
                    print(f"Skipping the row index : {idx}. it has no valid number")
                    continue


                print("Number ", number , type(number))
                if not number.startswith("+"):
                    number = "+" + number
            
                try:
                    kwargs_data ={"body_content" : payload.get("sms_content") , "customer_num":number }  
                    response = self.send_twilio_sms(**kwargs_data)
                    if response =="success":
                        data_dict ={"Phone Number": number , "status":True}
                        res_data.append(data_dict)
                    else:
                        data_dict ={"Phone Number": number , "status":False}
                        res_data.append(data_dict)
                       
                except TwilioException  as e:
                    return Response({
                        "message": f" error occur |: {str(e)}",
                        "status": 500
                    },status=500)
                
            return Response({
                "message": "success",
                "data": pd.DataFrame(res_data),
                "status" : 200

            }, status=200)
        
        except Exception  as e:
            import sys
            exc_type , exc_obj , exc_tb = sys.exc_info()
            return Response({
                "message": f" error occur |: {str(e)} in line no : {exc_tb.tb_lineno}",
                "status": 500
            },status=500)