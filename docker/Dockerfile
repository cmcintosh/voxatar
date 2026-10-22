# Voxatar Dockerfile — Phase 1 MVP
FROM python:3.11-slim

# System dependencies for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    portaudio19-dev \
    libsndfile1-dev \
    libgl1-mesa-glx \
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

# Expose WebRTC signaling port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Default command
CMD ["voxatar", "serve", "--agent", "examples/simple-agent.yaml", "--host", "0.0.0.0", "--port", "8080"]