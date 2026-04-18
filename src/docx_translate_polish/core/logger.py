"""Unified logging system."""
import datetime
from .utils import calculate_openai_cost

class TranslationLogger:
    """Unified logger for the translation module."""

    def _get_timestamp(self) -> str:
        return datetime.datetime.now().strftime("%H:%M:%S")

    def info(self, msg: str):
        """Log an info message."""
        print(f"[INFO][{self._get_timestamp()}] {msg}")

    def warn(self, msg: str):
        """Log a warning message."""
        print(f"[WARN][{self._get_timestamp()}] {msg}")

    def error(self, msg: str):
        """Log an error message."""
        print(f"[ERROR][{self._get_timestamp()}] {msg}")

    def log_cost(self, cost_dict: dict):
        """Format and log the cost summary."""
        if cost_dict.get("unknown_model"):
            self.warn(f"No known pricing for model '{cost_dict['model']}'. Cost set to 0.")

        print(f"[COST][{self._get_timestamp()}] Model: {cost_dict['model']}")
        print(f"[COST][{self._get_timestamp()}] Tokens: {cost_dict['total_tokens']} "
              f"({cost_dict['prompt_tokens']} prompt, {cost_dict['completion_tokens']} completion)")
        print(f"[COST][{self._get_timestamp()}] Total Cost: ${cost_dict['total_cost_usd']:.6f} USD")
