# Simple single-stage build for cross-platform compatibility
FROM python:3.11-slim

WORKDIR /app

# Copy everything
COPY . .

# Install the package (pip will compile what's needed)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Create directories
RUN mkdir -p /app/data /app/logs

# Expose API port
EXPOSE 8000

# Run the API server
CMD ["dane-api", "--host", "0.0.0.0", "--port", "8000"]
