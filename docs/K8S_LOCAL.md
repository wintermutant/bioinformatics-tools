# Local Kubernetes Testing (Optional)

Test your Kubernetes setup locally with minikube before deploying to Anvil.

**Skip this if:** You're confident in your Docker setup and want to deploy directly to production.

**Use this if:** You want to test the exact K8s manifests, ingress routing, and secrets before deploying to Anvil.

## Prerequisites

- Docker containers tested and working (see [DOCKER_TESTING.md](DOCKER_TESTING.md))
- Minikube installed

## Step 1: Install Minikube

```bash
# macOS
brew install minikube

# Or download from https://minikube.sigs.k8s.io/docs/start/
```

## Step 2: Start Minikube

```bash
# Start cluster
minikube start

# Enable ingress addon
minikube addons enable ingress

# Verify
kubectl get nodes
# Should show: minikube   Ready
```

## Step 3: Build Images in Minikube

Minikube has its own Docker daemon, so build images inside it:

```bash
# Point your terminal to minikube's Docker
eval $(minikube docker-env)

# Build backend
cd /Users/ddeemer/git-repos/bioinformatics-tools
docker build -t wintermutant/bsp-api:test .

# Build frontend (with empty API_URL for ingress routing)
cd /Users/ddeemer/git-repos/margie-fe/margie-fe
docker build --build-arg VITE_PUBLIC_API_URL="" \
  -t wintermutant/bsp-frontend:test .

# Point back to your normal Docker
eval $(minikube docker-env -u)
```

## Step 4: Create Test Manifests

```bash
cd /Users/ddeemer/git-repos/bioinformatics-tools

# Copy K8s manifests for testing
cp -r k8s k8s-test

# Edit k8s-test/backend/deployment.yaml
# Change: image: wintermutant/bsp-api:test
# Add:    imagePullPolicy: Never

# Edit k8s-test/frontend/deployment.yaml
# Change: image: wintermutant/bsp-frontend:test
# Add:    imagePullPolicy: Never  --> this is a newline after image:
```

## Step 5: Create Secrets

```bash
# Generate keys
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Copy the output

docker run --rm wintermutant/bsp-api:test python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Copy the output

# Create secret
kubectl create secret generic bsp-secrets \
  --from-literal=secret-key='PASTE_SECRET_KEY' \
  --from-literal=encryption-key='PASTE_ENCRYPTION_KEY'
```

## Step 6: Deploy to Minikube

```bash
# Deploy backend
kubectl apply -f k8s-test/backend/pvc.yaml
kubectl apply -f k8s-test/backend/deployment.yaml
kubectl apply -f k8s-test/backend/service.yaml

# Deploy frontend
kubectl apply -f k8s-test/frontend/deployment.yaml
kubectl apply -f k8s-test/frontend/service.yaml

# Deploy ingress
kubectl apply -f k8s-test/ingress-local.yaml

# Check status
kubectl get all
kubectl get ingress
```

## Step 7: Access the Application

### Option A: Port Forwarding (Easiest)

```bash
# Forward frontend
kubectl port-forward svc/bsp-frontend-svc 3001:3000

# Open browser
open http://localhost:3001
```

### Option B: Via Ingress (More realistic)

```bash
# Get minikube IP
minikube ip
# Example: 192.168.49.2

# Add to /etc/hosts
echo "$(minikube ip) bsp.local" | sudo tee -a /etc/hosts

# Open browser
open http://bsp.local
```

## Step 8: Test and Verify

- ✅ Pods are running: `kubectl get pods`
- ✅ Services created: `kubectl get services`
- ✅ Ingress created: `kubectl get ingress`
- ✅ Can access frontend
- ✅ Can register/login
- ✅ API calls route correctly through ingress

**Check logs:**
```bash
kubectl logs -f deployment/bsp-api
kubectl logs -f deployment/bsp-frontend
```

**Describe pod if issues:**
```bash
kubectl get pods
kubectl describe pod bsp-api-xxxxx
```

## Step 9: Test Database Persistence

```bash
# 1. Register a user via the app

# 2. Delete the backend pod
kubectl delete pod -l app=bsp-api

# 3. Wait for new pod to start
kubectl get pods -w

# 4. Try logging in with the same user
# If it works, data persisted!
```

## Clean Up

```bash
# Delete all resources
kubectl delete -f k8s-test/

# Delete secrets
kubectl delete secret bsp-secrets

# Stop minikube
minikube stop

# Delete cluster (if done testing)
minikube delete

# Remove test manifests
rm -rf k8s-test/
```

## Troubleshooting

### Pods stuck in Pending

```bash
kubectl describe pod <pod-name>
# Check Events section
```

### Ingress not working

```bash
# Check ingress controller
kubectl get pods -n ingress-nginx

# Restart ingress if needed
minikube addons disable ingress
minikube addons enable ingress
```

### Can't pull images

Make sure you set `imagePullPolicy: Never` in deployments so it uses local images.

## Next Steps

If minikube testing passes:
- [Deploy to production](K8S_PRODUCTION.md) on Anvil with confidence!
