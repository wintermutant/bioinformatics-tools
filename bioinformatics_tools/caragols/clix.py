"""
caragols.clix

I am the Command Line Invocation eXtension (clix)

The basic idea is to rely on JSON or YAML documents for default and/or complex configuration. There are global to program-specific configuration values
you can define; basically you can use the configuration file to customize anything.
"""
import logging
import os.path
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from uuid import uuid4

from bioinformatics_tools.caragols import carp, condo
from bioinformatics_tools.caragols.session import SessionLogger

LOGGER = logging.getLogger(__name__)

@dataclass
class Dispatch:
    '''represents natural language tokens mapping to a callable
    from methods starting with do_*'''
    tokens: list[str]
    action: Callable
    gravity: int = field(init=False)
    barewords: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.gravity = len(self.tokens)


class App:
    """Main application for configuration, logging, and command line parsing.
    """

    # Where default configs can be found
    template_config_path = Path(__file__).parent / 'config-template.yaml'
    config_filename = 'config.yaml'  # FIXME:
    default_config_path = Path.home() / '.config' / 'bioinformatics-tools' / config_filename

    def __init__(self, name=None, run_mode="cli", filetype=None, match=True):
        '''config, logging, and command line parsing'''
        # Session tracking for log demarcation
        self.session_id = str(uuid4())[:8]
        self.session_start = datetime.now()
        SessionLogger.start_session_info(LOGGER, self.session_id, self.session_start)

        SessionLogger.log_header_section(LOGGER, '(i) Starting init for clix')

        self._name = name
        self.filetype = filetype
        self.run_mode = run_mode
        self.comargs = ['help']  #TODO get rid  of this
        self.match_cmd_to_process = match
        self.report: carp.Report | None = None
        self.conf: condo.Condex

        # -- load any configurations that are in expected places in the file system -- #
        self.configure()

        # ---- the default dispatcher is loaded by reading self for .do_* methods ---- #
        SessionLogger.log_header_section(LOGGER, '(iii) Initializing Dispatches (do_) methods')
        self.dispatches: list[Dispatch] = []
        self.init_do_dispatches()

        # ------------------ setup the app to be ready for app.run() ----------------- #
        self.prepare_for_run(run_mode)
        SessionLogger.log_header_section(LOGGER, 'End of CLIX initialization')

    def init_do_dispatches(self):
        '''scan all methods starting with do_ and appending to dispatches'''
        for attr in dir(self):
            if attr.startswith("do_"):
                action = getattr(self, attr)
                if callable(action):
                    tokens = attr[3:].split('_')  # remove the str: do_
                    self.dispatches.append(Dispatch(tokens=tokens, action=action))

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
    def _initialize_user_config(cls) -> None:
        '''Inits or verifies ~/.config/bioinformatics-tools/config.yaml'''
        LOGGER.debug('Running _initialize_user_config')
        if not cls.default_config_path.exists():
            cls.default_config_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(cls.template_config_path, cls.default_config_path)
            LOGGER.debug('Initialized config file at %s', cls.default_config_path)
        else:
            LOGGER.debug('Yes, path exists for %s', cls.default_config_path)

    @classmethod
    def _template_config_path(cls):
        return cls.template_config_path
    
    @classmethod
    def _passed_config_file(cls) -> Optional[Path]:
        """Parse a command line arg for a file path to a configuration file
        """
        #FUTURE unhack this. We need to do it this way because this is upstream of command line
        # arguments being processed
        try:
            for i, arg in enumerate(sys.argv):
                if arg == 'config:' and i + 1 < len(sys.argv):
                    config_path = sys.argv[i + 1]
                    return Path(config_path).expanduser().absolute()
        except (IndexError, ValueError):
            pass
        return None

    @classmethod
    def _get_config_search_paths(cls) -> list[Path]:
        config_paths = [
            cls._template_config_path(),
            cls.default_config_path,
        ]
        if cl_config := cls._passed_config_file():
            config_paths.append(cl_config)
        LOGGER.debug('config paths: %s', config_paths)
        return config_paths

    @classmethod
    def get_configuration_files(cls) -> list[Path]:
        '''Return configuration files tested for existence'''
        config_files = []
        for path in cls._get_config_search_paths():
            if path and path.exists():
                config_files.append(path)
        if not config_files:
            LOGGER.warning('No configuration files found!')
        LOGGER.debug('Found the following config files: %s', config_files)
        return config_files

    def configure(self):
        '''Setup configuration by checking all locations and overriding based on
        _get_config_search_paths hierarchy'''
        SessionLogger.log_header_section(LOGGER, '(ii) Configuration Setup')
        nuconf = condo.Condex()

        self._initialize_user_config()
        config_files = self.get_configuration_files()
        if not config_files:
            LOGGER.warning('No configuration files found!')
            self.conf = nuconf  # Return BLANK config
            return

        for conf in config_files:
            try:
                nuconf.load(conf)
            except Exception:
                LOGGER.exception('Error loading conf file: %s', conf)
                raise
        self.conf = nuconf
    
    # ------------------------------
    # -- END configuration methods |
    # ------------------------------

    def cognize(self, comargs) -> Dispatch | None:
        """
        Given comargs, a "command" as a list of string tokens, I try to find a dispatch callable to act on the command.
        If I find a suitable method, I answer (action, barewords) where action is a reference to the callable (function, method, etc.)
        that matches the command. barewords is the list of remaining tokens that are not part of the command.
        Othwerise, I answer None.
        """
        LOGGER.debug('Cognizing %s', comargs)

        matched: Dispatch | None = None
        # for gravity, tokens, action in self.dispatches:
        for dispatch in self.dispatches:
            if comargs[:dispatch.gravity] == dispatch.tokens:
                LOGGER.debug('Matched: %s', comargs[:dispatch.gravity])
                matched = dispatch
                confargs = comargs[dispatch.gravity:]
                matched.barewords = self.conf.sed(confargs)
                break
        
        if not matched:
            LOGGER.debug('No match found when cognizing')
        return matched

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
        SessionLogger.log_header_section(LOGGER, "(iv) Preparing for run")
        # self.begun()

        if run_mode.lower() == 'cli':
            # Super important ---> where the CL interacts
            self.comargs = sys.argv[1:]
        else:
            sys.exit(1)

        self.matched_dispatch = self.cognize(self.comargs)
        # self.matched = matched

        SessionLogger.log_header_section(LOGGER, "(v) Matching & Configuration Update")
        if self.matched_dispatch:
            # tokens, action, barewords = matched  # Where the help or whatever action gets recognized

            try:
                # self.action, self.barewords = action, barewords
                self.action, self.barewords = self.matched_dispatch.action, self.matched_dispatch.barewords
                # When we run, rather call self.matched_dispatch.action and self.matched_dispatch.barewords
                return 0
            except Exception as err:
                LOGGER.exception('error unpacking cli?')
                self.report = self.crashed(str(err))
        if not self.match_cmd_to_process:
            pass  #TODO: Hack here for dane_wf to not worry about matching. Later we may want
        # workflow.do_example and then have that be how we map commands to files, instead of the
        # workflowmapper object in workflow_tools.main.py
        else:
            self.report = self.failed(
                'Bad request due to no "matched".\ntry using "help" command?')

        # # --------------------------------------------------
        # # -- If the action did not complete with a report, |
        # # -- this should be considered a crash!            |
        # # --------------------------------------------------
    
    def run(self):
        '''This goes beyond the initialization and runs the program'''
        # TODO: STARTHERE --> We run this action like this BUT in fasta.do_gc_content, for example, we use the self.conf to get the variables, not the
        # arguments to the method.
        if self.matched_dispatch:
            self.matched_dispatch.action()  # Running the do_ method we found
        # Each do_ method should end with a self.succeeded() message and self.failed() if not

        SessionLogger.log_header_section(LOGGER, "(vi): Running the final report")
        if getattr(self, 'report', None) is None:  # Report generates from do_ method
            LOGGER.warning('getattr(report) is none!')
            self.report = self.crashed("No report returned by action!")

        form = self.conf.get('report.form', 'prose') # Change report form

        if self.run_mode == "cli":
            LOGGER.info('\n📄 Report Generated:\n%s', self.report.formatted(form))
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

        return None

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
        self.report = carp.Report.Exception(**repargs)
        LOGGER.critical(msg)  # -- emit the message to our log.
        return self.report

    
    # ------------------------ begin default do_* methods ------------------------ #
    def do_help(self, **kwargs):
        """Show all command patterns and their help messages"""
        doclines = []
        for cnt, actionable in enumerate(self.dispatches): #TODO: Sort method for these
            humanable = " ".join(actionable.tokens)
            doclines.append(f'{cnt}: \033[92m $ {self.name} {humanable} type: {self.filetype} file: example.{self.filetype}\033[0m')
            if actionable.action.__doc__:  # Add docstring from functions to help message
                for line in actionable.action.__doc__.strip().split('\n'):
                    doclines.append(line)
                doclines.append('\n')
        doc = "\n".join(doclines)
        return self.succeeded(doc)
