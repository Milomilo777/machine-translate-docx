# ADR 003: Python GUI Interoperability

## Context
The Python desktop GUI (`src\machine_translate_gui.py`) invokes the translation logic as a sub-process and parses its standard output (`stdout`) to track progress and extract the final file path. It is extremely fragile to unexpected output formatting.

## Decision
To prevent integration breakages:
1. **Manual CLI Parsing:** `TranslationCliRunner` manually parses raw `String[] args` instead of relying on Spring's auto-magic `--key=value` parsing, perfectly matching Python's space-separated arguments.
2. **Strict Regex Contracts:** The final file output uses an unformatted `System.out.println("Saved file name: " + path)` instead of `log.info()`, guaranteeing Python's regex matches.
3. **Hard Exits:** The CLI runner catches `Throwable` and explicitly calls `SpringApplication.exit` and `System.exit(0/1)` to ensure the Tomcat context does not keep the JVM alive, which would cause the Python sub-process to hang indefinitely.
