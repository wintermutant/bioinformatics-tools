# General Tools (for Bioinformatics)
[![Documentation Status](https://readthedocs.org/projects/bioinformatics-tools/badge/?version=latest)](https://bioinformatics-tools.readthedocs.io/en/latest/?badge=latest)

Comprehensive toolkit for bioinformatics workflows.

### A Diet-Microbiome Interactions Lab-Supported Resource out of Purdue University

Here we present simple tools for common bioinformatic use-cases, as well as other convenient functionality for your everyday command-line hacker. The main functionality takes in a file and a specified type, and will validate the file plus perform any simple stats, permutations, or filters. We were tired of getting errors when shoving data that wasn't first validated into pipelines, as well as performing the same bash and python hacks to look a little deeper at our large files. Further, we wanted a way to extend file validation and hacks to custom file types in our lab. Lastly, we wanted a more robust way to configure settings and record our behavior so we could be more reproducible without expending any extra effort.

- [General Tools (for Bioinformatics)](#general-tools-for-bioinformatics)
    - [A Diet-Microbiome Interactions Lab-Supported Resource out of Purdue University](#a-diet-microbiome-interactions-lab-supported-resource-out-of-purdue-university)
  - [Setup \& Installation](#setup--installation)
    - [i) Setup (Start Here!)](#i-setup-start-here)
    - [ii) Installation](#ii-installation)
  - [How to use this library](#how-to-use-this-library)
    - [i) Getting help](#i-getting-help)
    - [ii) Command LIne Extension (CLIX)](#ii-command-line-extension-clix)
    - [iii) Configuration Settings](#iii-configuration-settings)
      - [Advanced Users](#advanced-users)
    - [iv) Logging](#iv-logging)
  - [EXTRAs: Some philosophical rants](#extras-some-philosophical-rants)
    - [Let's talk about file validation](#lets-talk-about-file-validation)
  - [Releases](#releases)
  - [TODO](#todo)
  - [Contributor Guide](#contributor-guide)


## Setup & Installation

### i) Setup (Start Here!)

This is a Python package, requiring the version of Python to be 3.6 or later (a higher number than 3.6). From your Terminal (mac) or terminal-emulator in Windows (putty, powershell, etc.), which we will refer to as your _terminal_, check if you have Python3 installed.  
`python --version`  
or  
`python3 --version`  
One of those commands should show "Python 3.6" or newer if you have python3 installed correctly. For the remaining steps, use the command (`python or python3`) that worked.

### ii) Installation

Installation should be pretty quick using the package manager _pip_. We recommend first creating and entering a virtual environment before installing our package, but this is not necessary. Perform the following command to install the package:  
`pip install bioinformatics_tools`

## How to use this library

### i) Getting help

One of the first things you may notice about this library is the interesting way in which you invoke it. Invocations always start with an executable from our library, such as:  
`dane`  
and they must always have a `type: EXAMPLE` key-value pair, as each executable is specific to the type of file it receives.

If you want to know what sort of arguments you're able to run for a particular executable, you just need to pass the word _help_ as the first positional argument (the first word _after_ dane), along with specifying the _type_:  
`dane help type: fasta`  
The `type: fasta` follows the pattern where you have a key followed by a colon (key:), then provide the name of a _value_ separated by a space, e.g., `key: value`.

Above, this will first provide a status report that consists of 4 lines, which look something like this:  
\# Success  
\## Status  
200: okay  
\## Response

Line one will tell you if the command succeeded or failed, lines 2 and 3 will give you a more specific status code, and line 4 will provide the response, which is often the part of the command output you'll be interested in. Output in this format is included in every command standard out you execute.

After, it will show a list of every possible command, along with the docstring content (or help message) for each said command. These list of commands will start with 0 and go up through the last command (sorted alphabetically). Notice if you change the **type** the possible commands will change.

### ii) Command LIne Extension (CLIX)

To run an executable, you must first type the executable's name (e.g., `dane`) and immediately after provide positional arguments that align with the action you wish to perform. For example, from the dane help page, you see:  
`$ dane seq length type: fasta file: example.fasta`

Let's break down this command.  
`dane` is the executable and is always required first.  
`seq length` is a series of 2 positional arguments that conform to an executable found in the help message. These positional arguments are what tell the executable what to do, and may be anywhere from 1 to 5 space-separated arguments.  
`type: TYPE` (in this case, `type: fasta`) is **always required**. This tells the executable what type of file we are dealing with. In later releases of this app, we will try to smart-parse files so this is not necessarily needed.  
`file: FILE` (in this case, `file: example.fasta`) is also **always required** for any action to occur. This is the file you want to perform some action on.

Great, but what about if I want to provide extra parameters to the command? You can specify as many parameters as you want using the following syntax:  
`key: value`  
which will specify the parameter you want and the value it will have. For example:  
`length: 100 width: 200`  
will tell our system that we have the parameter length=100 and width=200.

For the following command
`dane filter sequences type: fasta file: example.fasta length: 20`

Note that the position of the parameters, the type, and the file do not matter. The above command is the same as the below command:

`dane filter sequences length: 20 type: fasta file: example.fasta`

The only positional arguments that matter are the `dane` as the first and the next sequence of arguments specifying the action to invoke (`filter sequences`)

If you need help with a command and the parameters it requires, or just want more information, you can type:
`dane seq length type: fasta --help` -- add a trailing `--help` to get more information

### iii) Configuration Settings

One of our least favorite things to do is specify the same parameters over and over again, or forget which parameters we used because we did not document concisely enough. By default, we check your [current directory](https://hpc.nmsu.edu/onboarding/linux/commands/cd/#_print_current_directory) for a file named config-caragols.yaml. Attributes put into these files will automatically be added to the configuration, which is available for all your programs to use.  
For example, say you have a file `config-caragols.yaml` with the following parameters

```yml
name: "dane"
length: 10
```

If you were to invoke the following command:  
`dane filter sequences type: fasta file: example.fasta`  
and the action _filter sequences_ took in a _length_ parameter, the action can grab that length parameter from the configuration file by default. Now let's say you have that configuration file but it does not have the _length_ parameter specified. No worries, because each action will have default parameters baked into it. If you wanted to change the parameter on the fly _without_ having to edit your config-caragols.yaml file, you can easily do that by specifying the parameter on the command line:

`dane filter sequences type: fasta file: example.fasta length: 20`

If you have no configuration file in your [current directory](https://hpc.nmsu.edu/onboarding/linux/commands/cd/#_print_current_directory), the "default config" will be used, which exists inside this tool. See [Advanced Users](#advanced-users) to learn more about this.

If you have a config file that lives somewhere else outside your [current directory](https://hpc.nmsu.edu/onboarding/linux/commands/cd/#_print_current_directory), you can pass the path to file as part of the command, using the `--config-file` flag

```
dane filter sequences type: fasta file: example.fasta --config-file /tmp/myconfig.yaml
```

In summary, all the following commands are equivalent

`dane filter sequences type: fasta file: example.fasta length: 20` - uses the "default config"
`dane filter sequences type: fasta file: example.fasta` - where the "local config", config-caragols.yaml, is located in the current directory, and contains `length: 20`
`dane filter sequences type: fasta file: example.fasta --config-file /tmp/conf.yaml` - where `/tmp/conf.yaml` contains `length: 20`

#### Advanced Users

For those trying to share configs across multiple users (for example, a bioinformatician lab manager), you can modify the default configuration file. To see the default configuration info, run

```
python -m bioinformatics_tools.caragols.configurator
```

The `maintenance-info` section is a starter guide to help track configuration files used in shared environments. It is not used by the application yet, so you can replace it or modify it in any way you want that makes sense for you. The configuration file content is logged each time a command is ran, so it might be useful for debugging with users to add information here. Future versions of bioinformatics_tools may rely on such a section to detect when a local config is out of date with the default config, that way users can keep up with the recommended configuration for the lab even when they have defined their own configuration files.

### iv) Logging

Logs from each time you run a command are saved to your hard drive. By default in `~/.caragols`. These logs may be useful to look back on if you forget some work you did, or when you experience bugs, and us developers need more information in order to help. Up to 200MB of logs will be stored, after which, the oldest logs will start to get deleted.

You can configure some locations and settings for these logs.
To update, edit the file at path reported after running this command

```sh
python -c 'import bioinformatics_tools.caragols.logger; print(bioinformatics_tools.caragols.logger.CONFIG_PATH)'
```

The contents of the file should look something like this

```jsonc
{
    "logging": {
        "console_log_level": "INFO",
        "directory": "~/.caragols/logs",
        "use_user_subdir": true
    }
}
```

`console_log_level`: change this to WARNING if you want less information put
`directory`: is where logs will be stored on your machine
`user_user_subdir`: if true, the logs will be put one folder deeper (than that defined by `directory`), in a folder named after the current user. For example, if the user `bobbyboucher` runs any commands, their logs will appear under `~/.caragols/logs/bobbyboucher`

## EXTRAs: Some philosophical rants

### Let's talk about file validation

Often times we get a file in our hands of a known type, but...how confident are we that the file exactly adheres to the type specification? For example, we might encounter a fasta file that has a _V_ in the sequence, which may not be a big deal, but shoving the file into a pipeline may error out because a particular program determines the fasta file to be invalid. Or perhaps there's a pesky extra space in a file and another program was tricked into thinking the remaining file was empty and the program terminates early; we probably never would know that our program did not finish correctly! (This has happened to me before).  
So here's our solution, which is meant to be an open-source, collaborative effort. We are creating validation classes that scrub our files squeeky clean (and add additional logging) before performing any work on them.  
There's a folder called FileTypes, which contains Python classes that validate as many bioinformatics file types as possible. Each described file has the following capabilities and qualities:

-   Validate the file by scrubbing the entirety of the content
    -   `$ dane valid type: fasta file: example.py` # Return True or False
    -   Coming Soon: Strict vs. Lenient file validation levels
-   A standardized **Preferred Filename**, which removes ambiguity in file naming and extension.
    -   For example, .fna, .fasta, .fa, .fasta.gz, etc., will be coerced to _'.fasta.gz'_. This allows us to control not only the validation but also the naming of the file, which is helpful when we release automated analyses connected via **SnakeMake** (TBD...\*\*)
-   Rewrite a scrubbed, standardized (filename) file that adhered to the preferred filename attribute.
    `$ dane write confident type: fasta file: example`
-   A ton of properties that describe the file. For example, in a BAM file, how many reads are aligned? Or in a gff3 file, where are the XX1 genes located?
    -   This is the meat and potatoes (as we say in the midwest US) of the general toolset, allowing us to quickly and easily extend the things we can do with a particular file.
-   Subsetting functionality, or rewriting a new file based on a filtering condition. For example, you may want to write the 10 largest sequences, or sequences > 2000 basepairs to a new file in a fasta.

## Releases

This project adheres to [semantic versioning](https://semver.org/), and we are in our 0.y.z phase, so this project is not signifying initial development. These releases are not considered stable, and their APIs can change frequently and without warning.

## TODO

- [ ] Allow strict vs. lenient validation of files
- [ ] Add levels for self.validate (hard, soft, ad-hoc, etc.)
- [ ] Incorporate files interacting with other files
- [ ] Incorporate workflows
- [ ] Suffix error when you have file: example.
- [ ] dane type: generate requires a file: but it doesn't acknowledge it when it write it
- [ ] it's also kind of silly to do $ dane create slurm type: gen --> eventually should have some other magic logic
- [ ] BAM
  - [ ] imports
  - [ ] __init__
  - [ ] validate
  - [ ] @commands
- [ ] BED
  - [ ] imports
  - [ ] __init__
  - [ ] validate
  - [ ] @commands
- [ ] GFF
  - [ ] imports
  - [ ] __init__
  - [ ] validate
  - [ ] @commands
- [ ] GTF
  - [ ] imports
  - [ ] __init__
  - [ ] validate
  - [ ] @commands

## Contributor Guide

Dane Deemer: Senior Computational Biologist (Purdue University)
Nathan Denny: Lead Research Analyst (Purdue University)
Stephen Lindemann: Associate Professor (Purdue University)
Maverick Cook: Senior Software Engineer
