'''
module for printing and logging specific messages to
stdout, stderr, and log files
'''
from datetime import datetime
import sys


class SessionLogger:
    '''Housing static methods for log/stdout statements.
    If shared state is needed, can initialize. #FUTURE
    '''

    @staticmethod
    def start_session_info(logger, session_id, session_start = None):
        '''log for starting the app'''
        session_start = session_start or datetime.now()
        separator = "=" * 80
        logger.debug("%s", separator)
        logger.debug("NEW SESSION: %s | Session ID: %s",
        session_start.strftime("%Y-%m-%d %H:%M:%S"), session_id)
        logger.debug("Command: %s", " ".join(sys.argv))
        logger.debug("%s", separator)
    
    @staticmethod
    def log_header_section(logger, message):
        '''message to start a new section'''
        separator = "~" * len(message)
        logger.debug("%s", separator)
        logger.debug("%s", message)
        logger.debug("%s", separator)
