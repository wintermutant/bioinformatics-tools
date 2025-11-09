Configuration
=======================================

Configure Bioinformatics Tools for your environment and workflow.

Overview
-----------

This section covers how to configure the package settings, including:

- Configuration file locations
- Environment-specific settings
- Default parameters
- Customization options

Configuration Files
-------------------

Example configuration:

.. code-block:: yaml

   # config.yaml
   default_output_dir: ./output
   logging_level: INFO
   max_threads: 4

Python API
----------

.. code-block:: python

   from bioinformatics_tools import configure

   # Load configuration
   config = configure.load_config("config.yaml")

   # Set configuration programmatically
   configure.set("default_output_dir", "/path/to/output")
