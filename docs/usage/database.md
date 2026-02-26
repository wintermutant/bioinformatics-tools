# Database

Database operations and management for bioinformatics data.

## Quick Start

The database features are all going from several files to one database. In the simplest example, we take 1 file and turn
it from a flat file into a database. This is done by transforming the file into a database using a specific, defined
schema and adding the contents to a table. We use a sqlite3 database because they are easy to move around. We then perform
functions on the database to *"decorate"* it with more information or to extract information into a file or report. To make
it simple, we call these **decoration** and **extraction** functions.

1. **Decoration functions**: Given a database, we perform some function that adds more information to the database.
2. **Extraction functions**: Given a database, extract information from it to a report or flat file.

```bash
# Create a database from a fasta file
$ dane-db file: example.fasta type: fasta
# Decoration function below that adds annotation information to a genome
$ dane-db annotate db: example.db sources: kegg,tigrfam
# Decoration function that adds a summary to the database
$ dane-db summary db: example.db
```

Above, we start by creating a database from a file. This checks the file to see if there's a defined schema that can turn the
file into a database with the contents being in a sqlite3 table called *contents*. Next, we perform the function *annotate*
with the sources being *kegg and tigrfam*. This searches the fasta file contents against kegg and tigrfam databases and
tries to annotate sequences with genes. The sqlite3 database will then add 2 additional tables: annotation-kegg and
annotation-tigrfam.

In the function `dane-db summary db: example.db`, we scan all the tables in the database and output a
summary to the standard output. This will summarize the *contents*, as well as the *annotation-kegg* and *annotation-tigrfam*
tables.

### Metadata

For purposes of reproducibility and stopping redundant functions from being performed on a database, we provide a metadata
table for every database as well. This table is called *_metadata* and can be accessed via:

```bash
$ dane-db info db: example.db
```

Above, this will print out a ton of information about the database, including:

1. Names of each table
2. The contents of the *_metadata* table (see the Metadata Table section below for more information)
3. **TODO:** More information here

#### Metadata Table

The *_metadata* table has 4 columns and is meant to provide high-level information about the database, as well as a
super naive changelog. Think of it as a receipt (or transaction history) with a very brief account of all the activity
that has happened to the database.

| Type | Notes | Value | Timestamp |
|------|-------|-------|-----------|
| db_name | top-level name for the database | Example database | 15Jan2020 |
| creation_date | timestamp db was first created | 01Jan2000:08:20:20 | 01Jan2000 |
| activity | example_checksum-hd5120: performed summary stat | dane basic stats type: fasta db: example.db | 19Jan2020 |
| log_entry | log text entry | a bunch of sample log text... | 19Jan2020 |
| activity | example_checksum-hd5120: performed annotation | dane annotate type: fasta db: example.db annotations: tigerfam | 20Jan2020 |
| checksum_contents | checksum for file contents | example_checksum-hd5120 | 15Jan2020 |
| checksum_contents | checksum for file contents | example_checksum-hd5899 | 01Jan2020 |

The idea here is to keep track of some high-level attributes regarding the database. The checksum, for instance,
is used as a second check to determine if a particular function was already performed on the database. Let's break it down:

If the program *get largest* was previously ran on `example1.db`, this means the table (or entry) *get_largest* exists.
Say we run this program again - instead of simply returning the table with the results, we want to make sure the file
contents in the database have not changed so we can expect the same result. To verify, we check that the checksum
of the current *file_contents* is the same as the checksum when *get largest* was previously ran. Here's an example:

```bash
$ dane get largest db: example1.db  # first time running this
```

The following order of operations are performed:

1. We find no table with data for 'get largest', so we add the data and note the checksum of the file contents.

Now we want to run this again:

```bash
$ dane get largest db: example1.db
```

This time, before we run the program we find that data exists for 'get largest' already. Before we simply return it,
we want to make sure the checksum of the file contents the program was ran on matches the current checksum of the file contents.
We check this by checking the *_metadata* table and find the activity entry when 'get largest' was last ran and compare checksums.
If the checksums do not match, we run the program, overwrite the old 'get largest' results, and add an activity entry to our
metadata table.

See below for a full breakdown of the logic:

1. Check to see if *get_largest* table (or row) exists
2. If not, run **get largest** and create the new table with the current checksum
3. If *get_largest* table (or row) does exist, we check the **_metadata** table for activity that matches 'get largest'. We can see via the *Notes* column what the checksum was of the file contents when this program was ran.
4. If the checksum when this program was last ran matches the current checksum, we return the stored results.
5. If the checksums don't match, update the *get_largest* table with new values. Note: it is important to understand that this will **overwrite** old results but we will retain a receipt of both times we ran 'get largest' on this database.

Note that our database functionality is not meant to contain extensive version controlling beyond what sqlite3 already
has in place. We simply provide a modest activity log and a way to ensure if we have already ran a program on the database
that the results are up-to-date.

## Logging

Logs can be found inside of the *_metadata* table on a per-action basis - i.e., for each program ran on the database. We also
store 2 log files that capture all bioinformatics-tools commands at:

```bash
~/.caragols/logs/<USERNAME>/
```

## Configuration

**TODO:**
