"""Here, define your wildcards. To include more subtypes or gene segments, simply
add those to these lists, separated by commas"""
SUBTYPES = ["h3nx"]
SEGMENTS = ["pb2","pb1","na","np","pa","ns","mp"]
REPS = range(1000)

rule all:
	input:
		treesort = expand("results/{rep}/ha_treesort.tre", subtype=SUBTYPES, segment=SEGMENTS, rep= REPS)

"""Specify all input files here.  """
rule files:
    params:
        aln = "data/alignments/{subtype}_{segment}.fasta",
        dates = "data/strain_dates.csv",
        treesort_descriptor = "descriptor.csv"

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
        tree = "results/{rep}/trees_rooted/{subtype}_{segment}_rooted/rerooted.newick",
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
    	  tree = "results/{rep}/ha_treesort.tre"
    shell:
    	"""
        # Copy only what treesort needs
        mkdir -p results/{wildcards.rep}/data/alignments
        mkdir -p results/{wildcards.rep}/data/ha
        mkdir -p results/{wildcards.rep}/results/trees_rooted
        
        # Copy FASTA files only (not logs)
        cp data/alignments/*.fasta results/{wildcards.rep}/data/alignments/
        
        # Copy descriptor
        cp {input.descriptor} results/{wildcards.rep}/

        # Copy HA tree
        cp data/ha/output.nwk results/{wildcards.rep}/data/ha
        
        # Run treesort in isolated environment
        cd results/{wildcards.rep}
        treesort -i descriptor.csv -o ha_treesort.tre --no-collapse
        
        # Copy result back and cleanup
        rm -rf results/{wildcards.rep}/data results/{wildcards.rep}/results/trees_rooted results/{wildcards.rep}/descriptor.csv
        rm -rf results/{wildcards.rep}/treesort-descriptor-*/descriptor.csv.concatenated.fasta
		"""	
