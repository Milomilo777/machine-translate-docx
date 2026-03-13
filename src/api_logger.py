# pylint: disable=all
import os, json, time
from datetime import datetime

class APILogger:

    def __init__(self, doc_name: str, action: str, engine: str,
                 model: str, prompt_version: str, output_path: str):
        self._start_time  = time.time()
        self._output_path = output_path
        self.meta = {
            "doc_name":       doc_name,
            "action":         action,
            "engine":         engine,
            "model":          model,
            "prompt_version": prompt_version,
            "api_key_last4":  "",
            "started_at":     datetime.utcnow().isoformat() + "Z",
            "ended_at":       None,
            "total_duration_sec": None,
            "status":         "RUNNING"
        }
        self.blocks = []

    def set_api_key(self, api_key: str):
        try:
            self.meta["api_key_last4"] = (api_key[-4:] if api_key else "")
        except Exception:
            pass

    def log_block_start(self, block_id: int, line_start: int,
                        line_end: int, input_tokens: int = 0):
        try:
            self.blocks.append({
                "block_id":     block_id,
                "lines":        f"{line_start}-{line_end}",
                "status":       "RUNNING",
                "_started_ts":  time.time(),   # internal, not in JSON output
                "duration_sec": None,
                "input_tokens": input_tokens,
                "output_tokens": 0,
                "attempt_count": 1,
                "error":        None
            })
        except Exception:
            pass

    def log_block_end(self, block_id: int, status: str,
                      output_tokens: int = 0,
                      attempt_count: int = 1,
                      error: str = None):
        """
        status values: "SUCCESS" | "TIMEOUT" | "PARSE_ERROR"
                       | "API_ERROR" | "FAILED"
        """
        try:
            block = next(
                (b for b in self.blocks if b["block_id"] == block_id),
                None)
            if block:
                block["status"]        = status
                block["duration_sec"]  = round(
                    time.time() - block["_started_ts"], 2)
                block["output_tokens"] = output_tokens
                block["attempt_count"] = attempt_count
                block["error"]         = error
                del block["_started_ts"]   # remove internal field
        except Exception:
            pass

    def save(self):
        """
        Silent-fail. Must NEVER raise or crash the main process.

        Output location:
          {output_docx_folder}/API_Logs/{YYYY-MM}/
          {YYYYMMDD_HHMM}_{action}_{output_docx_basename}.json

        If output_path has no directory component,
        use the current working directory.
        """
        try:
            statuses = [b["status"] for b in self.blocks]
            if all(s == "SUCCESS" for s in statuses):
                self.meta["status"] = "SUCCESS"
            elif any(s == "SUCCESS" for s in statuses):
                self.meta["status"] = "PARTIAL_FAIL"
            else:
                self.meta["status"] = "FAILED"

            self.meta["ended_at"] = datetime.utcnow().isoformat() + "Z"
            self.meta["total_duration_sec"] = round(
                time.time() - self._start_time, 2)

            out_dir = os.path.dirname(os.path.abspath(self._output_path))
            month   = datetime.utcnow().strftime("%Y-%m")
            log_dir = os.path.join(out_dir, "API_Logs", month)
            os.makedirs(log_dir, exist_ok=True)

            ts       = datetime.utcnow().strftime("%Y%m%d_%H%M")
            docbase  = os.path.splitext(
                           os.path.basename(self._output_path))[0]
            filename = f"{ts}_{self.meta['action']}_{docbase}.json"

            # Exclude internal fields from output
            clean_blocks = [
                {k: v for k, v in b.items() if not k.startswith("_")}
                for b in self.blocks
            ]
            payload = {"meta": self.meta, "blocks": clean_blocks}

            with open(os.path.join(log_dir, filename),
                      "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

        except Exception:
            pass
