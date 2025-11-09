Environments
=======================================

Setting up and managing different environments for Bioinformatics Tools.

Overview
-----------

This section covers environment setup, dependencies, and deployment scenarios.

Installation
------------

Using pip
^^^^^^^^^

.. code-block:: bash

   pip install bioinformatics-tools

Using conda
^^^^^^^^^^^

.. code-block:: bash

   conda install -c conda-forge bioinformatics-tools

Development Environment
-----------------------

Setting up a development environment:

.. code-block:: bash

   # Clone the repository
   git clone https://github.com/yourusername/bioinformatics-tools.git
   cd bioinformatics-tools

   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

   # Install in development mode
   pip install -e ".[dev]"

Environment Variables
---------------------

Key environment variables:

- ``BIOTOOLS_CONFIG``: Path to configuration file
- ``BIOTOOLS_DATA_DIR``: Default data directory
- ``BIOTOOLS_CACHE_DIR``: Cache directory for temporary files

.. code-block:: bash

   export BIOTOOLS_CONFIG=/path/to/config.yaml
   export BIOTOOLS_DATA_DIR=/data
