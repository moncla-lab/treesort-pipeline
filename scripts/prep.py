import re
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--tree', type=str, required=True, help='annotated reassortment treesort tree')
parser.add_argument('--outdir', type=str, required=True, help='name of baltic readable tree')

args = parser.parse_args()

with open(args.tree, 'r') as file:
    nexus = file.read()
        
start_idx = nexus.find('(')
modified = nexus[start_idx:]

end_idx = modified.find('END;')
modified = modified[:end_idx]
	
# removing commas between segments
modified = re.sub(r'&rea="([^"]+)"', lambda match: f'&rea="{match.group(1).replace(",", "-")}"', modified)

# removing quotation marks around node names
modified = re.sub(r"'(TS_NODE_\d+)'", r'\1', modified)

# replacing ? with _ so baltic can read it in
modified = modified.replace('?', '_')

with open(args.outdir, "w") as output_file:
	output_file.write(modified.strip())