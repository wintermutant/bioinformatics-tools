# Workflow Tools

The workflow tools system ties together Snakemake pipelines, Apptainer containers,
and a SQLite database cache into a single `dane_wf` command. This page documents
the current architecture, execution flow, and database design, and closes with a
roadmap for eventually making workflows pluggable.

## Overview

`dane_wf <workflow> [options]` is the main entrypoint. It:

1. Selects the right Snakemake workflow file from an internal registry
2. Pulls and caches any required Apptainer (`.sif`) containers
3. Restores previously-computed rule outputs from the SQLite cache so Snakemake skips them
4. Runs Snakemake (locally or on SLURM)
5. Stores successful outputs back into the cache and writes a run log entry

## Class Hierarchy

All `dane_wf` commands are handled by a two-level class hierarchy:

```text
clix.App  (caragols CLI framework)
    └── ProgramBase             (programs.py)
            Single containerized program commands
            @command do_prodigal, etc.
        └── WorkflowBase        (workflow.py)
                Snakemake pipeline commands
                @command do_margie, do_quick_example, do_fresh_test, ...
```

`ProgramBase` handles one-shot Apptainer container executions (e.g. running
`prodigal` directly).

`WorkflowBase` inherits all of those and adds multi-step Snakemake pipelines.
Both are reached through the same `dane_wf` entrypoint.

## Workflow Registry

Each supported workflow is described by a `WorkflowKey` dataclass registered in
`workflow_keys` at the top of `workflow.py`:

```python
workflow_keys: dict[str, WorkflowKey] = {
    'margie': WorkflowKey(
        cmd_identifier='margie',
        snakemake_file='margie.smk',
        sif_files=[('prodigal.sif', '2.6.3-v1.0'), ...],
    ),
    'selftest': WorkflowKey(
        cmd_identifier='selftest',
        snakemake_file='selftest.smk',
        sif_files=[],       # touch-only, no containers needed
    ),
}
```

The registry is the single source of truth for which `.smk` file to use and which
containers to pre-cache. Adding a new workflow means adding an entry here and writing
a corresponding `@command do_<name>` method.

Snakemake files live alongside the Python source in `bioinformatics_tools/workflow_tools/`.

## Execution Flow

The shared `_run_pipeline()` method handles every workflow. Here is the full flow:

```text
dane_wf <workflow> [args]
      │
      ▼
WorkflowBase.__init__()
generate run_id (UUID)          ← every run gets a unique ID immediately
      │
      ▼
Lookup WorkflowKey in workflow_keys
      │ not found → self.failed(), return
      ▼
cache_sif_files()               ← pull/verify Apptainer .sif files
      │ CacheSifError → self.failed(), return
      ▼
restore_all(db, input, cache_map)
      │                         ← writes cached rule outputs to disk so
      │                           Snakemake sees them as already done
      ▼
build_executable()              ← assemble snakemake CLI command
_run_subprocess()               ← subprocess.run(snakemake ...)
      │
      ├── returncode != 0
      │       log_workflow_run(status='failed')
      │       self.failed()
      │       return
      │
      └── returncode == 0
              store_all(db, input, cache_map)
              log_workflow_run(status='success')
              self.succeeded()
```

Key design points:

- `--keep-going` is always passed to Snakemake so a failing rule does not abort
  the entire DAG. Partial results are still cached and logged.
- `mode='dev'` skips `--executor=slurm` and `--default-resources` for local runs.
- The subprocess always uses `capture_output=True`; stdout/stderr are logged and
  included in the structured result dict returned to the caller.

## Database Integration

All persistent state lives in a single SQLite database (`margie.db`).

### output_cache table

Stores the binary content of rule output files, keyed by a hash of the input file.
This allows Snakemake to skip expensive re-computation when the same input has been
processed before, even across fresh working directories.

```text
output_cache
┌────────────┬───────────┬──────────┬──────────┬─────────┬────────────┬────────────┐
│ id         │ input_hash│ tool     │ filename │ content │ size_bytes │ cached_at  │
│ (PK)       │ TEXT      │ TEXT     │ TEXT     │ BLOB    │ INTEGER    │ TEXT       │
└────────────┴───────────┴──────────┴──────────┴─────────┴────────────┴────────────┘
UNIQUE(input_hash, tool, filename)
```

- `input_hash`: first 16 hex chars of SHA-256 of the input file
- `tool`: rule/step name (e.g. `prodigal`, `step_a`)
- `content`: raw bytes of the output file

On restore, `restore_all()` writes each BLOB back to the expected output path before
Snakemake runs. Snakemake sees the files already present and skips those rules.

### run_log table

Records every workflow execution. Written by both `output_cache.py` (workflow runs)
and `load_to_db.py` (annotation loader runs). The two columns `row_count` and
`rules_completed` make it clear which type of run each row represents.

```text
run_log
┌────┬──────────┬───────────┬──────────┬────────────┬───────────┬──────────────────┬─────────┬──────────────────────────┐
│ id │ run_id   │input_hash │ tool     │ input_path │ row_count │ rules_completed  │ status  │ loaded_at                │
│ PK │ UUID     │ TEXT      │ TEXT     │ TEXT       │ INTEGER   │ INTEGER          │ TEXT    │ TEXT (ISO-8601 UTC)      │
└────┴──────────┴───────────┴──────────┴────────────┴───────────┴──────────────────┴─────────┴──────────────────────────┘
```

- `run_id`: UUID generated at the very start of `_run_pipeline()`, before anything runs
- `row_count`: populated by annotation loaders (`load_to_db.py`); 0 for workflow runs
- `rules_completed`: populated by workflow runs; 0 for annotation loaders
- `status`: `'success'` or `'failed'`

Every run — including partial failures — gets its own row. Re-running the same input
produces a new row rather than overwriting the previous one.

## Selftest Workflows

Two selftest commands exercise the full pipeline without requiring containers or HPC:

```text
dane_wf quick example    →  do_quick_example()
dane_wf fresh test       →  do_fresh_test()
```

Both use `selftest.smk`, which mirrors the shape of `margie.smk` using only
`touch` and `false` shell commands.

```text
selftest DAG (mirrors margie):

input_file
  ├── step_a  ──── step_a_db
  │     ├── step_b (inject_failure supported) ──── step_b_db
  │     └── step_c (2 outputs) ──── step_c_db
  └── all  ←  depends on step_a_db, step_b_db, step_c_db
```

The difference between the two commands:

| Command | Input content | Cache behaviour |
|---------|---------------|-----------------|
| `quick_example` | Fixed string — same every run | First run: cache miss, runs all rules, stores. Second run: cache hit, Snakemake skips all rules. |
| `fresh_test` | Includes timestamp — unique every run | Always a cache miss. All rules always run. |

Both commands use a `tempfile.TemporaryDirectory` as the Snakemake `workdir`.
All output paths are absolute (prefixed with the tmpdir path) so that `store_all`
and `restore_all` can find the files after Snakemake exits.

## Current File Structure

```text
bioinformatics_tools/
└── workflow_tools/
    ├── workflow.py         WorkflowBase — pipeline orchestration, run_id, _run_pipeline()
    ├── programs.py         ProgramBase  — single containerised program commands
    ├── models.py           WorkflowKey, ApptainerKey dataclasses
    ├── bapptainer.py       Apptainer container caching and execution
    ├── output_cache.py     restore_all / store_all / log_workflow_run
    ├── load_to_db.py       Annotation loader (GFF, CSV, TSV → SQLite)
    ├── margie.smk          Full annotation workflow (prodigal, pfam, cog, ...)
    ├── selftest.smk        Touch-only test workflow (no containers)
    └── example.smk         Minimal prodigal-only example workflow
```

## Plugin System — Future Work

The goal is to let anyone drop a `.smk` file into a well-known location and have it
automatically discovered and available as a `dane_wf` command, without touching any
Python source.

Below are the steps needed to get there, roughly in order:

**Discovery**

- Define a canonical plugin directory (e.g. `~/.local/share/bioinformatics-tools/workflows/`)
- At startup, scan that directory (and optionally a repo-local `plugins/` folder) for `*.smk` files paired with a sidecar metadata file (YAML or TOML)
- Populate `workflow_keys` dynamically from discovered metadata rather than hard-coding it

**Metadata sidecar**

- Each plugin would ship a `<name>.yaml` alongside `<name>.smk` declaring:
    - `cmd_identifier` — the CLI name
    - `sif_files` — list of containers and versions needed
    - `cache_map` — mapping of rule names to expected output file patterns
    - `input_keys` — which smk config keys map to `input_fasta` / `input_file`
    - `description` — shown in `dane_wf help`

**Registration**

- Replace hard-coded `workflow_keys` dict with a `PluginRegistry` class that loads from discovered metadata
- `WorkflowBase` would generate `do_<name>` methods dynamically from registered entries (likely via `__init_subclass__` or a class decorator)

**Safety**

- Hash/sign plugin metadata so users know they are running trusted workflows
- Validate that declared `sif_files` are reachable before registering the plugin

**Frontend integration**

- The program registry (TODO item #4) would consume the same plugin metadata to populate the UI workflow selection checkboxes (TODO item #5)
