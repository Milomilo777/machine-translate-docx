# pylint: disable=import-error
import os
from celery import Celery

# Use Redis as the broker and backend
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "machine_translator",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["server.worker"]
)

# Optional: Configuration
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=1, # Limit concurrent tasks to 1 to prevent RAM overload
)

if __name__ == "__main__":
    app.start()
