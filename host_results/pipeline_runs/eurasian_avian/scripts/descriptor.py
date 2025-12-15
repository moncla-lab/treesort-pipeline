import argparse

list_of_genes = ["ha", "pb2","pb1","na","np","pa","ns","mp"]

parser = argparse.ArgumentParser()
parser.add_argument('--backbone', type=str, required=True, help='the segment that will be the backbone')
parser.add_argument('--subtype', type=str, required=True, help='the subtype that is present in your file name (ex: h3nx_ha.fasta)')
parser.add_argument('--alns', type=str, required=True, help='the paths to the folder that has your alignment files')
parser.add_argument('--trees', type=str, required=True, help='the paths to the folder that has your rooted tree files')

args = parser.parse_args()

descriptor_entries = [] 

for gene in list_of_genes:

	gene_label = f"*{gene.upper()}" if gene == args.backbone else gene.upper()
	
	align_path = f"{args.alns}/{args.subtype}_{gene}.fasta"
	div_path = f"{args.trees}/{args.subtype}_{gene}_rooted/rerooted.newick"
	
	descriptor_entries.append([gene_label, align_path, div_path])

# descriptor csv
with open("descriptor.csv", 'w+') as descriptor_file:
	for row in descriptor_entries:
		descriptor_file.write(','.join(row) + '\n')