# 🌐 Professional DOCX Machine Translator (v1.2.3)

![Release v1.2.3](https://img.shields.io/badge/Release-v1.2.3-green)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-teal)
![RTL Support](https://img.shields.io/badge/RTL-Persian%20%7C%20Arabic-orange)

A modernized, high-performance web application for translating DOCX files using headless Google Chrome. Designed for professional translators handling high-volume workloads on hardware like the **Dell Vostro 3590**.

## 🚀 Features

- **Full-Stack Architecture:**
  - **Frontend:** Modern v0 Web Dashboard (Dark Mode, Drag & Drop).
  - **Backend:** FastAPI (Async) + Celery (Queue) + Redis (Broker).
  - **Engine:** Headless Google Chrome with `undetected_chromedriver` for bot evasion.
- **Atomic Reliability:**
  - **Smart Concurrency:** Limits worker threads to 1 per container to prevent RAM exhaustion on 8GB/16GB machines.
  - **Zombie Prevention:** Automatically kills stuck Chrome processes.
  - **Timeout Safety:** Extended HTTP timeouts (1 hour) for massive 500+ page documents.
- **Advanced Persian/RTL Support:**
  - Integrated `hazm`, `parsivar`, `khoshnevis`, `python-bidi`, and `arabic-reshaper`.
  - Ensures correct rendering of mixed English-Persian text and complex tables.
  - Includes custom fonts (`fonts-noto-core`, `fonts-arphic-ukai`) in Docker.

## 🛠️ Prerequisites

- **OS:** Windows 10/11 (WSL2 Recommended) or Linux (Ubuntu/Debian).
- **Docker:** Docker Desktop installed and running.
- **Hardware:** Optimized for 4+ Cores, 8GB+ RAM.

## 📦 Quick Start (Docker)

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/Milomilo777/machine-translate-docx.git
   cd machine-translate-docx
   ```

2. **Launch with Docker Compose:**
   ```bash
   docker-compose up --build -d
   ```
   *Note: First run may take a few minutes to download the 1.5GB Docker image.*

3. **Access the Dashboard:**
   Open your browser to: **[http://localhost:8000](http://localhost:8000)**

## 🔧 Manual Installation (Developer Mode)

If you need to run without Docker, ensure you have Python 3.11+ and install the full dependency suite:

```bash
pip install -r requirements.txt
pip install -r requirements-server.txt
sudo apt-get install google-chrome-stable redis-server
```

**Required Services:**
- Start Redis: `redis-server`
- Start Worker: `celery -A server.celery_app worker --loglevel=info`
- Start API: `uvicorn server.api:app --reload`

## ❓ Troubleshooting

### 🔴 Error 500 / "Internal Server Error"
- **Cause:** Often due to missing dependencies like `json5` or `hazm` in the worker environment.
- **Fix:** We fixed this in v1.2.3. Run `docker-compose build --no-cache` to refresh your image.

### 🔴 "Connection Refused" at localhost:8000
- **Cause:** The Docker container hasn't finished starting, or Redis is unhealthy.
- **Fix:** Check logs with `docker-compose logs -f`. Wait for "Application startup complete".

### 🔴 "ModuleNotFoundError: No module named 'bidi'"
- **Cause:** Incorrect package name.
- **Fix:** Ensure your `requirements.txt` lists `python-bidi`, NOT `bidi`.

## 📜 License

MIT License.
