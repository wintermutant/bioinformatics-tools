# Configuration Conventions

This document describes the configuration conventions used in MARGIE workflows and helper functions.

## Overview

All workflow configuration is managed through YAML files and accessed via helper functions in `workflow_helpers.py`. These conventions ensure consistent, predictable behavior across all tools and workflows.

---

## `rc()` - Rule Config Lookup

**Function:** `rc(key, default=None, config=None)`

**Purpose:** Retrieve configuration values using dot notation for nested keys.

### Convention: Dot Notation for Nesting

Use dots (`.`) to traverse nested YAML structures, supporting arbitrary nesting depth.

### Examples

**Simple top-level lookup:**
```yaml
# config.yaml
input_fasta: /data/genome.fasta
```
```python
# In Snakefile
rc('input_fasta', config=config)
→ '/data/genome.fasta'
```

**Nested lookup:**
```yaml
# config.yaml
prodigal:
  threads: 4
  mem_mb: 4096
  runtime: 30
```
```python
# In Snakefile
rc('prodigal.threads', 1, config=config)
→ 4

rc('prodigal.mem_mb', 2048, config=config)
→ 4096

rc('prodigal.not_set', 999, config=config)
→ 999  # default value
```

**Deep nesting (unlimited depth):**
```yaml
# config.yaml
compute:
  cluster_default:
    account: my_slurm_account
    partition: cpu
    resources:
      default_mem_mb: 4000
```
```python
# In Snakefile
rc('compute.cluster_default.account', None, config=config)
→ 'my_slurm_account'

rc('compute.cluster_default.resources.default_mem_mb', 2000, config=config)
→ 4000
```

### Benefits

- **Intuitive:** Mirrors YAML structure directly
- **Flexible:** Supports unlimited nesting depth
- **Safe:** Returns default if any part of the path doesn't exist
- **Clean:** Single parameter instead of multiple arguments

---

## `build_filepath()` - Tool Output Paths

**Function:** `build_filepath(config_key, suffix, config=None)`

**Purpose:** Generate output file paths with optional user-specified base filenames.

### Convention: First Part is Tool Name

**CRITICAL RULE:** The first part of `config_key` (before the first dot) **ALWAYS** determines the tool/directory name.

This ensures predictable directory structure while supporting arbitrary nesting for tool variants, versions, or configurations.

### How It Works

1. **Extract tool name:** First part of `config_key` (e.g., `'prodigal'` from `'prodigal.output'`)
2. **Check for custom filename:** Use `rc(config_key, ...)` to look up user-specified basename
3. **Generate path:**
   - If found: `{output_dir}/{tool}/{custom_filename}.{suffix}`
   - If not found: `{output_dir}/{tool}/{stem}-{tool}.{suffix}` (auto-generated)

### Examples

#### Simple Case (Standard Convention)

**Config:**
```yaml
# config.yaml
input_fasta: /data/ecoli.fasta
output_dir: results/2024-03-25

prodigal:
  output: my_genes  # Optional custom base filename
  threads: 4
```

**Usage:**
```python
# In Snakefile
build_filepath('prodigal.output', 'gff', config=config)
→ 'results/2024-03-25/prodigal/my_genes.gff'

build_filepath('prodigal.output', 'faa', config=config)
→ 'results/2024-03-25/prodigal/my_genes.faa'
```

**Both files share the same base filename!** This is intentional - a single `prodigal.output` value controls all prodigal outputs.

#### Without Custom Filename (Auto-generated)

**Config:**
```yaml
# config.yaml
input_fasta: /data/ecoli.fasta
output_dir: results

prodigal:
  threads: 4
  # No 'output' specified
```

**Usage:**
```python
build_filepath('prodigal.output', 'gff', config=config)
→ 'results/prodigal/ecoli-prodigal.gff'

build_filepath('prodigal.output', 'faa', config=config)
→ 'results/prodigal/ecoli-prodigal.faa'
```

Uses stem from `input_fasta` (`ecoli`) plus tool name (`prodigal`).

#### Nested Case (Versioning, Variants)

**Config:**
```yaml
# config.yaml
prodigal:
  version1:
    output: genes_v1
    threads: 2
  version2:
    output: genes_v2
    threads: 4
```

**Usage:**
```python
# Both go to 'prodigal/' directory (first part of config_key)
build_filepath('prodigal.version1.output', 'gff', config=config)
→ 'results/prodigal/genes_v1.gff'

build_filepath('prodigal.version2.output', 'gff', config=config)
→ 'results/prodigal/genes_v2.gff'
```

**Key Point:** Even with nesting, the directory is always determined by the **first part** (`prodigal`).

### Why This Convention?

1. **Predictable directories:** Users always know where to find tool outputs
2. **Supports nesting:** Can organize complex configs (versions, modes, etc.)
3. **Consistent auto-generation:** Default pattern always uses first part as tool name
4. **Clean separation:** Directory structure ≠ config structure (they can differ)

---

## `fixed_path()` - Fixed Filename Paths

**Function:** `fixed_path(tool, filename='', use_stem=True, config=None)`

**Purpose:** Generate output file paths for tools that produce files with fixed, unchanging names.

### When to Use

Use `fixed_path()` for tool outputs that:
- Always have the same filename (e.g., `pfam.tsv`, `overview.tsv`, `cog_classify.tsv`)
- Should NOT be customizable by users
- Are tool-specific output formats

For user-configurable outputs, use `build_filepath()` instead.

### Examples

**Fixed filename (no stem):**
```python
fixed_path('pfam', 'pfam.tsv', use_stem=False, config=config)
→ 'results/pfam/pfam.tsv'
```

**With stem:**
```python
fixed_path('cog', 'cog.tkn', use_stem=True, config=config)
# config: input_fasta = 'ecoli.fasta'
→ 'results/cog/ecoli-cog.tkn'
```

### Common Usage in MARGIE

```python
rule run_pfam:
    output:
        fixed_path('pfam', 'pfam.tsv', use_stem=False, config=config)
    # Pfam always outputs to 'pfam.tsv' - not configurable

rule run_cog:
    output:
        classify=fixed_path('cog', 'cog_classify.tsv', use_stem=False, config=config),
        counts=fixed_path('cog', 'cog_count.tsv', use_stem=False, config=config)
    # COG outputs have fixed names
```

---

## `db_token()` - Database Token Paths

**Function:** `db_token(tool, config=None)`

**Purpose:** Generate database token file paths for workflow caching.

### Convention

Always generates: `{output_dir}/{tool}/{stem}-{tool}_db.tkn`

### Examples

```python
db_token('prodigal', config=config)
→ 'results/prodigal/ecoli-prodigal_db.tkn'

db_token('pfam', config=config)
→ 'results/pfam/ecoli-pfam_db.tkn'
```

These token files indicate successful database loading and are used for workflow caching.

---

## Complete Workflow Example

### Config File
```yaml
# ~/.config/bioinformatics-tools/config.yaml
input_fasta: /data/ecoli.fasta
output_dir: results/run-2024-03-25
main_database: /data/annotations.db

prodigal:
  output: custom_genes  # Custom base filename
  threads: 4
  mem_mb: 4096
  runtime: 30

pfam:
  threads: 8
  mem_mb: 8000
  runtime: 240
  db: /depot/lindems/data/Databases/pfam
  # No 'output' key - will auto-generate

cog:
  threads: 4
  mem_mb: 8192
  db: /depot/lindems/data/Databases/cog/
```

### Snakefile Usage
```python
from workflow_helpers import rc, build_filepath, fixed_path, db_token

rule run_prodigal:
    input:
        rc('input_fasta', config=config)
    output:
        gff=build_filepath('prodigal.output', 'gff', config=config),
        faa=build_filepath('prodigal.output', 'faa', config=config)
    threads: rc('prodigal.threads', 1, config=config)
    resources:
        mem_mb=rc('prodigal.mem_mb', 2048, config=config),
        runtime=rc('prodigal.runtime', 30, config=config)
    shell:
        """
        prodigal -i {input} -f gff -o {output.gff} -a {output.faa}
        """

rule load_prodigal_to_db:
    input:
        gff=build_filepath('prodigal.output', 'gff', config=config)
    output:
        tkn=db_token('prodigal', config=config)
    params:
        db=rc('main_database', config=config)
    shell:
        """
        python load_to_db.py gff {input.gff} {params.db} prodigal --token {output.tkn}
        """
```

### Generated Paths
```
results/run-2024-03-25/
├── prodigal/
│   ├── custom_genes.gff        ← User specified 'custom_genes'
│   ├── custom_genes.faa
│   └── ecoli-prodigal_db.tkn   ← Auto-generated (db_token)
├── pfam/
│   ├── pfam.tsv                ← Auto-generated (no output key)
│   └── ecoli-pfam_db.tkn
└── cog/
    ├── cog_classify.tsv
    ├── cog_count.tsv
    └── ecoli-cog_db.tkn
```

---

## Summary of Conventions

| Function | Purpose | Convention | Example |
|----------|---------|-----------|---------|
| `rc()` | Config lookup | Dot notation for nesting | `rc('prodigal.mem_mb', 2048, config=config)` |
| `build_filepath()` | User-configurable outputs | First part = tool/directory, respects `tool.output` | `build_filepath('prodigal.output', 'gff', config=config)` |
| `fixed_path()` | Fixed filenames | Generates paths for unchanging filenames | `fixed_path('pfam', 'pfam.tsv', use_stem=False, config=config)` |
| `db_token()` | Database tokens | Fixed pattern: `{tool}/{stem}-{tool}_db.tkn` | `db_token('prodigal', config=config)` |

### Key Principles

1. **Explicit is better than implicit:** Always pass `config=config`
2. **First part matters:** In `build_filepath()`, first part determines directory
3. **Defaults are fallbacks:** Every `rc()` call should have a sensible default
4. **Consistency over cleverness:** Follow conventions even when they seem verbose

---

## Advanced: Tool Variants and Versions

For workflows that need multiple versions or configurations of the same tool:

```yaml
# config.yaml
prodigal:
  standard:
    output: genes_standard
    mode: single
  metagenome:
    output: genes_meta
    mode: meta
```

```python
# In Snakefile
rule run_prodigal_standard:
    output:
        gff=build_filepath('prodigal.standard.output', 'gff', config=config)
    params:
        mode=rc('prodigal.standard.mode', 'single', config=config)
    # ...

rule run_prodigal_metagenome:
    output:
        gff=build_filepath('prodigal.metagenome.output', 'gff', config=config)
    params:
        mode=rc('prodigal.metagenome.mode', 'meta', config=config)
    # ...
```

Both outputs go to `prodigal/` directory with different base filenames.

---

## Questions?

See `workflow_helpers.py` for implementation details and additional examples.
