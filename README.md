
# Pipeline for running Treesort in replicate 

Warning: This repository is a work in progress. It will be integrated with a [cladeset-mapping tool](https://github.com/moncla-lab/treesort-cladeset-mapping) developed by Stephen Shank in the Moncla lab.

## Overview

This pipeline provides a snakemake framework to run [TreeSort](https://github.com/flu-crew/TreeSort/tree/main) in replicate 
to traverse over uncertainties in tree topology and produce reassortment confidence values for each node & leaf. Before running this pipeline, you must first run 
TreeSort once to generate the binarized backbone tree annotated with reassortment events (see **Prerequisites 2**). This backbone tree remains fixed across all replicates and is used as the input for each replicate run.

While this backbone tree input does not change, new divergence trees are generated for the challenge segments for each replicate run.
The ```--no-collapse``` flag is used during ```rule treesort``` to ensure that all annotated TreeSort tree outputs retain the same topology as the backbone.

By default, the pipeline runs ```REPS=range(1000)``` replicates, but this can be adjusted in the Snakefile. Due to its computational intensity, we recommend running the pipeline on an HPC system

**Coming soon:**

Once TreeSort has been run for all replicates, ```rule summary``` will generate:

* A summary node data JSON.
* A summary Newick tree.

The summary tree can be plotted in [Baltic](https://github.com/evogytis/baltic/tree/master) and serves as the source tree for the [cladeset-mapping tool](https://github.com/moncla-lab/treesort-cladeset-mapping).

The summary node data is used for ```rule export``` and allows the visualization of reassortment event and reassorting segment confidence at each node & leaf via the [nextstrain auspice dashboard](https://docs.nextstrain.org/projects/auspice/en/stable/).

**For now, you can use the summary notebooks ```rea.ipynb``` and then ```summary.ipynb``` and then use the Snakefile in the ```summary_export``` folder.**

## Installation

**  nextstrain-treesort conda environment instructions will be updated here **

			conda create -n nextstrain-treesort dendropy snakemake augur auspice

## Prerequisites 

1. This pipeline assumes you already have generated alignment files, metadata files, and divergence trees for your dataset.
   Things to keep in mind:
   
   	a. Each sample should include the strain name and collection date. For example, a fasta file header should look like:

   			>A/blue-winged_teal/Alberta/221/1978|1978-08-07
   	
   	b. The dates should be in YYYY-MM-DD format. Any incomplete dates should have a placeholder instead (ex: instead of 1978-XX-XX, it could be 1978-01-01).
   	
	Note: ```to-add-dates.py``` can be used to format your data in this way.
   
2. Run [TreeSort](https://github.com/flu-crew/TreeSort/tree/main) locally using your alignment files and divergences trees as inputs in the descriptor file.
   Make sure your backbone tree is rooted (per TreeSort's instructions). The command should look like:

			treesort -i descriptor.csv -o annotated.tre
				
3. Run your backbone alignment through ```strain-dates-csv-maker.py``` to create a ```strain_dates.csv``` required by TreeTime for ```rule root``` in the snakemake. 

			python strain-dates-csv-maker.py -aln 'path_to_your_backbone_alignment_file' 
				
4. Convert the TreeSort ```annotated.tre``` nexus output to a newick format using ```prep.py``` since 

5. Now you have all the required data to run the pipeline. The folder organization should be as follows:
	
	a. the ```data``` folder which should include:
		
	* a folder with your alignments
	* a folder named ```backbone``` with the annotated tree generated in (2) and converted to newick format in (4)
	* the ```strains_dates.csv``` generated in (3)
		
	b. your ```descriptor.csv``` file that points the corrects alignment and divergence tree paths for ```rule treesort```. 
	   
	You can edit the provided descriptor.csv by running ```descriptor.py```:
	   
	   		python descriptor.py -backbone "backbone-tree-filename-located-in-the-backbone-folder" -subtype "the-subtype-your-data-belongs-to"
		
	c. your ```Snakefile``` where you can tailor the wildcards to fit your data needs.

## Running the pipeline:

**1. Activate the conda environment:**
			
			conda activate nextstrain-treesort
			
**2. Check a dry run first:**

			snakemake -n all 

**3. Run the pipeline:**

			date > clock.txt; snakemake -k -j $NUMBER-OF-JOBS all; date >> clock.txt
	
Here, ```clock.txt``` records compute time. 
The ```-k``` flag tells snakemake that if there is an error, to keep going if with remaining independent jobs. 
Since this pipeline is parallelized, the ```-j``` flag denotes how many jobs to run at once. Thus, ```$NUMBER_OF_JOBS``` should be at least 1, and no more than the number of cores on your computer.
		
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

Runs TreeSort at each replicate using the alignments and the rooted trees 

**Input**:

+ ```descriptor```: ```descriptor.csv``` provided in ```rule files``` (see **Prerequisites 5b**)
+ ```trees```: outputted rooted divergence trees from ```rule root```

**Ouptut**:

+ ```tree```: backbone tree annotated with reassortments outputted by TreeSort

## ** COMING SOON:**

### ```rule summary```:

Generates a summary tree and node data used for cladeset mapping & augur export

### ```rule cladeset-mapping```

Resolves the TreeSort tree to match the topology of the unaltered rooted backbone tree

### ```rule ancestral/translate/traits```

See nextstrain documentation

### ```rule export```

Visualizes summary tree and node data with [nextstrain augur/auspice](https://docs.nextstrain.org/projects/auspice/en/stable/)
