from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from datetime import datetime , timedelta, date


# Import python packages
import os 
import jwt
import sys
import pandas as pd
import torch
import numpy as np
from fuzzywuzzy import fuzz


# import Project files
from .response import *
from .models import *
from .utils import *
from .product_structure import *
from .tax_structure import *
from .profit_margin_predict import *
from .ceo_worker import *
from sentence_transformers import SentenceTransformer , util
from django.contrib.auth.hashers import make_password   , check_password
from SearchMind.settings import *
import requests
from .spello_train_model import *

from dotenv import load_dotenv
load_dotenv()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Load model once (GLOBAL)
SENTENCE_MODEL = None
TRANSFER_MODEL_PATH = os.path.join(os.getcwd(), "transfer_model", "all-MiniLM-L6-v2")

try:
    SENTENCE_MODEL = SentenceTransformer(TRANSFER_MODEL_PATH)
    SENTENCE_MODEL = SENTENCE_MODEL.to(device)
    print("SentenceTransformer model loaded successfully")
except Exception as e:
    print(f"❌ Model loading failed: {e}")
    SENTENCE_MODEL = None

# use in both tax and ceo worker semantic search api
TAX_CEO_WORKER_SIMILARITY = round(float(os.getenv("TAX_CEO_WORKER_SIMILARITY", 0.5)), 2)
TAX_CEO_WORKER_YEAR_SIMILARITY = round(float(os.getenv("TAX_CEO_WORKER_YEAR_SIMILARITY", 0.5)), 2)


# GET TOP_N MATCHED VALUE
TOP_N = int(os.getenv("TOP_N",10))

""" ###############################          Profit Margin Data    ##################################"""
# API to inference product trained model
class ProductSemanticSearchView(APIView):

    def FilterUserQuery(self , input_text: str) -> list:
        split_text = input_text.split(" ")
        unique_list = list(set(split_text))
        return unique_list
    
    # FUNCTION TO GET PRODUCT OF SINGLE USER QUERY
    def get_brand_products(self ,pickle_df, user_query: str) -> pd.DataFrame:
        try:
            # Make a copy of df
            df = pickle_df.copy()

            # Drop Duplicate Rows from the dataframe
            df = df.drop_duplicates(subset=["Brand", "Product Name", "Product Type", "Category", "Production Year"])

            # Normalize Brand Column
            df['Brand'] = df['Brand'].astype(str).str.lower().str.strip()

            # Handle synonyms
            if user_query.lower().strip() in ['apple', 'iphone']:
                user_query = "apple"
            else:
                user_query = user_query.lower().strip()

            # Check if Brand exists
            mask = df['Brand'].str.contains(user_query, case=False, na=False)
            if not mask.any():
                return ProductResponse("error", f"No products found for brand '{user_query}'")

            # Drop unnecessary columns
            drop_cols = [col for col in ["text_embedding", "brand_embedding", "text", "brand"] if col in df.columns]
            df = df.drop(columns=drop_cols, errors="ignore")

            # Get Masked DF & Sort
            masked_df = df[mask]
            sorted_df = masked_df.sort_values("Production Year", ascending=False)

            # Get Latest Matched Row
            matched_row = sorted_df.iloc[0].to_dict()

            # Extract Values
            brand_name = str(matched_row.get("Brand")).lower().strip()
            product_name = str(matched_row.get("Product Name")).lower().strip()

            # Filter same brand but different products
            filtered_df = sorted_df.loc[
                (sorted_df["Brand"].str.lower().str.strip() == brand_name) &
                (sorted_df["Product Name"].str.lower().str.strip() != product_name)
            ].sort_values("Production Year", ascending=False)

            # Select one unique product per year
            selected_rows = []
            used_products = set()

            for year, group in filtered_df.groupby("Production Year", sort=False):
                row = group.loc[~group["Product Name"].str.lower().isin(used_products)].head(1)
                if not row.empty:
                    selected_rows.append(row)
                    used_products.add(row["Product Name"].iloc[0].lower())

            if not selected_rows:
                return ProductResponse("error", f"No alternative products found for '{user_query}'")

            filtered_unique = (
                pd.concat(selected_rows)
                .sort_values("Production Year", ascending=False)
                .reset_index(drop=True)
            )

            # Format output
            filtered_unique["Brand"] = filtered_unique["Brand"].str.title()
            if len(filtered_unique) > 4:
                filtered_unique = filtered_unique.iloc[0:4]

            return filtered_unique

        except Exception as e:
            exc_type , exc_obj , exc_tb = sys.exc_info()
            error_message = f"[ERROR] failed to get Products for matched single category , error is : {str(e)} in line no : {exc_tb.tb_lineno}"
            return error_message

    def FilterMatchedRow_AndParameter(self, Embedding_df, Profit_Obj, global_search_obj, device_type, payload, FilterYear):
        
        # Call function to get matched row data based on the user query
        paramter_dict , matched_row_data_dict = Profit_Obj.GetMatchedRow_AndParameter(FilterYear , Embedding_df)     # Get matched row parameter dict

        # If searched data is not exist for filter year
        if paramter_dict is None and matched_row_data_dict is None:
            return DATA_NOT_FOUND(f"No Data Exist for Year : {FilterYear}")

        # create a dataframe from matched row data dict
        searched_df = pd.DataFrame([matched_row_data_dict])

        # if searched dataframe is empty  return empty json 
        if searched_df.empty:
            return ProfitProductResponse("failed",[], [])

        # Remove unneccary columns from searched dataframe
        searched_df = searched_df.drop(columns=["text", 'similarity_score','brand_embedding', 'brand', "brand_similarity_score"], errors="ignore", axis=1)
        matched_row_json = searched_df.to_dict(orient="records")            # convert json into dict


        # Get Required Parameter from the Matched Dataframe
        brand_name = str(matched_row_json[0]["Brand"]).lower().strip()
        production_year = int(matched_row_json[0]["Production Year"])
        searched_product_name = matched_row_json[0]["Product Name"]
        searched_product_type = matched_row_json[0]["Product Type"]
        # ProductName = searched_product_name + searched_product_type
        ProductName = searched_product_name


        # GET CEO WORKER GAP DATA BASED ON THE PROFIT MARGIN DATA
        CEO_WORKER_JSON_DATA = global_search_obj.Filter_CeoWorker_Data(device_type ,brand_name , production_year)
       
        # Function -3
        Product_Category_df = Profit_Obj.Get_Category_based_df(paramter_dict)  

        # Return Response if only matched row dataframe is true
        if Product_Category_df.empty:
            return ProfitProductResponse("success",matched_row_json, CEO_WORKER_JSON_DATA)

        # Function -4
        Product_Yearly_df = Profit_Obj.Get_year_based_df(paramter_dict , Product_Category_df) 

        # Return Response if only matched row dataframe is true
        if Product_Yearly_df.empty:
            return ProfitProductResponse("success",matched_row_json, CEO_WORKER_JSON_DATA)

        # Function -5
        Product_Gender_df = Profit_Obj.Get_gender_based_df(paramter_dict , Product_Yearly_df) 

        if Product_Gender_df.empty:
            return ProfitProductResponse("success",matched_row_json, CEO_WORKER_JSON_DATA)

        # Function -6
        brand_product_type_list= Profit_Obj.Filter_rows_list(paramter_dict , Product_Gender_df) 

        # Function -7 
        filtered_df = Profit_Obj.Filtered_Dataframe(brand_product_type_list)

        
 

        if isinstance(filtered_df , list):
            print("-- Skipping There is no any compare data found")
            return ProfitProductResponse('success', searched_df.to_dict(orient="records"), [])

        # Drop Unneccessary columns if it filtered_df is dataframe
        if isinstance(filtered_df , pd.DataFrame) and not filtered_df.empty:
            filtered_df = filtered_df.drop(columns=["text","similarity_score", "text_embedding", "brand_embedding", "brand"],  errors="ignore")      # remove unneccessary dataframe

        #Add percentage sign
        filtered_df["Profit Margin"] = filtered_df["Profit Margin"].astype(float).map(lambda x: f"{x:.2f} %")

        # DELETE OW IF THERE IS SAME BRAND EXIST 2 TIMES
        if not filtered_df.empty:
            filtered_df = filtered_df.drop_duplicates(subset=['Brand'], keep='first', inplace=False)

        # Merge bot dataframe
        merge_df = pd.concat([searched_df , filtered_df], ignore_index=True)    # concat both dataframe  

        # Only return three product in API
        if len(merge_df) > 4:
            merge_df = merge_df.iloc[0:4]

        # call function to update product track coubnt 
        if not merge_df.empty:
            brand_name = merge_df.iloc[0]["Brand"]
            ProductName = merge_df.iloc[0]["Product Name"]

            # Get Weight from Payload
            weight = 1
            if payload.get("action") == "compare":
                try:
                    extra_weight = int(payload.get("weight", 0))
                except (TypeError, ValueError):
                    extra_weight = 0
                weight = extra_weight

            vistor_track_res = ProductSearch_Object_create_func(
                brand_name=brand_name,
                product_name=ProductName,
                tab_type=payload.get("tab_type"),
                weight=weight
            )

        json_data = merge_df.to_dict(orient="records")
        return ProfitProductResponse('success',json_data , CEO_WORKER_JSON_DATA)
   

   # Main function 
    def post(self, request, format=None):
        try:
            PROFIT_MARGIN_SIMILARITY_SCORE = os.getenv("PROFIT_MARGIN_SIMILARITY_SCORE")            # use this in produict semantic search api

            # Get threshold value from environemnt file
            if isinstance(PROFIT_MARGIN_SIMILARITY_SCORE, str):
                PROFIT_MARGIN_SIMILARITY_SCORE = round(float(PROFIT_MARGIN_SIMILARITY_SCORE),2)

            # Required Fields
            required_fields= ['query','tab_type', 'device_type']
            # Get Payload data
            payload = request.data
       

            # Handle missing field
            missing_fields = [field for field in required_fields if payload.get(field) is None  or not payload.get(field)]
            if missing_fields:
                return Response({
                    'message':f"{', '.join(missing_fields)}: key is required .",
                    'status':status.HTTP_400_BAD_REQUEST
                }, status=status.HTTP_400_BAD_REQUEST)
        
            # Handle device type value
            device_type =str(payload.get("device_type")).lower().strip()

            if device_type not in ["mobile", "desktop"]:
                return Response({
                    "message": "Invalid device type , Please choose one from them ['mobile' , 'desktop']" ,
                    "status": 400,
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create a object of gloabl search APIVIEW
            global_search_obj = GlobalSearchAPIView()

            # get payload value in parameter
            user_query = str(payload.get("query")).lower().strip()

            # Call profit margin spell corrector functions
            product_spello_obj = SpellcorrectorModelInference()
            correction_query = product_spello_obj.product_spell_corrector(user_query)

            # call function to get year from user query 
            FilterYear= get_year(correction_query)

            # Define paths
            pickle_df_path = os.path.join(os.getcwd() ,"static", "media", "EmbeddingDir", "Profit Margin" ,"profit_embedding.pkl")

            # Load model
            model = SENTENCE_MODEL
            if model is None:
                return Internal_server_response("Model not loaded")
            
            pickle_df = pd.read_pickle(pickle_df_path)

            # CALL A CLASS TO PREDICT PROFIT MARGIN DATA 
            Profit_Obj  = ProfitMarginPreidction(pickle_df, model, correction_query)

            # Handle when user has asked about only brand name
            user_query_filter_list = self.FilterUserQuery(correction_query)

            if len(user_query_filter_list)  ==1:
                
                # call function to get dataframe
                result_df = self.get_brand_products(pickle_df , user_query)

                # HANDLE IF FUNCTION RETURN ERROR
                if isinstance(result_df ,str):
                    return Internal_server_response(result_df)
                
                # HANDLE IF FUNCTION RETURN ERROR
                elif isinstance(result_df ,pd.DataFrame):
                    json_output= result_df.to_dict(orient="records")

                    CEO_WORKER_JSON_DATA=[]
                    if json_output:
                        brand_name = str(json_output[0]["Brand"]).lower().strip()
                        production_year = int(json_output[0]["Production Year"])

                        # GET CEO WORKER GAP DATA BASED ON THE PROFIT MARGIN DATA
                        CEO_WORKER_JSON_DATA = global_search_obj.Filter_CeoWorker_Data(device_type ,brand_name , production_year)

                    return ProfitProductResponse("success", json_output, CEO_WORKER_JSON_DATA)
                
            # Function -1
            Embedding_df_  = Profit_Obj.apply_embedding()            # call function to get embedding df

            # Filter out dataframe if similarity score greater than threshold Value
            Filtered_Embedding_df = Embedding_df_.loc[Embedding_df_["similarity_score"] > PROFIT_MARGIN_SIMILARITY_SCORE]  

            # Handle if there is no matched data found and return most similar product
            if Filtered_Embedding_df.empty:
                unmatched_filtered_df = Embedding_df_.loc[Embedding_df_["similarity_score"] > 0.50]  
                if unmatched_filtered_df.empty:
                    return ProfitProductResponse("No Data Matched", [], [])
                else:
                    return self.FilterMatchedRow_AndParameter(Embedding_df_, Profit_Obj, global_search_obj, device_type, payload, FilterYear)
            
            return self.FilterMatchedRow_AndParameter(Filtered_Embedding_df, Profit_Obj, global_search_obj, device_type, payload, FilterYear)
        
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            error_message = f"[ERROR] Occurred: {str(e)} (line {exc_tb.tb_lineno})"
            print(error_message)
            return Internal_server_response(error_message)


# API For get all profit margin data
class GetProfitMarginData(APIView):# #""
    def get(self,request , format=None):
        try:
            limit = int(request.GET.get("limit", 1000))
            offset = int(request.GET.get("offset", 0))


            #CSV file name
            input_csv_file_path = os.path.join(
                os.getcwd(),
                "static", "media", "Profit Data",
                "profit_margin.csv"
            )
            
            if not os.path.exists(input_csv_file_path):
                return DATA_NOT_FOUND(f"File Not Found with Name : {input_csv_file_path}")
            
            # Read csv 
            df = pd.read_csv(input_csv_file_path)
            
            # Remove Extra spaces from the column Name
            df.columns = df.columns.str.strip()

            # Drop Unneccsary columns
            if "Unnamed: 8" in df.columns:
                df = df.drop("Unnamed: 8", axis=1)

            # Replace NaN/inf values with None so JSON can handle them
            df = df.replace([np.inf, -np.inf], np.nan)   # convert inf to NaN
            df = df.where(pd.notnull(df), None)          # convert NaN to None
            
            # Rename  column Name
            df= df.rename({"Product Type": "Type"}, axis=1)

            df = df.dropna(subset=['Product Name']) 
            df.drop_duplicates(inplace=True) # Remove duplicacy from dataframe

            # PAGINATION SLICE
            total_count = len(df)
            df_paginated = df.iloc[offset: offset + limit]

            # convert data into json
            json_data = df_paginated.to_dict(orient="records")

            return Response({
                "status": 200 if json_data else 404,
                "count": total_count,
                "limit": limit,
                "offset": offset,
                "results": json_data
            })

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            error_message = f"Failed to get profit margin data,  error occur: {str(e)} in (line {exc_tb.tb_lineno})"
            return Internal_server_response(error_message)


""" ###############################          Tax Avenue Data    ##################################"""
# API to inference Tax trained model
class TaxSemanticSearchView(APIView):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Function to get most matched query 
    def GetMatchedRowDict(self , model , user_query: str ,Input_df : pd.DataFrame, similarity_score : float) -> dict:
        try:
            df =Input_df.copy()

            # Remove dupicate rows
            df = df.drop_duplicates(subset=["Company Name", "Year"])
            query_embedding = model.encode(user_query, convert_to_tensor=True).to(self.device)

            # Convert all full Text  embeddings to tensor
            tax_embeddings = [torch.tensor(e).to(self.device) for e in df['tax_text_embedding']]
            tax_embedding_tensor = torch.stack(tax_embeddings)

            # Cosine similarity on full Text
            fullText_similarities = util.cos_sim(query_embedding, tax_embedding_tensor)[0].cpu().numpy()
            df['tax_similarity'] = fullText_similarities

            # SORT VALUES 
            embedding_df = (df.sort_values('tax_similarity', ascending=False).head(TOP_N))

            # Filter Dataframe based on the threshold value
            matched_row = embedding_df.loc[embedding_df["tax_similarity"].idxmax()]
            filtered_df = embedding_df.loc[embedding_df["tax_similarity"].astype(float) >= similarity_score]

            if filtered_df.empty:
                # Clean matched text before searching
                clean_query = re.sub(r"\s+", " ", user_query.strip().lower())
                normalized_matched = embedding_df["text"].astype(str).str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
                mask = normalized_matched.str.contains(re.escape(clean_query), case=False, na=False)

                if mask.any():
                    matched_row = embedding_df[mask]
                    matched_row_data = matched_row.to_dict(orient="records")[0]
                    return matched_row_data
                return []
            
            matched_row = filtered_df.loc[filtered_df["tax_similarity"].idxmax()]
            matched_row_data = matched_row.to_dict()

            return matched_row_data

        except Exception as e:
            exc_type , exc_obj , exc_tb = sys.exc_info()
            error_message = f"[ERROR] Failed to get matched row from dataframe error is : {str(e)} in line no : {exc_tb.tb_lineno}"
            return error_message

    def post(self , request , format=None):
        try:
            # Get User query from POST Request
            required_fields= ['query','tab_type']
            
            # Get payload data 
            payload = request.data

            # Handle missing data 
            missing_fields = [field for field in required_fields if payload.get(field) is None  or not payload.get(field)]
            if missing_fields:
                return Response({
                    'message':f"{', '.join(missing_fields)}: key is required .",
                    'status':status.HTTP_400_BAD_REQUEST
                })
            
            # Take Payload query value in parameter
            user_query = payload.get("query")

            # Call Tax spell corrector functions
            product_spello_obj = SpellcorrectorModelInference()
            correction_query = product_spello_obj.tax_spell_corrector(user_query)

            # Define paths
            tax_embedding_df_path = os.path.join(os.getcwd(),"static", "media",  "EmbeddingDir", "Tax", "tax_embedding.pkl")
            
            # Load model
            model = SENTENCE_MODEL
            if model is None:
                return Internal_server_response("Model not loaded")

            # Reaf full model and save mode
            df = pd.read_pickle(tax_embedding_df_path)
            original_df = df.copy()

            # Call function to get year status from  the user query ...
            FilterYear= get_year(correction_query)
            
            if FilterYear != "None":
                
                # Filter datfarame based on the year
                filtered_df = df.loc[df["Year"].astype(int) == int(FilterYear)]

                if filtered_df.empty:
                    return DATA_NOT_FOUND(f"No Data Exist for Year : {FilterYear}")
                
                # call function to get most similar row
                MatchedRow = self.GetMatchedRowDict(model , correction_query , filtered_df, TAX_CEO_WORKER_YEAR_SIMILARITY)

                # RETURN BAD RESPONSE IF MATCHED ROW VARIABLE GET STING ERROR MESSAGE
                if isinstance(MatchedRow , str):
                    return Internal_server_response(MatchedRow)
                
                # RETURN SUCCESS RESPONSE IF MATCHED ROW IS DICT
                elif isinstance(MatchedRow , dict):

                    # Get matched row data 
                    matched_company_name = MatchedRow.get("Company Name")
                    matched_year = MatchedRow.get("Year")
                    product_name = f"{matched_company_name} {matched_year}"

                    # call function to update product track coubnt 
                    vistor_track_res = ProductSearch_Object_create_func(matched_company_name , product_name , payload.get("tab_type"))
                
                    serached_df = pd.DataFrame([MatchedRow])
                    
                    serached_df = serached_df.drop(columns=["tax_similarity", "tax_text_embedding", "text"], axis=1)
                    
                    return ProductResponse("success",serached_df.to_dict(orient="records"))
                
                # IF THERE IS NO DATA RETURN DATA NOT FOUND RESPONSE
                else:
                    return DATA_NOT_FOUND('DATA NOT FOUND')
              
            else:
                
                # Add new column
                MatchedRow = self.GetMatchedRowDict(model , correction_query , df , TAX_CEO_WORKER_SIMILARITY)
                  
                # RETURN BAD RESPONSE IF MATCHED ROW VARIABLE GET STING ERROR MESSAGE
                if isinstance(MatchedRow , str):
                    return BAD_RESPONSE(MatchedRow)
                
                # RETURN SUCCESS RESPONSE IF MATCHED ROW IS DICT
                elif isinstance(MatchedRow , dict):

                    CompanyName = str(MatchedRow.get("Company Name")).lower().strip()

                    # call function to update product track coubnt 
                    vistor_track_res = ProductSearch_Object_create_func(CompanyName.title() , CompanyName.title() , payload.get("tab_type"))

                    # FILTERED DATAFRAME BASED ON THE COMPANY NAME
                    filtered_df = original_df.loc[original_df["Company Name"].astype(str).str.lower().str.strip() == CompanyName]

                    # DROP COLUMNS
                    filtered_df = filtered_df.drop(columns=["text", "tax_text_embedding"]).reset_index(drop=True)

                    # SORT DATAFRAME BASED ON THE YEAR COLUMN
                    sorted_df = filtered_df.sort_values(by="Year" , ascending=False)

                    # IF LENGTH OF THE SORTED DATAFRAME GET ONLY FIRST 4 ROWS
                    if len(sorted_df) > 4:
                        sorted_df = sorted_df.iloc[0:4]

                    return ProductResponse("success",sorted_df.to_dict(orient="records"))
                
                
                # IF THERE IS NO DATA RETURN DATA NOT FOUND RESPONSE
                else:
                    return DATA_NOT_FOUND('DATA NOT FOUND')


        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            error_message = f"[ERROR] Occur Reason: {str(e)} (line {exc_tb.tb_lineno})"
            return Internal_server_response(error_message)

# API For get all Tax Avenue data
class TaxAvenueView(APIView):
    def get(self, request):
        try:
            
            limit = int(request.GET.get("limit", 1000))
            offset = int(request.GET.get("offset", 0))

            # Get Data from Tax model
            tax_csv_file_path = os.path.join(
                os.getcwd(),
                "static", "media" , "Tax Data",
                'Tax_Avoidance.csv',
                )
            
            if not os.path.exists(tax_csv_file_path):
                return DATA_NOT_FOUND(
                    "File Not Found with Name : %s",
                    tax_csv_file_path,
                    )
            
            # Read CSV
            df = pd.read_csv(tax_csv_file_path)

            # Remove Extra spaces from the column Name
            df.columns = df.columns.str.strip()

            # Clean NaN and infinity values
            if not df.empty:
                df = df.dropna(how="all")

            # PAGINATION SLICE
            total_count = len(df)
            df_paginated = df.iloc[offset: offset + limit]

            json_data = df_paginated.to_dict(orient="records") if not df.empty else []

            return Response({
                "status" :200 if json_data else 404, 
                "count": total_count,
                "limit": limit,
                "offset": offset,
                "data": json_data
                })

        except Exception as e:
            exc_tb = sys.exc_info()[2]
            error_message = f"[ERROR] Failed to get Tax Data error is {str(e)} in line {exc_tb.tb_lineno})"
            return Internal_server_response(error_message)

""" ###############################          CEO Worker Frontline Data    ##################################"""

# API to inference CEO Worker  data
class CEOWorkerSemanticSearchView(APIView):
    CEO_WORKER_SIMILARITY =0.50           # Do it for only ceo gap search data 
 
    def clean_query_string(self,text):
        import re
        text = re.sub(r"[^a-zA-Z0-9 ]", " ", text)   # remove everything except letters/numbers/spaces
        text = re.sub(r"\s+", " ", text)
        # return text.replace(" ", "").lower().strip()
        return text.lower().strip()

    def search_res(self, df, user_query, filter_year, tab_type):

        matched_row = None

        # Find first exact or partial match in text column
        for idx, record in df.iterrows():
            all_text = str(record.get("text", "")).lower().strip()
            if user_query.lower() in all_text or user_query.lower() == all_text:
                matched_row = record
                break

        print("matched_row ",matched_row)

        # If no match found, return default response
        if matched_row is None:
            track_res_dict = ProductSearch_Object_create_func("Unknown", "Unknown", str(tab_type).title())
            return {"status": False, "matched_row": None}

        # Convert row to dict
        res_dict = matched_row.to_dict()

        # Track product search count
        track_res_dict = ProductSearch_Object_create_func(
            str(res_dict.get("Company Name")).title(),
            str(res_dict.get("CEO Name")).title(),
            str(tab_type).title()
        )

        # Remove unnecessary columns
        for key in ["tax_text_embedding", "text", "tax_similarity"]:
            res_dict.pop(key, None)

        # Filter dataframe based on company, CEO, and optionally year
        filtered_df = df[df["Company Name"] == res_dict.get("Company Name")]
        if filter_year and str(filter_year) != "None":
            filtered_df = filtered_df[
                (filtered_df["CEO Name"] == res_dict.get("CEO Name")) &
                (filtered_df["Year"] == res_dict.get("Year"))
            ]

        # Sort by year descending and limit to 4 rows
        if not filtered_df.empty and len(filtered_df) > 4:
            filtered_df = filtered_df.sort_values(by="Year", ascending=False).head(4)
            filtered_df = filtered_df.drop(columns=["text", "tax_text_embedding"], errors="ignore").reset_index(drop=True)
            return {
                "status": True,
                "matched_row": filtered_df.to_dict(orient="records")}
        
        return {"status": True, "matched_row": res_dict}


    def post(self, request, format=None):
        try:
            required_fields = ['query', 'tab_type', 'device_type']
            payload = request.data

            # Check missing fields
            missing_fields = [f for f in required_fields if not payload.get(f)]
            if missing_fields:
                return Response({
                    "message": f"{', '.join(missing_fields)}: key is required.",
                    "status": status.HTTP_400_BAD_REQUEST
                }, status=status.HTTP_400_BAD_REQUEST)

            device_type = str(payload.get("device_type")).lower().strip()
            if device_type not in ["mobile", "desktop"]:
                return Response({
                    "message": "Invalid device type. Choose from ['mobile', 'desktop'].",
                    "status": 400
                }, status=status.HTTP_400_BAD_REQUEST)

            user_query = self.clean_query_string(payload.get("query"))

            # Paths to embeddings
            embedding_base_path = os.path.join(os.getcwd(), "static", "media", "EmbeddingDir", "CEO-Worker")
            df_path = os.path.join(embedding_base_path, f"ceo_{device_type}_embedding.pkl")

            # Load dataframe
            df = pd.read_pickle(df_path)
            rename_map = {
                "mobile": {'phone_text_embedding': 'tax_text_embedding', 'phone_text': 'text'},
                "desktop": {'desktop_text_embedding': 'tax_text_embedding', 'desktop_text': 'text'}
            }
            df = df.rename(columns=rename_map[device_type])
            df = df.drop(columns=["Unnamed: 0"], errors="ignore").drop_duplicates(subset=["Company Name", "Year", "CEO Name"])

            # Copy original dataframe for searching
            original_df = df.copy()

            # Extract year from query
            filter_year = get_year(user_query)

            # Initialize semantic search model
            # Load model
            model = SENTENCE_MODEL
            if model is None:
                return Internal_server_response("Model not loaded")
            
            tax_obj = TaxSemanticSearchView()

            # Search in dataframe
            result_data = self.search_res(original_df, user_query, filter_year, payload.get("tab_type"))


            # If no exact match, use semantic similarity search
            if not result_data["status"]:
                if filter_year != "None":
                    df = df[df["Year"].astype(int) == int(filter_year)]
                    if df.empty:
                        return DATA_NOT_FOUND(f"No Data Exist for Year: {filter_year}")

                result_data = tax_obj.GetMatchedRowDict(model, user_query, df, CEOWorkerSemanticSearchView.CEO_WORKER_SIMILARITY)

                if not result_data:
                    return DATA_NOT_FOUND("Data Not Found")

                # Remove unnecessary keys
                for key in ["tax_text_embedding", "text", "tax_similarity"]:
                    result_data.pop(key, None)

            # Prepare response
            json_data = result_data.get("matched_row") if "status" in result_data else result_data

            if "Pay Ration" in json_data:
                json_data['Pay Ration'] = json_data['Pay Ration'].replace(',', '')

            if "Pay Ratio" in json_data:
                json_data['Pay Ration'] = json_data['Pay Ration'].replace(',', '')

            return Response({
                "status": 200,
                "message": "success",
                "data": json_data if isinstance(json_data, list) else [json_data],
                # "product_track_result": track_json_data
            }, status=200)

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            error_message = f"[ERROR] Occur Reason: {str(e)} (line {exc_tb.tb_lineno})"
            return Internal_server_response(error_message)

# API For get CEO Worker data
class CeoWorkerView(APIView):
    def get(self, request):
        try:

            limit = int(request.GET.get("limit", 1000))
            offset = int(request.GET.get("offset", 0))

            device_type = request.GET.get("device")
            
            # SET DEFAULT VALUE OF TAB TYPE
            if not device_type:
                device_type="desktop"

            # Decide key & file based on device
            if device_type == "mobile":
                file_name = "Phone_Tablet.csv"
            else:
                file_name = "Website.csv"
            

            # Load CSV
            file_path = os.path.join(
                os.getcwd(), 
                "static", "media", "CEO Worker Data", 
                file_name
            )

            df = pd.read_csv(file_path)

            # PAGINATION SLICE
            total_count = len(df)
            df_paginated = df.iloc[offset: offset + limit]

            json_data = df_paginated.to_dict(orient="records") if not df.empty else []

            return Response({
                "status" :200 if json_data else 404, 
                "count": total_count,
                "limit": limit,
                "offset": offset,
                "data": json_data,
                })
          
            
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            error_message = f"Failed to get CEO worker Data,  error occur: {str(e)} in (line {exc_tb.tb_lineno})"
            return Internal_server_response(error_message)
        

"""                 #######################          CSV RELATED API's              ###########################################               """
# Use Django SECRET_KEY or define a custom one
class AdminAuthenticationView(APIView):
    def post(self, request, format=None):
        raw_password = request.data.get('password')

        if not raw_password:
            return Response(
                {
                    'message': "Password is required.",
                    'status': status.HTTP_400_BAD_REQUEST
                }
            )

        admin_obj = AdminAuthenticationModel.objects.first()
        if not admin_obj:
            return Response({"message": "Admin not found", "status": 400})

        if not check_password(raw_password, admin_obj.password):
            return Response({"message": "Incorrect Password", "status": 400})

        # Payload for JWT
        payload = {
            "admin_id": admin_obj.id,
            "exp": datetime.utcnow() + timedelta(minutes=int(os.getenv("SESSION_EXPIRE_TIME"))),  # expires in 30 min
            "iat": datetime.utcnow()
        }

        secret_key = os.getenv("SECRET_KEY", "default_secret")  # fallback
        algorithm = os.getenv("ALGORITHM", "HS256")

        token = jwt.encode(payload, secret_key, algorithm=algorithm)

        # If jwt.encode returns bytes (older PyJWT)
        if isinstance(token, bytes):
            token = token.decode("utf-8")

        return Response({
            "message": "Login Successfully...",
            "status": 200,
            "token": token
        })

# API to validate token 
class TokenProtectedView(APIView):
    def get(self, request, *args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return Response({"error": "No token provided"}, status=status.HTTP_401_UNAUTHORIZED)

        # Remove "Bearer " prefix if present
        if token.startswith("Bearer "):
            token = token.split(" ")[1]

        validation = validate_token(token)

        if not validation["valid"]:
            return Response({"error": validation["error"]}, status=status.HTTP_401_UNAUTHORIZED)

        return Response({"message": "Token is Valid", "payload": validation["payload"]},  status=status.HTTP_202_ACCEPTED)


# APi to get product Visitor Track count data
class TrackProductSearchCount(APIView):
    def get(self,request):
        try:

            date_str = request.GET.get("date")

            Product_Data_obj = ProductSearchTrack.objects.all().values()

            if not Product_Data_obj:
                return DATA_NOT_FOUND("No data found .")
            
            df = pd.DataFrame(list(Product_Data_obj))

            df.columns = df.columns.str.lower().str.strip()

            # convert string data into lower case
            for col in df.columns:
                if pd.api.types.is_string_dtype(df[col]):
                    df[col] = df[col].str.lower().str.strip()
            
            df["brand_name"] = df["brand_name"].str.title()
            df["product_name"] = df["product_name"].str.title()

            # Convert to datetime
            df["created_at"] = pd.to_datetime(df["created_at"])
            df["date_only"] = df["created_at"].dt.date

            # GET ALL TIME PRODUCT SEARCH COUNT
            df["search_count"] = pd.to_numeric(df["search_count"], errors="coerce").fillna(0)
            ALL_TIME_TOTAL_PRODUCT_SEARCH = df["search_count"].sum()

            # FILTER DATAFRAME BASED ON THE INPUT DATE
            df = df.loc[df["date_only"].astype(str) == str(date_str)]
            df = df.drop(columns=["created_at","updated_at", "date_only"], axis=1)

            total_visits = df["search_count"].sum()
            
            # GROUPED DATAFRAME
            grouped = df.groupby('tab_type').agg({'search_count': 'sum'}).to_dict(orient='index')
            result_data = {tab: {'search_count': data['search_count']} for tab, data in grouped.items()}

            return Response(
                {
                "message": f"No Data Found for Date : {date_str}" if df.empty else f"Data get successfully of date : {date_str}" ,
                "status": status.HTTP_200_OK,
                "all_product_total_search_count": ALL_TIME_TOTAL_PRODUCT_SEARCH,
                "per_day_total_search": total_visits,
                "data": result_data
                }
            )
        
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            error_message = f"Failed to get profit margin data,  error occur: {str(e)} in (line {exc_tb.tb_lineno})"
            return Internal_server_response(error_message)


class AnalysisTable(APIView):
    def get(self,request):
        try:

            date_str = request.GET.get("date")

            Product_Data_obj = ProductSearchTrack.objects.all().values().order_by('-updated_at')

            if not Product_Data_obj:
                return DATA_NOT_FOUND("No data found .")
            
            df = pd.DataFrame(list(Product_Data_obj))

            
            df["brand_name"] = df["brand_name"].str.title()
            df["product_name"] = df["product_name"].str.title()

            # Convert to datetime
            df["created_at"] = pd.to_datetime(df["created_at"])
            df["date_only"] = df["created_at"].dt.date

            df = df.loc[df["date_only"].astype(str) == str(date_str)]
            df = df.drop(columns=["created_at","updated_at", "date_only"], axis=1)

            total_visits = df["search_count"].sum()
           
            # grouped = df.groupby('tab_type').apply(lambda group: group.to_dict(orient='records')).to_dict()
         
            return Response({
                "message": f"No Data Found for Date : {date_str}" if df.empty else f"Data get successfully of date : {date_str}" ,
                "status": status.HTTP_200_OK,
                "total_search": total_visits,
                "data": df.to_dict(orient="records"),
                # "data": grouped
            })
        
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            error_message = f"Failed to get profit margin data,  error occur: {str(e)} in (line {exc_tb.tb_lineno})"
            print(error_message)
            return Internal_server_response(error_message)


# Api for Track Visiotor count
class TrackVisitorCount(APIView):
    def post(self , request , format= None):
        try:
            message= "Visitor visited again today."
            user_browser_id = request.data.get("browser_id")
            if not user_browser_id:
                return BAD_RESPONSE(f"Browser ID is required , please send id with using key : 'browser_id'. ")
            
            # function to track vistor count 
            current_date = datetime.now().date()

            # Get or create object
            track_visitor_ob = VistorTrackCountModel.objects.filter(
                user_browser_id=user_browser_id).first()

            # If user does not exisy in table
            if not track_visitor_ob:
                VistorTrackCountModel.objects.create(
                    user_browser_id=user_browser_id,
                    created_date=current_date,
                    total_visit_count= 1,
                    daily_visit_count = 1,
                    visit_date = current_date ,
                )
                message = "New visitor added."

            # if user exist in database and visit again 
            # update if visit date is not same day
            elif track_visitor_ob.visit_date != current_date :
                track_visitor_ob.visit_date  = current_date
                track_visitor_ob.total_visit_count  += 1
                track_visitor_ob.daily_visit_count  = 1
                track_visitor_ob.save()
                message = "Visitor returned on a new day."


            return Response({
                "message": message,
                "status": status.HTTP_200_OK
            },status=status.HTTP_200_OK)

        except Exception as e:
            exc_type , exc_obj , exc_tb = sys.exc_info()
            error_message = f"[ERROR] Failed to create track  visitor count  Record, error ocuur : {str(e)} in line no : {exc_tb.tb_lineno}"
            return Internal_server_response(error_message)

# API FOR GET TRACK VISTOR BASED ON DATE
class GetVistorView(APIView):
    def get(self,format=None):
        try:
            queryset = VistorTrackCountModel.objects.all().values()
            # If data not found
            if not queryset:
                return Response({
                    "message": "Data Not Found",
                    "status": 400
                }, status=400)

            # Create dataframe
            df = pd.DataFrame(list(queryset))
            total_visits = df["total_visit_count"].sum()

            # Get Today's Visitors
            today = date.today() 

            todays_visitiors = 0
            df['visit_date'] = pd.to_datetime(df['visit_date']).dt.date
            filtered_df = df[df['visit_date'] == today]
            if not filtered_df.empty:
                todays_visitiors = filtered_df["daily_visit_count"].sum()

            return Response({
                "message":"Data get successfully",
                "status": 200,
                "today_date":today , 
                "total_visit_count": total_visits,
                "total_todays_visit_counts": todays_visitiors
            }, status=200)

        except Exception as e:
            exc_type , exc_obj , exc_tb = sys.exc_info()
            error_message = f"[ERROR] Failed to get track  visitor count data, error ocuur : {str(e)} in line no : {exc_tb.tb_lineno}"
            return Internal_server_response(error_message)


"""     ###################################           GLOBAL API'S                    ###############################       """
class GlobalSearchAPIView(APIView):

    def find_best_matching_client(self,brand_name, data, threshold=50):
        """
        Find the single best matching client based on highest fuzzy score.

        Args:
            brand_name (str): Name to search
            data (list): List of client records (dict)
            threshold (int): Minimum acceptable score

        Returns:
            dict or None: Best matching record with score
        """

        best_match = None
        best_score = 0

        if not brand_name or not isinstance(data, list):
            return None

        client_name_clean = brand_name.lower().strip()

        for compan_name in data:
            tax_company_name = compan_name.lower().strip()

            if not tax_company_name:
                continue

            tax_company_name_clean = tax_company_name.lower().strip()

            
            score = fuzz.token_sort_ratio(client_name_clean, tax_company_name_clean)

            if score >= threshold and score > best_score:
                best_score = score
                best_match = tax_company_name

        return best_match if best_match else None


    # function to filter tax data based on the brand name and year
    def Filter_Tax_Data(self,brand_name: str , year: int)-> list:
        # Tax Embedding DF Path
        tax_embedding_df_path = os.path.join(os.getcwd(),"static" , "media",  "EmbeddingDir", "Tax", "tax_embedding.pkl")
        tax_df = pd.read_pickle(tax_embedding_df_path)

        # USE FUZZ RATION
        tax_company_name_list = tax_df["Company Name"].unique().tolist()
        fuzz_ration_brand_name = self.find_best_matching_client(brand_name , tax_company_name_list)

        # Filtered Df
        filtered_tax_df = tax_df.loc[
            (tax_df["Company Name"].astype(str).str.lower().str.strip().str.contains(brand_name, case=False, regex=False))&
            (tax_df["Year"].astype(int) == year)
        ]  

        # FALLBACK 
        if filtered_tax_df.empty and  fuzz_ration_brand_name is not None:
            filtered_tax_df = tax_df.loc[
                (tax_df["Company Name"].astype(str).str.lower().str.strip().str.contains(fuzz_ration_brand_name, case=False , regex=False))&
                (tax_df["Year"].astype(int) == year)
            ] 

        # Drop Unneccessary columns
        filtered_tax_df = filtered_tax_df.drop(columns=['tax_text_embedding','text'],axis=1)

        # Convert into json
        json_output = filtered_tax_df.to_dict(orient="records")
        if json_output:
            json_output= json_output[0]

        return json_output
    
    # function to filter ceo worker data based on the brand name and year
    def Filter_CeoWorker_Data(self,device_type : str ,brand_name: str , year: int)-> list:
        
        # CEO Worker  Embedding DF Path
        Ceo_worker_tablet_csv_path= os.path.join(os.getcwd(),"static" , "media", "CEO Worker Data", "Phone_Tablet.csv")
        Ceo_worker_website_path = os.path.join(os.getcwd(), "static" , "media" ,"CEO Worker Data","Website.csv")

        # Read CSV
        tablet_df = pd.read_csv(Ceo_worker_tablet_csv_path)
        website_df = pd.read_csv(Ceo_worker_website_path)

        # Take Empty dataframe
        df = pd.DataFrame()
        if device_type =="mobile":
            df = tablet_df
        else:
            df = website_df
        
        # USE FUZZ RATION
        tax_company_name_list = df["Company Name"].unique().tolist()
        fuzz_ration_brand_name = self.find_best_matching_client(brand_name , tax_company_name_list)

        #Filtered Df
        filtered_ceo_worker_df = df.loc[
            (df["Company Name"].str.lower().str.strip() == brand_name)&
            (df["Year"].astype(int) == year)
        ]   
        
        # FALLBACK 
        if filtered_ceo_worker_df.empty and  fuzz_ration_brand_name is not None:
            filtered_ceo_worker_df = df.loc[
                (df["Company Name"].astype(str).str.lower().str.strip().str.contains(fuzz_ration_brand_name, case=False, regex=False))&
                (df["Year"].astype(int) == year)
            ] 

        # Convert into json
        json_output = filtered_ceo_worker_df.to_dict(orient="records")
        return json_output


    def post(self,request, format=None):
        try:
            # Get Query from User
            required_field =["query", "device_type", 'target_year']

            # get payload
            payload = request.data
            missing_fields = [ field for field in required_field if payload.get(field) is None or not payload.get(field)]
            
            if missing_fields:
                return Response({
                    "message": f'{", ".join(missing_fields)} key is required. ',
                    "status": 400,
                }, status=status.HTTP_400_BAD_REQUEST)
            

            device_type =str(payload.get("device_type")).lower().strip()
            

            if device_type not in ["mobile", "desktop"]:
                return Response({
                    "message": "Invalid device type , Please choose one from them ['mobile' , 'desktop']" ,
                    "status": 400,
                }, status=status.HTTP_400_BAD_REQUEST)

            # Handle target year 
            target_year =payload.get("target_year")
            if target_year =="null":
                target_year = ""
            
            else:
                target_year = str(target_year)

            # concate user query with target year
            user_query = payload.get("query") + " " + target_year
          
            # Get weight from request (default = 1)
            weight = payload.get("weight", 1)
            try:
                weight= int(weight)
            except Exception:
                weight=1

            #Safetly Clamp (prevent spam)
            if weight < 1:
                weight = 1
            if weight > 10:
                weight = 10

            #payload data
            data = {
                "query": user_query,
                "tab_type": "profit",
                "device_type": device_type,
                "weight":weight,
                "action": payload.get("action", "")
            }
            
            headers = {
                "content_type": "application/json"
            }

            # API URL
            url = f"{BASE_URL}/product-semantic-search"

            response = requests.post(url , json= data , headers=headers)
            
            # Get response Text.
            response_text = response.text

            # Handle if output json type is string
            if isinstance(response_text , str):
                import ast
                response_text = ast.literal_eval(response_text)

            # Check if response status is 200
            if response.status_code ==200:
                # Get data response
                response_status = response_text["status"]
                if response_status == 200:
                    
                    # Get json data 
                    json_data = response_text["data"]

                    # check if json data length is true
                    if len(json_data) > 0:

                        # get first matched data row
                        matched_row = json_data[0]

                        Brand_name = str(matched_row["Brand"]).lower().strip()# Brand name
                        Year = int(matched_row["Production Year"]) # Year

                        # Filter OUT Tax Data
                        tax_data_json = self.Filter_Tax_Data(Brand_name, Year)
                        ceo_worker_data = self.Filter_CeoWorker_Data(device_type ,Brand_name, Year)

                        return Response({
                            "message": "success",
                            "status": 200,
                            "data": response_text["data"],
                            "tax_data": tax_data_json if tax_data_json else [],
                            "ceo_worker_data": ceo_worker_data if ceo_worker_data else []

                        })

                    # Return bad response if no data found
                    else:
                        return Response({
                            "message": "Data not found",
                            "status": 404
                        }, status=status.HTTP_404_NOT_FOUND)
                    
                else:
                    return Response({
                        "message": response_text["message"],
                        "status": response_status
                    }, status=response_status)
            
            # Handle if response status is 404 
            elif response.status_code ==404:
                return Response({
                        "message": response_text["message"],
                        "status": response_text["status"]
                    }, status=response_text["status"])

            else :
                return Response({
                    "message": 'Getting issue in product semantic search api'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            exc_type , exc_obj , exc_tb = sys.exc_info()
            error_message = f"[ERROR] , Failed to Read Gloabl search Query, error occur is : {str(e)} in line no : {exc_tb.tb_lineno}"
            print(error_message)
            return error_message

# APi for send file url
class DataFilesSync(APIView):
   def get(self, request, format=None):
        try:
            base_path = os.path.join(os.getcwd(), "static", "media")

            # Define your files (exclude Profit Data)
            files = [
                ("Profit Data", "profit_margin.csv"),   # keep only cleaned version
                ("Tax Data", "Tax_Avoidance.csv"),
                ("CEO Worker Data", "Phone_Tablet.csv"),
                ("CEO Worker Data", "Website.csv"),
            ]

            file_list = []

            for folder, filename in files:
                file_path = os.path.join(base_path, folder, filename)

                # Special handling for profit_margin.csv
                if filename == "profit_margin.csv":

                    profit_df = pd.read_csv(file_path)
                    profit_df = profit_df.loc[:, ~profit_df.columns.str.contains("^Unnamed")]

                    # Drop Product Type column if present
                    if "Product Type" in profit_df.columns.str.strip():
                        profit_df = profit_df.drop("Product Type", axis=1)

                    # Reorder data frame
                    ordered_column = ["Brand", "Product Name", "Category", "Gender", "Production Year","Link to Product Pictures" ,"Release Price", "Profit Made",  "Profit Margin"]
                    profit_df_ordered = profit_df[ordered_column]

                    # Ensure Download Data folder exists
                    download_base_dir = os.path.join(base_path, "Download Data")
                    os.makedirs(download_base_dir, exist_ok=True)

                    # Save cleaned file
                    download_profit_margin_file_path = os.path.join(download_base_dir, "profit_margin.csv")
                    if os.path.exists(download_profit_margin_file_path):
                        os.remove(download_profit_margin_file_path)

                    profit_df_ordered.to_csv(download_profit_margin_file_path, index=False)

                    # Use cleaned file path for URL
                    file_path = download_profit_margin_file_path

                # Build file URL
                file_url = file_path.replace(os.getcwd(), BASE_URL)

                if HOST == "live":
                    file_url = file_url.replace("/static", "")

                file_list.append({
                    "filename": filename,
                    "file_url": file_url
                })
            return Response({"files": file_list, "status": 200}, status=200)


        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            error_message = f"[ERROR] Failed to load data files, error: {str(e)} in line {exc_tb.tb_lineno}"
            return Internal_server_response(error_message)


class TrainModelView(APIView):

    FILE_NAMES = ["profit_margin.csv", "Tax_Avoidance.csv", "Website.csv", "Phone_Tablet.csv"]
    TAB_TYPES = ["profit", "tax", "mobile", "desktop"]

    PRODUCT_DATA_COLUMNS = [
        "Brand", "Product Name", "Category", "Gender", "Production Year",
        "Link to Product Pictures", "Release Price", "Profit Made",
        "Profit Margin", "Product Type"
    ]

    # FUNCTION TO HANDLE FILE NAME
    def handle_file_name(self, uploaded_file, tab_type):
        if tab_type == "profit":
            expected_name = "profit_margin.csv"
            if uploaded_file.name != expected_name:
                uploaded_file.name = expected_name  

        elif tab_type == "tax":
            expected_name = "Tax_Avoidance.csv"
            if uploaded_file.name != expected_name:
                uploaded_file.name = expected_name  

        elif tab_type == "mobile":
            expected_name = "Phone_Tablet.csv"
            if uploaded_file.name != expected_name:
                uploaded_file.name = expected_name  
        
        elif tab_type == "desktop":
            expected_name = "Website.csv"
            if uploaded_file.name != expected_name:
                uploaded_file.name = expected_name  

        return uploaded_file


    # -------------------- Utility Paths --------------------
    def transfer_model_base_dir_path(self):
        path = os.path.join(os.getcwd(), "transfer_model")
        os.makedirs(path, exist_ok=True)
        return path

    def embedding_model_base_dir_path(self, tab_type):
        mapping = {
            "profit": "Profit Margin",
            "tax": "Tax",
            "mobile": "CEO-Worker",
            "desktop": "CEO-Worker"
        }
        base = mapping.get(tab_type, "Profit Margin")
        path = os.path.join(os.getcwd(), "static", "media", "EmbeddingDir", base)
        os.makedirs(path, exist_ok=True)
        return path

    def get_existing_file_path(self, tab_type):
        mapping = {
            "profit": os.path.join("Profit Data", "profit_margin.csv"),
            "tax": os.path.join("Tax Data", "Tax_Avoidance.csv"),
            "mobile": os.path.join("CEO Worker Data", "Phone_Tablet.csv"),
            "desktop": os.path.join("CEO Worker Data", "Website.csv")
        }
        return os.path.join(os.getcwd(), "static", "media", mapping[tab_type])

    def Handle_invalid_filename(self, filename, tab_type):
        if tab_type == "tax":
            return "Tax_Avoidance.csv"
        elif tab_type == "mobile":
            return "Phone_Tablet.csv"
        elif tab_type == "desktop":
            return "Website.csv"
        return "profit_margin.csv"

    # -------------------- Core Helpers --------------------
    def _normalize_for_comparison(self, df1, new_df, skip_cols):

        print("New df")

        common_cols = [c for c in df1.columns.intersection(new_df.columns) if c not in skip_cols]
        df1_cmp, new_cmp = df1.copy(), new_df.copy()

        for col in common_cols:
            if pd.api.types.is_string_dtype(df1[col]) or pd.api.types.is_string_dtype(new_df[col]):
                df1_cmp[col] = df1[col].where(df1[col].notna(), None).astype(object).map(
                    lambda x: x.lower().strip() if isinstance(x, str) else x
                )
                new_cmp[col] = new_df[col].where(new_df[col].notna(), None).astype(object).map(
                    lambda x: x.lower().strip() if isinstance(x, str) else x
                )
        return df1_cmp[common_cols], new_cmp[common_cols]

    def _merge_and_save(self, df1, df2_new, existing_file_path, tab_type):
        if not df2_new.empty:
            df2_new = df2_new.drop_duplicates(ignore_index=True)
            merged_df = pd.concat([df1, df2_new], ignore_index=True)

            if tab_type == "profit":
                merged_df = merged_df.drop_duplicates(subset=self.PRODUCT_DATA_COLUMNS, keep='first')

            merged_df.to_csv(existing_file_path, index=False)

            print(f"File updated with {len(merged_df) - len(df1)} new rows")

            return merged_df
        else:
            df1.to_csv(existing_file_path, index=False)
            print("No new rows, file saved as is")
            return df1

    def _train_model(self, tab_type, existing_file_path):
        if tab_type == "profit":
            model_response = AllProductDetailMain(
                self.embedding_model_base_dir_path(tab_type),
                self.transfer_model_base_dir_path(),
                existing_file_path
            )
            if isinstance(model_response, pd.DataFrame):
                return Response({"message": "Model Trained successfully with Profit Margin Data", "status": status.HTTP_200_OK})
            elif isinstance(model_response, list) and not model_response:
                return DATA_NOT_FOUND("No Data found for Profit Margin Data Tab")
            elif isinstance(model_response, str):
                return Internal_server_response(model_response)

        elif tab_type == "tax":
            resp = TaxMainFunc(existing_file_path, self.embedding_model_base_dir_path(tab_type), self.transfer_model_base_dir_path())
            return Response({"message": "Tax Model Train successfully ..." if resp == "success" else resp}, status=status.HTTP_200_OK)

        elif tab_type in ["mobile", "desktop"]:
            tablet_path = os.path.join(os.getcwd(), "static", "media", "CEO Worker Data", "Phone_Tablet.csv")
            website_path = os.path.join(os.getcwd(), "static", "media", "CEO Worker Data", "Website.csv")
            os.makedirs(self.transfer_model_base_dir_path(), exist_ok=True)

            resp = CeoWorkerMainFunc(tablet_path, website_path, self.embedding_model_base_dir_path(tab_type), self.transfer_model_base_dir_path())
            return Response({"status": status.HTTP_200_OK, "message": "Model Train successfully ..." if resp == "success" else resp})

    # -------------------- Main Entry --------------------
    def post(self, request, format=None):
        try:

            # Train spello models
            spello_train_obj = TrainSpelloModel()
            spello_train_obj.train_profit_margin_spell_corrector()
            spello_train_obj.train_tax_spell_corrector()
            spello_train_obj.train_paygap_spell_corrector()

            # Validate payload
            payload = request.data
            uploaded_file = request.FILES.get("file")
            tab_type = payload.get("tab_type")

            # change tab type
            if tab_type =="phone":
                tab_type = "mobile"

            # CHECK TAB TYPE
            if not tab_type:
                return BAD_RESPONSE("tab_type key is required.")
            
            # HANDLE FILE UPLOADING
            if not uploaded_file:
                return BAD_RESPONSE("Please select a file before making request, use 'file' key to upload file")
            
            # CHECK TYPE OF UPLOADE FILE
            if not check_suffix(uploaded_file):
                return FILE_NOT_ACCEPTABLE_RESPONSE("Invalid File Type, Only CSV file Accepted.")

            # CHECK TAB NAME
            if tab_type not in self.TAB_TYPES:
                return BAD_RESPONSE(f"Invalid Tab Type, Valid Tab types are {', '.join(self.TAB_TYPES)}")

            # HANDLE FILENAME
            uploaded_file = self.handle_file_name(uploaded_file ,tab_type)

            if uploaded_file.name not in self.FILE_NAMES:
                corrected_filename = self.Handle_invalid_filename(uploaded_file.name, tab_type)
                return BAD_RESPONSE(
                    f"Invalid file name. Correct file name is : {corrected_filename}",
                    )
            
            # READ UPLOADED CSV
            new_df = pd.read_csv(uploaded_file)

            # REMOVE EXTRA SPACES FROM COLUMNS NAME
            new_df.columns = new_df.columns.str.strip()

            # ADD NEW COLUMN IF DOES NOT EXIST IN DATAFRAME
            if tab_type == "profit" and "Product Type" not in new_df.columns:
                new_df["Product Type"] = new_df["Category"]

            # CHECK COLUMNS NAME
            column_status, expected_columns = check_columns(tab_type, new_df)

            if not column_status:
                return FILE_NOT_ACCEPTABLE_RESPONSE(
                    f"Columns do not match, Accepted columns list is : {expected_columns}"
                )      
                  
            # GET EXISTING FILE PATH AND READ CSV
            existing_file_path = self.get_existing_file_path(tab_type)

            df1 = pd.read_csv(existing_file_path)
            df1.columns = df1.columns.str.strip()

            if tab_type == "profit":
                df1 = df1[self.PRODUCT_DATA_COLUMNS]

            if "Wholesale Price" in df1.columns.str.strip():
                df1 = df1.drop("Wholesale Price", axis=1)

            # Compare and merge
            skip_cols = ["Link to Product Pictures", "Product Type"] if tab_type == "profit" else []

            df1_cmp, new_cmp = self._normalize_for_comparison(df1, new_df, skip_cols)

            mask = ~new_cmp.apply(tuple, axis=1).isin(df1_cmp.apply(tuple, axis=1))

            df2_new = new_df[mask].copy()

            self._merge_and_save(df1, df2_new, existing_file_path, tab_type)

            # Train model
            return self._train_model(tab_type, existing_file_path)

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            error_message = f"[ERROR] Failed to upload new data files, error: {str(e)} in line {exc_tb.tb_lineno}"
            return Internal_server_response(error_message)
