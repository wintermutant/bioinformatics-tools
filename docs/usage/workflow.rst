Workflow
=======================================

**Not currently implemented yet. Check back soon**

Workflow management and automation tools.

Theory
-------

We simplify the process of running commands by getting rid of the necessity to define virtual environments,
configuration, logging, and most importantly **data organization**. To best show you the value, let's walk through an
example of annotating a genomic sequence with an input FASTA file.

Example Use Case
-----------------

First, you start with a fasta file (or group of them), and move them to a directory of your choice. Most likely, this will
be in the form of a new folder representing a project.

.. code-block:: bash

    mkdir my-project-1
    mv ~/samples/sample1.fasta my-project-1
    mv ~/samples/sample2.fasta my-project-1
    mv ~/samples/*.fasta my-project-1  # More likely...

Let's say for the sake of our project we want to:

- obtain basic stats about the sequences
- filter out bad sequences
- determine gene calls using **prodigal**
- determine taxonomy using **blastn**
- Annotate using **CAZyme**

At the end, we want a way to dive into our results so we can make sense of all the information. Finally, we will present
this data and write about it in a paper.

Things to consider
~~~~~~~~~~~~~~~~~~~~~~~~~~~

A lot goes into this sort of work, including:

- programs to install
- setting up a virtual environment for us to work in
- organizing the folder structure
- compressing the data for storage and sending to other people
- keeping great notes to people can reproduce my work
- showing off what I've done!

We could talk about all the steps here and it could encompass a complete textbook. This would include aspects about: conda,
pip, uv, or any number of virtual environment and package managers, best practices in data recording, how to install programs
properly, knowing which programs have been validated, and the list goes on and on.

In this bioinformatics-tools package, we allow users to get straight to the point while maintaining incredibly beautiful and
professional bioinformatics practices **without having to think about them at all**. Here's what it looks like to take care
of all the components of our project checklist:

.. code-block:: bash

    dane_wf add genes file: sample1.fasta type: fasta
    dane_wf blast file: sample1.fasta type: fasta
    dane_wf cazyme file: sample1.fasta type: fasta

Starting with ``dane_wf add genes ...``, here's what happens when you run this:

1. Validates that sample1.fasta is indeed a valid fasta file
2. Matches the command ``add genes`` to all available gene callers, with **prodigal** currently being the only default
3. Magically loads in prodigal as an executable in a temporary virtual environment and safety checks that it works
4. Turns sample1.fasta into a sqlite3 database with a table for the sequences and a table for logs & metadata
5. Adds basic stats and quality control information to the database
6. **Runs prodigal** and adds the information to the fasta sqlite3 database as a new table
7. Exits the virtual environment and a report is created and sent to the command line to tell user of success/failure
8. Logging for all steps, including extra provenance information like checksums and timestamps, are all contained in the sqlite3 database.

At the end, you will go from having 1 file: ``/my-project-1/sample1.fasta`` to having only 1 other file:
``/my-project-1/sample1.db``. Inside this .db, all the gene calling information, as well as basic stats and quality control
metrics, will accessible for you.

We provide a simple syntax to extract the data from the database that matches the way you put data in. To get the
prodigal results, you can simply type:

.. code-block:: bash

    dane_wf get genes file: sample1.fasta

Above, this will extract the original prodigal information and write it as a file to the current working directory.

.. note::

    You see all the 'get' method from a database by typing:
    **dane_wf help file: sample1.fasta**

You can also add flags to the get commands to tell it how you want the information:

.. code-block:: bash

    dane_wf get genes file: sample1.fasta view: print  # Print to terminal
    dane_wf get genes file: sample1.fasta view: write  # Write to file

Moving on, let's outline what happens with the blast and cazyme. For these, almost all of the steps are the same with
the exception that it looks for **blast/cazyme** executables instead of prodigal. These will do the same stuff with the
database and create a new table containing the blast/cazyme information.

Here's what's cool - since sample1.db already exists in the directory, we can alter our command just a little bit
and keep with our concept of minimizing file counts:

.. code-block:: bash

    dane_wf blast file: sample1.db
    dane_wf cazyme file: sample1.db


Since we already have the seed of a database for **sample1.fasta**, we can point directly to that database. This will add
a new table to the already existing database for the blast and cazyme information. Now we still only have the 1 database file,
but it contains decorated information on gene calls, blast, and cazyme in 1 spot! This makes our directory super clean, as
well as portable - we just need to share 1 file!

Similar to viewing the gene calls, we can simply call:

.. code-block:: bash

    dane_wf get blast file: sample1.fasta view: print  # Print to terminal
    dane_wf get cazyme file: sample1.fasta view: write  # Write to file

This is the true beauty of the package - we eliminate the need for downloading programs, managing environments, and having
to organize thousands of files.

Usage
--------

Check back soon!