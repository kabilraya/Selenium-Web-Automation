FROM python:3.11-slim
 
WORKDIR /app
 
# Install system dependencies
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    git \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
 
# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
# Copy model folders and code LAST (only these layers rebuild on code changes)
COPY yolo5/ /app/yolo5/

 
# Copy application code
COPY main.py .
 
# Expose port
EXPOSE 8000
 
# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]