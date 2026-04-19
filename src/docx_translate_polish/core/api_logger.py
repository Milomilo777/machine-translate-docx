"""
PipelineFileLogger — Single-file black-box logger for docx_translate_polish pipeline.

One JSON file per run, saved beside the processed DOCX.
Captures: metadata, every API call (prompt/response/tokens/timing/errors),
split operations, retry events, cost estimate, and a token summary.

Usage:
    logger = PipelineFileLogger(output_docx_path="/path/to/output.docx")
    logger.set_meta(model="gpt-5.4", src_lang="en", dest_lang="fa",
                    splitting_mode="classic", source_file="input.docx")
    logger.log_call(
        stage="translate",          # "translate" | "split_ai" | "polish"
        block_index=0,
        lines_sent=["line1", "line2"],
        system_prompt="...",
        user_prompt="...",
        raw_response="...",
        input_tokens=120,
        output_tokens=95,
        cached_tokens=0,
        elapsed_seconds=1.42,
        attempt=1,                  # retry attempt number (1 = first try)
        error=None,                 # exception string if failed
    )
    logger.log_split(block_index=0, mode="classic",
                     lines_in=["long line"], lines_out=["part1", "part2"])
    logger.save()   # call once at end of pipeline
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Pricing table (per 1M tokens) ──────────────────────────────────────────
_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-5.4":          {"input": 3.00,  "cached": 1.50,  "output": 12.00},
    "gpt-5.4-mini":     {"input": 0.40,  "cached": 0.10,  "output": 1.60},
    # extend here for future models
}
_DEFAULT_PRICING = {"input": 0.0, "cached": 0.0, "output": 0.0}


def _calc_cost(model: str, input_t: int, cached_t: int, output_t: int) -> float:
    p = _PRICING.get(model, _DEFAULT_PRICING)
    return round(
        (input_t  - cached_t) / 1_000_000 * p["input"]
        + cached_t             / 1_000_000 * p["cached"]
        + output_t             / 1_000_000 * p["output"],
        6,
    )


# ── Main logger ─────────────────────────────────────────────────────────────
class PipelineFileLogger:
    """
    All-in-one black-box logger for one pipeline run.
    Thread-safe for append operations; call save() once at end of run.
    """

    VERSION = "2.0"

    def __init__(self, output_docx_path: str) -> None:
        path   = Path(output_docx_path)
        stem   = path.stem
        folder = path.parent
        self._log_path: Path = folder / f"{stem}.pipeline-log.json"
        self._meta:  Dict[str, Any]  = {}
        self._calls: List[Dict[str, Any]] = []
        self._splits: List[Dict[str, Any]] = []
        self._events: List[Dict[str, Any]] = []
        self._run_start: str = datetime.now(timezone.utc).isoformat()

    # ── Metadata ─────────────────────────────────────────────────────────
    def set_meta(self, **kwargs: Any) -> None:
        """Call once before pipeline starts. Pass all run-level info."""
        self._meta.update(kwargs)

    # ── API call logging ─────────────────────────────────────────────────
    def log_call(
        self,
        *,
        stage: str,                     # "translate" | "split_ai" | "polish"
        block_index: int,
        lines_sent: List[str],
        system_prompt: str,
        user_prompt: str,
        raw_response: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        elapsed_seconds: float = 0.0,
        attempt: int = 1,              # 1 = first try, 2+ = retry
        error: Optional[str] = None,
    ) -> None:
        model = self._meta.get("model", "")
        self._calls.append({
            "timestamp":       datetime.now(timezone.utc).isoformat(),
            "stage":           stage,
            "block_index":     block_index,
            "attempt":         attempt,
            "lines_count":     len(lines_sent),
            "lines_sent":      lines_sent,
            "system_prompt":   system_prompt,
            "user_prompt":     user_prompt,
            "raw_response":    raw_response,
            "tokens": {
                "input":       input_tokens,
                "output":      output_tokens,
                "cached":      cached_tokens,
                "total":       input_tokens + output_tokens,
            },
            "cost_usd":        _calc_cost(model, input_tokens, cached_tokens, output_tokens),
            "elapsed_seconds": round(elapsed_seconds, 3),
            "error":           error,
            "ok":              error is None,
        })

    # ── Split operation logging ───────────────────────────────────────────
    def log_split(
        self,
        *,
        block_index: int,
        mode: str,                     # "classic" | "ai"
        lines_in: List[str],
        lines_out: List[str],
        elapsed_seconds: float = 0.0,
        error: Optional[str] = None,
    ) -> None:
        self._splits.append({
            "timestamp":       datetime.now(timezone.utc).isoformat(),
            "block_index":     block_index,
            "mode":            mode,
            "lines_in_count":  len(lines_in),
            "lines_out_count": len(lines_out),
            "lines_in":        lines_in,
            "lines_out":       lines_out,
            "elapsed_seconds": round(elapsed_seconds, 3),
            "error":           error,
        })

    # ── General event logging ─────────────────────────────────────────────
    def log_event(self, level: str, message: str, **extra: Any) -> None:
        """Log pipeline-level events: start, finish, warning, skip, etc."""
        self._events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level":     level.upper(),   # INFO | WARN | ERROR | DEBUG
            "message":   message,
            **extra,
        })

    # ── Save ──────────────────────────────────────────────────────────────
    def save(self) -> str:
        """Write the full log to disk. Returns path string."""
        try:
            summary = self._build_summary()
            payload = {
                "logger_version":  self.VERSION,
                "run_start":       self._run_start,
                "run_end":         datetime.now(timezone.utc).isoformat(),
                "run_metadata":    self._meta,
                "summary":         summary,
                "api_calls":       self._calls,
                "split_operations": self._splits,
                "events":          self._events,
            }
            self._log_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return str(self._log_path)
        except Exception as exc:
            print(f"WARN: PipelineFileLogger could not write log: {exc}")
            return ""

    # ── Internal ─────────────────────────────────────────────────────────
    def _build_summary(self) -> Dict[str, Any]:
        stages = {}
        total_input = total_output = total_cached = total_cost = 0.0
        total_elapsed = 0.0
        errors = 0

        for call in self._calls:
            s = call.get("stage", "unknown")
            if s not in stages:
                stages[s] = {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                              "cached_tokens": 0, "cost_usd": 0.0, "errors": 0}
            b = stages[s]
            b["calls"]          += 1
            b["input_tokens"]   += call["tokens"]["input"]
            b["output_tokens"]  += call["tokens"]["output"]
            b["cached_tokens"]  += call["tokens"]["cached"]
            b["cost_usd"]       += call["cost_usd"]
            if not call["ok"]:
                b["errors"] += 1
                errors       += 1
            total_input   += call["tokens"]["input"]
            total_output  += call["tokens"]["output"]
            total_cached  += call["tokens"]["cached"]
            total_cost    += call["cost_usd"]
            total_elapsed += call["elapsed_seconds"]

        return {
            "total_api_calls":    len(self._calls),
            "total_split_ops":    len(self._splits),
            "total_errors":       errors,
            "total_elapsed_sec":  round(total_elapsed, 2),
            "tokens": {
                "input":          int(total_input),
                "output":         int(total_output),
                "cached":         int(total_cached),
                "total":          int(total_input + total_output),
            },
            "estimated_cost_usd": round(total_cost, 6),
            "by_stage":           stages,
        }

    @property
    def log_path(self) -> str:
        return str(self._log_path)
