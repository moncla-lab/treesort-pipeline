"""Here, define your wildcards. To include more subtypes or gene segments, simply
add those to these lists, separated by commas"""
SUBTYPES = ["h3nx"]
SEGMENTS = ["pb2","pb1","na","np","pa","ns","mp"]
REPS = range(3)

rule all:
	input:
		"results/summary/treesort_auspice/treesort.json",
		"results/summary/log.csv"
	

"""Specify all input files here.  """
rule files:
	params:
		backbone = "ha",
		aln = "EXAMPLE_DATA/alignments/{subtype}_{segment}.fasta",
		dates = "EXAMPLE_DATA/strain_dates.csv",
		treesort_descriptor = "descriptor.csv",
		backbone_tree = "EXAMPLE_DATA/backbone/backbone.nwk",
		target_tree = "EXAMPLE_DATA/backbone/original.nwk",
		backbone_aln = "EXAMPLE_DATA/alignments/h3nx_ha.fasta",
		metadata = "EXAMPLE_DATA/metadata.csv",
		reference = "EXAMPLE_DATA/config/ref/h3nx_ha.gb",
		colors = "EXAMPLE_DATA/config/colors_h3nx.tsv",
		lat_long = "EXAMPLE_DATA/config/lat_longs_h3nx.tsv",
		auspice_config = "EXAMPLE_DATA/config/auspice_config_h3nx.json"
		

files = rules.files.params

rule tree:
	message: "Building tree"
	input:
		alignment = files.aln
	output:
		tree = "results/{rep}/trees_unrooted/{subtype}_{segment}.nwk"
	params:
		method = "iqtree"
	shadow:
		"minimal"
	shell:
		"""
		augur tree \
			--alignment {input.alignment} \
			--output {output.tree} \
			--method {params.method} \
			--nthreads 1
		"""
		
rule root:
	message: "Inferring root"
	input:
		tree = rules.tree.output.tree,
		alignment = files.aln,
		dates = files.dates
	output:
		tree = "results/{rep}/trees_rooted/{subtype}_{segment}_rooted/rerooted.newick"
	shell:
		"""
		treetime clock \
			--tree {input.tree} \
			--dates {input.dates} \
			--aln {input.alignment} \
			--outdir "results/{wildcards.rep}/trees_rooted/{wildcards.subtype}_{wildcards.segment}_rooted"
		"""
	   
rule treesort:
	message: "running treesort to infer reassortment events"
	input:
		descriptor = files.treesort_descriptor,
		trees = expand(
			"results/{{rep}}/trees_rooted/{subtype}_{segment}_rooted/rerooted.newick",
			subtype=SUBTYPES,
			segment=SEGMENTS
		)
	output:
		  tree = "results/{rep}/annotated.tre"
	shell:
		"""
		# Copy only what treesort needs
		mkdir -p results/{wildcards.rep}/EXAMPLE_DATA/alignments
		mkdir -p results/{wildcards.rep}/EXAMPLE_DATA/backbone
		
		# Copy FASTA files only (not logs)
		cp EXAMPLE_DATA/alignments/*.fasta results/{wildcards.rep}/EXAMPLE_DATA/alignments/
		
		# Copy descriptor
		cp {input.descriptor} results/{wildcards.rep}/

		# Copy backbone tree
		cp EXAMPLE_DATA/backbone/backbone.nwk results/{wildcards.rep}/EXAMPLE_DATA/backbone
		
		# Run treesort in isolated environment
		cd results/{wildcards.rep}
		treesort -i descriptor.csv -o annotated.tre --no-collapse
		
		# Copy result back and cleanup
		rm -rf results/{wildcards.rep}/EXAMPLE_DATA results/{wildcards.rep}/results/trees_rooted results/{wildcards.rep}/descriptor.csv
		rm -rf results/{wildcards.rep}/treesort-descriptor-*/descriptor.csv.concatenated.fasta
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
	message: "creating a summary tree and node data with high confidence reassortments"
	input:
		jsons = expand("results/{rep}/rea.json", rep=REPS),
		backbone = files.backbone_tree
	output:
		nwk_tree = "results/summary/summary.nwk",
		nexus_tree = "results/summary/summary.nexus",
		node_data = "results/summary/summary.json"
	shell:
		"python scripts/summary.py --jsons {input.jsons} --backbone {input.backbone} --threshold 0.95 --summary_nwk {output.nwk_tree} --summary_nexus {output.nexus_tree} --node_data {output.node_data}"

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
		"python scripts/mapper.py --summary_json {input.node_data} --source_tree {input.source} --target_tree {input.target} --output_labeled_tree {output.export_tree} --output_node_data {output.node_data} --debug > {output.debug_path}"

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
		"python scripts/rea_rate.py --backbone {files.backbone} --trees {input.trees} --summary_tree {input.summary_tree} --backbone_aln {input.aln} --log_file {output.log_csv}"

rule ancestral:
	message: "Reconstructing ancestral sequences and mutations"
	input:
		tree = rules.cladeset_map.output.export_tree,
		alignment = files.backbone_aln
	output:
		node_data = "results/summary/cladeset/div_tree/nt_muts/nt-muts.json"
	params:
		inference = "joint"
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
	message: "Exporting data files for for auspice"
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

