
# Pipeline for running Treesort in replicate 

Warning: This repository is a work in progress. 

## Overview

This pipeline provides a snakemake framework to run [TreeSort](https://github.com/flu-crew/TreeSort/tree/main) in replicate 
to traverse over uncertainties in tree topology and produce reassortment confidence values for each node & leaf. Before running this pipeline, you must first run 
TreeSort once to generate the binarized backbone tree annotated with reassortment events (see **Prerequisites 2**). This backbone tree remains fixed and is used as the input for each replicate run.

While this backbone tree input does not change, new divergence trees are generated for the challenge segments for each replicate run.
The ```--no-collapse``` flag is used during ```rule treesort``` to ensure that all annotated TreeSort tree outputs retain the same topology as the backbone.

The current Snakefile is set to produce 3 replicate treesort runs (```REPS=range(3)```), but this can be increased to fit your data's needs. Due to its computational intensity, we recommend running >10 reps on an HPC system.

Once TreeSort has been run for all replicates, ```rule summary``` will generate:

* A summary node data JSON.
* A summary Newick tree.

The summary tree can be plotted in [Baltic](https://github.com/evogytis/baltic/tree/master) and serves as the source tree for the [cladeset-mapping tool](https://github.com/moncla-lab/treesort-cladeset-mapping) developed by Stephen Shank in the Moncla lab. 
This cladeset mapping tool is designed for downstream use of ```rule export``` and enables accurate visualization of reassortment event and segment-level confidence at each node & leaf via the [nextstrain auspice dashboard](https://docs.nextstrain.org/projects/auspice/en/stable/).

This pipeline will also calculate the reassortment rate for each replicate tree in `rule log` which can be found in `results/summary/log.csv`.

**Note:** The provided ```Snakefile``` and ```descriptor.csv``` is configured for the example data in ```EXAMPLE_DATA```. Change this to match your data after running the example.

## Installation

Clone this repo:

			git clone https://github.com/moncla-lab/treesort-pipeline.git

Navigate your way into the pipeline repo:

  			cd treesort-pipeline

Create a conda environment with the provided configuration file:

			conda env create -f env.yml

Activate the conda environment:

   			conda activate treesort-pipeline


## Prerequisites 

1. This pipeline assumes you already have generated alignment files, metadata files, and divergence trees for your dataset.
   Things to keep in mind:
   
   	a. Each sample should include the strain name and collection date. For example, a fasta file header should look like:

   			>A/blue-winged_teal/Alberta/221/1978|1978-08-07
   	
   	b. The dates should be in YYYY-MM-DD format. Any incomplete dates should have a placeholder instead (ex: instead of 1978-XX-XX, it could be 1978-01-01).
   	
	Note: You can run ```scripts/to-add-dates.py``` to format your alignments and metadata in this way.
   
2. Run [TreeSort](https://github.com/flu-crew/TreeSort/tree/main) locally using your alignment files and divergences trees as inputs in the descriptor file.
   Make sure your backbone tree is rooted (per TreeSort's instructions). The command should look like:

			treesort -i descriptor.csv -o annotated.tre
				
3. Run your backbone alignment through ```scripts/strain-dates-csv-maker.py``` to create a ```strain_dates.csv``` required by TreeTime for ```rule root``` in the snakemake. 

			python scripts/strain-dates-csv-maker.py --aln 'path_to_your_backbone_alignment_file' 
				
4. Convert the TreeSort ```annotated.tre``` nexus output to a newick format using ```scripts/to_nwk.py``` since that is the required input tree file format for TreeSort.

   			python scripts/to_nwk.py --tree 'annotated.tre'  --output 'output.nwk'

5. Now you have all the required data to run the pipeline. The folder organization should be as follows:
	
	a. the ```data``` folder which should include:
		
	* a folder with your alignments
	* a folder named ```backbone``` with the annotated tree generated in (2) and converted to newick format in (4) in addition to the original backbone input tree before TreeSort was run on it
    * a ```metadata.csv``` with the ancestral traits you want inferred by discrete trait analysis in [```rule traits```](https://docs.nextstrain.org/projects/augur/en/stable/usage/cli/traits.html)
    * a folder named ```config``` which includes a reference file in the subfolder ```ref```, a ```colors.tsv```, a ```lat_longs.tsv```, and an ```auspice_config.json```
	* the ```strains_dates.csv``` generated in (3)
		
	b. your ```descriptor.csv``` file that points to the correct alignment and divergence tree paths for ```rule treesort```. 
	   
	You can edit the provided descriptor.csv manually or make your own by running ```scripts/descriptor.py```:
	   
		python scripts/descriptor.py \
			  --backbone BACKBONE_SEGMENT \
			  --subtype SUBTYPE \ 
			  --alns PATH_TO_ALIGNMENTS_FOLDER \
			  --trees PATH_TO_FOLDER_WITH_ROOTED_TREES
   
	c. your ```Snakefile``` where you can tailor the wildcards to fit your data needs.

## Running the pipeline and using example data:

**1. Activate the conda environment:**
			
			conda activate treesort-pipeline
			
**2. Check a dry run first:**

			snakemake -n all 

**3. Run the pipeline:**

			date > clock.txt; snakemake -k -j $NUMBER-OF-JOBS all >> output.log; date >> clock.txt
	
Here, ```clock.txt``` records compute time. The ```output.log``` will store the outputs of the pipeline for debugging if needed.
The ```-k``` flag tells snakemake that if there is an error, to keep going if with remaining independent jobs. 
Since this pipeline is parallelized, the ```-j``` flag denotes how many jobs to run at once. Thus, ```$NUMBER_OF_JOBS``` should be at least 1, and no more than the number of cores on your computer.

**Using the example data:**

This pipeline is ready to be run on the example data provided in ```EXAMPLE_DATA```. This folder contains the alignments for 235 human H3N2 seasonal influenza viruses, a ```strains-dates.csv``` (see **Prerequisites 3**), and the HA backbone newick tree (see **Overview**). It also includes the metadata, reference file, and other needed config files. The provided ```descriptor.csv``` also points to all the correct paths.

## Usage

### ```rule tree```:

Generates new divergence trees for each challenge segment.

**Input**:

+ ```alignment```: alignment files for each segment provided in ```rule files```

**Ouptut**:

+ ```tree```: unrooted divergence tree (method iqtree) for each segment

### ```rule root```:

Infers a root for each of the challenge segment divergence trees using TreeTime.

**Input**:

+ ```tree```: outputted divergence tree from ```rule tree```
+ ```alignment```: alignment files for each segment provided in ```rule files```
+ ```dates```: ```strain_dates.csv``` provided in ```rule files``` (see **Prerequisites 3**)

**Ouptut**:

+ ```tree```: rooted divergence tree for each segment
		
### ```rule treesort```:

Runs TreeSort at each replicate using the alignments and the rooted trees.

**Input**:

+ ```descriptor```: ```descriptor.csv``` provided in ```rule files``` (see **Prerequisites 5b**)
+ ```trees```: outputted rooted divergence trees from ```rule root```

**Ouptut**:

+ ```tree```: backbone tree annotated with reassortments outputted by TreeSort

### ```rule prep```:

Converts the replicate treesort trees into Newick format for use in ```rule rea```.
This rule calls ```prep.py``` which is described in more detail in ```Scripts```.

**Input**:

+ ```tree```: outputted replicate treesort tree from ```rule treesort```

**Ouptut**:

+ ```outdir```: replicate treesort tree converted to newick format and readable by [Baltic](https://github.com/evogytis/baltic/tree/master) used in ```rule rea```

### ```rule rea```:

Generates reassortment node data for each replicate treesort tree for use in ```rule summary```. Randomly assigns uncertain reassortment events to one sibling brach in the tree.
This rule calls ```rea.py``` which is described in more detail in ```Scripts```.

**Input**:

+ ```tree```: replicate treesort tree in newick format from ```rule prep```

**Ouptut**:

+ ```json```: reassortment node data for each replicate treesort tree for use in ```rule summary```

### ```rule summary```:

Aggregates treesort replicate data generated in ```rule rea``` to produce a consensus tree and node data with confidence values used for cladeset mapping & augur export.
This rule calls ```summary.py``` which is described in more detail in ```Scripts```.

**Input**:

+ ```jsons```: reassortment node data jsons for each replicate treesort tree provided by ```rule rea```
+ ```backbone```: backbone divergence tree provided in ```rule files```

**Ouptut**:

+ ```nwk_tree```: backbone tree annotated with frequently inferred reassortments (default threshold: inferred in ≥95% of the runs) in Newick format, used by downstream rules.
+ ```nexus_tree```: backbone tree annotated with frequently inferred reassortments (default threshold: inferred in ≥95% of the runs) in Nexus format
+ ```node_data```: node-data containing 1) reassortments that pass the majority threshold and 2) less frequent events recorded with confidence values

### ```rule cladeset-mapping```

Maps high-confidence reassortment events inferred by `rule summary` onto a canonical backbone tree to enable visualization in Auspice.  
This  calls `mapper.py`, which is described in more detail in `Scripts`. This script was was developed by Stephen Shank in the Moncla lab.

**Input**:

+ `summary_json`: reassortment summary JSON generated by `rule summary`
+ `source_tree`: summary TreeSort tree generated by `rule summary`
+ `target_tree`: original backbone tree (before TreeSort was run on it) provided in `rule files`

**Output**:

+ `output_labeled_tree`: backbone tree with resolved topology designed for `rule export` visualization
+ `output_node_data`: node data matched to the output tree containing 1) reassortments that pass the majority threshold and 2) less frequent events recorded with confidence values

### ```rule log```

Calculates the reassortment rate for each TreeSort replicate tree and logs it in a csv file. 
This calls `rea_rate.py`, which is described in more detail in `Scripts`. This code was adapted from Alexey Markin's [`reassortment_utils.py`](https://github.com/flu-crew/TreeSort/blob/main/treesort/reassortment_utils.py).

**Input**:

+ `trees`: replicate TreeSort trees made readable for `Baltic` in `rule prep`
+ `summary_tree`: summary backbone tree for use in molecular clock estimation needed for reassortment rate calculations
+ `aln`: backbone alignment file for use in molecular clock estimation needed for reassortment rate calculations

**Output**:

+ `log_csv`: a csv file that records the inferred reassortment rate for each replicate tree for use in downstream analyses

### ```rule ancestral/translate/traits```

See [nextstrain documentation](https://docs.nextstrain.org/projects/augur/en/stable/usage/cli/cli.html)

*Note:* there are two `rule traits`.
+ `rule traits_treesort` is used for the `nwk_tree` output of `rule summary`
+ `rule traits_cladeset` is used for the `export_tree` output of `rule cladeset`

### ```rule export```

Visualizes summary tree and node data with [nextstrain augur/auspice](https://docs.nextstrain.org/projects/auspice/en/stable/).
This allows you to drag and drop the auspice json (which after running the pipeline can be found in ```results/summary/treesort_auspice/treesort.json```) at [auspice.us](https://auspice.us) to visualize the consensus tree generated in ```rule summary```.

## Scripts

### ```to-add-dates.py```

**To run:**

	python scripts/add_dates.py \
	  --subtype SUBTYPE \
	  --aln PATH_TO_ALIGNMENTS \
	  --backbone BACKBONE_SEGMENT \
	  --meta PATH_TO_METADATA \
	  --d tsv|csv

**Arguments:**
	
	--subtype: The subtype string used in your filenames (e.g., "h3nx" for files like h3nx_ha.fasta)
	--aln: Path to the folder containing your alignment files
	--backbone: The segment that is your backbone (e.g., "ha")
	--meta: Path to the metadata file corresponding to the backbone segment
	--d: Format of the metadata file: either "tsv" or "csv" (default: tsv)

 ### ```strain-dates-csv-maker.py```

**To run:**

	python scripts/strain-dates-csv-maker.py \
 	 --aln PATH_TO_ALIGNMENT_FILE

**Arguments:**
	
	--aln: Path to the alignment file for your backbone segment (must have headers in the format "strain|YYYY-MM-DD")

### ```descriptor.py```

**To run:**

	python scripts/descriptor.py \
	  --backbone BACKBONE_SEGMENT \
	  --subtype SUBTYPE \
	  --alns PATH_TO_ALIGNMENTS \
	  --trees PATH_TO_ROOTED_TREES

**Arguments:**
	
	--backbone: The segment that will be treated as the backbone (e.g., "ha")
	--subtype: The subtype string used in your filenames (e.g., "h3nx" for files like h3nx_ha.fasta)
	--alns: Path to the folder containing your alignment files
	--trees: Path to the folder containing your rooted tree files (it is assumed here that you used the snakemake to create these trees so it follows that format)

### ```to_nwk.py```

**To run:**

	python scripts/to_nwk.py \
	  --tree PATH_TO_NEXUS_TREE \
	  --output OUTPUT_NEWICK_FILE
   
**Arguments:**
	
	--tree: Path to the input tree file in Nexus format
	--output: Desired name of the output Newick (.nwk or .newick) file (e.g., "output.nwk")

### ```prep.py```

**Description:** 

Called in ```rule prep```.

Prepares the annotated Treesort output tree so it can be parsed by Baltic as used in ```rule rea```.  

This script:  
1. Converts treesort Nexus tree output to Newick.  
2. Replaces commas with `-` in reassorted segment annotations.  
3. Removes quotation marks around `TS_NODE_####` labels.  
4. Replaces `?` with `_` for uncertain reassortment events.  

**To run:**  

	python scripts/prep.py \
	  --tree PATH_TO_TREESORT_TREE \
	  --outdir OUTPUT_NEWICK_FILE

**Arguments:**

	--tree : path to the annotated reassortment tree in Nexus format (output from rule treesort)
	--outdir : path for the Baltic-readable tree in Newick format (used in rule rea)

### ```rea.py```

Called in ```rule rea```.

**Description:**  
Processes annotated Treesort output trees with uncertain reassortment events so they can be later summarized across runs.  

This script:  
1. Identifies sibling branches with uncertain reassortment events and randomly assigns uncertain segments to one child branch while removing them from the other.  
2. Generates a ```rea.json``` node data file annotating reassortment status, reassorted segments, and divergence values for each node and leaf.  

```reassortment_counter()``` was adapted from Jordan Ort's implementation using the phylo.bio package and translated for use with Baltic.  

**To run:**  

	python scripts/resolve_reassortment.py \
	  --tree PATH_TO_BALTIC_TREE \
	  --outdir OUTPUT_JSON_FILE

**Arguments:**

	--tree : path to the Baltic-readable tree in Newick format
	--outdir : path to the reassortment node data for use in rule summary

### ```summary.py```

Called in ```rule summary```.

**Description:**  
Generates a consensus summary newick tree and its associated node data featuring majority-inferred reassortment events across multiple Treesort replicates.  

This script:  
1. Reads in each replicate's reassortment node data produced in ```rule rea```.  
2. Computes consensus reassortment calls (including reassorting segments) for each node based on a confidence threshold (default: 0.95).  
4. Outputs a node data file with reassortment confidences and divergence values for use in downstream ```rule export```.  
5. Produces a summary backbone tree annotated with high-confidence reassortments in both Newick and Nexus formats.  

**To run:**  

	python scripts/summary.py \
	  --jsons LIST_OF_REASSORTMENT_JSONS \
	  --backbone BACKBONE_TREE \
	  --threshold 0.95 \ #default
	  --summary_nwk OUTPUT_SUMMARY_TREE.nwk \
	  --summary_nexus OUTPUT_SUMMARY_TREE.nexus \
	  --node_data OUTPUT_NODE_DATA.json

**Arguments:**

	--jsons : List of reassortment JSON files (from multiple Treesort replicates).
	--backbone : Backbone tree (Newick format) on which reassortments are placed.
	--threshold : Confidence threshold (default: 0.95) for annotating reassortment events and segments.
	--summary_nwk : Path to the output consensus tree in Newick format.
	--summary_nexus : Path to the output consensus tree in Nexus format.
	--node_data : Path to the output JSON file containing consensus reassortment data with confidences and entropy values.

### ```mapper.py```

Called in ```rule cladeset_map```.

**Description:**  

Maps high-confidence reassortment events from a Treesort summary onto a canonical backbone tree for visualization in Auspice.  

This script:  
1. Loads the reassortment summary JSON generated by `rule summary`.   
2. Builds leaf set mappings from both the source (Treesort) and target (backbone) trees.  
3. Uses an efficient ancestral walk algorithm to map reassortment events from source nodes to corresponding nodes in the target tree.  
4. Outputs a labeled backbone tree in Newick format with standardized node labels.  
5. Produces an augur-compatible node data JSON with reassorted status, event confidence, and segment-level annotations for use in downstream `rule export`. 

**To run:**  

	python scripts/mapper.py \
		--summary_json SUMMARY_REASSORTMENT.json \
		--source_tree SOURCE_TREESORT.nwk \
		--target_tree BACKBONE_TREE.nwk \
		--output_labeled_tree OUTPUT_LABELED_TREE.nwk \
		--output_node_data OUTPUT_NODE_DATA.json \
		--debug # optional

**Arguments:**

	`summary_json`: reassortment summary JSON generated by `rule summary`
	`source_tree`: summary TreeSort tree generated by `rule summary`
	`target_tree`: original backbone tree (before TreeSort was run on it) provided in `rule files`
	`output_labeled_tree`: backbone tree with resolved topology designed for `rule export` visualization
	`output_node_data`: node data matched to the output tree containing 1) reassortments that pass the majority threshold and 2) less frequent events recorded with confidence values

### ```rea_rate_.py```

Called in ```rule log```.

**Description:**  

Estimates reassortment rates from replicate TreeSort trees and records them in a CSV log.  

This script:  
1. Parses sampling dates from the provided backbone alignment.  
2. Fits a molecular clock to the summary tree using TreeTime to estimate the evolutionary rate from sampling dates.  
3. Loads each replicate tree with Baltic and identifies reassortment events annotated on internal nodes.  
4. Computes reassortment rates using two methods:  
   - **Simple rate**: event counts normalized by total tree length and scaled by clock rate.  
   - **Binary MLE rate**: maximum likelihood estimation of the reassortment rate that is an optimization of the simple rate.  
5. Writes out a log csv of reassortment rates across replicates.  

**To run:**  

	python scripts/log.py \
		--trees REPLICATE_TREES.nwk \
		--backbone SEGMENT_NAME \
		--summary_tree SUMMARY_TREE.nwk \
		--backbone_aln BACKBONE_ALIGNMENT.fasta \
		--log_file OUTPUT_LOG.csv

**Arguments:**

	trees: one or more replicate trees generated by TreeSort, in Newick format
	backbone: segment name to be treated as the backbone (e.g., PB2, NP, HA)
	summary_tree: consensus summary tree used for clock rate estimation
	backbone_aln: alignment corresponding to the backbone segment, used to extract tip dates
	log_file: output CSV file containing reassortment rates per replicate
