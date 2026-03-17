"""Here, define your wildcards. To include more subtypes or gene segments, simply
add those to these lists, separated by commas"""
SUBTYPES = ["h3nx"]
SEGMENTS = ["pb2","pb1","na","np","pa","ns","mp"]
REPS = range(3)

rule all:
	input:
		"results/summary/treesort_auspice/treesort.json",
		"results/summary/log.csv",
		"results/summary/traits/traits.json",
		"results/diagnostics/unmapped_targets.json",
		"results/diagnostics/unannotated_nodes.json",
		"results/diagnostics/auspice_validation.json",
		"results/diagnostics/verify.done",
		"results/benchmarks/all_benchmarks_detailed.csv",
		"results/benchmarks/all_benchmarks_summary.csv"


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
	benchmark:
		"results/benchmarks/tree/{rep}/{subtype}_{segment}.tsv"
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
	benchmark:
		"results/benchmarks/root/{rep}/{subtype}_{segment}.tsv"
	shell:
		"""
		treetime clock \
			--tree {input.tree} \
			--dates {input.dates} \
			--aln {input.alignment} \
			--outdir "results/{wildcards.rep}/trees_rooted/{wildcards.subtype}_{wildcards.segment}_rooted"
		"""

rule treesort_prep:
	message: "copying files into per-rep working directory for treesort"
	input:
		descriptor = files.treesort_descriptor,
		trees = expand(
			"results/{{rep}}/trees_rooted/{subtype}_{segment}_rooted/rerooted.newick",
			subtype=SUBTYPES,
			segment=SEGMENTS
		)
	output:
		done = touch("results/{rep}/treesort_prep.done")
	benchmark:
		"results/benchmarks/treesort_prep/{rep}.tsv"
	shell:
		"""
		mkdir -p results/{wildcards.rep}/EXAMPLE_DATA/alignments
		mkdir -p results/{wildcards.rep}/EXAMPLE_DATA/backbone
		cp EXAMPLE_DATA/alignments/*.fasta results/{wildcards.rep}/EXAMPLE_DATA/alignments/
		cp {input.descriptor} results/{wildcards.rep}/
		cp EXAMPLE_DATA/backbone/backbone.nwk results/{wildcards.rep}/EXAMPLE_DATA/backbone
		"""

rule treesort:
	message: "running treesort to infer reassortment events"
	input:
		prep_done = rules.treesort_prep.output.done
	output:
		tree = "results/{rep}/annotated.tre"
	benchmark:
		"results/benchmarks/treesort/{rep}.tsv"
	shell:
		"""
		cd results/{wildcards.rep}

		max_attempts=10
		for attempt in $(seq 1 $max_attempts); do
			treesort -i descriptor.csv -o annotated.tre --no-collapse && break
			echo "treesort attempt $attempt failed, retrying..." >&2
			rm -f annotated.tre
		done

		if [ ! -s annotated.tre ]; then
			echo "treesort failed to produce non-empty annotated.tre after $max_attempts attempts" >&2
			exit 1
		fi

		# Cleanup temporary copies
		rm -rf EXAMPLE_DATA results/trees_rooted descriptor.csv
		rm -rf treesort-descriptor-*/descriptor.csv.concatenated.fasta
		"""

rule prep:
	message: "converting annotated treesort tree into a newick to be read in by rule rea"
	input:
		tree = rules.treesort.output.tree
	output:
		outdir = "results/{rep}/output.nwk"
	benchmark:
		"results/benchmarks/prep/{rep}.tsv"
	shell:
		"python scripts/prep.py --tree {input.tree} --outdir {output.outdir}"

rule rea:
	message: "creating a reassortment summary json for each tree"
	input:
		tree = rules.prep.output.outdir
	output:
		json = "results/{rep}/rea.json",
	benchmark:
		"results/benchmarks/rea/{rep}.tsv"
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
	benchmark:
		"results/benchmarks/summary/summary.tsv"
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
	benchmark:
		"results/benchmarks/cladeset_map/cladeset_map.tsv"
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
	benchmark:
		"results/benchmarks/log/log.tsv"
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
	benchmark:
		"results/benchmarks/ancestral/ancestral.tsv"
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
	benchmark:
		"results/benchmarks/translate/translate.tsv"
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
	benchmark:
		"results/benchmarks/traits_cladeset/traits_cladeset.tsv"
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
	benchmark:
		"results/benchmarks/traits_treesort/traits_treesort.tsv"
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
	benchmark:
		"results/benchmarks/export/export.tsv"
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

rule diagnose_unmapped_targets:
	message: "Diagnosing unmapped target nodes"
	input:
		source = files.backbone_tree,
		target = files.target_tree,
		_cladeset_done = rules.cladeset_map.output.node_data
	output:
		json = "results/diagnostics/unmapped_targets.json"
	threads: 1
	resources:
		mem_mb=200,
		runtime=5
	benchmark:
		"results/benchmarks/diagnose_unmapped_targets/diagnose_unmapped_targets.tsv"
	shell:
		"python scripts/diagnose_unmapped_targets.py --source {input.source} --target {input.target} --output {output.json}"

rule diagnose_unannotated:
	message: "Diagnosing unannotated target nodes"
	input:
		target = files.target_tree,
		node_data = rules.cladeset_map.output.node_data
	output:
		json = "results/diagnostics/unannotated_nodes.json"
	threads: 1
	resources:
		mem_mb=200,
		runtime=5
	benchmark:
		"results/benchmarks/diagnose_unannotated/diagnose_unannotated.tsv"
	shell:
		"python scripts/diagnose_unannotated.py --target {input.target} --node_data {input.node_data} --output {output.json}"

rule validate_auspice_annotations:
	message: "Validating reassortment annotations in Auspice export"
	input:
		auspice = rules.export.output.auspice_json,
		unannotated = rules.diagnose_unannotated.output.json
	output:
		json = "results/diagnostics/auspice_validation.json"
	threads: 1
	resources:
		mem_mb=200,
		runtime=5
	benchmark:
		"results/benchmarks/validate_auspice/validate_auspice.tsv"
	shell:
		"python scripts/validate_auspice_annotations.py --auspice {input.auspice} --unannotated {input.unannotated} --output {output.json}"

rule verify_diagnostics:
	message: "Verifying diagnostic outputs"
	input:
		unmapped = rules.diagnose_unmapped_targets.output.json,
		unannotated = rules.diagnose_unannotated.output.json,
		auspice = rules.validate_auspice_annotations.output.json
	output:
		done = touch("results/diagnostics/verify.done")
	shell:
		"python scripts/verify_diagnostics.py"

rule aggregate_benchmarks:
	message: "Aggregating all benchmark statistics"
	input:
		tree = expand("results/benchmarks/tree/{rep}/{subtype}_{segment}.tsv",
			rep=REPS, subtype=SUBTYPES, segment=SEGMENTS),
		root = expand("results/benchmarks/root/{rep}/{subtype}_{segment}.tsv",
			rep=REPS, subtype=SUBTYPES, segment=SEGMENTS),
		treesort_prep = expand("results/benchmarks/treesort_prep/{rep}.tsv", rep=REPS),
		treesort = expand("results/benchmarks/treesort/{rep}.tsv", rep=REPS),
		prep = expand("results/benchmarks/prep/{rep}.tsv", rep=REPS),
		rea = expand("results/benchmarks/rea/{rep}.tsv", rep=REPS),
		summary = "results/benchmarks/summary/summary.tsv",
		cladeset_map = "results/benchmarks/cladeset_map/cladeset_map.tsv",
		log = "results/benchmarks/log/log.tsv",
		ancestral = "results/benchmarks/ancestral/ancestral.tsv",
		translate = "results/benchmarks/translate/translate.tsv",
		traits_cladeset = "results/benchmarks/traits_cladeset/traits_cladeset.tsv",
		traits_treesort = "results/benchmarks/traits_treesort/traits_treesort.tsv",
		export = "results/benchmarks/export/export.tsv",
		diagnose_unmapped = "results/benchmarks/diagnose_unmapped_targets/diagnose_unmapped_targets.tsv",
		diagnose_unannotated = "results/benchmarks/diagnose_unannotated/diagnose_unannotated.tsv",
		validate_auspice = "results/benchmarks/validate_auspice/validate_auspice.tsv"
	output:
		detailed = "results/benchmarks/all_benchmarks_detailed.csv",
		summary = "results/benchmarks/all_benchmarks_summary.csv"
	shell:
		"""
		python scripts/aggregate_benchmarks.py \
			--benchmarks {input.tree} {input.root} {input.treesort_prep} {input.treesort} {input.prep} {input.rea} \
				{input.summary} {input.cladeset_map} {input.log} {input.ancestral} \
				{input.translate} {input.traits_cladeset} {input.traits_treesort} {input.export} \
				{input.diagnose_unmapped} {input.diagnose_unannotated} {input.validate_auspice} \
			--detailed {output.detailed} \
			--summary {output.summary}
		"""
