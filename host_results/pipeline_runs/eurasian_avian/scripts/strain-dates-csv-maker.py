import pandas as pd
import os
import re
import sys
import subprocess
from datetime import datetime
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--aln', type=str, required=True, help='the path to your backbone alignment file')

args = parser.parse_args()

# treetime needs a dates.csv file to root the tree where the date column is in decimal format
# this assumes your sample is in the format of strain|date in your alignment file

def fasta_to_df(fasta_file):
    
    fasta_data = []
    
    with open(fasta_file) as f:
        header = ""
        sequence = ""
        for line in f:
            if line.startswith(">"):
                if header != "":
                    fasta_data.append({"header": header, "sequence": sequence})
                header = line.strip() 
                sequence = ""
            else:
                sequence += line.strip()
        fasta_data.append({"header": header, "sequence": sequence}) #last line
            
    return pd.DataFrame(fasta_data)

def create_date_csv(aln_date_map):
    
    file_name = "strain_dates.csv"
    
    with open(file_name, 'w') as date_file:
        date_file.write("name, date\n")
        
        for strain, date_str in aln_date_map.items():

            date = datetime.strptime(date_str, '%Y-%m-%d')
            
            # convert to decimal year because thats what treetime uses
            dec_date = date.year + ((date.month - 1) * 30 + date.day) / 365.0
        
            date_file.write(f"{strain}, {dec_date:.2f}\n")

df = fasta_to_df(args.aln)

df["strain"] = df["header"].str.split('|').str[0]
df["date"] = df["header"].str.split('|').str[1]

aln_date_map = dict(zip(df['header'].str.replace(">", ""), df['date']))

create_date_csv(aln_date_map)