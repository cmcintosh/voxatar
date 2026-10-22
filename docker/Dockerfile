# Voxatar Dockerfile
FROM python:3.11-slim

# System dependencies for audio/video processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    portaudio19-dev \
    libsndfile1-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    build-essential \
    cmake \
    git \
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

# Default command
CMD ["voxatar", "serve", "--host", "0.0.0.0", "--port", "8080"]