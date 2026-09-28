import sys
import os
import torch
import pandas as pd
from .models import *
from sentence_transformers import SentenceTransformer , util
from .utils import preprocess_text
from .type_mapping import *
from sklearn.preprocessing import LabelEncoder
from .response import *
le = LabelEncoder()

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

class ProductModelStructure:

    def __init__(self , csv_path):
        self.max_range = 20
        self.random_state_value = 42
        self.csv_path = csv_path
        self.device= torch.device("cuda" if torch.cuda.is_available() else "cpu")


    def DownloadUpdateModel(self , TransferModelDir):
        import os
        os.environ['HF_HOME'] = os.path.join(os.getcwd(), 'huggingface_cache')

        model_path = os.path.join(TransferModelDir, "all-MiniLM-L6-v2")

        if not os.path.exists(model_path):
            model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            model.save(model_path)

        else:
            model = SentenceTransformer(model_path)

        return model


    def DataAugmentation(self):
        print("Step 1: Data Augmentation and Create Dataframe ....")
        try:
            
            # GET PROFIT MARGIN DATA FROM THE PROFIT DATA MODEL
            df = pd.read_csv(self.csv_path)

            if df.empty :
                return []
            
            # REMOVE EXTRA SPACE FROM DATABASE
            df.columns = df.columns.str.strip()

            # REMOVE EXTRA COLUMNS FROM THE DATAFRAME
            if "id"  in df.columns.str.strip():
                df = df.drop("id", axis=1)
            
            # MAKE CORRECTION OF WHOLESALE PRICE COLUMN
            # df["Wholesale Price"] = df["Wholesale Price"].astype(str).str.replace("nan", "0")

            #Make correction of gender column 
            df["Gender"] = df["Gender"].fillna("Unisex").astype(str).str.strip()
            df["Gender"] = df["Gender"].map(gender_map).fillna("Unisex")

            # remove only rows which have no product Name
            df = df.dropna(subset=['Product Name']) 
            df.drop_duplicates(inplace=True) # Remove duplicacy from dataframe  

            #MAP dictionaries
            combined_map = {
                **makeup_variant_map,
                **skincare_variant_map,
                **bodycare_variant_map,
                **car_variant_map,
                **womens_outfit_varient_map,
                **scent_varient_map
            }
            df["Type Mapped"] = df["Product Type"].map(combined_map).fillna(df["Category"])

            # remove nan values
            df.dropna(inplace=True)
            print("dataframe size / shape ", df.shape)

            if df.empty:
                return []

            return df
        
        except Exception as e:
            exc_type , exc_obj , exc_tb = sys.exc_info()
            error_message = f"[ERROR] Failed to Data Augmentation , error occur {str(e)} in line no : {exc_tb.tb_lineno}"
            return error_message

    # function to create new column with name 'text' only used 'product name' and 'type' column .
    def preprocess_text_data(self, df):
        
        print("Step 2: Text Preprocessing is running ......")
        try:

            # make a copy of dataframe
            df = df.copy()
            
            #Add two column with different columns groups
            df["text"] = (df["Brand"] +" " + df["Product Name"] + " " +df["Product Type"] + " " +df["Production Year"].astype(str) + " " + df["Category"])
            df["brand"] = df["Brand"] 

            # Apply preprocess columns on both column
            df["text"] = df["text"].apply(preprocess_text)
            df["brand"] = df["brand"].apply(preprocess_text)
            return df
        
        except Exception as e:
            exc_type , exc_obj , exc_tb = sys.exc_info()
            error_message = f"[ERROR] Failed to Preprocess Text  , error occur {str(e)} in line no : {exc_tb.tb_lineno}"
            return error_message

    def apply_kmeans(self, df, embedding_dir_path):
        print(f"Step 3: Start to Implement Embedding on Text ........")
        try:

            # make a model path 
            transfer_model_path = os.path.join(os.getcwd(), "transfer_model", 'all-MiniLM-L6-v2')

            # Load sentence transer model
            model = SentenceTransformer(transfer_model_path)

            embeddings_full_text = model.encode(df['text'].tolist(), show_progress_bar=True)
            embeddings_sub_text = model.encode(df['brand'].tolist(), show_progress_bar=True)

            df["text_embedding"] = list(embeddings_full_text)
            df["brand_embedding"] = list(embeddings_sub_text)

            # save embedding df
            full_text_embedding_path = os.path.join(embedding_dir_path,"profit_embedding.pkl")
            df["Link to Product Pictures"] = df["Link to Product Pictures"]

            # Save dataframe on pickle file
            df.to_pickle(full_text_embedding_path)
            print( f"Full Embedding DataFrame saved to {full_text_embedding_path}")
            return df
        
        except Exception as e:
            exc_type , exc_obj , exc_tb = sys.exc_info()
            error_message = f"[ERROR] Failed to Implement Embedding , error occur {str(e)} in line no : {exc_tb.tb_lineno}"
            return error_message
        

def AllProductDetailMain(embedding_dir_path , TransferModelDir, File_path):
    try:
        product_structure = ProductModelStructure(File_path)        
        # call function to upload or run local model 
        model = product_structure.DownloadUpdateModel(TransferModelDir)

        # function to read csv and remove duplicacy and nan values
        dataframe  = product_structure.DataAugmentation()

        if isinstance(dataframe , list) or isinstance(dataframe, str):
            return dataframe
            
        # Get cleaned df 
        cleaned_df = product_structure.preprocess_text_data(dataframe)
        if isinstance(cleaned_df, str): 
            return cleaned_df
        
        Embedding_Df_response = product_structure.apply_kmeans(cleaned_df, embedding_dir_path)
        return Embedding_Df_response

    except Exception as e:
        exc_type , exc_obj , exc_tb = sys.exc_info()
        error_message = f"[ERROR] Failed to Data Augmentation , error occur {str(e)} in line no : {exc_tb.tb_lineno}"
        return error_message



