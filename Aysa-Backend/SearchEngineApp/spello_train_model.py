import pandas as pd
from spello.model import SpellCorrectionModel
import os
import pickle

class TrainSpelloModel:

    def __init__(self):
        self.profit_margin_csv = os.path.join(os.getcwd() , "static", "media", "Profit Data" , "profit_margin.csv")
        self.tax_avoidance_csv = os.path.join(os.getcwd() , "static", "media", "Tax Data" , "Tax_Avoidance.csv")
        self.tablet_ceo_worker_csv = os.path.join(os.getcwd() , "static", "media", "CEO Worker Data" , "Phone_Tablet.csv")
        self.trained_spello_model_base_dir = os.path.join(os.getcwd() , "spello_model")

    def remove_inner_duplicates(self,text):
        words = str(text).lower().strip().split()
        seen = set()
        return ' '.join([w for w in words if not (w in seen or seen.add(w))])

    def read_product_csv(self):
        profit_df = pd.read_csv(self.profit_margin_csv)
        return profit_df 
    
    def read_tax_csv(self):
        tax_df = pd.read_csv(self.tax_avoidance_csv)
        return tax_df
    
    def read_phone_tablet_csv(self):
        tablet_df = pd.read_csv(self.tablet_ceo_worker_csv)
        return  tablet_df

    def normalize_profit_margin_data(self):
        
        # call  function to get product df
        profit_df = self.read_product_csv()

        # Mwrge text and add new column with name Merge Text
        text = profit_df["Brand"] + " " + profit_df["Product Name"] + " " + profit_df["Product Type"] + " " + profit_df["Category"]
        profit_df["Merge Text"] = text

        # Get list of all Merge text data columns
        datalist = profit_df["Merge Text"].tolist()

        cleaned_list = []
        for item in datalist:

            # call function to remove duplicate word from datalist particaular cell text
            normalized = self.remove_inner_duplicates(item)
            if normalized not in cleaned_list:
                cleaned_list.append(normalized)
        
        return cleaned_list
    
    def normalize_tax_data(self):

        # call  function to get product df
        tax_df = self.read_tax_csv()

        # Merge text and add new column with name Merge Text
        tax_df["Merge Text"] = tax_df["Company Name"] + " " + tax_df["Year"].astype(str)

        # Get list of all Merge text data columns
        tax_df["Merge Text"] =tax_df["Merge Text"].str.strip().str.lower().tolist()

        df_cleaned = tax_df.drop_duplicates(subset=['Merge Text'])

        datalist = df_cleaned["Merge Text"].tolist()
        
        return datalist

    def normalize_CEO_WORKER_data(self):

        # call  function to get product df
        pay_gap_df = self.read_phone_tablet_csv()

        #Merge text and add new column with name Merge Text
        pay_gap_df["Merge Text"] = pay_gap_df["Company Name"] + " " + pay_gap_df["CEO Name"] 

        # Get list of all Merge text data columns
        pay_gap_df["Merge Text"] =pay_gap_df["Merge Text"].str.strip().str.lower().tolist()

        df_cleaned = pay_gap_df.drop_duplicates(subset=['Merge Text'])

        datalist = df_cleaned["Merge Text"].tolist()
        
        return datalist

    def train_profit_margin_spell_corrector(self):
        sp = SpellCorrectionModel(language='en')

        # Get cleande datalist 
        cleaned_profit_data = self.normalize_profit_margin_data()
        sp.train(cleaned_profit_data)

        product_spello_model_file_path = os.path.join(self.trained_spello_model_base_dir ,"profit_spello_model.pkl")

        # Save the trained model
        with open(product_spello_model_file_path, 'wb') as f:
            pickle.dump(sp, f)

        return f"Model train successfully and saved in : {product_spello_model_file_path}"

    def train_tax_spell_corrector(self):
        sp = SpellCorrectionModel(language='en')

        # Get cleande datalist 
        cleaned_tax_data = self.normalize_tax_data()
        sp.train(cleaned_tax_data)

        tax_spello_model_file_path = os.path.join(self.trained_spello_model_base_dir ,"tax_spello_model.pkl")

        # Save the trained model
        with open(tax_spello_model_file_path, 'wb') as f:
            pickle.dump(sp, f)

        return f"Model train successfully and saved in : {tax_spello_model_file_path}"

    def train_paygap_spell_corrector(self):
        sp = SpellCorrectionModel(language='en')

        # Get cleande datalist 
        cleaned_tax_data = self.normalize_CEO_WORKER_data()
        sp.train(cleaned_tax_data)

        paygap_spello_model_file_path = os.path.join(self.trained_spello_model_base_dir ,"pay_gap_spello_model.pkl")

        # Save the trained model
        with open(paygap_spello_model_file_path, 'wb') as f:
            pickle.dump(sp, f)

        return f"Model train successfully and saved in : {paygap_spello_model_file_path}"


class SpellcorrectorModelInference:

    def __init__(self):
        self.product_spello_model_path = os.path.join(os.getcwd(),"spello_model" , "profit_spello_model.pkl")
        self.tax_spello_model_path = os.path.join(os.getcwd(),"spello_model" , "tax_spello_model.pkl")
        self.paygap_spello_model_path = os.path.join(os.getcwd(),"spello_model" , "pay_gap_spello_model.pkl")

    def product_spell_corrector(self , input_text : str):

        with open(self.product_spello_model_path, "rb") as f:
            load_model = pickle.load(f)

        result = load_model.spell_correct(input_text)
        return result["spell_corrected_text"]


    def tax_spell_corrector(self , input_text : str):

        with open(self.tax_spello_model_path, "rb") as f:
            load_model = pickle.load(f)

        result = load_model.spell_correct(input_text)
        return result["spell_corrected_text"]
    
    def paygap_spell_corrector(self , input_text : str):


        with open(self.paygap_spello_model_path, "rb") as f:
            load_model = pickle.load(f)

        result = load_model.spell_correct(input_text)
        return result["spell_corrected_text"]
