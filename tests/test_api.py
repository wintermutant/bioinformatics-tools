"""
Pytest-based API tests using FastAPI TestClient.

No live server required — TestClient handles requests in-process.

Tiers:
  1. Health/root endpoints (no mocks)
  2. JobStore unit tests (in-memory, no mocks)
  3. SSH endpoints (mocked external calls)
  4. Path traversal security tests
"""
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bioinformatics_tools.api.main import app
from bioinformatics_tools.api.services.job_store import job_store


@pytest.fixture()
def client():
    """Fresh TestClient; clears job_store between tests."""
    job_store._jobs.clear()
    with TestClient(app) as c:
        yield c
    job_store._jobs.clear()


# ---------------------------------------------------------------------------
# Tier 1 — Health / root endpoints (no mocks needed)
# ---------------------------------------------------------------------------

class TestHealthEndpoints:
    """Smoke tests for every health and info endpoint."""

    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert "endpoints" in body

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_fasta_health(self, client):
        resp = client.get("/v1/fasta/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_ssh_health(self, client):
        resp = client.get("/v1/ssh/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_files_health(self, client):
        resp = client.get("/v1/files/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_files_config(self, client):
        resp = client.get("/v1/files/config")
        assert resp.status_code == 200

    def test_files_status(self, client):
        resp = client.get("/v1/files/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body


# ---------------------------------------------------------------------------
# Tier 2 — JobStore unit tests (purely in-memory)
# ---------------------------------------------------------------------------

class TestJobStore:
    """Direct tests of the JobStore singleton (no HTTP involved)."""

    def setup_method(self):
        job_store._jobs.clear()

    def teardown_method(self):
        job_store._jobs.clear()

    def test_create(self):
        job = job_store.create("j1", "/genomes/ecoli.fasta")
        assert job["job_id"] == "j1"
        assert job["status"] == "pending"
        assert job["genome_path"] == "/genomes/ecoli.fasta"
        assert job["work_dir"] is None
        assert "start_time" in job

    def test_get_missing(self):
        assert job_store.get("nonexistent") is None

    def test_update(self):
        job_store.create("j2", "/g")
        job_store.update("j2", status="running", phase="Aligning")
        job = job_store.get("j2")
        assert job["status"] == "running"
        assert job["phase"] == "Aligning"

    def test_append_log(self):
        job_store.create("j3", "/g")
        job_store.append_log("j3", "line one")
        job_store.append_log("j3", "line two")
        logs = job_store.get("j3")["logs"]
        assert "line one" in logs
        assert "line two" in logs

    def test_add_slurm_job(self):
        job_store.create("j4", "/g")
        job_store.add_slurm_job("j4", slurm_id="12345", rule="fastp")
        slurm_jobs = job_store.get_slurm_jobs("j4")
        assert len(slurm_jobs) == 1
        assert slurm_jobs[0]["job_id"] == "12345"
        assert slurm_jobs[0]["rule"] == "fastp"
        assert slurm_jobs[0]["status"] == "SUBMITTED"


class TestJobStatusEndpoint:
    """HTTP-level tests for job_status that rely on job_store state."""

    def test_job_status_endpoint(self, client):
        job_store.create("test-job-1", "/genomes/test.fasta")
        resp = client.get("/v1/ssh/job_status/test-job-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == "test-job-1"
        assert body["status"] == "pending"

    def test_job_status_404(self, client):
        resp = client.get("/v1/ssh/job_status/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tier 3 — SSH endpoints with mocks
# ---------------------------------------------------------------------------

class TestSSHEndpointsMocked:
    """Endpoints that call external SSH/SLURM services — all mocked."""

    @patch("bioinformatics_tools.api.routers.ssh.job_runner")
    def test_run_margie(self, mock_runner, client):
        resp = client.post(
            "/v1/ssh/run_margie",
            json={"genome_path": "/depot/genomes/ecoli.fasta"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "job_id" in body

        # Verify job_runner.submit_job was called with the created job_id
        mock_runner.submit_job.assert_called_once()
        call_args = mock_runner.submit_job.call_args
        assert call_args[0][0] == body["job_id"]

    @patch("bioinformatics_tools.api.routers.ssh.ssh_slurm")
    def test_run_slurm(self, mock_slurm, client):
        mock_slurm.submit_slurm_job.return_value = "99999"
        resp = client.post(
            "/v1/ssh/run_slurm",
            json={"script": "#!/bin/bash\necho hello"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["job_id"] == "99999"
        mock_slurm.submit_slurm_job.assert_called_once_with(
            script_content="#!/bin/bash\necho hello"
        )

    @patch("bioinformatics_tools.api.routers.ssh.ssh_slurm")
    def test_all_genomes(self, mock_slurm, client):
        mock_slurm.get_genomes.return_value = ["genome1.fasta", "genome2.fasta"]
        resp = client.get("/v1/ssh/all_genomes", params={"path": "/depot/genomes"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["Genomes"]) == 2
        mock_slurm.get_genomes.assert_called_once_with("/depot/genomes")


# ---------------------------------------------------------------------------
# Tier 4 — Path traversal security tests
# ---------------------------------------------------------------------------

class TestPathTraversalSecurity:
    """Ensure path-based endpoints reject directory traversal attempts."""

    def _create_job_with_workdir(self):
        jid = str(uuid.uuid4())
        job_store.create(jid, "/genomes/test.fasta")
        job_store.update(jid, work_dir="/remote/work/dir")
        return jid

    @patch("bioinformatics_tools.api.routers.ssh.ssh_sftp")
    def test_job_files_path_traversal(self, mock_sftp, client):
        jid = self._create_job_with_workdir()
        resp = client.get(
            f"/v1/ssh/job_files/{jid}",
            params={"subdir": "../../etc"},
        )
        assert resp.status_code == 400
        assert "Invalid" in resp.json()["detail"]
        mock_sftp.list_remote_dir.assert_not_called()

    @patch("bioinformatics_tools.api.routers.ssh.ssh_sftp")
    def test_download_file_path_traversal(self, mock_sftp, client):
        jid = self._create_job_with_workdir()
        resp = client.get(
            f"/v1/ssh/download_file/{jid}",
            params={"path": "../../etc/passwd"},
        )
        assert resp.status_code == 400
        assert "Invalid" in resp.json()["detail"]
        mock_sftp.stream_remote_file.assert_not_called()
