# Bioinformatics Tools API

REST API for bioinformatics file processing and analysis.

## Quick Start

### Installation

```bash
# Install with pip (includes API dependencies)
pip install bioinformatics-tools

# Or install from source
git clone https://github.com/yourname/bioinformatics-tools
cd bioinformatics-tools
pip install -e .
```

### Running the Server

**Option 1: Using the command-line entry point**
```bash
dane-api
# Server starts at http://localhost:8000
```

**Option 2: Using Python module**
```bash
python -m bioinformatics_tools.api.main
```

**Option 3: Using uvicorn directly**
```bash
uvicorn bioinformatics_tools.api.main:app --reload
```

## API Documentation

Once the server is running, visit:
- **Interactive Docs (Swagger)**: http://localhost:8000/docs
- **Alternative Docs (ReDoc)**: http://localhost:8000/redoc

## Available Endpoints

### Health Checks

**Root Endpoint**
```bash
curl http://localhost:8000/
```
Response:
```json
{
  "status": "success",
  "message": "Bioinformatics Tools API",
  "version": "0.0.1",
  "docs": "/docs",
  "endpoints": {
    "fasta": "/v1/fasta"
  }
}
```

**Health Check**
```bash
curl http://localhost:8000/health
```
Response:
```json
{
  "status": "success",
  "message": "API is healthy"
}
```

### FASTA Endpoints

**Calculate GC Content**
```bash
curl -X POST http://localhost:8000/v1/fasta/gc_content \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/your/file.fasta",
    "precision": 2
  }'
```

Response:
```json
{
  "status": "success",
  "data": {
    "1": {
      "header": "My_defline",
      "gc_content": 0.65
    },
    "2": {
      "header": "My_defline_2",
      "gc_content": 0.46
    }
  },
  "message": "GC content calculated for 2 sequences"
}
```

**FASTA Health Check**
```bash
curl http://localhost:8000/v1/fasta/health
```

## Examples

### Python Client Example

```python
import requests

# Calculate GC content
response = requests.post(
    "http://localhost:8000/v1/fasta/gc_content",
    json={
        "file_path": "/path/to/file.fasta",
        "precision": 3
    }
)

data = response.json()
print(data["data"])
```

### JavaScript/Frontend Example

```javascript
// Calculate GC content
const response = await fetch('http://localhost:8000/v1/fasta/gc_content', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    file_path: '/path/to/file.fasta',
    precision: 2
  })
});

const data = await response.json();
console.log(data.data);
```

### cURL Example

```bash
# Test with example file
curl -X POST http://localhost:8000/v1/fasta/gc_content \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "test-files/example.fasta",
    "precision": 4
  }'
```

## Production Deployment

### Using Gunicorn (Recommended)

```bash
# Install gunicorn
pip install gunicorn

# Run with multiple workers
gunicorn bioinformatics_tools.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install -e .

CMD ["gunicorn", "bioinformatics_tools.api.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000"]
```

### Environment Variables

```bash
# Set host and port (optional)
export API_HOST=0.0.0.0
export API_PORT=8000

# Run
dane-api
```

## Error Handling

The API returns standard HTTP status codes:

- **200**: Success
- **400**: Bad request (invalid file format)
- **404**: File not found
- **500**: Internal server error

Error response format:
```json
{
  "detail": "Error message here"
}
```

## Adding New Endpoints

To add new endpoints, create a new router in `bioinformatics_tools/api/routers/`:

```python
# bioinformatics_tools/api/routers/your_router.py
from fastapi import APIRouter

router = APIRouter(prefix="/v1/your_endpoint", tags=["your_tag"])

@router.post("/your_method")
async def your_method():
    return {"status": "success"}
```

Then include it in `main.py`:
```python
from bioinformatics_tools.api.routers import your_router
app.include_router(your_router.router)
```

## Security Considerations

For production deployments:

1. **CORS**: Update `allow_origins` in `main.py` to your specific domain
2. **Authentication**: Add API key or OAuth2 authentication
3. **Rate Limiting**: Implement rate limiting to prevent abuse
4. **HTTPS**: Always use HTTPS in production
5. **File Access**: Validate and sanitize file paths to prevent directory traversal

## Support

For issues or questions, please open an issue on GitHub.
