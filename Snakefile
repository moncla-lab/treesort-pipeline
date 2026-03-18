"""Here, define your wildcards. To include more subtypes or gene segments, simply
add those to these lists, separated by commas"""
SUBTYPES = ["h3nx"]
SEGMENTS = ["pb2","pb1","na","np","pa","ns","mp"]
REPS = range(1000)

rule all:
	input:
		"results/summary/treesort_auspice/treesort.json",
		"results/summary/log.csv",
		"results/summary/traits/traits.json"
	

"""Specify all input files here.  """
rule files:
	params:
		backbone = "ha",
		aln = "data/alignments/{subtype}_{segment}.fasta",
		dates = "data/strain_dates.csv",
		treesort_descriptor = "descriptor.csv",
		backbone_tree = "data/backbone/backbone.nwk",
		target_tree = "data/backbone/original.nwk",
		backbone_aln = "data/alignments/h3nx_ha.fasta",
		metadata = "data/metadata.csv",
		reference = "data/config/ref/h3nx_ha.gb",
		colors = "data/config/colors_h3nx.tsv",
		lat_long = "data/config/lat_longs_h3nx.tsv",
		auspice_config = "data/config/auspice_config_h3nx.json"
		

files = rules.files.params

rule tree:
	message: "Building tree"
	resources:
		mem_mb = 3000
	shadow: "shallow"
	input:
		alignment = files.aln
	output:
		tree = "results/{rep}/trees_unrooted/{subtype}_{segment}.nwk"
	threads: 1
	params:
		method = "iqtree"
	shell:
		"""
		#Add some random sleeping so we don't overwhelm RAM and storage
		sleep $[ ( $RANDOM % 2 ) + 1 ]s
		
		#Isolation of input
		cp {input.alignment} temp_align.fasta
		
		# Force RAM shadow directory use
		export TMPDIR=$(pwd)
		export TEMP=$(pwd)
		export TMP=$(pwd)
		
		ulimit -s unlimited
		export MALLOC_TRIM_THRESHOLD_=-1
		export OMP_NUM_THREADS={threads}

		mkdir -p $(dirname {output.tree})

		augur tree \
			--alignment temp_align.fasta \
			--output {output.tree} \
			--method {params.method} \
			--nthreads {threads}
		
		#Cooldown
		sleep $[ ( $RANDOM % 2 ) + 1 ]s
		"""
		
rule root:
	message: "Inferring root"
	resources:
		mem_mb = 3000
	threads: 1
	input:
		tree = rules.tree.output.tree,
		alignment = files.aln,
		dates = files.dates
	output:
		tree = "results/{rep}/trees_rooted/{subtype}_{segment}_rooted/rerooted.newick"
	shadow: "shallow"
	shell:
		"""
		#Add some random sleeping so we don't overwhelm RAM and storage
		sleep $[ ( $RANDOM % 2 ) + 1 ]s
		
		# Stabilize things
		ulimit -s unlimited
		ulimit -l 100000000
		export MALLOC_TRIM_THRESHOLD_=-1
		
		# Force RAM shadow directory use
		export TMPDIR=$(pwd)
		export TEMP=$(pwd)
		export TMP=$(pwd)
		
		mkdir -p $(dirname {output.tree})

		treetime clock \
			--tree {input.tree} \
			--dates {input.dates} \
			--aln {input.alignment} \
			--outdir $(dirname {output.tree})
		
		#Cooldown
		sleep $[ ( $RANDOM % 2 ) + 1 ]s
		"""
	   
rule treesort:
	message: "Running treesort for rep {wildcards.rep}"
	threads: 4
	retries: 5
	
	#Throttle how many of these rules can run at once.
	resources:
		treesort_limit = 1,
		mem_mb = 30000
	input:
		descriptor = files.treesort_descriptor,
		backbone_tree = files.backbone_tree,
		trees = expand(
			"results/{{rep}}/trees_rooted/{subtype}_{segment}_rooted/rerooted.newick",
			subtype=SUBTYPES,
			segment=SEGMENTS
			)
	output:
		  tree = "results/{rep}/annotated.tre"
	log:
		"results/{rep}/treesort.log"
	shadow: "shallow"
	shell:	
		"""		
		#Add some random sleeping so we don't overwhelm RAM and storage
		sleep $[ ( $RANDOM % 2 ) + 1 ]s
		
		# Increase stack and memory size for good measure bc likely using high threads
		ulimit -c 0
		ulimit -s unlimited
		ulimit -l 100000000
		
		# Attempt to prevent high core systems from creating memory allocation issues
		export MALLOC_ARENA_MAX=1
		export MALLOC_TRIM_THRESHOLD_=-1		
		#export OMP_NUM_THREADS={threads}
		#export MKL_NUM_THREADS={threads}
		#export OPENBLAS_NUM_THREADS={threads}
		#export VECLIB_MAXIMUM_THREADS={threads}
		#export NUMEXPR_NUM_THREADS={threads}
		
		# Force RAM shadow directory use
		export TMPDIR=$(pwd)
		export TEMP=$(pwd)
		export TMP=$(pwd)

		# Create temp dir structure this rule expects inside the RAM backed shadow dir
		mkdir -p data/ha
		
		# Symlink from expected location of backbone to where it is actually located
		ln -sf ../../{input.backbone_tree} data/ha/output.nwk
		
		# Recreate expected nested tree structure since tempfs is a flat dir
		for tree_path in {input.trees}; do
		FILE_PATH=$(echo "$tree_path" | cut -d'/' -f3-)
		DIR_NAME=$(dirname "$FILE_PATH")
		mkdir -p "$DIR_NAME"
		#Link file on nv storage to this RAM backed dir
		ln -sf "../../$tree_path" "$FILE_PATH"
		done
		
		#Create output in shadow directory
		mkdir -p $(dirname {output.tree})

		# Run treesort directly using symlink to root dir
		treesort -i {input.descriptor} -o annotated.tre --no-collapse || true
		
		#Cooldown
		sleep $[ ( $RANDOM % 2 ) + 1 ]s
		
		if [ -s "annotated.tre" ]; then
			echo "Treesort output detected. Ignoring potential exit code 139." >> {log}
			mv annotated.tre $(dirname {output.tree})/
		else
			echo "Treesort failed: Output file missing or empty." >> {log}
			exit 1
		fi
		"""
		
rule prep:
	message: "converting annotated treesort tree into a newick to be read in by rule rea"
	input:
		tree = rules.treesort.output.tree
	output:
		outdir = "results/{rep}/output.nwk"
	shell:
		"python scripts/prep.py --tree {input.tree} --outdir {output.outdir}"
		
rule rea:
	message: "creating a reassortment summary json for each tree"
	input:
		tree = rules.prep.output.outdir
	output:
		json = "results/{rep}/rea.json",
	shell:
		"python scripts/rea.py --tree {input.tree} --outdir {output.json}"
		
rule summary:
	message: "creating a summary tree and node data with replicates"
	input:
		jsons = expand("results/{rep}/rea.json", rep=REPS),
		backbone = files.backbone_tree
	output:
		nwk_tree = "results/summary/summary.nwk",
		nexus_tree = "results/summary/summary.nexus",
		node_data = "results/summary/summary.json",
		manifest = "results/summary/input_manifest.txt"
	resources:
		mem_mb = 64000
	run:
		#Write the too long file list to text file
		with open(output.manifest, 'w') as f:
			for json_path in input.jsons:
				f.write(json_path + "\n")
		shell(
			"""
			sleep $[ ( $RANDOM % 10 ) + 1 ]s
			
			ulimit -n 65000
			export MALLOC_ARENA_MAX=1
			
			python scripts/summary.py --jsons {output.manifest} --backbone {input.backbone} --threshold 0.95 --summary_nwk {output.nwk_tree} \
			--summary_nexus {output.nexus_tree} --node_data {output.node_data}
			"""
		)

# stephen shank wrote mapper.py
rule cladeset_map:
	message: "mapping reassortments back to the original topology"
	input:
		node_data = rules.summary.output.node_data,
		source = files.backbone_tree,
		target = files.target_tree
	output:
		export_tree = "results/summary/cladeset/treesort.nwk",
		node_data = "results/summary/cladeset/node.json",
		debug_path = "results/summary/cladeset/debug.txt"
	shell:
		"python scripts/mapper.py --support_threshold 0.95 --summary_json {input.node_data} --source_tree {input.source} --target_tree {input.target} --output_labeled_tree {output.export_tree} --output_node_data {output.node_data} --debug > {output.debug_path}"

rule log:
	message: "creating a log file of reassortment rates and segment info"
	input:
		jsons = expand("results/{rep}/rea.json", rep=REPS),
		trees = expand("results/{rep}/output.nwk", rep=REPS),
		summary_tree = rules.cladeset_map.output.export_tree,
		aln = files.backbone_aln
	output:
		log_csv = "results/summary/log.csv"
	shell:
		"""
		ulimit -n 65536
		python scripts/rea_rate.py --backbone {files.backbone} --trees {input.trees} --summary_tree {input.summary_tree} --backbone_aln {input.aln} --log_file {output.log_csv}
		"""

rule ancestral:
	message: "Reconstructing ancestral sequences and mutations"
	input:
		tree = rules.cladeset_map.output.export_tree,
		alignment = files.backbone_aln
	output:
		node_data = "results/summary/cladeset/div_tree/nt_muts/nt-muts.json"
	params:
		inference = "joint"
	shadow: "minimal"
	shell:
		"""
		augur ancestral \
			--tree {input.tree} \
			--alignment {input.alignment} \
			--output-node-data {output.node_data} \
			--inference {params.inference}\
			--keep-ambiguous
		"""

rule translate:
	message: "Translating amino acid sequences"
	input:
		tree = rules.cladeset_map.output.export_tree,
		node_data = rules.ancestral.output.node_data,
		reference = files.reference
	output:
		node_data = "results/summary/cladeset/div_tree/aa_muts/aa-muts.json"
	shell:
		"""
		augur translate \
			--tree {input.tree} \
			--ancestral-sequences {input.node_data} \
			--reference-sequence {input.reference} \
			--output {output.node_data}
		"""

rule traits_cladeset:
	message: "Inferring ancestral traits for {params.columns!s}"
	input:
		tree = rules.cladeset_map.output.export_tree,
		metadata = files.metadata
	output:
		node_data = "results/summary/cladeset/traits/traits.json"
	params:
		columns = 'host country region subtype order'
	shadow: "minimal"
	shell:
		"""
		augur traits \
			--tree {input.tree} \
			--metadata {input.metadata} \
			--output {output.node_data} \
			--columns {params.columns} \
			--confidence
		"""
		
rule traits_treesort:
	message: "Inferring ancestral traits for {params.columns!s}"
	input:
		tree = rules.summary.output.nwk_tree,
		metadata = files.metadata
	output:
		node_data = "results/summary/traits/traits.json"
	params:
		columns = 'host country region subtype order'
	shadow: "minimal"
	shell:
		"""
		augur traits \
			--tree {input.tree} \
			--metadata {input.metadata} \
			--output {output.node_data} \
			--columns {params.columns} \
			--confidence
		"""

"""This rule exports the results of the pipeline into JSON format, which is required
for visualization in auspice. To make changes to the categories of metadata
that are colored, or how the data is visualized, alter the auspice_config files"""

rule export:
	message: "Exporting data files for auspice"
	input:
		tree = rules.cladeset_map.output.export_tree,
		metadata = files.metadata,
		node_data = [rules.cladeset_map.output.node_data,rules.traits_cladeset.output.node_data,rules.ancestral.output.node_data,rules.translate.output.node_data],
		auspice_config = files.auspice_config,
		colors = files.colors,
		lat_long = files.lat_long
	output:
		auspice_json = "results/summary/treesort_auspice/treesort.json"
	shell:
		"""
		augur export v2 \
			--tree {input.tree} \
			--metadata {input.metadata} \
			--node-data {input.node_data}\
			--auspice-config {input.auspice_config} \
			--include-root-sequence \
			--colors {input.colors} \
			--lat-longs {input.lat_long} \
			--output {output.auspice_json}
		"""
