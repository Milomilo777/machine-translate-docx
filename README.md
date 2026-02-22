# Machine Translator v1.1 - Dockerized Web Dashboard

A modernized, high-performance web application for translating DOCX files using headless Google Chrome.
Supports Google Translate, Perplexity, and ChatGPT (API/Web).

![v1.1 Release](https://img.shields.io/badge/Release-v1.1-green)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-teal)

## 🚀 Features

- **Web Dashboard:** Modern, dark-themed UI with Drag & Drop uploads.
- **Dockerized:** Full stack (FastAPI + Celery + Redis + Chrome) in one container.
- **Concurrency Safe:** Limits worker threads to prevent RAM exhaustion.
- **Robust:** Handles massive documents (500+ pages) with extended timeouts.
- **Legacy Core:** Preserves the battle-tested scraping logic of the original script.

## 🛠️ Quick Start (Docker)

1. **Install Docker Desktop**.
2. **Clone & Run:**
   ```bash
   git clone https://github.com/Milomilo777/machine-translate-docx.git
   cd machine-translate-docx
   docker-compose up --build -d
   ```
3. **Access the Dashboard:**
   Open [http://localhost:8000](http://localhost:8000) in your browser.

## 📦 Manual Installation (Linux/Mac)

If you prefer running without Docker:

1. **Install Requirements:**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-server.txt
   sudo apt-get install google-chrome-stable redis-server
   ```
2. **Start Redis:**
   ```bash
   redis-server
   ```
3. **Start Worker:**
   ```bash
   celery -A server.celery_app worker --loglevel=info
   ```
4. **Start API:**
   ```bash
   uvicorn server.api:app --reload
   ```

## 🧠 Architecture

- **Frontend:** HTML5 + Tailwind CSS (served via FastAPI Jinja2).
- **Backend:** FastAPI (Async/Await).
- **Queue:** Celery + Redis (for background processing).
- **Engine:** Selenium + Undetected Chromedriver (Headless).

## ⚠️ Notes

- The first run might take a minute to download the Chrome binary in Docker.
- Large files may take 10-20 minutes to process. The UI will show a spinner. Do not close the tab.
- Output files are automatically renamed with the engine suffix (e.g., `MyDoc_Google.docx`).

## 📜 License

MIT License.
