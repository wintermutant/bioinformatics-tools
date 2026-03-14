# Local Development Guide

This is your daily development workflow - **no Docker required**.

## Prerequisites

- Python 3.11+
- Node.js 20+
- npm

## Backend Setup (bioinformatics-tools)

### 1. Install Dependencies

```bash
cd /Users/ddeemer/git-repos/bioinformatics-tools

# Using uv (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

### 2. Set Up Environment Variables

Create `.env` in the project root:

```bash
# Copy the example
cp .env.example .env

# Edit with your values
vim .env
```

Your `.env` should contain:
```bash
BSP_SECRET_KEY=your-dev-secret-key-here
BSP_ENCRYPTION_KEY=your-dev-encryption-key-here
BSP_DB_PATH=~/.local/share/bsp/bsp.db  # Optional, this is the default
```

**Generate keys:**
```bash
# Secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Encryption key (if you have cryptography installed)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Run the Backend

```bash
dane-api

# With custom port
dane-api --port 8001

# With reload (auto-restart on code changes)
dane-api --reload
```

Backend will be available at:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Frontend Setup (margie-fe)

### 1. Install Dependencies

```bash
cd /Users/ddeemer/git-repos/margie-fe/margie-fe

npm install
```

### 2. Run the Frontend

```bash
npm run dev
```

Frontend will be available at:
- App: http://localhost:5173 (or http://localhost:3000)

The frontend is configured to automatically use `http://localhost:8000` for API calls when running on localhost.

## Typical Development Workflow

### Terminal 1 - Backend
```bash
cd ~/git-repos/bioinformatics-tools
dane-api --reload
```

### Terminal 2 - Frontend
```bash
cd ~/git-repos/margie-fe/margie-fe
npm run dev
```

Now you can:
- Edit backend code → auto-reloads
- Edit frontend code → auto-reloads with HMR
- Test in browser at http://localhost:5173

## Database Location

Local development uses SQLite at:
```
~/.local/share/bsp/bsp.db
```

**View/query the database:**
```bash
sqlite3 ~/.local/share/bsp/bsp.db

# Inside sqlite3:
.tables              # List tables
SELECT * FROM users; # View users
.quit                # Exit
```

**Reset the database:**
```bash
rm ~/.local/share/bsp/bsp.db
# Restart dane-api to recreate
```

## Testing Changes

### Backend Tests
```bash
cd ~/git-repos/bioinformatics-tools
pytest
```

### Frontend Type Checking
```bash
cd ~/git-repos/margie-fe/margie-fe
npm run check
```

## Common Issues

### Backend won't start - missing env vars

**Error:** `RuntimeError: BSP_SECRET_KEY environment variable is not set`

**Fix:** Create `.env` file with required keys (see step 2 above)

### Frontend can't reach backend

**Error:** Network errors in browser console

**Fix:**
1. Check backend is running: `curl http://localhost:8000/health`
2. Check CORS is enabled in `bioinformatics_tools/api/main.py`

### Database locked errors

**Error:** `database is locked`

**Fix:**
1. Close any other processes using the database
2. Delete lock file: `rm ~/.local/share/bsp/bsp.db-*`

## Next Steps

Once your changes are working locally:
- [Test with Docker](DOCKER_TESTING.md) before deploying
- [Deploy to production](K8S_PRODUCTION.md)
