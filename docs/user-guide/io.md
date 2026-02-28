# IO

File input/output operations for bioinformatics data.

## Quick Start

i/o (input/output) functions are all about taking in a specific file and doing some sort of work on it. By work, we mean performing
some sort of computations on the file. The result is either

1. output printed to your terminal with a report or
2. writing of a new file with new information about the input file (with or without a report printed in your terminal)

The idea here is to quickly get useful stats about a particular file or to rewrite a file into a different format.

### Command Line Usage

For all i/o functions, you **must** specify a filetype. This bioinformatics-tools package starts by determining if we can
recognize the particular filetype. The type of file and the input file must match up. To see all the filetypes this package
supports, call the help command:

```bash
# Use 'dane' to invoke the program
$ dane help
```

Here, help will list out all the available filetypes you can specify. **TODO:** Eventually, there will be support and documentation to
guide users how to add their own custom filetypes to this library.

Here is how you specify a fasta file:

```bash
# Invoke bioinformatics-tools with the fasta type
$ dane help type: fasta  # shows all available fasta programs
$ dane valid type: fasta file: example.fasta
$ dane basic stats type: fasta file: example.fasta
```

The first command will show all the available programs that you can run on a fasta file. The second provides a report to
the standard output that tells you whether or not the file is valid. Anytime a program is run, it always first checks to
determine if the file is valid. The third command prints out basic stats of the file to the standard output.

#### Providing Arguments

Notice the way we invoke programs here. We always start with **dane**, followed by any number of positional arguments.
After the positional arguments (for example, 'basic stats'), we provide any number of key: value arguments. The key here
is we **must always** use the **file:** and **type:** arguments. One day we will try to invoke smart file parsing, but
for now, the easiest way is to tell the program your file type.

When invoking a program, you can see all the possible arguments available using the *--help* flag at the end of your command:

```bash
$ dane n largest seqs type: fasta --help
# Based on help, can specify keyword more arguments
$ dane n largest seqs type: fasta file: example.fasta output: out.fasta n: 20
# Above, all commands have default values for every argument besides file: and type:
```

Above, we also specified the *output* and *n* keyword to customize the way we want the program to run. By specifying
`n: 20`, we can output the 20 largest seqs to the `output: out.fasta` file.

#### Defaults & Configuration

Having to specify a ton of parameters, or even just a few often, can quickly become annoying. This is where your default
configuration file comes in. There is a file located at the path `~/.config/bioinformatics-tools/config.yaml` where you
can specify any number of arguments.

**TODO (LOGIC):** You can customize your `config.yaml` file with all your own default values. For instance, if you always
wanted the program:

```bash
dane n largest seqs type: fasta
```

to have a default n of 40, you could update your *config.yaml* and put in an entry:

```yaml
n_largest_seqs:
   - n: 40
   - output: ~/n_largest_seqs.fasta
```

Above, we can just specify a top-level yaml mapping called *n_largest_seqs* and then underneath have nested values to
specify the values we want. This allows us to customize the default behavior of any program we wish to execute. We sometimes
refer to your configuration file as your *profile*.

**TODO (LOGIC):** In future updates, you will be able to specify both global profiles (configs) as well as project-specific
configurations. Right now, you can specify a custom configuration by adding the `config: </path/to/config.yaml>` key to
any command.

#### Logging and Reproducibility

The commands you run, as well as extra information about the specific execution of the programs can be found in our log file
that we automatically create for you. This is placed at the location: `~/.caragols/logs/<username>/`. There will be two files:

1. `log.jsonl`
2. `log.txt`

We go beyond just logging what was performed on the command line. All of the functions in this package provide detailed logging
on the specific actions the program performed, as well as providing checksums on the input and output. The goal of this is for
people to not have to re-run programs on files if they have already been performed. It also allows a comprehensive guide for
other people to understand what exact programs were ran on which files, all with validated signatures through our programs.
By signatures, we mean we authorize that a specific action (or set of actions) was performed on a specific file (via checksum).

#### Eliminating Redundancy

Following my spiel on logging and reproducibility, we further extend our principles into reducing redundant computations. For sake
of performance, we do not check whether a program has been run on a file nor do any caching with any i/o functionality. We do
have plans to build this behavior into all of our **database** and **workflow** functionality. Briefly, in our database
functionality start by turning a particular file type into a database. When we perform an action on it, say, *n largest seqs*,
we add a table to the database file that provides that particular information.

If we ran the *n largest seqs* on the same
database file we would do no computation and instead return the stored result - with one caveat. When we first ran *n largest seqs*
on the database, that there is a hash of this result against the value of the file contents in the database. If the contents change,
and hence the hash mapping the *n largest seqs* to the contents does not match, the program will rerun. For more information,
see the [Database Section](database.md).
