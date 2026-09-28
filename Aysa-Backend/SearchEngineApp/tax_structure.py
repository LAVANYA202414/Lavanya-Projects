import pandas as pd
import sys
import os
import torch
from sentence_transformers import SentenceTransformer , util
from sklearn.metrics import silhouette_score
from .utils import preprocess_text
from sklearn.preprocessing import LabelEncoder
le = LabelEncoder()

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)


class TaxModelStructure:

    def __init__(self, csv_path):
        self.csv_path = csv_path
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
            df = pd.read_csv(self.csv_path)
            # remove nan values
            df.dropna(inplace=True)

            # remove duplicacy 
            df.drop_duplicates(inplace=True)

            return df
        
        except Exception as e:
            exc_type , exc_obj , exc_tb = sys.exc_info()
            error_message = f"Faile to read csv file and clean categories , error occur {str(e)} in line no : {exc_tb.tb_lineno}"
            print(error_message)
            return []

    # function to create new column with name 'text' only used 'product name' and 'type' column .
    def preprocess_text_data(self, df):
        
        print("Step 2: Text Preprocessing is running ......")
        try:

            # make a copy of dataframe
            df = df.copy()

            # Add two column with different columns groups
            df["text"] = (df["Company Name"] +" " +df["Year"].astype(str))

            # Apply preprocess columns on both column
            df["text"] = df["text"].apply(preprocess_text)
            return df
        
        except Exception as e:
            exc_type , exc_obj , exc_tb = sys.exc_info()
            error_message = f"Failed preprocess text  , error occur {str(e)} in line no : {exc_tb.tb_lineno}"
            print(error_message)
            return []

    def apply_kmeans(self, df, embedding_dir_path):
        print(f"Step 3: Text Embedding is starting ........")
        try:

            # make a model path 
            transfer_model_path = os.path.join(os.getcwd(), "transfer_model", 'all-MiniLM-L6-v2')

            # Load sentence transer model
            model = SentenceTransformer(transfer_model_path)

            embeddings_full_text = model.encode(df['text'].tolist(), show_progress_bar=True)

            df["tax_text_embedding"] = list(embeddings_full_text)

            # Remove 0 values with N/A
            # df["Taxes Paid"] = df["Taxes Paid"].str.replace(
            #         r'^\$0+(\.0+)?(\s*(billion|million|b|m))?$',  # regex
            #         "N/A",
            #         regex=True)
            
            # df["Taxes Avoided"] = df["Taxes Avoided"].str.replace(
            #         r'^\$0+(\.0+)?(\s*(billion|million|b|m))?$',  # regex
            #         "N/A",
            #         regex=True)
            
            # save embedding df
            full_text_embedding_path = os.path.join(embedding_dir_path,"tax_embedding.pkl")

            # Save dataframe on pickle file
            df.to_pickle(full_text_embedding_path)
            print( f"Tax Embedding DataFrame saved to {full_text_embedding_path}")

            return "success"
        
        except Exception as e:
            raise Exception(f"KMeans clustering failed: {e}")
        

def TaxMainFunc(file_path, embedding_dir_path , TransferModelDir):
    try:
        product_structure = TaxModelStructure(file_path)
        
        # call function to upload or run local model 
        model = product_structure.DownloadUpdateModel(TransferModelDir)

        # function to read csv and remove duplicacy and nan values
        df = product_structure.read_csv()
        if isinstance(df, list): 
            return None

        # Get cleaned df 
        cleaned_df = product_structure.preprocess_text_data(df)
        if isinstance(cleaned_df, list): 
            return None
        
        response = product_structure.apply_kmeans(cleaned_df, embedding_dir_path)

        return response     

    except Exception as e:
        error_message = f"Failed to process product model structure: {e}"
        print(error_message)
        return None



