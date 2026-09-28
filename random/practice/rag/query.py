import pandas as pd

# Define your file path
file_path = "/home/lavanya/Desktop/Lavanya/random/rag/products_cleaned_fixed_columns.csv"

# Load the CSV straight into a DataFrame
df = pd.read_csv(file_path)

# View the first 5 rows
print(df.head())
