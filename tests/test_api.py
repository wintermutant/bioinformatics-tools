"""
Pytest-based API tests using FastAPI TestClient.

No live server required — TestClient handles requests in-process.

Tiers:
  1. Health/root endpoints (no mocks)
  2. JobStore unit tests (in-memory, no mocks)
  3. SSH endpoints (mocked external calls)
  4. Path traversal security tests
  5. Auth endpoints (register / login / me)
"""
import io
import uuid
from unittest.mock import MagicMock, patch

import paramiko
import pytest
from fastapi.testclient import TestClient

from bioinformatics_tools.api.auth import get_current_user
from bioinformatics_tools.api.main import app
from bioinformatics_tools.api.services.job_store import job_store


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

#: Fake user dict returned by the get_current_user dependency override.
#: user_id=1 must match what we pass to job_store.create(user_id=...) in
#: tests that exercise ownership checks.
FAKE_USER = {
    "user_id": 1,
    "username": "testuser",
    "cluster_host": "test.cluster.edu",
    "cluster_username": "testuser",
    "home_dir": "/home/testuser",
    "private_key_encrypted": "fake_encrypted_key",
}


@pytest.fixture(scope="session")
def test_rsa_key():
    """Generate a 1024-bit RSA key once per session for auth tests."""
    key = paramiko.RSAKey.generate(1024)
    buf = io.StringIO()
    key.write_private_key(buf)
    return buf.getvalue()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """
    Fresh TestClient with an isolated SQLite DB and cleared job store.

    monkeypatch sets BSP_DB_PATH to a per-test temp dir so that the startup
    event creates a clean users table each time.
    """
    monkeypatch.setenv("BSP_DB_PATH", str(tmp_path / "test.db"))
    job_store._jobs.clear()
    with TestClient(app) as c:
        yield c
    job_store._jobs.clear()


@pytest.fixture()
def authed_client(client):
    """
    client with get_current_user dependency overridden to return FAKE_USER.

    Use this for any test that hits an authenticated endpoint but isn't
    specifically testing the auth flow itself.
    """
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    yield client
    app.dependency_overrides.pop(get_current_user, None)


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

    def test_create_with_user_id(self):
        job = job_store.create("j1b", "/genomes/ecoli.fasta", user_id=42)
        assert job["user_id"] == 42

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
    """HTTP-level tests for job_status (requires auth, enforces ownership)."""

    def test_job_status_endpoint(self, authed_client):
        # user_id must match FAKE_USER["user_id"] (1) to pass ownership check
        job_store.create("test-job-1", "/genomes/test.fasta", user_id=1)
        resp = authed_client.get("/v1/ssh/job_status/test-job-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == "test-job-1"
        assert body["status"] == "pending"

    def test_job_status_404(self, authed_client):
        resp = authed_client.get("/v1/ssh/job_status/nonexistent")
        assert resp.status_code == 404

    def test_job_status_ownership_denied(self, authed_client):
        # Job belongs to a different user — should get 403
        job_store.create("other-users-job", "/genomes/test.fasta", user_id=999)
        resp = authed_client.get("/v1/ssh/job_status/other-users-job")
        assert resp.status_code == 403

    def test_job_status_requires_auth(self, client):
        resp = client.get("/v1/ssh/job_status/any-job")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tier 3 — SSH endpoints with mocks
# ---------------------------------------------------------------------------

class TestSSHEndpointsMocked:
    """Endpoints that call external SSH/SLURM services — all mocked."""

    @patch("bioinformatics_tools.api.routers.ssh._build_connection")
    @patch("bioinformatics_tools.api.routers.ssh.job_runner")
    def test_run_margie(self, mock_runner, mock_build_conn, authed_client):
        resp = authed_client.post(
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

    @patch("bioinformatics_tools.api.routers.ssh._build_connection")
    @patch("bioinformatics_tools.api.routers.ssh.ssh_slurm")
    def test_run_slurm(self, mock_slurm, mock_build_conn, authed_client):
        mock_slurm.submit_slurm_job.return_value = "99999"
        resp = authed_client.post(
            "/v1/ssh/run_slurm",
            json={"script": "#!/bin/bash\necho hello"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["job_id"] == "99999"
        mock_slurm.submit_slurm_job.assert_called_once()

    @patch("bioinformatics_tools.api.routers.ssh._build_connection")
    @patch("bioinformatics_tools.api.routers.ssh.ssh_slurm")
    def test_all_genomes(self, mock_slurm, mock_build_conn, authed_client):
        mock_slurm.get_genomes.return_value = ["genome1.fasta", "genome2.fasta"]
        resp = authed_client.get("/v1/ssh/all_genomes", params={"path": "/depot/genomes"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["Genomes"]) == 2
        mock_slurm.get_genomes.assert_called_once()

    def test_all_genomes_requires_auth(self, client):
        resp = client.get("/v1/ssh/all_genomes", params={"path": "/depot/genomes"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tier 4 — Path traversal security tests
# ---------------------------------------------------------------------------

class TestPathTraversalSecurity:
    """Ensure path-based endpoints reject directory traversal attempts."""

    def _create_job_with_workdir(self):
        jid = str(uuid.uuid4())
        # user_id=1 matches FAKE_USER so ownership check passes
        job_store.create(jid, "/genomes/test.fasta", user_id=1)
        job_store.update(jid, work_dir="/remote/work/dir")
        return jid

    @patch("bioinformatics_tools.api.routers.ssh.ssh_sftp")
    def test_job_files_path_traversal(self, mock_sftp, authed_client):
        jid = self._create_job_with_workdir()
        resp = authed_client.get(
            f"/v1/ssh/job_files/{jid}",
            params={"subdir": "../../etc"},
        )
        assert resp.status_code == 400
        assert "Invalid" in resp.json()["detail"]
        mock_sftp.list_remote_dir.assert_not_called()

    @patch("bioinformatics_tools.api.routers.ssh.ssh_sftp")
    def test_download_file_path_traversal(self, mock_sftp, authed_client):
        jid = self._create_job_with_workdir()
        resp = authed_client.get(
            f"/v1/ssh/download_file/{jid}",
            params={"path": "../../etc/passwd"},
        )
        assert resp.status_code == 400
        assert "Invalid" in resp.json()["detail"]
        mock_sftp.stream_remote_file.assert_not_called()


# ---------------------------------------------------------------------------
# Tier 5 — Auth endpoints (register / login / me)
# ---------------------------------------------------------------------------

class TestAuth:
    """
    End-to-end tests for the auth flow.

    Registration requires a valid SSH private key and a reachable cluster.
    We mock make_user_connection at the router level so no real SSH happens.
    """

    #: Base registration payload — private_key added per-test from the
    #: session-scoped test_rsa_key fixture.
    BASE_REG = {
        "username": "authtest",
        "password": "S3cur3P@ss!",
        "cluster_host": "test.cluster.edu",
        "cluster_username": "authtest",
    }

    def _mock_ssh_conn(self, home_dir: str = "/home/authtest"):
        """Return a MagicMock SSHConnection whose connect() returns a stub SSH client."""
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = home_dir.encode() + b"\n"
        mock_ssh = MagicMock()
        mock_ssh.exec_command.return_value = (None, mock_stdout, None)
        mock_conn = MagicMock()
        mock_conn.connect.return_value = mock_ssh
        return mock_conn

    # --- register ---

    @patch("bioinformatics_tools.api.routers.auth.make_user_connection")
    def test_register_success(self, mock_make_conn, client, test_rsa_key):
        mock_make_conn.return_value = self._mock_ssh_conn()
        resp = client.post(
            "/v1/auth/register",
            json={**self.BASE_REG, "private_key": test_rsa_key},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["username"] == "authtest"
        assert "user_id" in body

    @patch("bioinformatics_tools.api.routers.auth.make_user_connection")
    def test_register_duplicate_username(self, mock_make_conn, client, test_rsa_key):
        mock_make_conn.return_value = self._mock_ssh_conn()
        data = {**self.BASE_REG, "private_key": test_rsa_key}
        client.post("/v1/auth/register", json=data)  # first succeeds
        resp = client.post("/v1/auth/register", json=data)  # duplicate fails
        assert resp.status_code == 400
        assert "taken" in resp.json()["detail"].lower()

    def test_register_bad_private_key(self, client):
        resp = client.post(
            "/v1/auth/register",
            json={**self.BASE_REG, "private_key": "this-is-not-a-valid-ssh-key"},
        )
        assert resp.status_code == 400
        assert "parse" in resp.json()["detail"].lower()

    @patch("bioinformatics_tools.api.routers.auth.make_user_connection")
    def test_register_ssh_connection_fails(self, mock_make_conn, client, test_rsa_key):
        mock_make_conn.return_value.connect.side_effect = Exception("Connection refused")
        resp = client.post(
            "/v1/auth/register",
            json={**self.BASE_REG, "private_key": test_rsa_key},
        )
        assert resp.status_code == 400
        # Error message mentions the cluster host
        assert "test.cluster.edu" in resp.json()["detail"]

    # --- login ---

    @patch("bioinformatics_tools.api.routers.auth.make_user_connection")
    def test_login_success(self, mock_make_conn, client, test_rsa_key):
        mock_make_conn.return_value = self._mock_ssh_conn()
        client.post("/v1/auth/register", json={**self.BASE_REG, "private_key": test_rsa_key})

        resp = client.post(
            "/v1/auth/login",
            json={"username": "authtest", "password": "S3cur3P@ss!"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        resp = client.post(
            "/v1/auth/login",
            json={"username": "nonexistent", "password": "wrong"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    @patch("bioinformatics_tools.api.routers.auth.make_user_connection")
    def test_login_wrong_password_for_real_user(self, mock_make_conn, client, test_rsa_key):
        mock_make_conn.return_value = self._mock_ssh_conn()
        client.post("/v1/auth/register", json={**self.BASE_REG, "private_key": test_rsa_key})

        resp = client.post(
            "/v1/auth/login",
            json={"username": "authtest", "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    # --- /me ---

    @patch("bioinformatics_tools.api.routers.auth.make_user_connection")
    def test_me_with_valid_token(self, mock_make_conn, client, test_rsa_key):
        mock_make_conn.return_value = self._mock_ssh_conn()
        client.post("/v1/auth/register", json={**self.BASE_REG, "private_key": test_rsa_key})
        login_resp = client.post(
            "/v1/auth/login",
            json={"username": "authtest", "password": "S3cur3P@ss!"},
        )
        token = login_resp.json()["access_token"]

        resp = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "authtest"
        assert body["cluster_host"] == "test.cluster.edu"
        assert body["home_dir"] == "/home/authtest"
        # Sensitive fields must never be exposed
        assert "password_hash" not in body
        assert "private_key_encrypted" not in body
        assert "private_key" not in body

    def test_me_without_token(self, client):
        resp = client.get("/v1/auth/me")
        assert resp.status_code == 401

    def test_me_with_invalid_token(self, client):
        resp = client.get("/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
        assert resp.status_code == 401

    # --- protected endpoints require auth ---

    def test_protected_endpoint_rejects_no_token(self, client):
        resp = client.get("/v1/ssh/all_genomes", params={"path": "/depot/genomes"})
        assert resp.status_code == 401

    @patch("bioinformatics_tools.api.routers.auth.make_user_connection")
    @patch("bioinformatics_tools.api.routers.ssh._build_connection")
    @patch("bioinformatics_tools.api.routers.ssh.ssh_slurm")
    def test_protected_endpoint_with_real_token(
        self, mock_slurm, mock_build_conn, mock_make_conn, client, test_rsa_key
    ):
        """Full round-trip: register → login → hit a protected endpoint."""
        mock_make_conn.return_value = self._mock_ssh_conn()
        mock_slurm.get_genomes.return_value = ["genome1.fasta"]

        client.post("/v1/auth/register", json={**self.BASE_REG, "private_key": test_rsa_key})
        login_resp = client.post(
            "/v1/auth/login",
            json={"username": "authtest", "password": "S3cur3P@ss!"},
        )
        token = login_resp.json()["access_token"]

        resp = client.get(
            "/v1/ssh/all_genomes",
            params={"path": "/depot/genomes"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["Genomes"] == ["genome1.fasta"]
