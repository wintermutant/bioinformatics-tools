# BSP Deployment Guide

Clear, step-by-step guides for developing and deploying the Bioinformatics Suite Platform (BSP).

## 📚 Documentation Structure

Follow these guides in order:

### 1. [Local Development](docs/LOCAL_DEV.md)
**Daily development workflow - no Docker needed**
- Running `dane-api` for backend
- Running `npm run dev` for frontend
- Setting up environment variables
- Database location

### 2. [Docker Testing](docs/DOCKER_TESTING.md)
**Test your containers locally before deploying**
- Build Docker images
- Test backend container
- Test frontend container
- Test both together with docker-compose

### 3. [Kubernetes Local Testing](docs/K8S_LOCAL.md) *(Optional)*
**Test K8s setup on your machine with minikube**
- Set up minikube
- Deploy to local cluster
- Test ingress routing
- Verify everything works before production

### 4. [Production Deployment](docs/K8S_PRODUCTION.md)
**Deploy to Anvil Composable**
- Build and push to Docker Hub
- Set up secrets and storage
- Deploy to production
- Update deployments
- Rollback if needed

## Quick Reference

```bash
# Local dev
dane-api                    # Backend on :8000
npm run dev                 # Frontend on :5173

# Docker testing
docker build -t wintermutant/bsp-api:test .
docker run -p 8000:8000 --env-file .env.test wintermutant/bsp-api:test

# Production deployment
./deploy.sh wintermutant   # Build and push images
kubectl apply -f k8s/       # Deploy to Anvil
```

## Current Setup

- **Backend**: FastAPI on port 8000 (`dane-api` command)
- **Frontend**: SvelteKit on port 3000
- **Database**: SQLite at `~/.local/share/bsp/bsp.db` (local) or `/data/bsp.db` (K8s)
- **Production**: https://dane.anvilcloud.rcac.purdue.edu

## Need Help?

- Local development issues? → [docs/LOCAL_DEV.md](docs/LOCAL_DEV.md)
- Docker problems? → [docs/DOCKER_TESTING.md](docs/DOCKER_TESTING.md)
- K8s deployment issues? → [docs/K8S_PRODUCTION.md](docs/K8S_PRODUCTION.md)
