FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# System dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependencies
COPY requirements.txt .

# Install python libs
RUN pip install --no-cache-dir -r requirements.txt

# Copy your tracker script
COPY tracker.py .

CMD ["python", "tracker.py"]
