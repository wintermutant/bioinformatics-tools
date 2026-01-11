"""
FastAPI application entry point for Bioinformatics Tools API

Usage:
    Development: uvicorn bioinformatics_tools.api.main:app --reload
    Production: dane-api (after installing with pip install .[api])
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from bioinformatics_tools.api.routers import fasta, ssh_upload, example

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
LOGGER = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title='Bioinformatics Tools API',
    version="0.0.1",
    description="API for bioinformatics file processing and analysis",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware (adjust origins for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(fasta.router)
app.include_router(ssh_upload.router)
app.include_router(example.router)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "status": "success",
        "message": "Bioinformatics Tools API",
        "version": "0.0.1",
        "docs": "/docs",
        "endpoints": {
            "fasta": "/v1/fasta",
            "ssh_upload": "/v1/ssh"
        }
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "success", "message": "API is healthy"}


def serve(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """
    Entry point for running the API server
    """
    LOGGER.info(f"Starting Bioinformatics Tools API server on {host}:{port}")
    uvicorn.run(
        "bioinformatics_tools.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    # For development: python -m bioinformatics_tools.api.main
    serve(reload=True)
