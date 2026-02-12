"""
SFTP file operations over SSH.

Provides remote directory listing and file streaming via paramiko SFTP.
"""
import logging
import stat

from bioinformatics_tools.utilities.ssh_connection import default_connection

LOGGER = logging.getLogger(__name__)


def list_remote_dir(remote_path: str) -> list[dict]:
    """List files and directories in a remote path via SFTP.

    Returns a list of dicts: {name, type, size}.
    """
    ssh = default_connection.connect()

    sftp = ssh.open_sftp()
    entries = []
    for attr in sftp.listdir_attr(remote_path):
        entry_type = 'directory' if stat.S_ISDIR(attr.st_mode) else 'file'
        entries.append({
            'name': attr.filename,
            'type': entry_type,
            'size': attr.st_size,
        })

    sftp.close()
    ssh.close()
    return entries


def stream_remote_file(remote_path: str):
    """Generator that streams a remote file in chunks via SFTP.

    Yields bytes chunks (8KB each).
    """
    ssh = default_connection.connect()

    sftp = ssh.open_sftp()
    with sftp.open(remote_path, 'rb') as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            yield chunk

    sftp.close()
    ssh.close()
