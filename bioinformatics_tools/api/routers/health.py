"""
SSH File Upload endpoints - Upload files to remote server via SSH
"""
import logging

import paramiko
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ssh", tags=["ssh"])


class SSHUploadResponse(BaseModel):
    status: str
    message: str
    remote_path: str
    file_size: int


@router.post("/upload", response_model=SSHUploadResponse)
async def upload_file_to_remote(
    file: UploadFile = File(...),
    remote_path: str = "~/uploads/",
):
    """
    Upload a file via SSH to remote server
    """
    try:
        # Read uploaded file content
        file_content = await file.read()
        file_size = len(file_content)

        LOGGER.info(f"Received file: {file.filename} ({file_size} bytes)")

        # SSH connection details - TODO: Move to config/env vars
        ssh_host = 'negishi.rcac.purdue.edu'
        ssh_username = 'ddeemer'

        # Connect via SSH
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        LOGGER.info(f"Connecting to {ssh_host}...")
        ssh.connect(ssh_host, username=ssh_username)

        # Create remote directory if it doesn't exist
        stdin, stdout, stderr = ssh.exec_command(f'mkdir -p {remote_path}')
        stdout.channel.recv_exit_status()  # Wait for command to complete

        # Upload file using SFTP
        sftp = ssh.open_sftp()
        remote_file_path = f"{remote_path}/{file.filename}"

        LOGGER.info(f"Uploading to {remote_file_path}...")

        # Write file to remote
        with sftp.open(remote_file_path, 'wb') as remote_file:
            remote_file.write(file_content)

        # Verify file was uploaded
        remote_stat = sftp.stat(remote_file_path)

        sftp.close()
        ssh.close()

        LOGGER.info(f"Upload successful: {remote_file_path}")

        return SSHUploadResponse(
            status="success",
            message=f"File uploaded successfully",
            remote_path=remote_file_path,
            file_size=remote_stat.st_size
        )

    except paramiko.SSHException as e:
        LOGGER.exception("SSH connection error")
        raise HTTPException(
            status_code=500,
            detail=f"SSH connection failed: {str(e)}"
        ) from e
    except Exception as e:
        LOGGER.exception("Error uploading file")
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        ) from e
    finally:
        await file.seek(0)  # Reset file pointer


@router.get("/config")
async def config():
    '''grab the config from ~/.config/bioinformatics-tools/config.yaml'''
    return {'value1': 'param', 'value2': 'param2'}


@router.get("/status")
async def status():
    '''get status for username and public key'''
    return {'status': 'success', 'message': 'connected successfully', 'connected': False}


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "success", "message": "SSH upload endpoint is healthy"}
