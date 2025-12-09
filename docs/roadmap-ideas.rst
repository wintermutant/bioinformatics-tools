Roadmap & Ideas
===============

This document tracks implementation ideas, architectural decisions, and future directions for the bioinformatics-tools project.

Last Updated: 2025-11-25

Container-Based Dependency Management
--------------------------------------

Vision
~~~~~~

Use Singularity/Apptainer containers (.sif files) to provide isolated, reproducible environments for bioinformatics tools. This approach:

- Eliminates installation headaches for users
- Allows revival of unmaintained/broken tools through containerization
- Provides true reproducibility (entire environment in one file)
- Works on HPC clusters without root access
- Single file format makes distribution easy

Architecture Concept
~~~~~~~~~~~~~~~~~~~~

Tool Registry with Container References
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each tool in ``~/.cache/dane_wf/tools/`` would have a definition pointing to a container:

.. code-block:: yaml

    name: prodigal
    version: "2.6.3"
    container:
      type: singularity
      source: docker://biocontainers/prodigal:2.6.3
      # OR
      source: https://github.com/ddeemer/biotools-containers/releases/download/prodigal-2.6.3.sif
      # OR
      source: oras://ghcr.io/ddeemer/prodigal:2.6.3
    executable: prodigal
    validation: "prodigal -v"

Tool Wrapper Execution
^^^^^^^^^^^^^^^^^^^^^^

Running a tool would:

1. Check if container exists in ``~/.cache/dane_wf/containers/``
2. Download/cache if missing
3. Execute via: ``singularity exec container.sif prodigal [args]``
4. Bind mount data directories automatically

Container Sources
~~~~~~~~~~~~~~~~~

1. **BioContainers** - Pre-built containers for 8000+ tools

   - Available as Docker images
   - Can pull with: ``singularity pull docker://biocontainers/prodigal:2.6.3``

2. **Custom Container Repository** - For revived/custom tools

   - Fork unmaintained GitHub repos
   - Create working Dockerfile/Singularity definition
   - Build and host containers (GitHub Container Registry, Sylabs Cloud, etc.)
   - Maintain collection of "rescued" bioinformatics tools

3. **Community Contributions** - Allow users to add tools

   - Define tool interface
   - Point to their container
   - Share with community

Revival of Old Tools ("Robin Hood" Approach)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Many excellent bioinformatics tools become unusable due to:

- Broken dependencies
- Incompatible Python/R versions
- Missing system libraries
- Archived repositories
- Original authors moved on

**Solution**: Create containers that preserve working environments

Process:

1. Find broken tool on GitHub/publications
2. Fork repository to preserve code
3. Create Singularity definition with working dependencies
4. Build and test container
5. Add to bioinformatics-tools registry
6. Users can now run with: ``dane_wf [tool] file: example.fasta``

Benefits:

- Preserves scientific software
- Makes old papers reproducible
- Reduces "tool installation hell"
- Community service to field

Example Tools to Revive
^^^^^^^^^^^^^^^^^^^^^^^^

(Track candidates here)

- [ ] Tool X - broken numpy dependency
- [ ] Tool Y - requires Python 2.7
- [ ] Tool Z - unmaintained, critical for metagenomic analysis

Technical Implementation Notes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Container Caching Strategy
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    ~/.cache/dane_wf/
    ├── containers/
    │   ├── prodigal-2.6.3.sif
    │   ├── blast-2.12.0.sif
    │   └── cazyme-1.0.sif
    ├── tools/
    │   ├── prodigal.yaml
    │   ├── blast.yaml
    │   └── cazyme.yaml
    └── logs/

Singularity Execution Pattern
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    import subprocess
    from pathlib import Path

    def run_in_container(container_path, command, bind_paths=None):
        """Execute command in Singularity container"""
        bind_args = []
        if bind_paths:
            for host, container in bind_paths.items():
                bind_args.extend(["--bind", f"{host}:{container}"])

        cmd = [
            "singularity", "exec",
            *bind_args,
            str(container_path),
            *command
        ]

        return subprocess.run(cmd, capture_output=True, text=True)

Benefits Over Conda Approach
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- **Reproducibility**: Entire environment in one immutable file
- **HPC Friendly**: Singularity designed for shared clusters
- **No Activation**: Just execute, no environment activation needed
- **Version Control**: Containers can be versioned, hashed, stored in Git LFS
- **Tool Revival**: Can rescue unmaintained tools
- **Speed**: No dependency resolution at runtime

Challenges to Address
^^^^^^^^^^^^^^^^^^^^^

- **Disk Space**: Containers are larger than conda envs (mitigate with caching)
- **Build Time**: Creating custom containers takes time (do once, reuse)
- **Learning Curve**: Need to learn Singularity definition syntax
- **Storage**: Where to host custom containers? (GitHub releases, Sylabs Cloud, ORAS)

Next Steps
~~~~~~~~~~

1. Create proof-of-concept with single tool (prodigal)
2. Design tool registry format
3. Implement container caching and execution
4. Build first custom container for revived tool
5. Create documentation for contributing new tools
6. Set up container hosting strategy

Unified CLI Interface
---------------------

Current Design
~~~~~~~~~~~~~~

.. code-block:: bash

    dane_wf add genes file: example.fasta
    dane_wf blast file: example.fasta
    dane_wf get genes file: example.fasta view: print

Benefits
~~~~~~~~

- Natural language-like syntax
- Key-value arguments reduce memorization
- Self-documenting commands
- Consistent across all tools

Future Enhancements
~~~~~~~~~~~~~~~~~~~

- Tab completion for all commands
- Interactive mode: ``dane_wf interactive``
- Dry-run mode: ``dane_wf --dry-run add genes ...``
- Pipeline mode: Chain multiple operations
- Config files: Define complex workflows in YAML

Tool Management Commands
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    dane_wf tools list                    # Like 'module list' on clusters
    dane_wf tools search <keyword>        # Find available tools
    dane_wf tools info prodigal           # Show tool details and container info
    dane_wf tools install prodigal        # Pre-cache container
    dane_wf tools update                  # Update tool registry
    dane_wf tools clean                   # Remove unused containers

SQLite Database Integration
----------------------------

Current Approach
~~~~~~~~~~~~~~~~

- Each FASTA → SQLite database
- Tables for sequences, metadata, tool results
- Provenance tracking built-in

Future Ideas
~~~~~~~~~~~~

- Database merging: Combine results from multiple samples
- Export formats: CSV, JSON, Excel, Parquet
- Visualization: Built-in plotting commands
- Comparison: Diff two databases

Data Portability
~~~~~~~~~~~~~~~~

One database file contains:

- Original sequences
- All analysis results
- Complete provenance
- Tool versions and parameters
- Checksums and timestamps

Share science by sharing a single ``.db`` file!

Community and Contribution
---------------------------

Container Repository
~~~~~~~~~~~~~~~~~~~~

Create GitHub org: ``biotools-containers``

- Each tool gets own repo with Singularity definition
- Automated builds via GitHub Actions
- Store containers in GitHub Container Registry
- Community can contribute new tools
- Document each tool rescue story

Tool Registry
~~~~~~~~~~~~~

Central registry of available tools (like Bioconda recipes)

- Tool metadata
- Container locations
- Validation tests
- Usage examples
- Citations

Documentation Needs
~~~~~~~~~~~~~~~~~~~

- Container building tutorial
- Contributing guide for new tools
- Best practices for reviving old tools
- Case studies of rescued tools

Philosophy
----------

Make Bioinformatics Accessible
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Primary goal: Remove barriers for biologists

- No conda troubleshooting
- No dependency hell
- No "it works on my machine"
- Focus on science, not sysadmin

Preserve Scientific Software
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Secondary goal: Be stewards of bioinformatics tools

- Maintain working versions of abandoned tools
- Document and containerize
- Enable reproducibility of old papers
- Give back to community

Open Questions
--------------

1. Should we support both Singularity and Docker?
2. How to handle tools that need large databases (BLAST, Diamond)?
3. Auto-generate containers from conda recipes?
4. Integration with workflow managers (Snakemake, Nextflow)?
5. GUI for non-command-line users?
6. Cloud execution (AWS Batch, GCP)?

References and Reading
----------------------

Container Technologies
~~~~~~~~~~~~~~~~~~~~~~

- Apptainer/Singularity docs: https://apptainer.org/docs/
- BioContainers: https://biocontainers.pro/
- Docker for bioinformatics
- ORAS (OCI Registry as Storage)

Similar Projects
~~~~~~~~~~~~~~~~

- BioContainers registry
- Nextflow nf-core modules
- Snakemake wrappers
- Galaxy tool wrappers
- BioConda recipes

Standards
~~~~~~~~~

- Common Workflow Language (CWL)
- Workflow Description Language (WDL)
- Nextflow DSL2
- GA4GH standards

Ideas Backlog
-------------

Random ideas to explore later:

- Version control for databases (git-like for .db files)
- Automatic benchmarking of tools
- Tool recommendation: "Based on your data, try X"
- Integration with lab notebooks (Jupyter, RMarkdown)
- Slack/Discord notifications for long-running jobs
- Web dashboard for browsing results
- Automated figure generation
- Paper-ready tables and figures
- Reproducibility badges for databases
- DOI minting for analysis databases
