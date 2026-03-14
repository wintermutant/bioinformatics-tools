# Production Deployment (Anvil Composable)

Deploy BSP to production at https://bsp.anvilcloud.rcac.purdue.edu

## Prerequisites

- Docker containers tested (see [DOCKER_TESTING.md](DOCKER_TESTING.md))
- `kubectl` configured for Anvil cluster
- Docker Hub account (wintermutant)
- Access to Anvil Composable

## Part 1: Initial Deployment

### Step 1: Build and Push Production Images

**IMPORTANT for Apple Silicon (M1/M2/M3) users:**

Anvil Composable runs on **linux/amd64** architecture. If you're building on Apple Silicon, you need to build for the correct platform.

**Set up cross-platform builder (one-time setup):**

```bash
# Remove old builder and cache (if it exists)
docker buildx rm multiarch 2>/dev/null || true
docker buildx prune -af

# Create fresh builder
docker buildx create --name multiarch --use
docker buildx inspect --bootstrap
```

**Build and push images for linux/amd64:**

```bash
# Backend
cd /Users/ddeemer/git-repos/bioinformatics-tools
docker buildx build --platform linux/amd64 \
  -f Dockerfile.simple \
  -t wintermutant/bsp-api:latest \
  --push .

# Frontend (with empty API_URL for ingress routing)
cd /Users/ddeemer/git-repos/margie-fe/margie-fe
docker buildx build --platform linux/amd64 \
  --build-arg VITE_PUBLIC_API_URL="" \
  -t wintermutant/bsp-frontend:latest \
  --push .
```

**Note:** If you get "exec format error", your buildx cache has ARM64 images. Run the setup commands above to clear it.

**For Intel Macs or Linux AMD64:**

```bash
# Backend
cd /Users/ddeemer/git-repos/bioinformatics-tools
docker build -t wintermutant/bsp-api:latest .
docker push wintermutant/bsp-api:latest

# Frontend
cd /Users/ddeemer/git-repos/margie-fe/margie-fe
docker build --build-arg VITE_PUBLIC_API_URL="" \
  -t wintermutant/bsp-frontend:latest .
docker push wintermutant/bsp-frontend:latest
```

### Step 1.5: Configure Kubectl

Download the kubeconfig from Anvil and set it:

```bash
# Download kubeconfig from Anvil Composable UI
# Save to ~/.kube/

# Set KUBECONFIG environment variable
export KUBECONFIG=~/.kube/anvil-09mar26.yaml

# Test connection
kubectl get nodes
```

### Step 1.6: Create Namespace in Rancher

You need a namespace to deploy your resources. Create one via Rancher UI:

1. Go to https://composable.anvil.rcac.purdue.edu
2. Click on your cluster
3. Navigate to **Projects/Namespaces** in the left menu
4. Click **Create Namespace**
5. Name it (e.g., `danetutorial` or `bsp-prod`)
6. Click **Create**

**Set it as your default namespace:**

```bash
# Replace 'danetutorial' with your namespace name
kubectl config set-context --current --namespace=danetutorial

# Verify
kubectl config view --minify | grep namespace
```

All subsequent `kubectl` commands will use this namespace by default.

### Step 2: Check Storage Classes

Find out what persistent storage is available on Anvil:

```bash
kubectl get storageclass

# It should output:
# NAME                    PROVISIONER                     RECLAIMPOLICY   VOLUMEBINDINGMODE   ALLOWVOLUMEEXPANSION   AGE
# anvil-block (default)   rook-ceph.rbd.csi.ceph.com      Delete          Immediate           true                   4y140d
# anvil-bucket            rook-ceph.ceph.rook.io/bucket   Delete          Immediate           false                  4y140d
# anvil-filesystem        rook-ceph.cephfs.csi.ceph.com   Delete          Immediate           true                   4y140d
# cvmfs                   cvmfs.csi.cern.ch               Delete          Immediate           false                  2y354d 
```

Choose anvil-block

Update `k8s/backend/pvc.yaml` with the correct `storageClassName`.

Common options:
- `standard` or `default`
- `nfs`
- `rook-ceph-block`

### Step 3: Create Secrets

**Generate production keys locally (never commit these!):**

```bash
# Secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Copy this output

# Encryption key
docker run --rm wintermutant/bsp-api:latest python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Copy this output
```

**Create the secret in Kubernetes:**

```bash
kubectl create secret generic bsp-secrets \
  --from-literal=secret-key='PASTE_YOUR_SECRET_KEY_HERE' \
  --from-literal=encryption-key='PASTE_YOUR_ENCRYPTION_KEY_HERE'

# Verify (shows keys but not values)
kubectl describe secret bsp-secrets
```

### Step 4: Deploy Database Storage

```bash
cd /Users/ddeemer/git-repos/bioinformatics-tools

# Create persistent volume claim
kubectl apply -f k8s/backend/pvc.yaml

# Check it's bound
kubectl get pvc
# Should show STATUS: Bound
```

### Step 5: Deploy Backend

```bash
# Deploy backend
kubectl apply -f k8s/backend/deployment.yaml
kubectl apply -f k8s/backend/service.yaml

# Check status
kubectl get pods
kubectl logs -f deployment/bsp-api

# Should see: INFO: Uvicorn running on http://0.0.0.0:8000
```

### Step 6: Migrate Existing Database (Optional)

If you have an existing database with users at `~/.local/share/bsp/bsp.db`:

```bash
# Get the pod name
kubectl get pods
# Example: bsp-api-abc123-xyz

# Copy database to pod
kubectl cp ~/.local/share/bsp/bsp.db bsp-api-abc123-xyz:/data/bsp.db

# Restart to pick it up
kubectl rollout restart deployment/bsp-api
```

**Or start fresh** - skip this step and create new users via the API.

### Step 7: Deploy Frontend

```bash
kubectl apply -f k8s/frontend/deployment.yaml
kubectl apply -f k8s/frontend/service.yaml

# Check status
kubectl get pods
kubectl logs -f deployment/bsp-frontend
```

### Step 8: Deploy Ingress

```bash
kubectl apply -f k8s/ingress-prod.yaml

# Check ingress
kubectl get ingress
kubectl describe ingress bsp-ingress
```

### Step 9: Verify Deployment

```bash
# Check all pods are running
kubectl get pods
# Should see: bsp-api and bsp-frontend pods Running

# Check services
kubectl get services

# Check ingress
kubectl get ingress
```

**Test the application:**
```bash
# Health check
curl https://bsp.anvilcloud.rcac.purdue.edu/v1/health

# Open in browser
open https://bsp.anvilcloud.rcac.purdue.edu
```

## Part 2: Updating the Application

When you make code changes and want to deploy them:

### Quick Update (Same Version)

```bash
# 1. Build and push new images
cd /Users/ddeemer/git-repos/bioinformatics-tools
./deploy.sh wintermutant

# 2. Restart deployments to pull new images
kubectl rollout restart deployment/bsp-api
kubectl rollout restart deployment/bsp-frontend

# 3. Watch the rollout
kubectl rollout status deployment/bsp-api
kubectl rollout status deployment/bsp-frontend
```

### Versioned Update (Recommended)

Tag your releases for easier rollbacks:

```bash
# 1. Build with version tag
cd /Users/ddeemer/git-repos/bioinformatics-tools
docker build -t wintermutant/bsp-api:v1.2.0 .
docker push wintermutant/bsp-api:v1.2.0

cd /Users/ddeemer/git-repos/margie-fe/margie-fe
docker build --build-arg VITE_PUBLIC_API_URL="" \
  -t wintermutant/bsp-frontend:v1.2.0 .
docker push wintermutant/bsp-frontend:v1.2.0

# 2. Update deployments to use new version
kubectl set image deployment/bsp-api \
  bsp-api=wintermutant/bsp-api:v1.2.0

kubectl set image deployment/bsp-frontend \
  bsp-frontend=wintermutant/bsp-frontend:v1.2.0

# 3. Watch the rollout
kubectl rollout status deployment/bsp-api
kubectl rollout status deployment/bsp-frontend
```

### Zero-Downtime Updates

Kubernetes automatically does rolling updates:
1. Starts new pod with new image
2. Waits for it to be ready
3. Stops old pod
4. Repeat for each replica

Monitor it:
```bash
kubectl get pods -w
# Watch pods being created and terminated
```

## Part 3: Rolling Back

If something breaks after an update:

### Rollback to Previous Version

```bash
# Rollback backend
kubectl rollout undo deployment/bsp-api

# Rollback frontend
kubectl rollout undo deployment/bsp-frontend

# Check status
kubectl rollout status deployment/bsp-api
```

### Rollback to Specific Version

```bash
# View rollout history
kubectl rollout history deployment/bsp-api

# Rollback to specific revision
kubectl rollout undo deployment/bsp-api --to-revision=3
```

### Rollback to Specific Image Tag

```bash
# Rollback to a known good version
kubectl set image deployment/bsp-api \
  bsp-api=wintermutant/bsp-api:v1.1.0

kubectl set image deployment/bsp-frontend \
  bsp-frontend=wintermutant/bsp-frontend:v1.1.0
```

## Part 4: Database Management

### Backup Database

```bash
# Get pod name
kubectl get pods
# Example: bsp-api-abc123-xyz

# Backup to local machine
kubectl cp bsp-api-abc123-xyz:/data/bsp.db \
  ./backups/bsp-backup-$(date +%Y%m%d-%H%M%S).db
```

### Restore Database

```bash
# Copy backup to pod
kubectl cp ./backups/bsp-backup-20260309-140000.db \
  bsp-api-abc123-xyz:/data/bsp.db

# Restart pod
kubectl rollout restart deployment/bsp-api
```

### Automated Backups

Set up a daily backup cron job - create `k8s/backend/backup-cronjob.yaml`:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: bsp-db-backup
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: wintermutant/bsp-api:latest
            command:
            - /bin/sh
            - -c
            - |
              cp /data/bsp.db /backup/bsp-$(date +%Y%m%d).db
              find /backup -name "bsp-*.db" -mtime +7 -delete
            volumeMounts:
            - name: bsp-data
              mountPath: /data
              readOnly: true
            - name: backup-storage
              mountPath: /backup
          restartPolicy: OnFailure
          volumes:
          - name: bsp-data
            persistentVolumeClaim:
              claimName: bsp-db-pvc
          - name: backup-storage
            persistentVolumeClaim:
              claimName: bsp-backup-pvc  # Create separate PVC for backups
```

Deploy it:
```bash
kubectl apply -f k8s/backend/backup-cronjob.yaml
```

## Part 5: Monitoring and Troubleshooting

### View Logs

```bash
# Real-time logs
kubectl logs -f deployment/bsp-api
kubectl logs -f deployment/bsp-frontend

# Last 100 lines
kubectl logs deployment/bsp-api --tail=100

# Logs from specific pod
kubectl logs bsp-api-abc123-xyz
```

### Check Pod Status

```bash
# List all pods
kubectl get pods

# Detailed info
kubectl describe pod bsp-api-abc123-xyz

# Shell into pod
kubectl exec -it bsp-api-abc123-xyz -- /bin/bash
```

### Check Resource Usage

```bash
# Pod resource usage
kubectl top pods

# Node resource usage
kubectl top nodes
```

### Common Issues

#### Pods stuck in CrashLoopBackOff

```bash
kubectl logs bsp-api-abc123-xyz
kubectl describe pod bsp-api-abc123-xyz
# Check Events section for errors
```

Common causes:
- Missing secrets
- Database connection issues
- Out of memory

#### ImagePullBackOff

```bash
kubectl describe pod bsp-api-abc123-xyz
```

Common causes:
- Image doesn't exist on Docker Hub
- Wrong image name in deployment
- Private repo without credentials
- **Wrong architecture**: Built for ARM64 (Apple Silicon) but Anvil needs AMD64
  - Error: `no matching manifest for linux/amd64 in the manifest list entries`
  - Fix: Rebuild with `docker buildx build --platform linux/amd64` (see Step 1)

#### Service not reachable

```bash
# Check service endpoints
kubectl get endpoints

# Check ingress
kubectl describe ingress bsp-ingress
```

### Scale Replicas

**Important:** With SQLite, keep backend at 1 replica!

Frontend can scale:
```bash
kubectl scale deployment/bsp-frontend --replicas=3
```

Backend (when you migrate to PostgreSQL):
```bash
kubectl scale deployment/bsp-api --replicas=2
```

## Part 6: Complete Teardown

To remove everything:

```bash
# Delete deployments and services
kubectl delete -f k8s/backend/
kubectl delete -f k8s/frontend/
kubectl delete -f k8s/ingress-prod.yaml

# Delete secrets
kubectl delete secret bsp-secrets

# Delete PVC (WARNING: deletes database!)
kubectl delete pvc bsp-db-pvc
```

## Quick Reference

```bash
# Deploy
./deploy.sh wintermutant
kubectl apply -f k8s/

# Update
kubectl rollout restart deployment/bsp-api
kubectl rollout restart deployment/bsp-frontend

# Rollback
kubectl rollout undo deployment/bsp-api

# Monitor
kubectl get pods
kubectl logs -f deployment/bsp-api
kubectl describe pod <pod-name>

# Backup database
kubectl cp <pod-name>:/data/bsp.db ./backup.db

# Scale
kubectl scale deployment/bsp-frontend --replicas=3
```

## Deployment Checklist

**Before deploying:**
- [ ] Code tested locally with `dane-api` and `npm run dev`
- [ ] Docker containers tested with docker-compose
- [ ] Kubeconfig downloaded and `KUBECONFIG` set
- [ ] Namespace created in Rancher and set as default
- [ ] Secrets generated and created in cluster
- [ ] Storage class configured in pvc.yaml
- [ ] Image names updated in deployments

**After deploying:**
- [ ] All pods running: `kubectl get pods`
- [ ] Health endpoint works: `curl https://bsp.anvilcloud.rcac.purdue.edu/v1/health`
- [ ] Can access frontend in browser
- [ ] Can register/login
- [ ] Database persists (test by deleting pod and logging in again)

## Next Steps for Production

1. **Set up monitoring**: Prometheus + Grafana
2. **Configure backups**: Automated daily database backups
3. **Add alerts**: Slack/email notifications for pod failures
4. **CI/CD**: GitHub Actions to auto-deploy on push
5. **Migrate to PostgreSQL**: For horizontal scaling (multiple replicas)
