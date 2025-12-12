'''
All things logging
'''

import getpass
import logging.config
import shutil
import sys
from pathlib import Path
import yaml

import bioinformatics_tools

LOG_HANDLERS: list[str]
_logging_configured = False  # Guard to prevent duplicate configuration

LOGGING_CONFIG_TEMPLATE_PATH = Path(__file__).parent / 'logging-config.yaml'
LOGGING_CONFIG_DEFAULT_PATH =  Path.home() / '.config' / 'bioinformatics-tools' / 'logging-config.yaml'

def initialize_logging_config() -> Path:
    '''Init config file is not found using the template and placing in home
    This log file tells us where to place the logs and some other basic stuff, but mainly
    where the log should be
    #FUTURE: This can be configured by an admin so a groups log info can go to 1 spot
    '''
    if not LOGGING_CONFIG_DEFAULT_PATH.exists():
        LOGGING_CONFIG_DEFAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(LOGGING_CONFIG_TEMPLATE_PATH, LOGGING_CONFIG_DEFAULT_PATH)
    return LOGGING_CONFIG_DEFAULT_PATH

def load_config():
    '''Open and initialize logging'''
    logging_config_path = initialize_logging_config()
    with open(logging_config_path) as f:
        logging_config = yaml.safe_load(logging_config_path.read_text())

    log_dir = Path(logging_config['directory']).expanduser().absolute()

    if logging_config['use_user_subdir']:
        log_dir /= getpass.getuser()
    log_dir.mkdir(parents=True, exist_ok=True)
    console_log_level = logging_config['console_log_level']
    

    root_log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            # https://docs.python.org/3/library/logging.html#logrecord-attributes
            "caragols_basicFormatter": {
                "format": "[%(asctime)s %(levelname)s %(name)s] - %(message)s",
                "datefmt": "%H:%M:%S",
            },
            "caragols_verboseFormatter": {
                "format":
                    "[%(asctime)s %(levelname)s %(process)d %(filename)s:%(funcName)s:%(lineno)d] - %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
            },
            "caragols_jsonFormatter": {
                "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                "format": "%(asctime)s.%(msecs)03d %(levelname)s %(name)s %(filename)s %(module)s %(process)d %(processName)s %(thread)d %(funcName)s %(lineno)d %(message)s"
            }
        },
        "handlers": {
            "caragols_consoleHandler": {
                "level": console_log_level,
                "class": "logging.StreamHandler",
                "formatter": "caragols_basicFormatter",
                "stream": sys.stdout,
            },
            "caragols_plaintextFileHandler": {
                "level": "DEBUG",
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "caragols_verboseFormatter",
                "filename": log_dir / 'log.txt',
                "maxBytes": 2e6, # 2MB
                "backupCount": 100,
            },
            "caragols_jsonFileHandler": {
                "level": "DEBUG",
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "caragols_jsonFormatter",
                "filename": log_dir / 'log.jsonl',
                "maxBytes": 2e6, # 2MB
                "backupCount": 100,
            },
        },
        "loggers": {
            # when used a library (python api), there should be no handlers configured, so users of the lib can configure logs as they wish
            # when used as an CLI / directly, we will add our specific handlers
            "bioinformatics_tools": {
                "level": "DEBUG",
                "handlers": [],
            },
        },
    }

    return root_log_config


startup_info = {
    'cwd': Path.cwd(),
    'user': getpass.getuser(),
    'argv': sys.argv,
    'package_version': bioinformatics_tools.__version__
}


def config_logging_for_app():
    """(re)Configure the main logger for running as a CLI app

    We default to running in a "library" logging config, meaning no handlers are added to the logger, so clients can add
    their own, as recommended by https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library

    This allows us to still leverage the convenience of dictConfig
    """
    global LOGGER, _logging_configured

    # Prevent duplicate configuration
    if _logging_configured:
        return

    log_config: dict = load_config()
    log_handlers: list = log_config['handlers'].keys()
    # Add handlers to bioinformatics_tools logger (all modules inherit from this)
    log_config['loggers']['bioinformatics_tools']['handlers'] = log_handlers
    logging.config.dictConfig(config=log_config)
    LOGGER = logging.getLogger('bioinformatics_tools')
    LOGGER.debug('\nStartup: %s\n', startup_info)
    _logging_configured = True

logging.config.dictConfig(config=load_config())
LOGGER = logging.getLogger('bioinformatics_tools')
