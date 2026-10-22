# Voxatar Dockerfile — Phase 1.5
FROM python:3.12-slim

# System dependencies for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    portaudio19-dev \
    libsndfile1-dev \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    cmake \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Application
COPY . /app
WORKDIR /app
RUN pip install --no-cache-dir -e .

# Create data directories for SQLite, ChromaDB, and documents
RUN mkdir -p /app/data/chromadb /app/data/documents /app/agents

# Copy default agent config
COPY examples/simple-agent.yaml /app/agents/simple-agent.yaml

# Expose WebRTC signaling port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Default command
CMD ["voxatar", "serve", "--agent", "/app/agents/simple-agent.yaml", "--host", "0.0.0.0", "--port", "8080", "--ollama-url", "http://host.docker.internal:11434/v1"]