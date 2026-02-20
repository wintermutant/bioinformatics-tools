"""
Touch-only workflow that mirrors margie's DAG shape.
No containers — uses shell touch/false commands.

DAG structure (same shape as margie):

    input_file
      ├── step_a  (2 outputs, like prodigal)
      │     ├── step_a_db
      │     ├── step_b  (like pfam — inject_failure supported)
      │     │     └── step_b_db
      │     └── step_c  (2 outputs, like cog)
      │           └── step_c_db
      └── all  ← depends on all _db outputs

Usage:
    dane_wf quick_example                   # cache-hit path
    dane_wf fresh_test                      # no-cache, runs everything
    dane_wf fresh_test inject_failure: true  # step_b fails
"""

workdir: config.get("workdir", ".")

INJECT_FAILURE = config.get("inject_failure", "false").lower() == "true"
STEM = config.get("stem", "sample-a")


rule all:
    input:
        config.get("out_step_a_db", f"step_a/{STEM}-step_a_db.tkn"),
        config.get("out_step_b_db", f"step_b/{STEM}-step_b_db.tkn"),
        config.get("out_step_c_db", f"step_c/{STEM}-step_c_db.tkn"),


rule step_a:
    """Primary step — takes input file, produces two outputs (like prodigal)."""
    input:
        config.get("input_file", "input.txt"),
    output:
        main=config.get("out_step_a", f"step_a/{STEM}-step_a.out"),
        extra=config.get("out_step_a_extra", f"step_a/{STEM}-step_a.extra"),
    shell:
        "mkdir -p step_a && touch {output.main} {output.extra}"


rule step_a_db:
    """Load step_a output to DB (like prodigal_db)."""
    input:
        config.get("out_step_a", f"step_a/{STEM}-step_a.out"),
    output:
        config.get("out_step_a_db", f"step_a/{STEM}-step_a_db.tkn"),
    shell:
        "touch {output}"


rule step_b:
    """Depends on step_a extra output (like pfam depends on .faa). Supports inject_failure."""
    input:
        config.get("out_step_a_extra", f"step_a/{STEM}-step_a.extra"),
    output:
        config.get("out_step_b", f"step_b/{STEM}-step_b.out"),
    params:
        fail=INJECT_FAILURE,
    shell:
        """
        if [ "{params.fail}" = "True" ]; then
            echo "Injected failure in step_b" >&2
            exit 1
        fi
        mkdir -p step_b && touch {output}
        """


rule step_b_db:
    """Load step_b output to DB (like pfam_db)."""
    input:
        config.get("out_step_b", f"step_b/{STEM}-step_b.out"),
    output:
        config.get("out_step_b_db", f"step_b/{STEM}-step_b_db.tkn"),
    shell:
        "touch {output}"


rule step_c:
    """Depends on step_a extra output, produces two outputs (like cog)."""
    input:
        config.get("out_step_a_extra", f"step_a/{STEM}-step_a.extra"),
    output:
        primary=config.get("out_step_c_primary", f"step_c/{STEM}-step_c.tsv"),
        secondary=config.get("out_step_c_secondary", f"step_c/{STEM}-step_c_count.tsv"),
    shell:
        "mkdir -p step_c && touch {output.primary} {output.secondary}"


rule step_c_db:
    """Load step_c output to DB (like cog_db)."""
    input:
        primary=config.get("out_step_c_primary", f"step_c/{STEM}-step_c.tsv"),
        secondary=config.get("out_step_c_secondary", f"step_c/{STEM}-step_c_count.tsv"),
    output:
        config.get("out_step_c_db", f"step_c/{STEM}-step_c_db.tkn"),
    shell:
        "touch {output}"
