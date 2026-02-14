"""
Centralized SSH connection configuration.

Provides a single place to manage host, username, and connection setup
instead of hardcoding paramiko boilerplate in every function.
"""
import logging

import paramiko

LOGGER = logging.getLogger(__name__)


class SSHConnection:
    """Manages paramiko SSH connections with configurable host/user."""

    def __init__(self, host: str = 'negishi.rcac.purdue.edu', username: str = 'ddeemer'):
        self.host = host
        self.username = username

    def connect(self) -> paramiko.SSHClient:
        """Open and return a new SSH connection."""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.host, username=self.username)
        LOGGER.debug('Connected to %s as %s', self.host, self.username)
        return ssh


# Module-level default instance
default_connection = SSHConnection()
