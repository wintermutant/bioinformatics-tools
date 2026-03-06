"""
Centralized SSH connection configuration.

Provides a single place to manage host, username, and connection setup
instead of hardcoding paramiko boilerplate in every function.

All SSH/SFTP operations are API-layer only. The CLI runs directly on the
cluster and has no need to establish outbound SSH connections.

API usage:
    Call make_user_connection(host, username, private_key_str), which reads
    the user's cluster credentials from the database record, loads the
    decrypted private key into memory (never written to disk), and returns
    a ready SSHConnection.
"""
import io
import logging

import paramiko

LOGGER = logging.getLogger(__name__)

_KEY_CLASSES = (
    paramiko.RSAKey,
    paramiko.Ed25519Key,
    paramiko.ECDSAKey,
)


def load_private_key(key_str: str) -> paramiko.PKey:
    """
    Auto-detect SSH key type and return a paramiko PKey object.
    Tries RSA, Ed25519, ECDSA, and DSS in order.
    Raises ValueError if none succeed.
    """
    for key_class in _KEY_CLASSES:
        try:
            return key_class.from_private_key(io.StringIO(key_str.strip()))
        except (paramiko.SSHException, Exception):
            continue
    raise ValueError('Unsupported or invalid SSH private key format')


class SSHConnection:
    """Manages paramiko SSH connections with configurable host/user/key."""

    def __init__(
        self,
        host: str | None = None,
        username: str | None = None,
        pkey: paramiko.PKey | None = None,
        key_filename: str | None = None,
    ):
        self.host = host
        self.username = username
        self.pkey = pkey               # in-memory key object (API usage)
        self.key_filename = key_filename   # file path (CLI fallback)

    def connect(self) -> paramiko.SSHClient:
        """Open and return a new SSH connection."""
        if not self.host or not self.username:
            raise ValueError(
                'SSHConnection requires host and username. '
                'Use make_user_connection() in API context, or set host/username '
                'from the user config for CLI usage.'
            )
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs: dict = {'username': self.username}
        if self.pkey:
            connect_kwargs['pkey'] = self.pkey
        elif self.key_filename:
            connect_kwargs['key_filename'] = self.key_filename
        # If neither is set, paramiko falls back to the system SSH agent (CLI default)
        ssh.connect(self.host, **connect_kwargs)
        LOGGER.debug('Connected to %s as %s', self.host, self.username)
        return ssh


def make_user_connection(
    cluster_host: str,
    cluster_username: str,
    private_key_str: str,
) -> SSHConnection:
    """
    Build an SSHConnection for a specific user's cluster account.

    Accepts the plaintext (already-decrypted) private key string, loads it
    into a paramiko PKey object in memory, and returns an SSHConnection.
    The key is never written to disk.
    """
    pkey = load_private_key(private_key_str)
    return SSHConnection(host=cluster_host, username=cluster_username, pkey=pkey)


