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
            "output_path":    output_path,
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
                      input_tokens: int = 0,
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
                block["input_tokens"]  = input_tokens
                block["output_tokens"] = output_tokens
                block["attempt_count"] = attempt_count
                block["error"]         = error

                # Extract start/end lines if present (stored as "start-end")
                start_line = None
                end_line = None
                lines_str = block.get("lines", "")
                try:
                    if isinstance(lines_str, str) and "-" in lines_str:
                        parts = lines_str.split("-", 1)
                        start_line = int(parts[0]) if parts[0].isdigit() else None
                        end_line = int(parts[1]) if parts[1].isdigit() else None
                except Exception:
                    start_line = None
                    end_line = None

                # remove internal field if present
                try:
                    del block["_started_ts"]
                except Exception:
                    pass

                # JSON fallback: always attempt to write a per-block summary to ./logs/
                # Do this for successful blocks; wrap in try/except so it never crashes.
                try:
                    if status == "SUCCESS":
                        payload = {
                            "doc_name": self.meta.get("doc_name"),
                            "action": self.meta.get("action"),
                            "model": self.meta.get("model"),
                            "block_id": block_id,
                            "start_line": start_line,
                            "end_line": end_line,
                            "input_tokens": block.get("input_tokens", 0),
                            "output_tokens": block.get("output_tokens", 0),
                            # cost may not be available in this logger; include if present, else None
                            "cost_usd": self.meta.get("total_cost_usd", None)
                        }
                        _out = self.meta.get("output_path") or __file__
                        logs_dir = os.path.join(os.path.dirname(os.path.abspath(_out)), "logs")
                        os.makedirs(logs_dir, exist_ok=True)
                        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                        doc = (self.meta.get("doc_name") or "unknown").replace(" ", "_")
                        act = (self.meta.get("action") or "unknown").replace(" ", "_")
                        filename = f"{doc}_{act}_{block_id}_{ts}-SUCCESS.json"
                        file_path = os.path.join(logs_dir, filename)
                        with open(file_path, "w", encoding="utf-8") as fh:
                            json.dump(payload, fh, ensure_ascii=False, indent=2)
                except Exception:
                    # Never allow logging fallback to raise
                    pass
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
