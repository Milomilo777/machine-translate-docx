import os
import shutil
import uuid
import logging
from typing import Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from server.celery_app import app as celery_app
from server.worker import translate_task

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FastAPI")

app = FastAPI(title="Machine Translator API", version="2.0.0")

# Setup Shared Data Dir (Docker Volume)
SHARED_DATA_DIR = os.environ.get("SHARED_DATA_DIR", os.path.join(os.getcwd(), "shared_data"))
os.makedirs(SHARED_DATA_DIR, exist_ok=True)

# Setup Templates
templates = Jinja2Templates(directory="server/templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the Web Dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/translate")
async def translate_document(
    file: UploadFile = File(...),
    source_lang: str = Form("Auto"), # Fixed: Changed from src_lang to match HTML form
    dest_lang: str = Form("fa"),
    engine: str = Form("Google"),
    split_sentences: bool = Form(True)
):
    """
    Endpoint to upload a DOCX file and receive the translated version.
    Current architecture: Synchronous wait for Celery task result.
    """
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported.")

    # 1. Save File to Shared Data Dir
    file_id = str(uuid.uuid4())
    safe_filename = "".join(c for c in file.filename if c.isalnum() or c in (' ', '.', '_')).rstrip()
    temp_path = os.path.join(SHARED_DATA_DIR, f"{file_id}_{safe_filename}")

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    logger.info(f"File uploaded: {temp_path}")

    try:
        # 2. Dispatch Celery Task
        # Synchronously waiting for result to simplify API response for now.
        # In a production environment, you might return a task_id and poll for status.
        task = translate_task.delay(
            docx_path=temp_path,
            src_lang=source_lang, # Pass corrected variable
            dest_lang=dest_lang,
            engine=engine,
            split_sentences=split_sentences
        )

        # Wait up to 20 minutes for large files
        result = task.get(timeout=1200)

        if result["status"] == "success":
            output_path = result["file_path"]
            if os.path.exists(output_path):
                filename = os.path.basename(output_path)
                return FileResponse(
                    path=output_path,
                    filename=filename,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                )
            else:
                 raise HTTPException(status_code=500, detail="Output file missing after successful task.")
        else:
             logger.error(f"Task Failed: {result.get('message')}")
             raise HTTPException(status_code=500, detail=f"Translation failed: {result.get('message')}")

    except Exception as e:
        logger.exception("Error processing request")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup logic if desired
        pass

@app.get("/health")
def health_check():
    return {"status": "ok", "celery_status": "connected", "storage": SHARED_DATA_DIR}
