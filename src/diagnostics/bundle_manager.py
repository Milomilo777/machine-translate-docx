import os
import json
import time
import uuid
import traceback
from datetime import datetime
import copy

class DiagnosticBundleManager:
    def __init__(self, base_log_dir="logs"):
        self.base_log_dir = base_log_dir
        self.max_retention = 50

    def _redact_sensitive_info(self, data):
        """Redact sensitive data like API keys from dictionaries/lists recursively."""
        if isinstance(data, dict):
            redacted = {}
            for k, v in data.items():
                if 'key' in k.lower() or 'password' in k.lower() or 'token' in k.lower() or 'secret' in k.lower():
                    redacted[k] = "***"
                else:
                    redacted[k] = self._redact_sensitive_info(v)
            return redacted
        elif isinstance(data, list):
            return [self._redact_sensitive_info(item) for item in data]
        else:
            return data

    def _update_latest_status(self, file_name, bundle_data):
        try:
            latest_file = os.path.join(self.base_log_dir, file_name, "latest_status.json")
            os.makedirs(os.path.dirname(latest_file), exist_ok=True)
            with open(latest_file, "w", encoding="utf-8") as f:
                json.dump(bundle_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[DiagnosticBundleManager] Failed to update latest status: {e}")

    def _update_global_index(self, bundle_data):
        try:
            index_file = os.path.join(self.base_log_dir, "index.json")
            os.makedirs(self.base_log_dir, exist_ok=True)

            index_data = []
            if os.path.exists(index_file):
                try:
                    with open(index_file, "r", encoding="utf-8") as f:
                        index_data = json.load(f)
                except Exception:
                    pass

            # Extract high-level summary for the index
            summary = {
                "trace_id": bundle_data["trace_id"],
                "timestamp": bundle_data["timestamp"],
                "file_name": bundle_data["file_name"],
                "stage": bundle_data["stage"],
                "level": bundle_data["level"],
                "error_message": bundle_data["error_message"]
            }

            index_data.append(summary)

            # Retention logic: Keep only the last `max_retention` entries
            if len(index_data) > self.max_retention:
                index_data = index_data[-self.max_retention:]

            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[DiagnosticBundleManager] Failed to update global index: {e}")

    def create_bundle(self, file_name, stage, error, payload=None, state=None, trace_id=None):
        """
        Creates a diagnostic bundle containing error details and state.

        Args:
            file_name (str): The name of the file being processed.
            stage (str): The stage of the pipeline where the failure occurred.
            error (Exception or str): The exception that occurred.
            payload (dict, optional): The current payload being processed.
            state (dict, optional): Additional state information.
        """
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.basename(file_name) if file_name else "unknown"

            # Create folder structure: logs/<file_name>/<timestamp>_failure/
            bundle_dir = os.path.join(self.base_log_dir, base_name, f"{timestamp}_failure")
            os.makedirs(bundle_dir, exist_ok=True)

            error_msg = str(error)
            tb = traceback.format_exc() if isinstance(error, Exception) else None

            if not trace_id:
                trace_id = uuid.uuid4().hex
            bundle_data = {
                "trace_id": trace_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "file_name": base_name,
                "stage": stage,
                "level": "ERROR",
                "error_message": error_msg,
                "traceback": tb,
            }

            if payload is not None:
                try:
                    # Deep copy and redact
                    safe_payload = copy.deepcopy(payload)
                    bundle_data["payload"] = self._redact_sensitive_info(safe_payload)
                except Exception as e:
                    bundle_data["payload"] = f"[Could not serialize payload: {e}]"

            if state is not None:
                try:
                    safe_state = copy.deepcopy(state)
                    bundle_data["state"] = self._redact_sensitive_info(safe_state)
                except Exception as e:
                    bundle_data["state"] = f"[Could not serialize state: {e}]"

            bundle_file = os.path.join(bundle_dir, "diagnostic_bundle.json")
            with open(bundle_file, "w", encoding="utf-8") as f:
                json.dump(bundle_data, f, ensure_ascii=False, indent=2)

            self._update_latest_status(base_name, bundle_data)
            self._update_global_index(bundle_data)

            return bundle_file
        except Exception as e:
            # Failsafe, don't crash the main process if logging fails
            print(f"[DiagnosticBundleManager] Failed to create bundle: {e}")
            return None
