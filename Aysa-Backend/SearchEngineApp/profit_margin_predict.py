import pandas as pd
import torch
import random
from sentence_transformers import SentenceTransformer , util
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

# Detect device CPU or GPU
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Take a  parameter to filter out dataframe
top_n = 80

class ProfitMarginPreidction:

    def __init__(self, pickle_df , model, user_query):
        self.df = pickle_df
        self.model = model
        self.user_query = user_query
        self.original_df = pickle_df.copy()

    # function to  change profit margin value...
    # Remove all characters except digits and dot
    def convert_profit_margin(self , df : pd.DataFrame) -> pd.DataFrame:
        df["Profit Margin"] = (
            df["Profit Margin"]
            .astype(str)
            .str.replace(r"[^0-9.-]", "", regex=True)  # keep digits, minus, dot
            .replace("", "0")  # if empty string, set to 0
            .astype(float)
        )
        return df
    
    
    # This function is return dataframe if user asked about only Brand Name
    def BrandDF(self, user_query: str, pickle_df: pd.DataFrame) -> pd.DataFrame:

        # Normalize dataframe columns
        for col in ["Brand", "Product Name", "Product Type", "Category"]:
            if col in pickle_df.columns:
                pickle_df[col] = pickle_df[col].astype(str).str.lower().str.strip()

        # Normalize query
        user_query = str(user_query).lower().strip()

        # Columns to check in order
        search_cols = ["Brand", "Product Name", "Product Type", "Category"]

        # Initialize empty DataFrame
        filtered_df = pd.DataFrame()

        # Find first column where user_query matches
        for col in search_cols:
            if user_query in pickle_df[col].values:
                filtered_df = pickle_df[pickle_df[col] == user_query]

        # If matches found, clean up
        if not filtered_df.empty:
            filtered_df = (
                filtered_df.sort_values("Production Year", ascending=False)
                        .drop_duplicates(subset=["Brand", "Production Year"], keep="first")   # <-- Changed here
                        .head(3)                                           # Keep only top 3
                        .drop(columns=["Category", "text", "text_embedding", "brand_embedding"], errors="ignore")
                    )

        return filtered_df

    # function to apply embedding 
    def apply_embedding(self):

        query_embedding = self.model.encode(self.user_query, convert_to_tensor=True).to(device)      # convert user query into vector   
        # Convert all full Text  embeddings to tensor
        # tensor([-0.0947, -0.0559, 0.0754, 0.0389, ...], device='cuda:0')

        full_embeddings = [torch.tensor(e).to(device) for e in self.df['text_embedding']]  
        full_text_embedding_tensor = torch.stack(full_embeddings)                #(num_rows, embedding_dimension)   like     [10000, 384]
        similarity_score = util.cos_sim(query_embedding, full_text_embedding_tensor)[0].cpu().numpy()
       
        brand_embeddings = [torch.tensor(e).to(device) for e in self.df['brand_embedding']]  
        brand_name_embedding_tensor = torch.stack(brand_embeddings)               
        brand_similarity_score = util.cos_sim(query_embedding, brand_name_embedding_tensor)[0].cpu().numpy()

        self.df['similarity_score'] = similarity_score
        self.df['brand_similarity_score'] = brand_similarity_score
        
        # remove unnessary columns from the Embeddingf df
        embedding_df = (
            self.df.drop(columns=["text_embedding", "brand_embedding"])
            .sort_values('similarity_score', ascending=False)
            .head(top_n)
            )
        return embedding_df


    def GetMatchedRow_AndParameter(self, filter_year, embedding_df: pd.DataFrame) -> dict:

        # Get the row with the highest similarity score
        matched_row = embedding_df.loc[embedding_df["similarity_score"].idxmax()]
        matched_row_data = matched_row.to_dict()
        # print("matched_row_data : \n ", matched_row_data)
        # print()

        # Extract key fields
        matched_year = int(matched_row_data.get("Production Year"))
        matched_brand = str(matched_row_data.get("Brand")).lower().strip()
        matched_category = str(matched_row_data.get("Category")).lower().strip()

        # Check if user-provided year matches the highest-similarity row's year
        if filter_year != 'None' and matched_year != int(filter_year):
            print("Year does not match =========================")
            sort_brand_df = embedding_df.sort_values("brand_similarity_score", ascending=False).head(top_n)
            print("sort_brand_df : \n ", sort_brand_df)
            print()
            sorted_df_matched_row = sort_brand_df.loc[sort_brand_df["brand_similarity_score"].idxmax()]
            brand_similarity = sorted_df_matched_row["brand_similarity_score"]

            if brand_similarity > 0.60:

                # Get brand name 
                matched_brand = str(sorted_df_matched_row["Brand"]).lower().strip()


            print("MatchedBrand ", matched_brand, 'brand_similarity ', brand_similarity , "type ", type(brand_similarity))
            
            # Filter dataframe for the same brand and requested year
            GetYearBasedDF = embedding_df.loc[
                (embedding_df["Brand"].astype(str).str.lower().str.strip() == matched_brand) &
                (embedding_df["Production Year"].astype(int) == int(filter_year))
            ]

            # if user query year does not exist
            if GetYearBasedDF.empty:

                # No data for requested year → pick a random available year for same brand
                unique_years_list = (
                    embedding_df.loc[
                        embedding_df['Brand'].astype(str).str.lower().str.strip() == matched_brand,
                        'Production Year'
                    ]
                    .dropna()
                    .astype(int)
                    .unique()
                    .tolist()
                )

                if not unique_years_list:
                    print("No available years found for brand:", matched_brand)
                    return None, None

                random_year = random.choice(unique_years_list)
                random_year_df = embedding_df.loc[
                    (embedding_df["Brand"].astype(str).str.lower().str.strip() == matched_brand) &
                    (embedding_df["Production Year"].astype(int) == int(random_year))
                ]

                matched_row = random_year_df.loc[random_year_df["similarity_score"].idxmax()]
                matched_row_data = matched_row.to_dict()

            else:
                # Data exists for requested year — take highest similarity row from that year
                matched_row = GetYearBasedDF.loc[GetYearBasedDF["similarity_score"].idxmax()]
                matched_row_data = matched_row.to_dict()
        
        # Extract final parameters
        matched_brand = str(matched_row_data.get("Brand")).lower().strip()
        matched_category = str(matched_row_data.get("Category")).lower().strip()
        matched_year = int(matched_row_data.get("Production Year"))
        matched_product_type = str(matched_row_data.get("Product Type")).lower().strip()
        matched_variant_map = str(matched_row_data.get("Type Mapped")).lower().strip()
        matched_gender = str(matched_row_data.get("Gender")).lower().strip()

        # Prepare response
        response_dict = {
            "matched_brand": matched_brand,
            "matched_category": matched_category,
            "matched_year": matched_year,
            "matched_product_type": matched_product_type,
            "matched_gender": matched_gender,
            "matched_variant_map": matched_variant_map
        }

        return response_dict, matched_row_data

    # function to return filter out dataframe based on the category value
    def Get_Category_based_df(self,response_dict : dict) -> pd.DataFrame:

        # Make lower case and remove extra space
        self.original_df.loc[:,"Category"] =  self.original_df["Category"].astype(str).str.lower().str.strip()
        
        # Get Category value from Matched Row dict
        matched_category = response_dict.get("matched_category")

        # filter df
        categorized_df = self.original_df.loc[self.original_df["Category"] == matched_category]
        return categorized_df

    # function to return filter out dataframe based on the matched year value
    def Get_year_based_df(self,response_dict : dict , categorized_df: pd.DataFrame) -> pd.DataFrame:
        
        # Get Year value from Matched Row dict
        matched_year = response_dict.get("matched_year")

        # filter df
        yearly_df = categorized_df.loc[categorized_df["Production Year"].astype(int) == matched_year]
        return yearly_df
    
    # function to return filter out dataframe based on the matched GENDER value
    def Get_gender_based_df(self, response_dict: dict, yearly_df: pd.DataFrame) -> pd.DataFrame:
        # Make Gender column lowercase and strip extra spaces
        yearly_df.loc[:,"Gender"] = yearly_df["Gender"].str.strip().str.lower()
        # Get matched_gender from response_dict
        matched_gender = response_dict.get("matched_gender")


        if matched_gender:
            matched_gender = matched_gender.lower()
            if matched_gender in ["men", "women"]:
                # Replace "unisex" with matched gender
                yearly_df.loc[: ,"Gender"] = yearly_df["Gender"].replace("unisex", matched_gender)

            elif matched_gender == "unisex":
                # Replace "men" and "women" with "unisex"
                yearly_df.loc[:,"Gender"] = yearly_df["Gender"].replace({"men": "unisex", "women": "unisex"})

            # Filter dataframe based on matched gender
            gender_based_df = yearly_df[yearly_df["Gender"] == matched_gender]
            return  gender_based_df
        else:
            return pd.DataFrame()  # Return an empty dataframe if no matched_gender

    
    # This function Returning Two lists
    # One is compare list which is filter rows based on the Brand value and Product Type Value
    # Second is brand list which is filter rows based on the only Brand Value
    def Filter_rows_list(self, response_dict: dict, genderly_df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter rows from genderly_df based on matched_brand, matched_product_type, and matched_variant_map.
        Ensures that returned rows have a different brand from the matched_brand but similar product type or variant.
        """

        # Extract response parameters
        matched_brand_name = str(response_dict.get("matched_brand", "")).lower().strip()
        matched_product_type = str(response_dict.get("matched_product_type", "")).lower().strip()
        matched_variant_map = str(response_dict.get("matched_variant_map", "")).lower().strip()
        matched_category = response_dict.get("matched_category", "")

        filtered_rows = []

        # First pass: filter by product type but different brand
        for idx, row in genderly_df.iterrows():
            row_brand = str(row.get("Brand", "")).lower().strip()
            row_product_type = str(row.get("Product Type", "")).lower().strip()
            row_variant_map = str(row.get("Type Mapped", "")).lower().strip()

            if row_brand != matched_brand_name and (
                row_product_type == matched_product_type or
                matched_product_type in row_product_type or
                row_product_type in matched_product_type
            ):
                filtered_rows.append(row)

        # If less than 2 unique brands, second pass: check by variant
        compare_df = pd.DataFrame(filtered_rows)
        if compare_df.empty or compare_df["Brand"].nunique() < 3:
            print(" - Searching for second brand ........")
            for idx, row in genderly_df.iterrows():
                row_brand = str(row.get("Brand", "")).lower().strip()
                row_variant_map = str(row.get("Type Mapped", "")).lower().strip()

                if row_brand != matched_brand_name and row_variant_map == matched_variant_map:
                    # Append only if not already in filtered_rows
                    if not any(row.equals(r) for r in filtered_rows):
                        filtered_rows.append(row)

        # Return as DataFrame
        return filtered_rows

    
    # This function is just filtering dataframe 
    # Based on the brand product type list
    # And only brand name list
    def Filtered_Dataframe(self,brand_product_type_list: list) -> pd.DataFrame:
 
        filtered_df = pd.DataFrame(brand_product_type_list)
        
        # Return Empty list when filtered df is empty 
        if filtered_df.empty:
            return []
        
        # Remove extra sign , percentage sign and extra spaces from profit margin csv
        filtered_df = self.convert_profit_margin(filtered_df)
        
        # Get min amd max value of specific brand
        agg_df = filtered_df.groupby("Brand")["Profit Margin"].agg(["min", "max"]).reset_index()

        # print("agg_df : \n ", agg_df)
        # print()
        # if there is multiple brand exist in dataframe
        if len(agg_df) >1 :
            # Remove e  xtra spaces from the brand column value
            agg_df["Brand"] = agg_df["Brand"].str.strip()

            # Sort agg_df by max descending for max profit, min ascending for min profit
            agg_df_max_sorted = agg_df.sort_values('max', ascending=False)
            agg_df_min_sorted = agg_df.sort_values('min', ascending=True)

            # Pick the brand with highest profit
            max_brand = agg_df_max_sorted.iloc[0]['Brand']
            max_profit = agg_df_max_sorted.iloc[0]['max']

            # Pick the brand with lowest profit, but ensure it's different
            min_brand_row = agg_df_min_sorted[agg_df_min_sorted['Brand'] != max_brand].iloc[0]
            min_brand = min_brand_row['Brand']
            min_profit = min_brand_row['min']

            # # Get rows from filtered_df
            highest_row = filtered_df[(filtered_df['Brand'].str.strip() == max_brand) & 
                                    (filtered_df['Profit Margin'].astype(float) == max_profit)]
            
            lowest_row = filtered_df[(filtered_df['Brand'].str.strip() == min_brand) & 
                                    (filtered_df['Profit Margin'].astype(float) == min_profit)]

            # # Combine and sort
            filtered_df = pd.concat([highest_row, lowest_row], ignore_index=True)
            filtered_df = filtered_df.sort_values('Profit Margin', ascending=False)

            # Handle if  profit margins of both brands is same
            if max_profit !=  min_profit:
                filtered_df = filtered_df.drop_duplicates(subset=["Profit Margin"], keep="first")

            # print("filtered df : \n ", filtered_df)
            # print()

        elif len(agg_df) ==1 : 
            print('agg df elif condition is running ')
            # Only one brand exists, get max profit margin row
            brand_name = str(agg_df['Brand'].iloc[0]).strip()
            profit_margin = float(agg_df['min'].iloc[0])

            filtered_df = filtered_df[(filtered_df['Brand'].str.strip() == brand_name) & 
                                    (filtered_df['Profit Margin'].astype(float) == profit_margin)]
        return filtered_df

