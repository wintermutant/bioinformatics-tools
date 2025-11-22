"""
caragols.clix

I am the Command Line Invocation eXtension (clix)

The basic idea is to rely on JSON or YAML documents for default and/or complex configuration. There are global to program-specific configuration values
you can define; basically you can use the configuration file to customize anything.
"""
import inspect
import logging
import os.path
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

import yaml

from bioinformatics_tools.caragols import carp, condo

LOGGER = logging.getLogger(__name__)


class App:
    """Main application for configuration, logging, and command line parsing.
    """

    # Where default configs can be found
    default_config_template_path = Path(__file__).parent / 'config-template.yaml'
    config_filename = 'config.yaml'
    default_config_path = Path.home() / '.config' / 'bioinformatics-tools' / config_filename

    try:
        default_config = yaml.safe_load(default_config_path.read_text())
    except FileNotFoundError:
        default_config = yaml.safe_load(default_config_template_path.read_text())


    def __init__(self, name=None, run_mode="cli", comargs: list = ['help'], filetype=None, **kwargs):
        # Configure logging for CLI app (attaches handlers)
        from .logger import config_logging_for_app
        config_logging_for_app()

        # Session tracking for log demarcation
        self.session_id = str(uuid4())[:8]
        self.session_start = datetime.now()

        # Log session startup banner
        separator = "=" * 80
        LOGGER.debug("\n%s", separator)
        LOGGER.debug("NEW SESSION: %s | Session ID: %s",
                   self.session_start.strftime("%Y-%m-%d %H:%M:%S"), self.session_id)
        LOGGER.debug("Command: %s", " ".join(sys.argv))
        LOGGER.debug("%s", separator)

        LOGGER.debug('(i) Starting init for clix')

        self.filetype = filetype
        self.run_mode = run_mode
        self.comargs = comargs
        self.actions = []
        self.dispatches = []
        self._name = name
        self.conf: condo.Condex

        # ---------------------------------------------------------------------------
        # -- load any configurations that are in expected places in the file system |
        # ---------------------------------------------------------------------------
        self.configure()

        # -----------------------------------------------------------------------
        # -- the default dispatcher is loaded by reading self for .do_* methods |
        # -----------------------------------------------------------------------
        LOGGER.debug('\n\n(ii) Attr Parsing')
        for attr in dir(self):
            if attr.startswith("do_"):
                action = getattr(self, attr)
                if callable(action):
                    tokens = attr[3:].split('_')
                    self.dispatches.append((tokens, action))

        tokens = [' '.join(v[0]) for v in self.dispatches]

        # -----------------------------------------------------------------------
        # -- Perform the app.prepare_for_run() to setup the app                  |
        # -----------------------------------------------------------------------
        self.prepare_for_run(run_mode)
        LOGGER.debug('# ~~~~~~~~~~ INIT End: CLIX ~~~~~~~~~~ #\n')
        # Note: We do not do the app.run() --> this is controlled elsewhere so it runs when needed


    @classmethod
    def _initialize_user_config(cls) -> None:
        '''Init config file is not found using the template and placing in home'''
        LOGGER.debug('Running _initialize_user_config')
        if not cls.default_config_path.exists():
            cls.default_config_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(cls.default_config_template_path, cls.default_config_path)
            LOGGER.debug('Initialized config file at %s', cls.default_config_path)
        else:
            LOGGER.debug('Yes, path exists for %s', cls.default_config_path)
    
    @property
    def name(self):
        if self._name is None:
            here = os.path.abspath(sys.argv[0])
            _, scriptfile = os.path.split(here)
            appname, _ = os.path.splitext(scriptfile)
            self._name = appname
        return self._name

    # --------------------------------
    # -- BEGIN configuration methods |
    # --------------------------------
    @classmethod
    def _template_config_path(cls):
        return cls.default_config_template_path
    
    @classmethod
    def _passed_config_file(cls) -> Optional[Path]:
        """Parse a command line arg for a file path to a configuration file
        """
        try:
            for i, arg in enumerate(sys.argv):
                if arg == 'config:' and i + 1 < len(sys.argv):
                    config_path = sys.argv[i + 1]
                    return Path(config_path).expanduser().absolute()
        except (IndexError, ValueError):
            pass
        return None

    @classmethod
    def configuration_file(cls) -> Path:
        """
        Returns: 
            the first path that exists, starting in order
            1. check sys.argv for config: <example.config> argument
            2. the default configuration file cls.config_filename
            3. check current working directory for default_config_template_path
            
        Raises: 
            FileNotFoundError: No configuration found
        """
        paths_to_check = [
            cls._passed_config_file(),
            cls.default_config_path,
            cls._template_config_path(),
        ]

        LOGGER.debug('Paths to check: %s', paths_to_check)
        for path in paths_to_check:
            if path and path.exists():
                LOGGER.info('Using config file: %s', path)
                return path
        raise FileNotFoundError('No configuration found')

    def configure(self):
        '''Setup configuration'''
        LOGGER.debug('\n(i) Configuration Setup')
        nuconf = condo.Condex()

        self._initialize_user_config()
        config_file = self.configuration_file()
        # self._check_for_outdated_config(config_file)
        try:
            nuconf.load(config_file)
        except Exception:
            LOGGER.exception('loading configuration file: %s', config_file)
            raise
        self.conf = nuconf
    
    def _iter_commands(self):
        # only methods explicitly decorated (have __cmd_name__)
        for _, fn in inspect.getmembers(self, predicate=callable):
            if getattr(fn, "__cmd_name__", None):
                yield fn

    # ------------------------------
    # -- END configuration methods |
    # ------------------------------

    @property
    def idioms(self):
        """
        I am the list of actions available in the form of [(gravity, tokens, action), ...]
        """
        idioms = []
        for tokens, action in self.dispatches:
            gravity = len(tokens)
            idioms.append((gravity, tokens, action))
        idioms = list(sorted(idioms, reverse=True))
        LOGGER.debug('Created %i idioms', len(idioms))
        return idioms

    def cognize(self, comargs):
        """
        Given comargs, a "command" as a list of string tokens, I try to find a dispatch callable to act on the command.
        If I find a suitable method, I answer (action, barewords) where action is a reference to the callable (function, method, etc.)
        that matches the command. barewords is the list of remaining tokens that are not part of the command.
        Othwerise, I answer None.
        """
        LOGGER.debug('Cognizing %s', comargs)
        xtraopts = {'xtraopt': 'Pass for now'}

        matched = False
        for gravity, tokens, action in self.idioms:
            if comargs[:gravity] == tokens:
                LOGGER.debug('Matched: %s', comargs[:gravity])
                matched = True
                break

        if matched:
            confargs = comargs[gravity:]
            LOGGER.debug('Found confargs: %s', confargs)
            barewords = self.conf.sed(confargs)
            # TODO: We find the barewords and don't do anything with them for now?
            LOGGER.debug('Found barewords: %s', barewords)
            LOGGER.debug('Configuration:\n%s', self.conf.show())
            return (tokens, action, barewords, xtraopts)

    # ----------------------------
    # -- BEGIN app state methods |
    # ----------------------------
    def begun(self) -> None:
        """
        I am called after construction and initialization.
        Override my behavior in a subclass as a relatively easy way to do additional initialization ...
        ... after the configuration pile has been loaded and merged.
        """
        # FUTURE
        return None

    def prepare_for_run(self, run_mode):
        """
        I am the central dispatcher.
        I gather arguments from the command line,
        then invoke the appropriate "do_*" method.
        """
        LOGGER.debug('\n(iii) Preparing for run')
        LOGGER.debug(sys.argv)
        # TODO: Tracking the build of the application before running.
        self.begun()

        # ------------------------------------------------------------------------
        # -- scan for a matching dispatch in order of highest gravity to lowest. |
        # -- Here, "gravity" is the number of tokens in the action, e.g.         |
        # -- "make catalog" has a gravity of 2, while ...                        |
        # -- "make new catalog" would have a gravity of 3.                       |
        # ------------------------------------------------------------------------

        if run_mode.lower() == 'cli':
            # Super important ---> where the CL interacts
            self.comargs = sys.argv[1:]
        elif run_mode.lower() == 'gui':
            # TODO: Figure out how to account for sys.argv[1:]
            #                      comargs={???} if run_mode=='gui'
            comargs = ['help']
        else:
            # Idea --> in init has comargs=sys.argv[1:] if run_mode=='cli
            sys.exit(1)

        matched = self.cognize(self.comargs)
        self.matched = matched

        LOGGER.debug(f'\n\n(iv) Matching & Configuration Update. {matched=}')
        if matched:
            tokens, action, barewords, xtraopts = matched  # Where the help or whatever action gets recognized

            try:
                self.action, self.barewords, self.xtraopts = action, barewords, xtraopts
                return 0
            except Exception as err:
                LOGGER.exception('error unpacking cli?')
                self.report = self.crashed(str(err))
        else:
            self.report = self.failed(
                'Bad request due to no "matched".\ntry using "help" command?')

        # # --------------------------------------------------
        # # -- If the action did not complete with a report, |
        # # -- this should be considered a crash!            |
        # # --------------------------------------------------
        # # TODO: Alter the below code to sort based off of CLI vs. GUI modes

        # if getattr(self, 'report', None) is None:
        #     self.report = self.crashed("no report returned by action!")

        # form = self.conf.get('report.form', 'prose')

        # if run_mode == "cli":
        #     sys.stdout.write(self.report.formatted(form))
        #     sys.stdout.write('\n')
        #     self.done()
        #     if self.report.status.indicates_failure:
        #         sys.exit(1)
        #     else:
        #         sys.exit(0)
        # elif run_mode == "gui":
        #     return {'status': 'success'}
    
    def run(self):
        '''This goes beyond the initialization and runs the program'''
        LOGGER.debug('\n\n(v) Running the actual executable --> %s', self.action)
        xtraopts = self.xtraopts
        # TODO: STARTHERE --> We run this action like this BUT in fasta.do_gc_content, for example, we use the self.conf to get the variables, not the
        # arguments to the method.
        # self.action(self.barewords, **xtraopts)
        self.action()
        # --------------------------------------------------
        # -- If the action did not complete with a report, |
        # -- this should be considered a crash!            |
        # --------------------------------------------------
        # TODO: Alter the below code to sort based off of CLI vs. GUI modes

        LOGGER.debug('\n\n(vi): Running the final report')
        if getattr(self, 'report', None) is None:
            self.report = self.crashed("No report returned by action!")

        form = self.conf.get('report.form', 'csv') # Change report form

        if self.run_mode == "cli":
            # Below is the culprite for the duplication!
            LOGGER.info('📄 Report Generated:\n%s', self.report.formatted(form))
            self.done()
            if self.report.status.indicates_failure:
                sys.exit(1)
            else:
                sys.exit(0)
        elif self.run_mode == "gui":
            return {'status': 'success'}

    def done(self):
        """
        I do any finalization just before exiting.
        My default behavior is to do nothing; however,
        override my behavior if any additional "clean up" is needed after the app has run (and dispatched).
        """
        # Log session completion banner
        session_end = datetime.now()
        duration = (session_end - self.session_start).total_seconds()
        separator = "=" * 80

        LOGGER.debug("%s", separator)
        LOGGER.debug("SESSION COMPLETED: %s | Session ID: %s",
                   session_end.strftime("%Y-%m-%d %H:%M:%S"), self.session_id)
        LOGGER.debug("Duration: %.2f seconds", duration)
        LOGGER.debug("%s\n", separator)

        return None

    # -----------------------------------------------------------------
    # -- BEGIN completion methods                                     |
    # -- All do_* methods should end by calling one of these methods. |
    # -----------------------------------------------------------------

    def succeeded(self, msg="", dex=None, **kwargs):
        repargs = kwargs.copy()
        repargs['body'] = msg
        repargs['data'] = dex
        self.report = carp.Report.Success(**repargs)
        return self.report

    def finished(self, msg="", dex=None, **kwargs):
        repargs = kwargs.copy()
        repargs['body'] = msg
        repargs['data'] = dex
        self.report = carp.Report.Inconclusive(**repargs)
        return self.report

    def failed(self, msg="", dex=None, **kwargs):
        repargs = kwargs.copy()
        repargs['body'] = msg
        repargs['data'] = dex
        self.report = carp.Report.Failure(**repargs)
        return self.report

    def crashed(self, msg="", dex=None, **kwargs):
        repargs = kwargs.copy()
        repargs['body'] = msg
        repargs['data'] = dex
        # self.report     = carp.Report.Exception(msg, **repargs)
        self.report = carp.Report.Exception(**repargs)
        LOGGER.critical(msg)  # -- emit the message to our log.
        return self.report

    # ---------------------------
    # -- END completion methods |
    # ---------------------------

    # --------------------------------------------
    # -- BEGIN app operation, aka "do_*" methods |
    # --------------------------------------------

    def do_help(self, barewords, **kwargs):
        """Show all command patterns and their help messages"""
        doclines = []
        print(f'Dispatches:\n{self.dispatches}')
        for cnt, actionable in enumerate(sorted(self.dispatches)):
            tokens, action = actionable
            humanable = " ".join(tokens)
            doclines.append(f'{cnt}: \033[92m $ {self.name} {humanable} type: {self.filetype} file: example.{self.filetype}\033[0m')
            # Below, we want the docstring to be added with a decorator function
            if action.__doc__:
                for line in action.__doc__.strip().split('\n'):
                    doclines.append(line)
                doclines.append('\n')
        doc = "\n".join(doclines)
        return self.succeeded(doc)

    # ------------------------------
    # -- END app operation methods |
    # ------------------------------
