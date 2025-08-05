import argparse
import os
import pandas as pd

list_of_genes = ["ha", "pb2","pb1","na","np","pa","ns","mp"]

# take in alignment and metadata files and change to be strain|date for treesort/treetime
# assumes metadata date column header is "date" and strain name header is "strain"
# outputs to folder called "dates_added"
# divergence trees should be made using these files

parser = argparse.ArgumentParser()
parser.add_argument('--subtype', type=str, required=True, help='the subtype that is present in your file names (ex: h3nx_ha.fasta)')
parser.add_argument('--aln', type=str, required=True, help='the paths to the folder that has your alignment files')
parser.add_argument('--backbone', type=str, required=True, help='the segment that is your backbone')
parser.add_argument('--meta', type=str, required=True, help='the path to your backbone metadata file')
parser.add_argument('--d', type=str, choices=['tsv', 'csv'], default='tsv', help='is your metadata a tsv or csv (default: tsv)')

args = parser.parse_args()

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
        fasta_data.append({"header": header, "sequence": sequence}) # last line
            
    return pd.DataFrame(fasta_data)
    
def fasta_writer(path, filename, df):
            
    try:  
        os.mkdir(path)

    except OSError as error:
        pass

    with open(f"{path}{filename}", "w") as f:
        for index, row in df.iterrows():
            f.write(f"{row['header']}\n")
            f.write(f"{row['sequence']}\n")

for path in [f"dates_added/alignments", f"dates_added/metadata"]:
		if not os.path.exists(path):
			os.makedirs(path)
		else:
			pass
			
metadata_file = args.meta
delimiter = '\t' if args.d == 'tsv' else ','
metadata = pd.read_csv(metadata_file, delimiter=delimiter)
metadata["date"] = metadata["date"].str.replace('XX', '01')

for gene in list_of_genes:
	
	align_file = f"{args.aln}/{args.subtype}_{gene}.fasta"
	output_align = f"dates_added/alignments/{args.subtype}_{gene}.fasta"
	
	align = fasta_to_df(align_file)
	align.header = align.header.str.replace(">", "")

	merged = pd.merge(align, metadata[['strain', 'date']], left_on='header', right_on='strain', how='left')
	merged["header"] = merged[['strain', 'date']].apply('|'.join, axis=1)

	merged["header"] = ">" + merged["header"]
	
	fasta_writer("dates_added/alignments/", f"{args.subtype}_{gene}.fasta", merged)
			 
metadata["strain"] = metadata[['strain', 'date']].apply('|'.join, axis=1)

metadata.to_csv(f"dates_added/metadata/{args.subtype}_{args.backbone}.csv", index=False)