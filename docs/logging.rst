Logging
=======================================

Logging and debugging information for Bioinformatics Tools.

Overview
-----------

The package uses Python's built-in logging module to provide detailed information about operations and errors.

Log Levels
----------

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARNING**: Warning messages for potential issues
- **ERROR**: Error messages for serious problems
- **CRITICAL**: Critical errors that may cause the program to fail

Configuration
-------------

Command Line
^^^^^^^^^^^^

.. code-block:: bash

   # Set logging level
   bioinformatics-tools --log-level DEBUG command

Python API
^^^^^^^^^^

.. code-block:: python

   import logging
   from bioinformatics_tools import setup_logging

   # Configure logging
   setup_logging(level=logging.DEBUG, log_file="output.log")

Log Output
----------

Logs can be directed to:

- Console (stderr)
- File
- Both console and file simultaneously
