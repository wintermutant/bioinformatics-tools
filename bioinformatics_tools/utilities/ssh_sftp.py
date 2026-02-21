"""
SFTP file operations over SSH.

Provides remote directory listing, file streaming, and YAML config
read/write via paramiko SFTP.

All functions accept an optional `connection` parameter. When called from
the API layer, pass a per-user SSHConnection built with make_user_connection().
When called from the CLI (or legacy code), the default_connection singleton
is used unchanged.
"""
import logging
import stat

import yaml

from bioinformatics_tools.utilities.ssh_connection import SSHConnection, default_connection

LOGGER = logging.getLogger(__name__)


def list_remote_dir(
    remote_path: str,
    connection: SSHConnection = default_connection,
) -> list[dict]:
    """List files and directories in a remote path via SFTP.

    Returns a list of dicts: {name, type, size}.
    """
    ssh = connection.connect()
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


def stream_remote_file(
    remote_path: str,
    connection: SSHConnection = default_connection,
):
    """Generator that streams a remote file in chunks via SFTP.

    Yields bytes chunks (8KB each).
    """
    ssh = connection.connect()
    sftp = ssh.open_sftp()
    with sftp.open(remote_path, 'rb') as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            yield chunk
    sftp.close()
    ssh.close()


def read_remote_yaml(
    remote_path: str,
    connection: SSHConnection = default_connection,
) -> dict:
    """Read and parse a YAML file from the remote cluster.

    Returns the parsed dict, or an empty dict if the file does not exist.
    """
    ssh = connection.connect()
    sftp = ssh.open_sftp()
    try:
        with sftp.open(remote_path, 'r') as f:
            content = f.read().decode('utf-8')
        return yaml.safe_load(content) or {}
    except FileNotFoundError:
        LOGGER.info('Remote config not found at %s — returning empty dict', remote_path)
        return {}
    finally:
        sftp.close()
        ssh.close()


def write_remote_yaml(
    remote_path: str,
    data: dict,
    connection: SSHConnection = default_connection,
) -> None:
    """Write a dict as YAML to a remote path via SFTP.

    Creates parent directories on the remote if they do not exist.
    """
    ssh = connection.connect()

    # Ensure parent directory exists
    parent = remote_path.rsplit('/', 1)[0]
    if parent:
        ssh.exec_command(f'mkdir -p {parent}')

    sftp = ssh.open_sftp()
    content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
    with sftp.open(remote_path, 'w') as f:
        f.write(content)
    sftp.close()
    ssh.close()
    LOGGER.info('Wrote remote config to %s', remote_path)
