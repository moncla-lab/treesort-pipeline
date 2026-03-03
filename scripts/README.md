# Scripts

## Pipeline Scripts

These scripts are called by the Snakefile as part of the main pipeline.

### `prep.py`

Preprocesses TreeSort output by converting nexus format to Newick, replacing commas with dashes in reassortment annotations, removing quote marks, and replacing "?" with "\_" to make the output compatible with Baltic.

### `rea.py`

Resolves uncertain reassortment events by randomly assigning ambiguous segments to sibling branches, then generates a JSON file documenting which nodes/leaves were reassorted and their divergence values across TreeSort runs.

### `summary.py`

Aggregates reassortment annotations from multiple TreeSort replicates into a single summary, applying confidence thresholds and entropy calculations. Generates annotated Newick/Nexus summary trees with reassortment metadata.

### `mapper.py`

Maps reassortment annotations from a TreeSort summary tree to a canonical target tree using leaf-set matching and ancestral walking. Produces a labeled target tree and Augur-compatible node data JSON.

### `rea_rate.py`

Estimates reassortment rates by calculating molecular clock rates from a summary tree, then computing overall and per-segment reassortment rates across TreeSort replicate trees using both simple counting and maximum likelihood estimation methods.

## Shared Libraries

### `tree_utils.py`

Shared dendropy-based utilities used by `mapper.py` and the diagnostic scripts. Provides functions for loading/normalizing trees, labeling internal nodes, building leaf-set mappings, and performing ancestral walks to match nodes between trees.

### `fasta_editing.py`

Utility module providing `fasta_to_df()` and `fasta_writer()` for converting between FASTA files and pandas DataFrames.

## Diagnostic Scripts

### `diagnose_unmapped_targets.py`

Identifies internal nodes in the target tree that receive zero mappings from any source node. For each unmapped node, reports its leaf count and the closest partial matches from the source tree.

### `diagnose_unannotated.py`

Identifies internal nodes in the target tree that are missing from the mapper's output (`node.json`). Reports counts and leaf-size statistics for the unannotated nodes.

### `validate_auspice_annotations.py`

Validates that reassortment annotations survive the Augur export into Auspice JSON format. Flags inconsistencies where unannotated nodes unexpectedly carry a `reassorted` attribute in the final export.

### `aggregate_benchmarks.py`

Collects Snakemake benchmark TSV files from all rules and produces two CSV reports: a detailed per-run file and a statistical summary (mean, median, std, min, max) grouped by rule.

## Data Preparation Scripts

These are standalone utilities for preparing input data.

### `add-dates.py`

Takes alignment FASTA files and metadata with dates, reformats strain headers as "strain|date" for TreeSort/TreeTime processing.

### `strain-dates-csv-maker.py`

Parses strain-date pairs from alignment headers (format: strain|date) and outputs a `strain_dates.csv` with decimal year format for TreeTime rooting.

### `descriptor.py`

Generates a `descriptor.csv` mapping gene segments (HA, PB2, etc.) to their corresponding alignment and rooted tree file paths, marking the backbone segment.

### `to_nwk.py`

Converts a Nexus format tree to Newick format by extracting the tree string.
