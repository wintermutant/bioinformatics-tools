# Docker Container Testing

Test your Docker containers locally before deploying to production.

## Prerequisites

- Docker Desktop installed and running
- Your code working in local dev (see [LOCAL_DEV.md](LOCAL_DEV.md))

## Step 1: Build Backend Image

```bash
cd /Users/ddeemer/git-repos/bioinformatics-tools

docker build -t wintermutant/bsp-api:test .
```

**Expected output:**
```
Successfully built abc123def456
Successfully tagged wintermutant/bsp-api:test
```

## Step 2: Test Backend Container

```bash
docker run -p 8000:8000 --name bsp-api-test \
  --env-file .env.test \
  wintermutant/bsp-api:test
```

**What this does:**
- Starts backend container with test credentials
- Maps port 8000 to localhost
- Uses `.env.test` for required environment variables

**Expected output:**
```
INFO:     Started server process [1]
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Test it:** (in another terminal)
```bash
curl http://localhost:8000/health
# Should return: {"status":"success","message":"API is healthy"}

open http://localhost:8000/docs
```

**Stop the container:**
```bash
# Press Ctrl+C, then:
docker rm bsp-api-test
```

## Step 3: Build Frontend Image

```bash
cd /Users/ddeemer/git-repos/margie-fe/margie-fe

# Build with localhost API URL for local Docker testing
docker build \
  --build-arg VITE_PUBLIC_API_URL="http://localhost:8000" \
  -t wintermutant/bsp-frontend:test .
```

**Expected output:**
```
npm run build
✓ built in 15s
Successfully tagged wintermutant/bsp-frontend:test
```

## Step 4: Test Both Together

### Option A: Docker Compose (Recommended)

Update `docker-compose.yml`:
```yaml
version: '3.8'

services:
  api:
    image: wintermutant/bsp-api:test
    container_name: bsp-api-test
    ports:
      - "8000:8000"
    env_file:
      - .env.test
    networks:
      - bsp-network

  frontend:
    image: wintermutant/bsp-frontend:test
    container_name: bsp-frontend-test
    ports:
      - "3001:3000"  # Use 3001 to avoid conflicts
    depends_on:
      - api
    networks:
      - bsp-network

networks:
  bsp-network:
    driver: bridge
```

**Run both:**
```bash
cd /Users/ddeemer/git-repos/bioinformatics-tools
docker-compose up
```

(No need to `source .env.test` - docker-compose loads it automatically via `env_file`)

**Test in browser:**
```bash
open http://localhost:3001
```

**Stop:**
```bash
# Press Ctrl+C, then:
docker-compose down
```

### Option B: Individual Containers

**Terminal 1 - Backend:**
```bash
docker run -p 8000:8000 --name bsp-api-test \
  --env-file .env.test \
  wintermutant/bsp-api:test
```

**Terminal 2 - Frontend:**
```bash
docker run -p 3001:3000 --name bsp-frontend-test \
  wintermutant/bsp-frontend:test
```

**Terminal 3 - Test:**
```bash
open http://localhost:3001
```

**Cleanup:**
```bash
docker rm -f bsp-api-test bsp-frontend-test
```

## Step 5: Verify Everything Works

Open http://localhost:3001 and test:

- ✅ Login page loads
- ✅ Can register a new user
- ✅ Can login
- ✅ API calls work (check Network tab in DevTools - F12)
- ✅ No errors in console

## Common Issues

### CORS Errors

**Symptom:** Browser console shows CORS policy errors

**Check:** `bioinformatics_tools/api/main.py` has:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or ["http://localhost:3001"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Frontend Can't Reach Backend

**Symptom:** Network errors, "Failed to fetch"

**Fix:** Rebuild frontend with correct API URL:
```bash
docker build --build-arg VITE_PUBLIC_API_URL="http://localhost:8000" \
  -t wintermutant/bsp-frontend:test .
```

### Container Won't Start

**View logs:**
```bash
docker logs bsp-api-test
docker logs bsp-frontend-test
```

**Shell into container:**
```bash
docker exec -it bsp-api-test /bin/bash
```

## Clean Up

```bash
# Remove test containers
docker rm -f bsp-api-test bsp-frontend-test

# Remove test images
docker rmi wintermutant/bsp-api:test wintermutant/bsp-frontend:test

# Remove all stopped containers and unused images
docker system prune -a
```

## Next Steps

If Docker testing passes:
- **Optional:** [Test on local Kubernetes](K8S_LOCAL.md) with minikube
- **Deploy:** [Push to production](K8S_PRODUCTION.md) on Anvil
