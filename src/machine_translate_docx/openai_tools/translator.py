import os
import uuid
import json
import time
import tiktoken
# 2026-05-13 (feat/exe-packaging): mysql.connector is an OPTIONAL
# dependency — only required when MARIADB_HOST is set in the
# environment. Top-level import broke PyInstaller builds for users who
# never touch the DB feature. Lazy-load inside `get_db_connection`.
from openai import OpenAI
from pathlib import Path
import re

from ._retry import call_with_retry, prompt_hash

# Single source of truth for the default model id. Centralised in
# `src/config.py` so a typo or rename only has to land in one place
# (W-3 + B-004 in docs/real-engine-test-findings.md).
try:
    from ..config import DEFAULT_AI_MODEL as _DEFAULT_AI_MODEL
except Exception:
    # Fallback when openai_tools is imported without `src/` on sys.path —
    # keeps the default in sync with config.py at the time of writing.
    _DEFAULT_AI_MODEL = "gpt-5.5"

# ── language-code normalisation ───────────────────────────────────────────────
_LANG_CODE_MAP = {
    "persian": "fa",
    "farsi":   "fa",
    "fa-ir":   "fa",
    "fa_ir":   "fa",
    "arabic":  "ar",
    "french":  "fr",
    "german":  "de",
    "spanish": "es",
    "chinese": "zh",
    "russian": "ru",
    "japanese":"ja",
    "korean":  "ko",
}


def _normalize_lang(lang: str) -> str:
    lower = lang.lower().strip()
    if lower in _LANG_CODE_MAP:
        return _LANG_CODE_MAP[lower]
    return lower.split("-")[0].split("_")[0]


# Maps normalised lang code → prompt file suffix (ISO 639-2/B uppercase)
_PROMPT_FILE_MAP = {
    'fa': 'PER',
    'ar': 'ARA',
}


def _prompt_lang_code(dest_lang: str) -> str:
    code = _normalize_lang(dest_lang)
    return _PROMPT_FILE_MAP.get(code, code)


def _find_prompts_dir(anchor: Path) -> Path:
    """Walk up from *anchor* to find the project-level prompts/ directory.

    Frozen-build hook (2026-05-13, feat/exe-packaging): PyInstaller
    bundles `prompts/` under ``sys._MEIPASS/prompts``. An explicit
    ``MTD_FROZEN_ROOT/prompts`` (set by the wrapper) overrides — that
    lets a packaged user drop a customised prompts directory beside the
    .exe without rebuilding.
    """
    import os as _os
    import sys as _sys
    frozen_root = _os.environ.get("MTD_FROZEN_ROOT", "").strip()
    if frozen_root:
        override = Path(frozen_root) / "prompts"
        if override.is_dir():
            return override
    meipass = getattr(_sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / "prompts"
        if bundled.is_dir():
            return bundled
    for candidate in [
        anchor / "../../../prompts",
        anchor / "../../prompts",
        anchor / "../prompts",
        anchor / "prompts",
    ]:
        resolved = candidate.resolve()
        if resolved.is_dir():
            return resolved
    raise FileNotFoundError(
        f"prompts/ directory not found (searched relative to {anchor})"
    )


class OpenAITranslator:
    # model="gpt-5.4-mini"  ← mini (cheaper, faster, lower quality)
    def __init__(self, model=_DEFAULT_AI_MODEL, filename=None):
        self.model = model
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        self.client = OpenAI(api_key=self.api_key)

        # DB persistence is opt-in. Only attempt to connect when MARIADB_HOST
        # is set in the environment — otherwise skip every DB call cheaply
        # and silently. Avoids two connection retries per API call when no
        # database is provisioned (most local-launcher runs).
        self.db_enabled = bool(os.environ.get("MARIADB_HOST"))
        self.db_config = {
            "host": os.environ.get("MARIADB_HOST", "localhost"),
            "user": os.environ.get("MARIADB_USER", "root"),
            "password": os.environ.get("MARIADB_PASSWORD", ""),
            "database": os.environ.get("MARIADB_DB", "translation")
        }

        self.doc_id = None
        self.filename = None
        self.last_call_data = {}

        if filename:
            self.set_filename(filename)

    def set_filename(self, filename):
        """Change active document context."""
        self.filename = filename
        self.doc_id = str(uuid.uuid4())
        if not self.db_enabled:
            print(f"[INFO] (db disabled) document: {self.filename} ({self.doc_id})")
            return
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO documents (doc_id, filename) VALUES (%s, %s)",
                (self.doc_id, self.filename)
            )
            conn.commit()
            print(f"[INFO] Created document: {self.filename} ({self.doc_id})")
        except Exception as e:
            print(f"[Warning] Failed to save document info: {e}")
        finally:
            try: cursor.close(); conn.close()
            except Exception: pass

    def get_db_connection(self):
        # Lazy import: optional dep, only needed when DB persistence is on.
        import mysql.connector  # noqa: WPS433 — intentional in-function import
        return mysql.connector.connect(**self.db_config)

    def get_doc_id(self):
        return self.doc_id

    # ── prompt loading ─────────────────────────────────────────────────────────

    def _load_system_prompt(self, source_lang: str, dest_lang: str) -> str:
        """
        Load the translation system prompt for *dest_lang*.
        Falls back to translate_universal.txt when no language-specific file exists.

        2026-05-15 (v7 STATIC + JOB_CONFIG): the system prompt is now
        byte-identical across all documents and language pairs. Language
        identity, line count, and input text are all supplied in the
        user message via a <JOB_CONFIG> + <LINES> envelope. This keeps
        the system prompt cacheable (OpenAI prompt cache needs the
        first ≥1024 tokens of the prefix to match byte-for-byte).

        For Persian (translate_PER.txt), the SMTV brand lexicon is
        prepended from a shared `_smtv_locks.txt` block. The combined
        string stays byte-identical across calls and the cache hits it.
        For other languages, translate_universal.txt is used standalone.

        The `source_lang` / `dest_lang` arguments are kept on the
        signature for API stability but are NO LONGER substituted into
        the prompt body; they are placed in the user message instead.
        """
        prompts_dir = _find_prompts_dir(Path(__file__).parent)
        lang_code   = _prompt_lang_code(dest_lang)
        specific    = prompts_dir / f"translate_{lang_code}.txt"
        universal   = prompts_dir / "translate_universal.txt"
        path = specific if specific.exists() else universal
        template = path.read_text(encoding="utf-8")

        # Persian: prepend the shared SMTV lexicon block.
        if specific.exists() and lang_code == "PER":
            shared = prompts_dir / "_smtv_locks.txt"
            if shared.exists():
                template = shared.read_text(encoding="utf-8") + "\n\n" + template

        # v7 contract: no template substitution. Both Persian-specific
        # prompts and the universal prompt are written without
        # `{SOURCE_LANG}` / `{DEST_LANG}` / `{N}` placeholders. The
        # template is returned verbatim so the cache prefix is stable.
        return template

    @staticmethod
    def _build_user_message(source_lang: str, dest_lang: str, text: str) -> str:
        """Return the JOB_CONFIG + LINES user payload.

        v7 STATIC + JOB_CONFIG layout: the user message starts with a
        small <JOB_CONFIG> block (source language, target language,
        line count N), followed by a <LINES> block containing the
        numbered input lines. The system prompt is generic; this
        envelope binds the per-job language pair to the static policy.

        Putting language identity in the user message (not the system
        prompt) is the GPT-5.5-recommended layout for maximum prompt
        cache reuse across language pairs.
        """
        from ._lang_descriptors import lang_descriptor
        lines = text.split("\n")
        n = len(lines)
        src_desc = lang_descriptor(source_lang)
        tgt_desc = lang_descriptor(dest_lang)
        numbered = "\n".join(f"Line {i + 1}: {line}" for i, line in enumerate(lines))
        return (
            "<JOB_CONFIG>\n"
            f"SOURCE_LANGUAGE: {src_desc}\n"
            f"TARGET_LANGUAGE: {tgt_desc}\n"
            f"N: {n}\n"
            "</JOB_CONFIG>\n"
            "\n"
            "<LINES>\n"
            f"{numbered}\n"
            "</LINES>"
        )

    # ── token / cost helpers ───────────────────────────────────────────────────

    @staticmethod
    def estimate_tokens(text: str) -> int:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

    @staticmethod
    def calculate_openai_cost(response_json):
        model = response_json.get("model", "")
        usage = response_json.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        # 2026-05-16 (P2.8): pricing table consolidated to
        # openai_tools._pricing.PRICES so future model adds touch one place.
        from ._pricing import get_price

        cached_tokens = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        non_cached_tokens = max(0, prompt_tokens - cached_tokens)

        price = get_price(model)

        if price is None:
            print(f"[WARN] No known pricing for model '{model}'. Cost will be set to 0.")
            return {
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "input_cost_usd": 0.0,
                "output_cost_usd": 0.0,
                "total_cost_usd": 0.0,
            }

        cached_price = price.get("cached", price["input"] * 0.1)
        input_cost  = (non_cached_tokens  / 1_000_000) * price["input"] \
                    + (cached_tokens      / 1_000_000) * cached_price
        output_cost = (completion_tokens  / 1_000_000) * price["output"]
        total_cost  = input_cost + output_cost

        print("Total cost in USD:", round(total_cost, 6))

        return {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "input_cost_usd":  round(input_cost,  6),
            "output_cost_usd": round(output_cost, 6),
            "total_cost_usd":  round(total_cost,  6),
        }

    # ── translation ────────────────────────────────────────────────────────────

    def translate(self, source_lang, dest_lang, text_to_translate):
        if not self.doc_id:
            print("[INFO] No document context. Generating new doc_id and using filename 'inline_text'.")
            self.set_filename("inline_text")

        lines         = text_to_translate.split("\n")
        n             = len(lines)
        system_prompt = self._load_system_prompt(source_lang, dest_lang)
        user_message  = self._build_user_message(source_lang, dest_lang, text_to_translate)

        # B5 (audit 2026-05-13): full user payload only goes to stdout when
        # `MTD_DEBUG_PAYLOADS=1` is set. By default we emit a redacted summary
        # — line count, first-line sample, token estimate — so production
        # logs don't archive subtitle content and Telegram failure alerts
        # don't accidentally exfiltrate document text.
        input_tokens = self.estimate_tokens(system_prompt + user_message)
        if os.environ.get("MTD_DEBUG_PAYLOADS") == "1":
            print("user_message:")
            print(user_message)
        else:
            _first_line = lines[0] if lines else ""
            _sample = _first_line[:80] + ("…" if len(_first_line) > 80 else "")
            print(
                f"[INFO] Translator input: {n} lines, est. {input_tokens} tokens. "
                f"First line: {_sample!r}"
            )
        print(f"Estimated number of input tokens: {input_tokens}")

        start_time = time.time()

        _messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ]

        # 2026-05-15 (cache reliability fix): pair prompt_cache_retention with
        # a stable prompt_cache_key. Without a stable key, OpenAI derives the
        # cache identity from request metadata (SDK version, headers, IP),
        # which can vary call-to-call and silently miss the cached prefix
        # even when the system prompt is byte-identical. A fixed key per
        # logical pipeline + prompt-version pins the cache lookup so every
        # translator call hits the same archived prefix.
        # Bump the version suffix whenever translate_PER.txt / _smtv_locks.txt
        # change in a non-backwards-compatible way; otherwise old/new prompts
        # collide on the same key and confuse the cache.
        _extra = {
            "prompt_cache_retention": "24h",
            "prompt_cache_key": "mtd-translator-v7.3",
        }

        # GPT-5.x models have broken prompt-caching via chat.completions (known
        # OpenAI bug — community.openai.com/t/caching-is-borked-for-gpt-5-models).
        # Routing them to the Responses API restores cache hits.
        _use_responses_api = (
            "pro" in self.model.lower()
            or self.model.lower().startswith("gpt-5")
        )

        if _use_responses_api:
            # C2: never spend reasoning tokens on the translator.
            # 2026-05-17 (FLYIN hang fix): use streaming for gpt-5.x via
            # Responses API. The non-streaming code path in openai-python
            # SDK hangs indefinitely on payloads >~25K tokens against
            # gpt-5 models (openai/openai-python#2725). Streaming uses a
            # different parse path that avoids the hang. Output text +
            # usage are reassembled from event chunks.
            #
            # 2026-05-18 hardening: ``MTD_FORCE_NON_STREAM=1`` degrades
            # this site to a non-streaming Responses-API call. Reserved
            # for emergency rollback only — non-streaming still has the
            # #2725 hang risk on gpt-5.x with large payloads.
            from ._stream_helper import (
                use_non_stream,
                maybe_log_unknown_event,
            )
            from ._stream_circuit import (
                record_stream_success,
                record_stream_failure,
            )
            if use_non_stream():
                print(
                    "[INFO] translator using non-stream Responses API "
                    "(rollback active: MTD_FORCE_NON_STREAM=1 or circuit "
                    "breaker OPEN); #2725 hang risk on large gpt-5.x payloads",
                    flush=True,
                )
                response = call_with_retry(
                    lambda: self.client.responses.create(
                        model=self.model,
                        input=_messages,
                        extra_body=_extra,
                        reasoning={"effort": "none"},
                        timeout=1800,
                    ),
                    label="translator.responses.create(non-stream)",
                )
            else:
                def _stream_call():
                    stream = self.client.responses.create(
                        model=self.model,
                        input=_messages,
                        extra_body=_extra,
                        reasoning={"effort": "none"},
                        timeout=1800,
                        stream=True,
                    )
                    _chunks: list[str] = []
                    _final = None
                    _delta_n = 0
                    for event in stream:
                        et = getattr(event, "type", "")
                        if et == "response.output_text.delta":
                            _chunks.append(getattr(event, "delta", "") or "")
                            _delta_n += 1
                            # B3 (2026-05-18): emit a tick every 50 deltas so
                            # the launcher can nudge the UI progress bar
                            # while the stream is still draining.
                            if _delta_n % 50 == 0:
                                print(f"[STREAM] role=translator chunks={_delta_n}", flush=True)
                        elif et == "response.completed":
                            _final = getattr(event, "response", None)
                        elif et in ("response.failed", "response.incomplete"):
                            _final = getattr(event, "response", None)
                            raise RuntimeError(
                                f"translator stream ended with type={et}: {_final}"
                            )
                        else:
                            # 2026-05-18 hardening: surface SDK changes
                            # (renamed / added event types) instead of
                            # silently dropping them.
                            maybe_log_unknown_event("translator", et)
                    return {"text": "".join(_chunks), "final": _final}

                stream_result = call_with_retry(
                    _stream_call,
                    label="translator.responses.create(stream)",
                )
                # Build a SimpleNamespace that mimics the non-streaming response
                # shape so the rest of the code below works unchanged.
                from types import SimpleNamespace
                _final = stream_result["final"]
                _text = stream_result["text"]
                # CODE-C-9 (2026-05-18 audit): when the stream ends without a
                # `response.completed` event (network reset, server early-
                # close), `_final` stays None. We still have the assembled
                # text, but token / cost usage is unknown — log it so the
                # sidecar zero is explainable. Also feed the outcome into
                # the circuit breaker so repeated failures auto-rollback.
                if _final is None:
                    print(
                        "[WARN] translator: stream ended without response.completed — "
                        "usage data unavailable, log sidecar will record zero tokens/cost",
                        flush=True,
                    )
                    record_stream_failure("translator", "no_response_completed")
                else:
                    record_stream_success("translator")
                response = SimpleNamespace(
                    output_text=_text,
                    model_dump=(lambda f: (lambda: f.model_dump()))(_final) if _final else (lambda: {}),
                )
        else:
            response = call_with_retry(
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=_messages,
                    extra_body=_extra,
                    timeout=1800,
                ),
                label="translator.chat.completions.create",
            )

        elapsed_time  = time.time() - start_time
        response_json = response.model_dump()

        # Normalize Responses-API usage shape -> Chat-Completions shape so
        # downstream cost calc + JSON sidecar work unchanged. Consolidated
        # to _retry.normalize_usage 2026-05-16 (P2.9).
        from ._retry import normalize_usage
        response_json = normalize_usage(response_json)

        # B5 (audit 2026-05-13): full response JSON only when explicitly
        # asked for. Default: usage + cost summary only.
        if os.environ.get("MTD_DEBUG_PAYLOADS") == "1":
            print("response:")
            print(json.dumps(response_json, indent=4))
            print("--end of response--")
        else:
            _u = response_json.get("usage") or {}
            print(
                f"[INFO] Translator response: model={response_json.get('model', self.model)}, "
                f"prompt={_u.get('prompt_tokens', '?')} (cached "
                f"{(_u.get('prompt_tokens_details') or {}).get('cached_tokens', 0)}), "
                f"completion={_u.get('completion_tokens', '?')}, "
                f"total={_u.get('total_tokens', '?')}"
            )

        cost_info = self.calculate_openai_cost(response_json)

        # Responses API exposes output_text directly; Chat Completions uses choices.
        if _use_responses_api and hasattr(response, "output_text") and response.output_text is not None:
            translated_text = response.output_text.strip()
        else:
            translated_text = response.choices[0].message.content.strip()
        translated_text = re.sub(r'\n+', '\n', translated_text)

        in_lines  = text_to_translate.split("\n")
        out_lines = translated_text.split("\n")

        if len(in_lines) != len(out_lines):
            # B6 (audit 2026-05-13): single-call mode routes through the
            # reconciler in chatgpt_api.py — that path is unaffected. The
            # per-block path lands here. We surface the mismatch loudly so
            # downstream (cell writer) sees the structural risk in stdout,
            # but still hand back the raw output to preserve the legacy
            # contract (some callers fix this themselves via reconciler).
            # The next refactor will lift this into a structured
            # TranslationFailure that the launcher can flag.
            print(
                f"[WARNING] Line count mismatch — "
                f"input={len(in_lines)} output={len(out_lines)}. "
                f"Downstream MUST reconcile; raw output retained for now."
            )
            translated_text = "\n".join(out_lines)

        # Save query record (only when DB persistence is enabled)
        if self.db_enabled:
            try:
                conn   = self.get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO queries
                    (doc_id, type, model_name, prompt_json, response_json, execution_time_sec,
                     input_tokens, output_tokens, total_tokens, cost_usd)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        self.doc_id,
                        "translate",
                        self.model,
                        json.dumps({"system": system_prompt, "user": user_message}),
                        json.dumps(response_json),
                        elapsed_time,
                        cost_info["prompt_tokens"],
                        cost_info["completion_tokens"],
                        cost_info["total_tokens"],
                        cost_info["total_cost_usd"],
                    )
                )
                conn.commit()
            except Exception as e:
                print(f"[Warning] Failed to save query info: {e}")
            finally:
                try: cursor.close(); conn.close()
                except Exception: pass

        # 2026-05-15 (log compaction): by default the sidecar records the
        # *metadata* of each API call (hash, tokens, cost, timing) but not
        # the prompt bodies — those are written ONCE at the run_info level
        # by cli.write_translation_log(), since they are byte-identical
        # across blocks. To audit a specific call's payload, set
        # MTD_LOG_VERBOSE=1 — that restores the legacy per-block fields.
        _verbose = os.environ.get("MTD_LOG_VERBOSE", "").strip() == "1"
        self.last_call_data = {
            "type":            "translate",
            "model":           self.model,
            "prompt_hash":     prompt_hash(system_prompt),
            "output_text":     translated_text,
            "tokens": {
                "prompt":      cost_info.get("prompt_tokens", 0),
                "completion":  cost_info.get("completion_tokens", 0),
                "total":       cost_info.get("total_tokens", 0),
                "cached":      (response_json.get("usage") or {})
                               .get("prompt_tokens_details", {})
                               .get("cached_tokens", 0),
            },
            "cost_usd":        cost_info.get("total_cost_usd", 0.0),
            "elapsed_seconds": round(elapsed_time, 3),
        }
        if _verbose:
            self.last_call_data["system_prompt"] = system_prompt
            self.last_call_data["user_prompt"]   = user_message
            self.last_call_data["response_raw"]  = response_json

        # Always remember the latest system prompt so the run_info section
        # of the sidecar can carry it ONCE per run, regardless of how many
        # blocks were translated. The full user-message envelope is also
        # cached so an auditor can see the JOB_CONFIG/LINES shape without
        # turning on verbose mode.
        self.last_system_prompt = system_prompt
        self.last_user_prompt   = user_message

        # 2026-05-15 (v7 follow-up): post-translation validator gate.
        # Disabled by default; opt in with MTD_VALIDATOR_ENABLED=1. The
        # report only logs to stdout — we never reject the translation
        # output because of validator findings (the legacy contract
        # always returns the model's output for the cell writer to
        # consume). The validator is a diagnostic. Future work: feed
        # error lines back into a tight repair-prompt loop.
        try:
            from ..validators import validate_translate_output, is_validator_enabled
            if is_validator_enabled():
                report = validate_translate_output(
                    source_lines=in_lines,
                    translate_output=out_lines,
                    target_lang=dest_lang,
                )
                if report.issues:
                    print(f"[validator] post-translate: {report.summary()}")
                    for issue in report.errors():
                        print(
                            f"[validator] ERROR line {issue.line_no}: "
                            f"{issue.code} — {issue.message}"
                        )
                    for issue in report.warnings():
                        print(
                            f"[validator] warn  line {issue.line_no}: "
                            f"{issue.code} — {issue.message}"
                        )
        except Exception as _e:
            # The validator must never break a job. Log and move on.
            print(f"[validator] post-translate gate skipped: {_e}")

        return response, translated_text
