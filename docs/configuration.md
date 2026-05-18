# Configuration reference

> Every tunable in the codebase, in one place.
>
> Two sections: **environment variables** (operator-facing knobs) and **tuning constants** (in-code defaults that someone might want to change).
>
> Updated 2026-05-18.

---

## Environment variables

All variables are prefixed `MTD_` so they're easy to find with `git grep MTD_`.

### Pipeline behaviour

| Variable | Default | Purpose | File |
|---|---|---|---|
| `MTD_MAX_CONCURRENT_JOBS` | `2` | Cap on simultaneous backend subprocesses. Each loads python-docx + openai client + tiktoken (~250–500 MB). Third upload while two are running gets `status='queued'` and waits at the semaphore. | `local_launcher.py` |
| `MTD_FROZEN_ROOT` | unset | Set by the PyInstaller wrapper. Points to the bundled `prompts/` dir beside the .exe so a packaged user can drop a custom prompts directory without rebuilding. | `log_paths.py`, `translator.py` |
| `MTD_RUNTIME_DIR` | unset | Override for the launcher's runtime dir (defaults to `<tempdir>/machine_translate_docx_local`). Used by `server_config.py` to find `config.toml`. | `server_config.py` |
| `MTD_CONFIG_PATH` | unset | Explicit path to `config.toml` if you don't want the launcher to auto-resolve. | `server_config.py` |
| `MTD_DISABLE_SIDECAR` | unset | When `=1`, skip writing the per-run JSON sidecar log. | `docx_io/save.py` |

### OpenAI / model behaviour

| Variable | Default | Purpose | File |
|---|---|---|---|
| `MTD_FORCE_NON_STREAM` | unset | When `=1`, every Responses-API call (translator / polisher / splitter / aligner) uses non-stream mode. Emergency rollback only — the openai-python #2725 hang risk returns under non-stream. | `_stream_helper.py` |
| `MTD_STREAM_TRIP_THRESHOLD` | `3` | Consecutive stream failures required for the circuit breaker to trip OPEN. | `_stream_circuit.py` |
| `MTD_STREAM_COOLDOWN_SECONDS` | `3600` | How long the circuit stays OPEN before promoting to HALF_OPEN for a probe. | `_stream_circuit.py` |
| `MTD_STREAM_CIRCUIT_STATE_FILE` | (derived) | Override the persisted state file path. Default is `<tempdir>/machine_translate_docx_local/_stream_circuit.json`. Used by tests + hot-swap. | `_stream_circuit.py` |
| `MTD_POLISH_REASONING` | model-default | One of `none / low / medium / high / xhigh`. Overrides per-model defaults in `polisher.py`. `mini` defaults to `medium`; non-mini defaults to `none`. | `polisher.py` |
| `MTD_FA_ALIGNER_USE_LLM` | `0` | When `=1`, the Persian Double-Lines aligner uses LLM rescue for hard groups. Off by default — the mechanical aligner handles the vast majority of cases. | `persian_double_lines.py` |

### Diagnostics / logging

| Variable | Default | Purpose | File |
|---|---|---|---|
| `MTD_DEBUG_PAYLOADS` | unset | When `=1`, full user_message + response JSON are echoed to stdout. Default mode logs only a redacted summary so subtitle content doesn't leak into archived logs / Telegram failure alerts. | `translator.py`, `polisher.py`, `splitting.py` |
| `MTD_LOG_VERBOSE` | unset | When `=1`, the per-run sidecar JSON keeps `system_prompt`, `user_prompt`, and `response_raw` instead of dropping them. Multiplies log size; use only for debug. | `translator.py`, `polisher.py` |
| `MTD_VALIDATOR_ENABLED` | unset | When `=1`, post-translate / post-polish validators run and log findings. Off by default — validators are diagnostic, never reject output. | `validators/__init__.py` |
| `MTD_SKIP_STATS_BROWSER` | unset | When `=1`, `statistics.run_statistics` / `get_robot_usage_comment` early-return — saves a Chrome launch on the basic-split spawn (~22 s → ~8 s). | `statistics.py` |
| `MTD_SELENIUM_VERBOSE` | unset | When set, dump verbose Selenium driver logs. Off by default. | `engines/_base.py` |

### Network / security

| Variable | Default | Purpose | File |
|---|---|---|---|
| `MTD_NETWORK_ALLOW_HOSTS` | (built-in list) | Extra allowed hosts for outbound HTTP — appends to the built-in allowlist used by `_assert_safe_url`. Comma-separated. | `network_utils.py` |

### Notifications

| Variable | Default | Purpose | File |
|---|---|---|---|
| `MTD_TELEGRAM_TOKEN` | unset | When set with `MTD_TELEGRAM_CHAT_ID`, every Saturday at 12:00 in `MTD_SCHEDULER_TZ` the launcher uploads `subscribers.txt` as a Telegram document. | `local_launcher.py` |
| `MTD_TELEGRAM_CHAT_ID` | unset | Telegram chat ID to receive the weekly subscribers report. | `local_launcher.py` |
| `MTD_SCHEDULER_TZ` | `Europe/Paris` | Timezone for the weekly Telegram subscribers-report scheduler. | `local_launcher.py` |
| `MTD_FAILURE_EMAIL` | unset | Comma-separated list of email addresses to alert on backend subprocess failure. Requires SMTP config to also be present. | `local_launcher.py` |
| `MTD_FAILURE_WEBHOOK` | unset | Discord / generic webhook URL for failure alerts. POST with formatted body. | `local_launcher.py` |

### Engine: DeepL

| Variable | Default | Purpose | File |
|---|---|---|---|
| `MTD_DEEPL_EMAIL` | unset | DeepL.com login email. Used by the Selenium-driven DeepL engine. | `engines/deepl.py` |
| `MTD_DEEPL_PASSWORD` | unset | DeepL.com login password. | `engines/deepl.py` |
| `MTD_DEEPL_ENABLED` | unset | When `=1`, allow the DeepL engine to spawn even without credentials (use anonymous-tier limits). | `engines/deepl.py` |

### Tests

| Variable | Default | Purpose | File |
|---|---|---|---|
| `MTD_REGRESSION_LIVE` | unset | When `=1`, run live API tests in `tests/test_prompts_regression.py` (otherwise skipped). | `tests/test_prompts_regression.py` |

### External

| Variable | Default | Purpose | File |
|---|---|---|---|
| `OPENAI_API_KEY` | — | Required for any chatgpt / chatgpt-polish run. Strip from CLI args for security. | passed via env to subprocess |
| `HTTP_PROXY` / `HTTPS_PROXY` / etc. | — | The launcher **strips proxy env vars** before spawning the backend subprocess (security guard — see `.claude/rules/security.md`). | `local_launcher.py` |

---

## Tuning constants

Hardcoded values someone might want to tune. None are env-overridable today — change requires a code edit + tests.

### Retry / circuit / timeouts

| Constant | Default | File | Why this value |
|---|---|---|---|
| `MAX_RETRIES` | `5` | `_retry.py` | Empirical balance between transient-failure tolerance and runaway-cost risk. Combined with the `APITimeoutError → _NON_RETRYABLE` move, this won't bill 5× on hung calls (fixed 2026-05-17). |
| `TRIP_THRESHOLD` | `3` | `_stream_circuit.py` | Trip on 3 consecutive failures. Env override: `MTD_STREAM_TRIP_THRESHOLD`. |
| `COOLDOWN_SECONDS` | `3600` | `_stream_circuit.py` | 1-hour cooldown before probe. Env override: `MTD_STREAM_COOLDOWN_SECONDS`. |
| Translator timeout | `1800` | `translator.py` | 30 minutes. Bounded for very long documents on slow tier load. |
| Polisher timeout | `1800` | `polisher.py` | Same as translator. |
| Aligner LLM-rescue timeout | `120` | `persian_double_lines.py` | 2 minutes. Aligner LLM call is small + rare; long hangs there are bugs. |
| Splitter cache key | `mtd-splitter-v7` | `splitting.py` | Bumped on prompt change. |
| Translator cache key | `mtd-translator-v7.3` | `translator.py` | Bumped on prompt change. |
| Polisher cache key | `mtd-polisher-v7.6` | `polisher.py` | Bumped on prompt change. |
| Aligner cache key | `mtd-aligner-v7` | `persian_double_lines.py` | Bumped on prompt change. |
| Reconciler cache key | `mtd-reconciler-v7` | `line_count_reconciler.py` | Bumped on prompt change. |

### Models

| Constant | Default | File | Why |
|---|---|---|---|
| `DEFAULT_AI_MODEL` | `gpt-5.5` | `config.py` | Best-quality translator/polisher model as of 2026-05-18. Override via CLI `--aimodel`. |
| `ALIGNER_MODEL` | `gpt-5.4-mini` | `config.py` | **HARDCODED by invariant C** — must not change. Mechanical aligner is the primary path; LLM rescue is rare. |
| `RECONCILER_MODEL` | `gpt-5.4-mini` | `line_count_reconciler.py` | Cheap model for line-count correction. Always mini, never the user's main `--aimodel`. |
| `VALID_AI_MODELS` | whitelist | `config.py` | CLI rejects `--aimodel <unknown>` at parse time. Update when adding a new model. |

### Line-count reconciler

| Constant | Default | File | Why |
|---|---|---|---|
| `max_attempts` | `4` | `line_count_reconciler.py` | Bumped from 2 in audit B13 (2026-05-13) to give the mini model room to converge on dense documents. |

### Persian Double-Lines aligner

| Constant | Default | File | Why |
|---|---|---|---|
| `MAX_CHARS_PER_LINE` | `50` | `persian_double_lines.py` | Persian broadcast-grade chunk limit. Subtitle reading speed and screen width. |
| `MIN_TARGET` | `30` | `persian_double_lines.py` | Minimum chunk size for the doubling pass. |
| `TARGET_DOUBLE_RATIO` | `[0.25, 0.55]` | `persian_double_lines.py` | Acceptable doubling-ratio range — flag if outside. |

### Cache / retention

| Constant | Default | File | Why |
|---|---|---|---|
| `prompt_cache_retention` | `"24h"` | every OpenAI caller | Set in `extra_body`. 24h is the OpenAI maximum. **C4 invariant** — must stay on every OpenAI call. |
| Recent-runs cache TTL | 5 days | `local_launcher.py` | Bumped from 36h on 2026-05-15. Document payload-keyed cache used to skip re-translation on re-upload. |
| `_LOG_DIR_NAME` | `"Log json file"` | `log_paths.py` | Central per-run JSON sidecar folder under project root. |
| `_RETENTION_DAYS` | `10` | `log_paths.py` | Auto-purge JSON sidecars older than 10 days. |

### File handling

| Constant | Default | File | Why |
|---|---|---|---|
| File-name max length | `200` | `local_launcher.py` | Filesystem-safe max; longer names get truncated keeping the extension. |
| Upload size limit | Content-Length-driven | `local_launcher.py` | No explicit cap; trusts HTTP framing. |

---

## How this list is maintained

When you add a new env var or move a hardcoded value, **append a row here**. The audit prompt (used by the periodic deep-debug session) checks for env vars that exist in code but not in this table.

Also keep the short table in `CLAUDE.md` ("Runtime environment variables") in sync for the 8 most-touched vars. This file is the canonical extended reference; CLAUDE.md is the quick-skim version.

---

## See also

- [`CLAUDE.md`](../CLAUDE.md) — short env-var table (top 8) + project router
- [`PROJECT_MEMORY.md`](../PROJECT_MEMORY.md) — C1-C39 invariants (some of which lock specific constants)
- [`docs/quickref.md`](quickref.md) — one-page repo at a glance
- [`docs/index.md`](index.md) — index of all docs
