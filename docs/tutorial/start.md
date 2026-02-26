# Getting Started

!!! note
    This is a work in progress. Please come back and check for updates!

By the end of this tutorial, you should be a master data wrangler and much more confident in your
bioinformatics and command line skills to accomplish new research tasks.

## What can you do with a bioinformatics file?

As far as this package is concerned, there are 2 types of file:

1. Files we recognize
2. Files we don't recognize

For (2), we do not have much functionality right now. Thus, we will focus on files we recognize.

**What do we mean by a file we recognize?** The *bioinformatics-tools* repo has a list of defined filetypes that
it can automatically recognize and process. Imagine a program that mimics the behavior of a person opening up a file,
looking at the contents, and then deciding if they know what the file is. Let's look at a simple example using
the infamous **[FASTA](https://en.wikipedia.org/wiki/FASTA_format)** file format.

Say you have a file called *sample1.fasta* and you believe it is a FASTA file. Great - you can test if it is indeed a valid
fasta file without ever having to open the file yourself:

```bash
$ dane valid type: fasta file: sample1.fasta
# Returns a report. Below, if valid:
[17:02:57 INFO] - 📄 Report Generated:
# ✅ Success
## Status
200: ok
## Response 💬
File was scrubbed and found to be True

# Below, if invalid fasta file:
[17:04:03 ERROR] - Line has invalid character...#gff3 - DaneDeemer - combineFunctionsAndGeneCalls.py
[17:04:03 ERROR] - File is not valid according to validation
[17:04:03 INFO] - # ❌ Failure
## Status
400: error in request
## Response 💬
File is not valid according to validation
```

As we see above, if the fasta file is invalid we get information on why it is not valid. This is helpful if you
believe you have a specific filetype but there may be an error in it.

Notice how we provide arguments in our program. We use a combination of key: value pairs, such as
*file: sample1.fasta* and *type: fasta*. We invoke the generic bioinformatics-tools program by first
typing *dane*, followed by the specific program we want run (*valid*), and then add our arguments.

Let's see another example:

```bash
$ dane valid type: gff file: sample1.gff3
[17:07:19 INFO] - 📄 Report Generated:
# ✅ Success
## Status
200: ok
## Response 💬
File was scrubbed and found to be True
```

## What filetypes are supported?

There are default filetypes that are supported **and you can define your own as well!**
To add your own filetype, please see [the contribution guide](../contribution.md).
By default, you can see all the filetypes we currently support by running:

```bash
$ dane help
[17:09:02 INFO] - Available file types:
Generate
GeneTransferFormat
BAM
Fastq
BrowserExtensibleData
class_skeleton
Fasta
GeneralFeatureFormat
```

As we update the package we will be adding more and more supported filetypes. For each filetype, you can
validate any file via:

```bash
$ dane valid file: <filename> type: <filetype>
```

## What else can we do with files?

We provide a ton of functionality to manipulate your files to make doing your analyses much easier. Our main goal
is to reduce the amount of time you need to spend opening up files and manually making changes - we know how much
time can be spent with file manipulation and plotting!

To see all the programs that can run on your file, lets look at an example with fasta files:

```bash
$ dane help type: fasta
0:  $ dane add to db type: fasta file: example.fasta
Add the fasta records to an existing sqlite database


1:  $ dane all headers type: fasta file: example.fasta
Return all headers to standard out


2:  $ dane all seqs type: fasta file: example.fasta
Return all sequences to standard out

...etc.
```

You will see a long list of programs you are able to run and hopefully the positional arguments you type
are self-explanatory for what the program does. Oftentimes, you'll still need more information about what
a program does, which you can append the **--help** flag to the command:

```bash
$ dane add to db type: fasta --help
```

This will print a nice help message telling you about what the program does and what arguments you can specify
to customize it to your needs. For this particular program, you can specify the *--db-path*, for instance.

## Customizing your default values

When you install the *bioinformatics-tools* repository, we create a folder in `~/.config/bioinformatics-tools`. Here,
we have a couple of files:

**default-config.yaml:** A yaml file you can specify any default parameters on. See below for an example:

```yaml
# Default, global parameters
username: wintermute  # Overrides your default username ($WHOAMI)
output: output-example.txt

io-seq-length:
    n: 10
    output: seqlen-example-output.txt

io-basic-stats:
    stat-level: advanced

db-make-db:
    output: my-fancy-db-name
```

Let's break down a couple interesting things about this. First, the *username* and *output* parameters we defined will
be applied to any program you run in this bioinformatics-tools package. This means if you ran the program:

```bash
$ dane write valid type: fasta file: example.fasta
```

Then the program would write to *output-example* (in the current working directory) and the **logging information** would
report the user *wintermute* ran the command. **Note:** We still also log who the *system user* was if we can retrieve that
to protect against total identity theft (hehe).

Since all bioinformatics-tools programs are broken down into categories of io, database/db, workflows/wf, and projects/pj,
we preface our config values with the category. Here we specify for seq length (`$ dane seq length...`) using **io-seq-length:**
and nest under it the **n** and **output** parameters. This means if we ran:

```bash
$ dane seq length type: fasta file: example.fasta
```

The output file would be **seqlen-example-output.txt** - notice how it overrides the global output file name. The more specific
the config parameter, the higher power to override. This would also take into account the **n** parameter and only count
seqs over 10 base pairs. You can see more information for a particular program's parameters using the --help flag:

```bash
$ dane seq length type: fasta --help
```

Every program that is run in bioinformatics tools can have a default value specified in your `~/.config/default-config.yaml`.
This includes extensions you create on your own, as long as you follow the convention of having the **program type category**
as the prefix (e.g., db-) followed by a hyphen (-) separated string for the command name (db-new-example-command).

## Selected Examples

**Basic stats about a fasta file**

If you want some basic stats about a fasta file, you can run:

```bash
$ dane basic stats type: fasta file: sample1.fasta
[17:25:17 INFO] - 📄 Report Generated:
# ✅ Success
## Status
200: ok
## Response 💬
Basic statistics:
{'Total Sequences': 3, 'Total Sequence Length': 49, 'Total GC Content': 53.51}
```

Notice how we always get a report when we run programs. This lets us know with certainty that the program finished
correctly and you can trust your results. Under the ##Response section, you can see stats for:

1. Total sequences
2. Total sequence length
3. Total GC content

As of right now, users cannot extend the results of the program (i.e., the Response), but we are working on making
that super simple for our users. For example, if you wanted to make the *$ dane basic stats* program a little more
robust by adding GC content per sequence, this report could add that information.

Let's look at another example where we run:

```bash
$ dane write binid type: fasta file: sample1.fasta
[17:29:02 INFO] - 📄 Report Generated:
# ✅ Success
## Status
200: ok
## Response 💬
Wrote the binID file to example-BinID.txt.gz
```

Notice the output is a file that is gzipped. We are always data storage conscious so we write compressed (gzip)
files by default. The output is a file that is comma-separated with 2 columns: the fasta header and the filename.
Some programs require this particular format, thus we made a quick program to allow people to adhere to this format
with a click of a button. This is in line with our theme of making common file manipulations super easy for our users.

### Turning files into databases

We don't like dealing with a ton of files because folders and projects can be cluttered easily and you can spend an
unlimited amount of time organizing. This is why we prefer using portable (movable) SQLITE3 databases, which are helpful:

1. Ensuring your file doesn't get changed easily and keeps the provenance
2. When you run an analysis on a file, you can keep all the input and output in 1 database file instead of needing multiple folders

Let's dive into an example of turning a fasta into a database and then doing some work on it in a clean manner.

```bash
$ dane write db type: fasta file: sample1.fasta
[17:36:05 INFO] - 📄 Report Generated:
# ✅ Success
## Status
200: ok
## Response 💬
3 records written to database at fasta_records.db
```

Above, we call a command that created `fasta_records-121125-1736.db` from `sample1.db`. We could have specified the output file
name via using the *--output* flag. Now, let's say we want to run basic stats on this file. Instead of just having the
result go to the standard output in a report or writing to a separate file, we can have it write this information in the
database file directly:

```bash
$ dane basic stats type: fasta file: fasta_records.db
# ✅ Success
## Status
200: ok
## Response 💬
Contents of report saved in database!
Basic statistics:
{'Total Sequences': 3, 'Total Sequence Length': 49, 'Total GC Content': 53.51}
```

We still see a report when the command finishes, but it also saves a copy of the report in the database. This is helpful for
many reasons:

1. This information is **essentially cached, or saved**, in the database so we don't need to run the same computations
when we want to see this information later. Imagine a fasta file with 10 million sequences and it takes 10 seconds
to run this report. Without the database (and just the fasta file), if you forgot to store this information you'd
have to run the program again. With the database, you can instantly retrieve this information.

2. Secondly, we end up dealing with a ton less files per project. Previously, without the database, you may have stored `sample1.fasta`
and `basic_stats_about_sample1.txt`. You can imagine when you run many programs on a file, such as annotations from a dozen
sources on a fasta file, gene calls, blast hits, etc., you create a ton of files. With the database technique, you have
1 file with all the extra information in 1 place. Makes it easy to not only go back and look at old projects, but also
sharing comprehensive data with other people.

3. Thirdly, we store additional logging and provenance information in these databases, making it easy to write methods or share
methods with collaborators months after you completed your work.

```bash
$ dane logs file: fasta_records.db
# Print out a list of all the commands ran on fasta_records.db

$ dane all logs file: fasta_records.db output: fasta_records.logs
# Write comprehensive logging to fasta_records.logs

$ dane notebook file: fasta_records.db
# Turns records of all work done on your database into a nice markdown or txt lab notebook entry!
```

### Decorating a database with more information

Say we have a fasta file called `sample1.fasta` and we turn it into a database:

```bash
$ dane write db type: fasta file: sample1.fasta
```

Now we want to run [PRODIGAL](https://github.com/hyattpd/Prodigal) to find locations where genes are in this file. When we run prodigal normally,
we get one or more new files with information about the annotation of the genome. From Prodigal's website:

> "Prodigal produces one output file, which consists of gene coordinates and some metadata associated with each gene. However, the program can produce four more output files at the user's request."

Instead of dealing with 2 or more files and having to move them together and what not, we can work with just 1
sqlite3 database file.

```bash
$ dane annotate type: fasta file: sample1.db program: prodigal
Wrote output inside of sample1.db...
```

Here, we have 1 file and the contents of the prodigal output are placed in a table in `sample1.db`. To view the results
you either access the sqlite3 database yourself (not advised), or do:

```bash
$ dane show file: sample1.db program: prodigal
# This will write the results to standard output
$ dane show file: sample1.db program: prodigal output: sample1-prodigal.txt
# Write the output to its own file (same as original output from prodigal)
```
