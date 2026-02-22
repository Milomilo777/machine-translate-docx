# Use official Python slim image based on Debian Bookworm
FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV SHARED_DATA_DIR=/app/shared_data
ENV DISPLAY=:99

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends     wget     gnupg     unzip     curl     xvfb     fonts-liberation     fonts-noto-core     fonts-noto-cjk     fonts-noto-color-emoji     fonts-arphic-ukai     fonts-arphic-uming     fonts-ipafont-mincho     fonts-ipafont-gothic     fonts-unfonts-core     libnss3     libgconf-2-4     libxss1     libappindicator3-1     libasound2     libatk-bridge2.0-0     libgtk-3-0     libgbm1     && rm -rf /var/lib/apt/lists/*

# Install Google Chrome Stable
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -     && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list     && apt-get update     && apt-get install -y google-chrome-stable     && rm -rf /var/lib/apt/lists/*

# Verify Chrome installation
RUN google-chrome --version

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
COPY requirements-server.txt .
RUN pip install --no-cache-dir --upgrade pip     && pip install --no-cache-dir -r requirements.txt     && pip install --no-cache-dir -r requirements-server.txt

# Copy application code
COPY . .

# Create shared directory
RUN mkdir -p /app/shared_data

# Expose port for API
EXPOSE 8000

# Default command (overridden by docker-compose)
CMD ["uvicorn", "server.api:app", "--host", "0.0.0.0", "--port", "8000"]
