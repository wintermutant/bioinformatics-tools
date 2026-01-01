'''base class and utilities for i/o (file classes)
The idea is you can add a new module, NewFileType.py, then create a class that inherits from clix.App
Any do_* methods will automatically become command line tools
class NewFileType(clix.App)
def do_something_fun(self):
    print('Hi!)
def do_something_mean(self):
    print('You are stinky!')
Above gets parsed and CLI finds new type: newfiletype so you can run the commands:
$ dane something fun type: newfiletype
$ dane something mean type: newfiletype
'''
from contextlib import redirect_stdout
import gzip
import io
import inspect
import logging
import mimetypes
import pathlib
import re
import sys

import typer

from bioinformatics_tools.caragols import clix
from bioinformatics_tools.caragols.session import SessionLogger

LOGGER = logging.getLogger(__name__)

MAIN_EXECUTABLE_NAME='dane' # TODO: This will have to change when we have more executables


class ListHandler(logging.Handler):
    '''Custom handler that stores formatted log strings in a list'''
    #TODO: Move to logger.py
    def __init__(self):
        super().__init__()
        self.log_records = []
        self.setFormatter(logging.Formatter(
            '[%(asctime)s %(levelname)s %(name)s:%(funcName)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%dT%H:%M:%S'
        ))

    def emit(self, record):
        self.log_records.append(self.format(record))

def get_global_cli_parameters():
    """
    #FUTURE
    Returns a list of global CLI parameters that should be available to all commands.
    Each parameter is a tuple of (name, annotation, default_value).
    """
    return [
        # (
        #     'config_file',
        #     str,
        #     typer.Option(None, "--config-file", help="Path to configuration file")
        # ),
    ]

def add_global_parameters_to_signature(sig, global_params):
    """
    Add global parameters to a function signature.
    """
    new_params = []

    # Add original function parameters first
    for param_name, param in sig.parameters.items():
        if param_name not in ["self", "barewords", "kwargs"]:
            # Extract actual default value from typer.Option objects
            default_value = param.default
            if hasattr(default_value, 'default'):
                default_value = default_value.default

            new_params.append(param.replace(default=default_value))

    # Add global parameters as keyword-only at the end
    for param_name, param_type, param_default in global_params:
        global_param = inspect.Parameter(
            param_name,
            inspect.Parameter.KEYWORD_ONLY,
            annotation=param_type,
            default=param_default
        )
        new_params.append(global_param)

    return inspect.Signature(parameters=new_params) if new_params else sig

def command(fn_or_name=None, *, aliases: list[str] | None = None):
    """
    Decorator that creates a typer app for a method and handles --help integration.
    Supports both @command and @command() syntax.
    """
    def deco(fn):
        # Handle case where decorator is used without parentheses
        name = fn_or_name if isinstance(fn_or_name, str) else None
        cmd_name = name or fn.__name__.removeprefix("do_").replace("_", " ")
        cmd_aliases = aliases or []

        # Create typer app for this command
        app = typer.Typer()

        # Get function signature and create typer wrapper
        sig = inspect.signature(fn)

        def create_typer_command():
            # Get global parameters from shared location
            global_params = get_global_cli_parameters()
            global_param_names = [param[0] for param in global_params]

            # Build dynamic function with global parameters
            global_param_args = ", ".join([
                f"{param_name}: {param_type.__name__} = {param_name}_default"
                for param_name, param_type, param_name_default in global_params
            ])

            # Create function dynamically with correct signature, including global args
            def typer_cmd(*args, **kwargs):
                """Typer wrapper for the original function"""
                # Remove global args that aren't part of the original function
                func_kwargs = {k: v for k, v in kwargs.items() if k not in global_param_names}
                # Call original function, passing None for self and barewords
                return fn(None, None, *args, **func_kwargs)

            # Set the function signature to include both original params and global args
            typer_cmd.__signature__ = add_global_parameters_to_signature(sig, global_params)

            # Copy docstring
            typer_cmd.__doc__ = fn.__doc__

            # Copy type annotations including global args
            typer_cmd.__annotations__ = {}
            for param_name, param_type, _ in global_params:
                typer_cmd.__annotations__[param_name] = param_type

            for param_name, param in sig.parameters.items():
                if param_name not in ["self", "barewords", "kwargs"]:
                    typer_cmd.__annotations__[param_name] = param.annotation if param.annotation != inspect.Parameter.empty else str

            return typer_cmd

        # Register command with typer
        typer_command = create_typer_command()
        app.command()(typer_command)

        # Attach typer app to function
        fn.__typer_app__ = app
        fn.__cmd_name__ = cmd_name
        fn.__cmd_aliases__ = cmd_aliases

        def wrapper(self, *args, **kwargs):
            # Check for --help in arguments
            if '--help' in sys.argv:
                

                # Capture help output
                help_buffer = io.StringIO()
                try:
                    with redirect_stdout(help_buffer):
                        app(["--help"])
                except SystemExit:
                    pass

                # Transform help text: replace --option with option:
                help_text = help_buffer.getvalue()
                # Replace patterns like "--precision" or "--min-length" with "precision:" or "min-length:"
                help_text = re.sub(r'--([a-z0-9-]+)', r'\1:', help_text)
                # Replace short options like "-l" with corresponding text
                help_text = re.sub(r'\s+-([a-z])\s+', r' ', help_text)
                # Update section headers (handle both with and without colons, and with box drawing characters)
                help_text = re.sub(r'Options:?(\s|─)', r'Parameters (use key: value syntax):\1', help_text)
                help_text = help_text.replace('[OPTIONS]', '[PARAMETERS]')
                help_text = help_text.replace('OPTIONS', 'PARAMETERS')

                print(help_text)

                if hasattr(self, 'succeeded'):
                    self.succeeded(msg=f"Help displayed for {cmd_name} command", dex={"action": "help", "command": cmd_name})
                return

            return fn(self, *args, **kwargs)

        # Copy attributes to wrapper
        wrapper.__typer_app__ = app
        wrapper.__cmd_name__ = cmd_name
        wrapper.__cmd_aliases__ = cmd_aliases
        wrapper.__doc__ = fn.__doc__
        wrapper.__name__ = fn.__name__

        return wrapper

    # Handle @command without parentheses
    if callable(fn_or_name):
        return deco(fn_or_name)

    return deco

class BioBase(clix.App):
    '''
    Base class for all file classes. This is more about shared methods versus initialization
    '''
    known_compressions = ['.gz', '.gzip']
    known_extensions = []

    def __init__(self, detect_mode="medium", run_mode='cli', filetype=None) -> None:
        self.detect_mode = detect_mode

        # ------------------------ Running base clix.App init ------------------------ #
        super().__init__(run_mode=run_mode, name=MAIN_EXECUTABLE_NAME, filetype=filetype)
        SessionLogger.log_header_section(LOGGER, f"Starting Biobase Init with conf:\n{self.conf.show()}")
        self.file = self.conf.get('file', None)

        # TODO: Don't like returns nested in here
        if not self.matched_dispatch:
            LOGGER.info('%s \n', self.report.formatted(self.conf.get('report.form')))
            self.done()
            #TODO: sys.exit should be replaced with a report.
            if self.report.status.indicates_failure:
                sys.exit(1)
            else:
                sys.exit(0)

        # Check for --help before file validation: skip validation if so
        if '--help' in sys.argv:
            self.file_path = None
            self.file_name = None
        elif 'help' in self.matched_dispatch.tokens[0]:  # If just running help, don't need to do anything
            self.run()
        elif self.file:
            self.file_path = pathlib.Path(self.file)
            self.file_name = self.file_path.name
        else:  #TODO: Case when type: generate and no file provided, it should be okay
            message = 'ERROR: No file provided. Please add file via: $ dane file: example.fasta'
            self.failed(msg=f"{message}", dex=message)
            LOGGER.info('%s \n', self.report.formatted(self.form))
            self.done()
            if self.report.status.indicates_failure:
                sys.exit(1)
            else:
                sys.exit(0)
        SessionLogger.log_header_section(LOGGER, 'Finished Biobase Init')

    def clean_file_name(self) -> pathlib.Path | None:
        '''
        e.g. for standard file suffix - always want our fastq file to end in .fastq.gz.
        For example, if a file comes in as myfile.fg, it'll be renamed to myfile.fastq.gz
        Or, if a file is fastq.txt, it'll be renamed to myfile.fastq.gz
        '''
        if self.file_path is None:
            # Return a dummy value for --help mode
            return pathlib.Path("dummy-filename.txt")

        suffixes = self.file_path.suffixes
        self.basename = self.file_path.stem
        if suffixes and suffixes[-1] in self.known_compressions:
            if len(suffixes) > 1 and suffixes[-2] in self.known_extensions:
                self.basename = pathlib.Path(self.basename).stem
                return self.file_path.with_name(f'{self.basename}-VALIDATED{self.preferred_extension}')
            return None
        return self.file_path.with_name(f'{self.basename}-VALIDATED{self.preferred_extension}')
    
    # ~~~ Validation Stuff ~~~ #
    def is_known_extension(self) -> bool:
        '''
        Is there a known extension of the file?
        '''
        if self.file_path is None:
            # Return True for --help mode to avoid validation issues
            return True

        suffixes = self.file_path.suffixes
        if suffixes[-1] in self.known_compressions:
            return len(suffixes) > 1 and suffixes[-2] in self.known_extensions
        else:
            return suffixes[-1] in self.known_extensions
    
    def is_valid(self) -> bool:
        if self.file_path is None:
            # Return True for --help mode to avoid validation issues
            return True
        
        if not self.file_path.exists():
            LOGGER.debug('File does not exist: %s', self.file_path)
            return False

        _, encoding = mimetypes.guess_type(self.file_path)

        # Here, open up the file and validate it to determine if it is indeed the correct file type
        if not encoding:  # This means no compression
            LOGGER.debug('File is not compressed')
            with open(str(self.file_path), 'rt', encoding='utf-8') as open_file:
                return self.validate(iter(open_file))
        #TODO Add dynamic opening from self.known_compressions
        elif encoding == 'gzip':
            LOGGER.debug('File is gzip compressed')
            with gzip.open(str(self.file_path), 'rt') as open_file:
                return self.validate(iter(open_file))
        else:
            LOGGER.debug('File is compressed but in an unknown format: %s', encoding)
            return False
    
    def file_not_valid_report(self):
        '''default report when file is not valid'''
        message = 'File is not valid according to validation'
        LOGGER.error(message)
        self.failed(
            msg=f"{message}", dex=message)
        LOGGER.info('\n%s', self.report.formatted(self.conf.get('report.form', 'prose')))
        self.done()
        if self.report.status.indicates_failure:
            sys.exit(1)
        else:
            sys.exit(0)
    
    @command
    def do_valid(self):
        '''Check to see if the file is valid, meaning it has been parsed and the contents are correct'''
        response = self.valid
        self.succeeded(
            msg=f"File was scrubbed and found to be {response}", dex=response)
        return 0
