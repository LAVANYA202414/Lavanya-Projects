import pandas as pd
import sys
import os
import re
import torch
from sentence_transformers import SentenceTransformer , util
from sklearn.cluster import KMeans
from .utils import preprocess_text
from sklearn.preprocessing import LabelEncoder
le = LabelEncoder()

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)


class CeoWorkerModelStructure:

    def __init__(self, Tablet_File_path, Website_File_path):
        self.phone_csv_path  = Tablet_File_path
        self.Website_File_path  = Website_File_path
        self.max_range = 20
        self.random_state_value = 42
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


    def read_csv(self):
        print("Step 1: Reading CSV file ....")
        try:
            # Read Phone/Tablet CSV
            tablet_df = pd.read_csv(self.phone_csv_path)
            tablet_df.dropna(inplace=True)
            tablet_df.drop_duplicates(inplace=True)

            # Read website CSV
            website_df = pd.read_csv(self.Website_File_path)
            website_df.dropna(inplace=True)
            website_df.drop_duplicates(inplace=True)
            return tablet_df , website_df
        
        except Exception as e:
            exc_type , exc_obj , exc_tb = sys.exc_info()
            error_message = f"Faile to read csv file and clean categories , error occur {str(e)} in line no : {exc_tb.tb_lineno}"
            print(error_message)
            return []

    # function to create new column with name 'text' only used 'product name' and 'type' column .
    def preprocess_text_data(self,tablet_df , website_df):
        
        print("Step 2: Text Preprocessing is running ......")
        try:

            # make a copy of dataframe
            phone_df = tablet_df.copy()
            desktop_df = website_df.copy()

            # Add two column with different columns groups
            # Apply preprocess columns on both column
            phone_df["phone_text"] = (phone_df["Company Name"] +" "  + phone_df["CEO Name"].astype(str)+ phone_df["Year"].astype(str))
            phone_df["phone_text"] = phone_df["phone_text"].apply(preprocess_text)

            desktop_df["desktop_text"] = (desktop_df["Company Name"] +" " +desktop_df["CEO Name"].astype(str) +" " +desktop_df["Year"].astype(str))
            desktop_df["desktop_text"] = desktop_df["desktop_text"].apply(preprocess_text)

            return phone_df , desktop_df
        
        except Exception as e:
            exc_type , exc_obj , exc_tb = sys.exc_info()
            error_message = f"Failed preprocess text  , error occur {str(e)} in line no : {exc_tb.tb_lineno}"
            print(error_message)
            return []

    def apply_kmeans(self,phone_df, desktop_df, embedding_dir_path, model):
        print(f"Step 3: Text Embedding is starting ........")
        try:

            # Phone Tablet Embedding
            phone_embeddings_full_text = model.encode(phone_df['phone_text'].tolist(), show_progress_bar=True)
            phone_df["phone_text_embedding"] = list(phone_embeddings_full_text)

            # phone_df["CEO Total Compensation"] = phone_df["CEO Total Compensation"].str.replace(
            #     r'^\s*\$0+(?:\.0+)?(?:\s*(?:billion|million|b|m))?\s*$',
            #     "N/A",
            #     regex=True,
            #     flags=re.IGNORECASE
            # )

            full_text_embedding_path = os.path.join(embedding_dir_path,"ceo_mobile_embedding.pkl")
            phone_df.to_pickle(full_text_embedding_path)
            print( f"CEO Worker Phone  DataFrame saved to {full_text_embedding_path}")

            # Phone Tablet Embedding
            desktop_embeddings_full_text = model.encode(desktop_df['desktop_text'].tolist(), show_progress_bar=True)
            desktop_df["desktop_text_embedding"] = list(desktop_embeddings_full_text)

            # Remove 0 values with N/A
            # desktop_df["CEO Total Compensation"] = desktop_df["CEO Total Compensation"].str.replace(
            #     r'^\s*\$0+(?:\.0+)?(?:\s*(?:billion|million|b|m))?\s*$',
            #     "N/A",
            #     regex=True,
            #     flags=re.IGNORECASE
            # )
            
            full_text_embedding_path = os.path.join(embedding_dir_path,"ceo_desktop_embedding.pkl")
            desktop_df.to_pickle(full_text_embedding_path)
            print( f"CEO Worker Website  DataFrame saved to {full_text_embedding_path}")
            return "success"
        
        except Exception as e:
            raise Exception(f"KMeans clustering failed: {e}")
        

def CeoWorkerMainFunc(Tablet_File_path ,Website_File_path, embedding_dir_path , TransferModelDir):
    try:
        product_structure = CeoWorkerModelStructure(Tablet_File_path, Website_File_path)
        
        # call function to upload or run local model 
        model = product_structure.DownloadUpdateModel(TransferModelDir)

        # function to read csv and remove duplicacy and nan values
        tablet_df , website_df  = product_structure.read_csv()
        if isinstance(tablet_df, list) or isinstance(website_df, list): 
            return None

        # Get cleaned df 
        cleaned_phone_df , cleaned_desktop_df= product_structure.preprocess_text_data(tablet_df ,website_df)
        if isinstance(cleaned_phone_df, list) or isinstance(cleaned_desktop_df ,list): 
            return None
        
        response = product_structure.apply_kmeans(cleaned_phone_df,cleaned_desktop_df,  embedding_dir_path, model)

        return response     

    except Exception as e:
        error_message = f"Failed to process product model structure: {e}"
        print(error_message)
        return None



