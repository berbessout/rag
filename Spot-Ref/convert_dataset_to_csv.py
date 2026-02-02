#!/usr/bin/env python3
"""
Convert Dataset.xlsx to CSV format.
"""

import pandas as pd
import os
from pathlib import Path

def convert_excel_to_csv(excel_path: str, csv_path: str = None) -> str:
    """
    Convert an Excel file to CSV format.
    
    Args:
        excel_path (str): Path to the Excel file
        csv_path (str, optional): Path for the output CSV file. 
                                 If None, will use the same name with .csv extension
    
    Returns:
        str: Path to the created CSV file
    """
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel file not found: {excel_path}")
    
    # If no CSV path provided, create one from Excel path
    if csv_path is None:
        excel_file = Path(excel_path)
        csv_path = excel_file.with_suffix('.csv')
    
    try:
        # Read the Excel file
        print(f"Reading Excel file: {excel_path}")
        df = pd.read_excel(excel_path)
        
        # Display basic info about the dataset
        print(f"Dataset shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        print("\nFirst few rows:")
        print(df.head())
        
        # Save as CSV
        print(f"\nSaving as CSV: {csv_path}")
        df.to_csv(csv_path, index=False, encoding='utf-8')
        
        print(f"✅ Successfully converted {excel_path} to {csv_path}")
        return str(csv_path)
        
    except Exception as e:
        print(f"❌ Error converting file: {e}")
        raise

def main():
    """Main function to convert the dataset."""
    # Define paths
    excel_file = "test/Dataset.xlsx"
    csv_file = "test/Dataset.csv"
    
    # Check if we're in the right directory
    if not os.path.exists(excel_file):
        print("⚠️ Make sure to run this script from the Spot-Ref directory")
        return
    
    # Convert the file
    try:
        result_path = convert_excel_to_csv(excel_file, csv_file)
        print(f"\n🎉 Dataset successfully converted to: {result_path}")
    except Exception as e:
        print(f"❌ Failed to convert dataset: {e}")

if __name__ == "__main__":
    main() 