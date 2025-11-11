Logging
=======================================

Logging and debugging information for Bioinformatics Tools.

Overview
-----------

The package uses Python's built-in logging module to provide detailed information about operations and errors.
We collect extra log information and place it in the following location:

.. code-block:: bash

   ~/.caragols/logs/<username>

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

   # Example setting log levels in the future when it is implemented
   bioinformatics-tools --log-level DEBUG command  # Not yet implemented
