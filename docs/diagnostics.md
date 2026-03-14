# Central Diagnostic Bundle Engine

The **Central Diagnostic Bundle Engine** (`src/diagnostics/bundle_manager.py`) provides structured, robust error tracking across the machine-translate-docx pipelines (Translate, Polish, Align, and Double).

## Purpose
Previous versions of this tool relied on basic print statements which made diagnosing API timeouts, JSON decode failures, and UI crashes difficult. The new system automatically intercepts exceptions and writes comprehensive "Diagnostic Bundles" out to JSON files.

These bundles can be requested by the development team from end-users to quickly identify the root cause of an issue.

## Where to find logs
When a critical pipeline error occurs, a diagnostic bundle is generated in the `logs` directory using the following structure:
```
logs/<file_name>/<timestamp>_failure/diagnostic_bundle.json
```
For example:
```
logs/document.docx/20260314_103000_failure/diagnostic_bundle.json
```

## What is captured
Each `diagnostic_bundle.json` contains:
1. **timestamp**: The exact time of the error in UTC.
2. **file_name**: The document being processed.
3. **stage**: The execution pipeline stage (e.g., `init`, `translate`, `polish`, `align_json`, `double`, `google_translate_html_javascript_file`).
4. **error**: The stringified Exception message.
5. **traceback**: The full python traceback indicating where the error was thrown.
6. **payload** (Optional): The data payload that caused the failure (e.g., the JSON `target_dict` or `text_to_translate`).
7. **state** (Optional): Relevant program state (e.g., `doc_id`, `model`).

### Security
The bundle engine automatically redacts sensitive information. If a payload or state dictionary contains keys resembling `api_key`, `token`, `secret`, or `password`, their values will be replaced with `[REDACTED]` before saving.

## Indexing and Log Retention
To prevent logs from consuming infinite space and to make finding the right logs easier, the Diagnostic Bundle Engine maintains two helpful index mechanisms:

### Global Registry (`logs/index.json`)
Every time a bundle is created, its high-level summary (file, stage, timestamp, error) is appended to a global `logs/index.json` registry file. This file acts as a centralized dashboard.

### Latest Pointer (`logs/<file_name>/latest_status.json`)
Inside every individual document's log directory, a `latest_status.json` file is maintained. This file is continuously overwritten and will always contain the full `diagnostic_bundle.json` contents of the *most recent* failure for that specific document.

### Retention Policy
The global registry array is capped at a maximum of **50 entries**. When the 51st error occurs, the oldest entry in the index is dropped. *(Note: This currently limits the JSON index size; future versions may also delete the physical folders).*

## Telemetry and Standardized JSON Schema
For observability and integrations with systems like Datadog, ELK, or generic dashboards, all bundles follow a strictly typed schema. A unified **Trace ID** correlates actions across multiple pipelines on the same document:

1. **`trace_id`**: An identifier (e.g., UUID) passed throughout the Translate/Polish/Align/Double layers to link log entries. If none is passed, one is randomly generated.
2. **`timestamp`**: UTC.
3. **`file_name`**: Document Name.
4. **`stage`**: Execution stage tag.
5. **`level`**: Always set to `ERROR`.
6. **`error_message`**: Clean string exception message.
7. **`traceback`**: Detailed execution stack.
8. **`payload`**: The original action dictionary (with secrets masked out as `***`).
