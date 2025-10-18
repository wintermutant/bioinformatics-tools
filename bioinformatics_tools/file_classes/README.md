# Contribution Guide

# Class Rules Representing a File

## Class Attributes

- self.known_extensions
- self.known_compressions
- self.preferred_extension: each has a 'preferred' extension and encoding
- self.available_rules
  - ADD MORE INFO HERE
- self.outputs
  - ADD MORE INFO HERE (Potential SnakeMake tie-in)

## Attributes

- self.file_path -> The input files path
- self.file_name -> The input files name
- self.detect_mode -> Detection mode for validation (default: medium)
- self.preferred_file_path
  - This is used for writing to a known output in the format: {wildcard}-VALIDATED{self.preferred_extension}. NOTE: This does not write any file, just creates the preferred file path
- self.valid -> We call the unique self.validate() method in order to create this attribute
- self.valid_extension -> Does the initial file have a valid/known extension
  - This is a little misleading, because it makes it seem like a valid_extension ensures the encoding matches the extension or it does not/is unknown

## Methods

- clean_file_name() -> given the input, create the self.preferred_file_path in the form {wildcard}-VALIDATED{self.preferred_extension}
- validate() -> Validate the specific file type. This is where the bulk of the code should be, especially unique code.
- self.write\_<filetype> -> This writes a validated file
- self.write_table -> This writes a validated tabular version of the file
- self.write_confident

## Properties

- Properties allow us to get low-level information on the file, such as length, total count, and various other properties we might be interested. This is where community effort can extend the functionality of the class

## Writing Validated Output

- Whenever I write a new file, I write it from the fastaKey values, not the initial file
  - This requires the file to be validated, since that's where we grabbed that internal data

### What I want to be able to do

1. $ dane myfile.fasta
   1. By default will output a verification such as: > Encoding: None, Compression: None, Valid: True, CheckSum 5AFKFKCA441, etc.
2. $ dane myfile.fasta --list-programs
   1. \> (i) make_validated; (ii) filter; (iii) trim; etc.
3. $ dane myfile.fasta filter
   1. \> Params == default
   2. How are we fully able to configure the params? At that point we may as well run the program...
   3. What about a config in the home directory specifying the the default value and params, but the user could change those as necessary
      1. This is configurability through a config file versus via a command line
4. $ dane myfile.fasta filter --cluster
5. $ dane myfile.fasta --verify --mode soft

### Notes

- Do I want some stuff to work with validation and some without? Need to think more on the validation wrapper/decorator
- Will need a class for each file type
- Will need a mapper for each rule
- To determine file types, will most likely need a hierarchical approach to guess
- When I want to extend the capabilities of the class, what's the best approach?
  - I think preference, validation, and internal permutations MUST be within the class
  - Another bucket: called an external program to do work on the file
    - For this, always write the -VALIDATED{preferred_extension}, that way we control the output's complete form --> {wildcard}-VALIDATED{preferred_extension}
      - Should I have -VALIDATED{preferred_extension} or -VALIDATED.{preferred_extension}? IDK

### TODO

1. Fasta
   1. Support for multiple files added to the class
2. Command line invocation method (probably CLIX)
3. When I add functionality, what's the easiest thing?
4.
