# Use Python 3.9 slim image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    # Development settings
    DEBUG=1 \
    ENVIRONMENT=development \
    # Security settings (relaxed for dev)
    MAX_FILE_SIZE=52428800 \
    CHUNK_SIZE=1048576 \
    UPLOAD_TIMEOUT=60 \
    MAX_CONCURRENT_UPLOADS=10 \
    RATE_LIMIT_REQUESTS=120 \
    RATE_LIMIT_BURST=20

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p data/exports data/logs data/encrypted data/temp data/backup keys && \
    chmod -R 755 /app && \
    chmod -R 777 /app/logs

# Expose port
EXPOSE 8501

# Set healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run the application with development settings
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.maxUploadSize=50", \
     "--server.enableCORS=true", \
     "--server.enableXsrfProtection=true", \
     "--server.enableWebsocketCompression=true", \
     "--server.runOnSave=false", \
     "--server.headless=true", \
     "--server.maxMessageSize=200", \
     "--server.maxUploadSize=50", \
     "--browser.serverAddress=0.0.0.0"]
