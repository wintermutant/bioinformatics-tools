"""
All code related to fetching containers
"""
import hashlib
import logging
import shutil
import subprocess
import sys
from pathlib import Path

import requests
from tqdm import tqdm

from bioinformatics_tools.workflow_tools.models import ApptainerKey

LOGGER = logging.getLogger(__name__)


class CacheSifError(Exception):
    """Raised when there's an error caching SIF files"""
    pass

CACHE_DIR = Path.home() / ".cache" / "bioinformatics-tools"


def verify_sha256(file_path: Path, expected_sha256: str) -> bool:
    """Verify file SHA256 checksum"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest() == expected_sha256


def download_container_with_progress(url: Path, dest: Path, expected_sha256: str | None = None):
    '''Download with progress bar and compare against a SHA256 if available'''
    registry_url = 'https://github.com/wintermutant/biotools-containers/releases/download'
    latest_version ='v0.0.2'
    full_url = f"{registry_url}/{latest_version}/{url}"
    LOGGER.info('Downloading data from the registry...%s', full_url)
    response = requests.get(full_url, stream=True, timeout=None)
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))

    with open(dest, 'wb') as f, tqdm(
        desc=dest.name, total=total_size,
        unit="B", unit_scale=True, unit_divisor=1024
    ) as progress_bar:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            progress_bar.update(len(chunk))
    
    if expected_sha256:
        print('Verifying SHA256...')
        if verify_sha256(dest, expected_sha256):
            print('Verification successful')
        else:
            dest.unlink()  # Delete the corrupted file
            raise ValueError('SHA256 verification failed')
    
    return dest


def find_apptainer_command(apptainer_path: str | None = None) -> str | None:
    '''Check for system-level apptainer command'''
    commands_to_check = [apptainer_path, 'apptainer.lima', 'apptainer']
    for cmd in commands_to_check:
        if cmd and shutil.which(cmd):
            LOGGER.debug('Running command: %s', cmd)
            return cmd
    return None


def init_cache():
    '''standard or custom cache location'''
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cached_file(filename: Path) -> Path | None:
    '''Search default cache directory for a file'''
    # TODO: Later, put the version in the cached name
    cached_file = CACHE_DIR / filename
    if cached_file.exists():
        print('Found file in cache. Using that')
        return cached_file
    return None


def init_apptainer():
    pass


def run_apptainer():
    pass


def pull_container_from_ghcr(container_name: Path, tag: str, output_filename: str | None = None) -> Path:
    '''Pull container from GitHub Container Registry using apptainer

    Args:
        container_name: Name of the container (e.g., 'prodigal')
        tag: Version tag (e.g., '2.6.3-v1.0')
        output_filename: Optional output filename (e.g., 'prodigal.sif').
                        If None, defaults to '{container_name}.sif'

    Returns:
        Path to the pulled .sif file in cache directory

    Example:
        pull_container_from_ghcr('prodigal', '2.6.3-v1.0')
        # Pulls docker://ghcr.io/wintermutant/prodigal:2.6.3-v1.0
        # Saves to ~/.cache/bioinformatics-tools/prodigal.sif
    '''
    # Determine output filename
    if output_filename is None:
        output_filename = f'{container_name}.sif'

    # Check if already cached
    if cached := get_cached_file(Path(output_filename)):
        LOGGER.info('Found %s in cache', output_filename)
        return cached

    dest = CACHE_DIR / output_filename
    str_container_name = str(container_name)
    docker_url = f'docker://ghcr.io/wintermutant/{str_container_name}:{tag}'

    LOGGER.info('Pulling %s from GitHub Container Registry...', docker_url)

    apptainer_cmd = find_apptainer_command()
    if not apptainer_cmd:
        raise RuntimeError('Apptainer not found. Cannot pull container.')

    # Ensure destination directory exists
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Build apptainer pull command
    cmd = [apptainer_cmd, 'pull', str(dest), docker_url]
    LOGGER.info('Running: %s', ' '.join(cmd))

    try:
        subprocess.run(cmd, check=True)
        LOGGER.info('Successfully pulled %s to %s', container_name, dest)
        return dest
    except subprocess.CalledProcessError as e:
        LOGGER.error('Failed to pull container: %s', e)
        raise


def get_sif_files(sif_paths: list[Path]):
    pass


def cache_sif_files(sif_paths: list[tuple[str, str]]):
    '''ensure all paths are in ~/.cache and accessible

    Raises:
        CacheSifError: If any SIF file cannot be cached
    '''
    for sif_name, sif_version in sif_paths:
        try:
            get_verified_sif_file(sif_name, sif_version)
        except Exception as e:
            LOGGER.critical('Issue getting a cached file: %s:%s', sif_name, sif_version)
            raise CacheSifError(f'Failed to cache {sif_name}:{sif_version}') from e


def get_verified_sif_file(sif_name: str, sif_version: str):
    '''search cache for sif file, if does not exist then download'''
    # sif_path = [(prodigal, 2.6.3), (program, version)]
    sif_path = Path(sif_name)
    LOGGER.info('SIF path: %s Version: %s', sif_path, sif_version)

    if cached := get_cached_file(sif_path):
        return cached
    dest = CACHE_DIR / sif_path
    LOGGER.info('Destination: %s', dest)
    # verified_sif_file = download_container_with_progress(url=sif_hack, dest=dest)
    # pull_container_from_ghcr('prodigal', '2.6.3-v1.0')
    #TODO: un-hardcode this
    verified_sif_file = pull_container_from_ghcr(sif_path, sif_version)
    LOGGER.info('Verified sif: %s', verified_sif_file)
    return verified_sif_file


def run_apptainer_container(app_obj: ApptainerKey, container_args: list[str]) -> int:
    """
    Run an Apptainer container with the specified arguments.
    Returns exit code from the container execution
    """
    sif_path = Path(app_obj.sif_path)
    LOGGER.debug('Sif path: %s', sif_path)

    if not sif_path:
        sys.exit('No bueno, brotha')

    verified_sif_file = get_verified_sif_file(sif_path)

    apptainer_command = find_apptainer_command(app_obj.executable)
    if apptainer_command is None:
        LOGGER.error('Apptainer not found. Please install Apptainer LiMa')
        return 127

    # Build the command
    cmd = [apptainer_command, 'exec', str(verified_sif_file)] + container_args
    cmd_string = ' '.join(cmd)
    LOGGER.info(cmd_string)

    # Execute the container
    try:
        result = subprocess.run(
            cmd,
            capture_output=False,  # Stream output directly to terminal
            text=True,
            check=True
        )
        return result.returncode
    except FileNotFoundError:
        LOGGER.error("Apptainer not found. Please install Apptainer/Singularity.")
        LOGGER.error("See: https://apptainer.org/docs/admin/main/installation.html")
        return 127
    except Exception as e:
        LOGGER.error("Failed to run container: %s", e)
        return 1
