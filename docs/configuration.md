# Configuration

**Work in Progress - Check back soon**

Configure Bioinformatics Tools for your environment and workflow.

## Overview

This section covers how to configure the package settings, including:

- Configuration file locations
- Environment-specific settings
- Default parameters
- Customization options

## Configuration Files

When you run bioinformatics-tools, it will create a configuration file: *~/.config/bioinformatics-tools/config.yaml.* By default, this configuration
file gets loaded and used whenever you run a program. You can edit this file as you need! We also have 2 other locations for config file: one can
be specified on the command line via --config <config-example.yaml> and lastly within this package we have a fallback default. We advise you only edit
the ~/.config/bioinformatics-tools/config.yaml or a config file you specify on the command line. To recap, there are 3 ways to use a config file:

1. `~/.config/bioinformatics-tools/config.yaml`
2. Command line argument: `--config config-example.yaml`
3. In this package: `bioinformatics-tools/caragols/config-template.yaml`

Example configuration:

```yaml
# Generic
output: ./output
logging_level: INFO
max_threads: 4

report:
   form: prose

maintenance-info:
   version: 1
   description: This is the default configuration file
   contact: https://github.com/Diet-Microbiome-Interactions-Lab/GeneralTools/issues

# Program specific
fasta:
   gc_content:
      precision: 5

gff:
   valid:
      verbose: true
```

Let's start from the first configuration variable and work our way down.

1. **output:** this defines a default output file location *relative to your working directory*, unless you use an absolute path.
2. **logging_level:** How verbose you want *the command line stdout logging*. Note: this will not affect your verbose logfile that is being stored as an immutable reference.
3. **max_threads:** NOT YET SUPPORTED. In the future, we will allow resource constraints. This will be more relevant when we interface with supercomputers and job queues more easily.
4. **report.form:** This customizes how you want the stdout print messages to be formatted when using the command line.
5. **maintenance-info:** Stuff for the developers. Briefly, we have future plans to version control configuration files with the latest bioinformatics-tools version for data provenance and reproducibility purposes.
6. **fasta:** All programs within the *type: fasta* can have custom parameters defined. The first level defines the type (fasta), then the program **without the do_** prefix, and then simply the command joined with a `_`.
7. **gff:** Same concept as (6 - fasta) above.
