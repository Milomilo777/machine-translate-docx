import os
import sys
import subprocess
import logging
import signal
from typing import Optional
from celery import Task
from server.celery_app import app

# Setup logger
logger = logging.getLogger("MachineTranslatorWorker")
logging.basicConfig(level=logging.INFO)

# Calculate base directory (root of the repo)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGACY_SCRIPT_PATH = os.path.join(BASE_DIR, "src", "machine-translate-docx.py")

@app.task(bind=True, name="translate_docx")
def translate_task(self: Task, docx_path: str, src_lang: str, dest_lang: str, engine: str, split_sentences: bool = True):
    """
    Celery task to run the machine translation script.

    Args:
        docx_path: Full path to the uploaded DOCX file.
        src_lang: Source language code (or "Auto").
        dest_lang: Destination language code.
        engine: Translation engine name (e.g., "Google", "ChatGPT (API)").
        split_sentences: Whether to split sentences.

    Returns:
        dict: {"status": "success", "file_path": str} or {"status": "error", "message": str}
    """
    logger.info(f"Task started: Translate {docx_path} -> {dest_lang} using {engine}")

    if not os.path.exists(LEGACY_SCRIPT_PATH):
        return {"status": "error", "message": f"Legacy script not found at {LEGACY_SCRIPT_PATH}"}

    cmd = [sys.executable, LEGACY_SCRIPT_PATH]

    # Build Args
    cmd.extend(["--docxfile", docx_path])
    cmd.extend(["--destlang", dest_lang])

    if src_lang != "Auto":
        cmd.extend(["--srclang", src_lang])

    if split_sentences:
        cmd.append("--split")

    # No --showbrowser for server headless execution
    # cmd.append("--showbrowser")

    # Engine logic matching GUI
    if engine == "Google":
        cmd.extend(["--engine", "google"])
    elif engine == "Perplexity":
        cmd.extend(["--engine", "perplexity"])
    elif "ChatGPT" in engine:
        cmd.extend(["--engine", "chatgpt"])
        method = "api" if "API" in engine else "phrasesblock"
        cmd.extend(["--enginemethod", method])

    saved_filename = None
    process = None

    try:
        # Run subprocess
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding='utf-8',
            errors='replace',
            cwd=BASE_DIR,
            preexec_fn=os.setsid # Create a process group for clean termination
        )

        # Prevent EOFError on input()
        try:
            process.stdin.write('\n')
            process.stdin.flush()
        except:
            pass

        # Capture output
        logs = []
        for line in process.stdout:
            if line:
                stripped = line.strip()
                logs.append(stripped)
                if "Saved file name: " in stripped:
                    parts = stripped.split("Saved file name: ")
                    if len(parts) > 1:
                        saved_filename = parts[1].strip()

        process.wait()

        if process.returncode != 0:
            logger.error(f"Translation failed with code {process.returncode}")
            return {"status": "error", "message": f"Process exited with code {process.returncode}", "logs": logs}

        if saved_filename and os.path.exists(saved_filename):
            # Rename with engine suffix
            try:
                engine_suffix = "".join(c for c in engine if c.isalnum() or c in (' ', '.', '_')).rstrip().replace(" ", "_")
                dir_name = os.path.dirname(saved_filename)
                base_name = os.path.basename(saved_filename)
                name, ext = os.path.splitext(base_name)

                new_name = f"{name}_{engine_suffix}{ext}"
                new_path = os.path.join(dir_name, new_name)

                os.rename(saved_filename, new_path)
                logger.info(f"Renamed output to: {new_path}")
                return {"status": "success", "file_path": new_path}
            except Exception as e:
                logger.warning(f"Rename failed: {e}")
                return {"status": "success", "file_path": saved_filename}
        else:
             return {"status": "error", "message": "Output file not found in logs.", "logs": logs}

    except Exception as e:
        logger.exception("Unexpected error in worker task")
        return {"status": "error", "message": str(e)}

    finally:
        # Prevent Zombie Processes: Ensure subprocess and its children are killed
        if process and process.poll() is None:
            logger.warning("Terminating hanging subprocess...")
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception as e:
                logger.error(f"Error terminating process: {e}")
