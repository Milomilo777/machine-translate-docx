# UML — machine-translate-docx

> Five Mermaid-based UML diagrams covering the architecturally relevant
> facets of the project. Render natively in GitHub or any Mermaid-aware
> viewer (VS Code Mermaid extension, mermaid.live, GitHub web UI). This
> file is the companion to:
>
> - [`architecture.md`](architecture.md) — prose component breakdown.
> - [`diagrams/architecture-light.svg`](diagrams/architecture-light.svg) — high-level SVG.
> - [`diagrams/architecture-detailed-light.svg`](diagrams/architecture-detailed-light.svg) — full module-level SVG.

## Reflection — what UML buys us, and where it doesn't

Not everything in this project benefits from UML. Persian pipeline,
Selenium engines, and the OpenAI client wrappers are mostly functional
code; class diagrams of them would be padding. Where UML genuinely
helps:

| Aspect | Useful UML | Why |
|---|---|---|
| `RuntimeContext` composition | Class | 7 dataclasses, one root; a single picture beats 600 lines of reading. |
| Engine pluggability | Class | Protocol + 3 implementations is textbook OO. |
| Main pipeline | Sequence | 6 actors talk to each other; reading the call graph from code takes longer than glancing at the diagram. |
| Failure path | Sequence | 3 alert channels + archive + structured `[FAIL]` line, all conditional. |
| Job lifecycle decisions | Activity | Engine branch, polish gate, split branch, C13 lock — captured as a single flow chart. |
| Deployment topology | Deployment | Three surfaces (dev / prod / frozen `.exe`) differ in non-obvious ways. |

What is intentionally absent:
- **Use-case diagram** — one use case (translate a docx); the diagram
  would have one ellipse.
- **State diagram of an engine** — the only real state transition is
  the R15 DeepL `phrasesblock → singlephrase` fallback, which is
  captured in the activity diagram below.
- **Class diagram of every `openai_tools/*` class** — they are loosely
  coupled API wrappers without inheritance worth drawing.

---

## 1 — Class diagram

`RuntimeContext` composition + Engine protocol + OpenAI tool surface +
Validators + Exceptions. Methods are abbreviated where the body is
incidental.

```mermaid
classDiagram
    direction LR

    class RuntimeContext {
        +FlagsCtx flags
        +LanguageCtx language
        +EngineCtx engine
        +OpenAICtx openai
        +DocxCtx docx
        +BrowserCtx browser
        +ConfigCtx config
        +empty() RuntimeContext$
    }

    class FlagsCtx {
        +str word_file_to_translate
        +str word_file_to_translate_save_as_path
        +bool silent
        +bool splitonly
        +bool with_polish
        +bool use_api
        +str xlsxreplacefile
    }

    class LanguageCtx {
        +str src_lang
        +str dest_lang
        +str src_lang_name
        +str dest_lang_name
        +str dest_lang_tag
        +str dest_font
    }

    class EngineCtx {
        +str engine
        +str method
        +Callable dispatcher
    }

    class OpenAICtx {
        +OpenAITranslator translator
        +OpenAIPolisher polisher
        +dict translation_log
    }

    class DocxCtx {
        +Document docxdoc
        +int numrows
        +int numcols
        +list~str~ from_text_table
        +list~str~ to_text_by_phrase_separator_table
        +list~str~ translation_array
        +int docxfile_table_number_of_phrases
        +int translation_errors_count
        +dict source_columns_snapshot
    }

    class BrowserCtx {
        +WebDriver driver
        +module webdriver_module
        +Options chrome_options
        +bool google_translate_first_page_loaded
        +bool closed_cookies_accept_message_bool
        +bool logged_into_deepl
        +float deepl_sleep_wait_translation_seconds
    }

    class ConfigCtx {
        +list json_configuration_array
        +int max_translation_block_size
        +list shading_color_ignore_text
    }

    RuntimeContext *-- FlagsCtx
    RuntimeContext *-- LanguageCtx
    RuntimeContext *-- EngineCtx
    RuntimeContext *-- OpenAICtx
    RuntimeContext *-- DocxCtx
    RuntimeContext *-- BrowserCtx
    RuntimeContext *-- ConfigCtx

    class Engine {
        <<Protocol>>
        +translate(ctx, text) tuple~bool, str~
    }

    class GoogleEngine {
        +translate(ctx, text)
        +selenium_chrome_google_translate(ctx, text)
        +selenium_chrome_google_click_cookies_consent_button(ctx)
    }

    class DeepLEngine {
        +translate(ctx, text)
        +selenium_chrome_deepl_log_in(ctx)
        +selenium_chrome_deepl_log_off(ctx)
        +selenium_chrome_deepl_translate(ctx, text)
        +deepl_close_messages(ctx)
        +deepl_double_linefeed_between_phrases(dest_lang)$
    }

    class ChatGPTEngine {
        +run_openai_single_call(...)$
    }

    Engine <|.. GoogleEngine
    Engine <|.. DeepLEngine
    Engine <|.. ChatGPTEngine

    class OpenAITranslator {
        +str model
        +str dest_lang
        +OpenAI client
        +translate(src, dest, text) tuple
        +dict last_call_data
        +str last_system_prompt
    }

    class OpenAIPolisher {
        +str model
        +str dest_lang
        +str source_lang
        +OpenAI client
        +polish(source, translated) str
        +dict last_call_data
        +str system_prompt
    }

    class FASubtitleAligner {
        +str model
        +int llm_threshold
        +align(docxdoc) Document
        +dict last_stats
    }

    class OpenAISubtitleSplitter {
        +str model
        +str doc_id
        +set_model(model)
        +set_filename(filename)
    }

    OpenAICtx --> OpenAITranslator : has
    OpenAICtx --> OpenAIPolisher  : has

    class TranslationFailure {
        <<exception>>
        +str reason
        +str message
    }
    class EmptyDocxError
    class EmptyTranslationError

    TranslationFailure <|-- EmptyDocxError
    TranslationFailure <|-- EmptyTranslationError

    class ValidatorReport {
        +bool passed
        +list~ValidatorIssue~ issues
    }

    class ValidatorIssue {
        +str code
        +str message
        +int line_no
    }

    ValidatorReport *-- ValidatorIssue
```

Reading guide:
- `*--` (composition) = the parent owns the child's lifetime
  (RuntimeContext owns its sub-contexts; ValidatorReport owns its issues).
- `<|..` (interface realization) = the class implements the Protocol.
- `<|--` (inheritance) = exception hierarchy.

---

## 2 — Sequence diagram (happy path)

End-to-end translation, OpenAI `chatgpt --enginemethod api --with-polish`
shown as the main branch with `alt` blocks for the other engines.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Browser
    participant Launcher as local_launcher.py
    participant CLI as cli.py::main()
    participant Parse as docx_io.parse
    participant Dispatch as dispatch.py
    participant Runner as runner.py
    participant Engine as engines.*
    participant TR as openai_tools.translator
    participant PL as openai_tools.polisher
    participant Save as docx_io.save
    participant Log as translation_log_writer

    User->>Browser: drag-drop .docx
    Browser->>Launcher: POST /upload (multipart)
    Launcher->>Launcher: _validate_docx_payload (magic + 50 MB)
    Launcher->>Launcher: register jobId, _strip_timestamp
    Launcher->>CLI: subprocess.Popen([python, -m, cli, ...])

    Note over CLI: argparse · RuntimeContext bootstrap · proxy stripped
    CLI->>Parse: read_and_parse_docx_document(ctx)
    Parse->>Parse: snapshot cols 0+1 (C13 lock)
    Parse-->>CLI: ctx.docx.* arrays populated

    CLI->>CLI: assert_source_has_content(ctx)
    CLI->>Dispatch: set_translation_function(ctx)
    Dispatch-->>CLI: ctx.engine.dispatcher assigned

    alt engine=chatgpt + method=api (single-call path)
        CLI->>Runner: run_openai_single_call
        Runner->>TR: translate(src_name, dest_name, full_source)
        TR-->>Runner: full_translated + last_call_data
        opt --with-polish
            Runner->>PL: polish(full_source, full_translated)
            PL-->>Runner: polished_text + last_call_data
        end
        Runner->>Runner: append block to ctx.openai.translation_log
    else engine=google / deepl (block-loop path)
        CLI->>Runner: selenium_chrome_translate_maxchar_blocks(ctx)
        loop per block
            Runner->>Engine: translate(ctx, block)
            Engine-->>Runner: (success, translated_block)
            alt success=False (R15 fallback for deepl)
                Runner->>Dispatch: flip method to singlephrase
                Runner->>Runner: rebuild driver
            end
        end
    end
    Runner-->>CLI: ctx.docx.translation_array populated

    CLI->>CLI: assert_translation_present(ctx)
    CLI->>CLI: document_split_phrases(ctx)
    CLI->>Save: save_docx_file(ctx)
    Save->>Save: _restore_source_column (C13 lock check)
    Save->>Log: write_translation_log(ctx, log_path)
    Log->>Log: aggregate tokens · cost · cached
    Log-->>Save: JSON sidecar written

    Save-->>CLI: docx + sidecar on disk
    CLI->>Launcher: stdout "Saved file name: ..."
    CLI-->>Launcher: exit 0

    Launcher->>Launcher: jobs[id].status = "done"
    Browser->>Launcher: GET /status/<id> (poll every 4s)
    Launcher-->>Browser: { done, filename }
    Browser->>Launcher: GET /download/<filename>
    Launcher-->>User: translated .docx
```

---

## 3 — Sequence diagram (failure + alerting)

What happens when the pipeline fails. Captures B-001 (structured
failure exit), B-002 (failure archive), and the three alert channels.

```mermaid
sequenceDiagram
    participant CLI as cli.py::main()
    participant Health as translation_health
    participant Launcher as local_launcher.py
    participant Archive as runtime_dir/failures/
    participant Telegram
    participant Email as smtplib (Email)
    participant Webhook

    CLI->>Health: assert_source_has_content(ctx)
    alt source docx empty / no translatable rows
        Health-->>CLI: raise EmptyDocxError
        CLI->>CLI: print [FAIL] reason=empty_source ...
        CLI-->>Launcher: sys.exit(20)
    end

    CLI->>Health: assert_translation_present(ctx)
    alt engine returned empty translation array
        Health-->>CLI: raise EmptyTranslationError
        CLI->>CLI: print [FAIL] reason=empty_translation ...
        CLI-->>Launcher: sys.exit(20)
    end

    Launcher->>Launcher: parse stdout for [FAIL] reason=token

    Launcher->>Archive: copy input.docx (verbatim)
    Launcher->>Archive: copy stdout.log
    Launcher->>Archive: write meta.json + UNREVIEWED.txt

    opt MTD_TELEGRAM_TOKEN + CHAT_ID set
        Launcher->>Telegram: text alert
        opt docx <= 20 MB and MTD_TELEGRAM_NO_ATTACHMENT unset
            Launcher->>Telegram: send docx as document
        end
    end
    opt MTD_FAILURE_EMAIL set
        Launcher->>Email: SMTP send (best-effort)
    end
    opt MTD_FAILURE_WEBHOOK set
        Launcher->>Webhook: POST {reason, jobId, message}
    end

    Note over Launcher: alert delivery never blocks the failure-archive write

    Launcher->>Launcher: jobs[id].status = "error", reason recorded
```

---

## 4 — Activity diagram (job lifecycle)

The full decision tree from upload to download, including every branch
point. Square boxes are actions; diamonds are decisions; double-ended
boxes are terminal states.

```mermaid
flowchart TD
    A([User drops .docx on /v2/ or /]) --> B[POST /upload]
    B --> C{magic bytes OK<br/>size &le; 50 MB?}
    C -->|no| F0([400 Bad Request])
    C -->|yes| D[register jobId, spawn subprocess]

    D --> E[read_and_parse_docx_document]
    E --> E1[snapshot cols 0+1 - C13 lock]
    E1 --> F{source has<br/>content?}
    F -->|no| F1[/FAIL reason=empty_source/]
    F -->|yes| G[set_translation_function]

    G --> H{engine}
    H -->|chatgpt+api| I[single-call full-doc translate]
    H -->|google / deepl| J[block-loop translate per block]
    J --> J1{engine returned<br/>success?}
    J1 -->|deepl+phrasesblock<br/>failed| J2[flip to singlephrase<br/>rebuild driver]
    J2 --> J
    J1 -->|yes| L
    I --> L{--with-polish?}
    L -->|yes| M[OpenAIPolisher.polish]
    L -->|no| N{translation<br/>present?}
    M --> N

    N -->|no| F2[/FAIL reason=empty_translation/]
    N -->|yes| O{split method?}
    O -->|persian_double_lines<br/>FA target| P[FASubtitleAligner.align]
    O -->|none / basic| Q[skip split]
    P --> Q

    Q --> R[save_docx_file]
    R --> R1[restore source cols 0+1<br/>C13 enforcement]
    R1 --> R2[write JSON sidecar via<br/>translation_log_writer]
    R2 --> S([Saved file name:<br/>exit 0])
    S --> T[launcher: jobs id = done]
    T --> U([user downloads .docx])

    F1 --> FAIL[copy to failures dir]
    F2 --> FAIL
    FAIL --> FAIL1[Telegram / Email / Webhook]
    FAIL1 --> FAIL2([UI shows error reason])

    classDef terminal fill:#F2F7EF,stroke:#A8C49A,stroke-width:2
    classDef bad     fill:#FBEFE9,stroke:#E4A382,stroke-width:2
    classDef decide  fill:#FAF9F5,stroke:#E8E4D9
    class A,F0,F1,F2,S,U,FAIL2 terminal
    class FAIL,FAIL1 bad
    class C,F,H,J1,L,N,O decide
```

---

## 5 — Deployment diagram

Three production surfaces with different bill-of-materials. The CLI is
the same; the wrapper changes.

```mermaid
flowchart LR
    subgraph DEV [Dev / Windows / single operator]
        direction TB
        D_B[Browser /v2/ or /]
        D_L["local_launcher.py<br/>(stdlib http.server)"]
        D_C["python -m machine_translate_docx.cli"]
        D_DISK["runtime_dir/<br/>cache (5d) · failures/ · Log json file/"]
        D_B -->|HTTP localhost:3000| D_L
        D_L -->|subprocess.Popen| D_C
        D_C --> D_DISK
    end

    subgraph PROD [Linux production server]
        direction TB
        P_B[Browser]
        P_E["server.js<br/>(Express + multer)"]
        P_L["local_launcher.py<br/>(or Express direct spawn)"]
        P_C["python -m machine_translate_docx.cli"]
        P_DISK["uploads/ · Log json file/<br/>(path-confined download)"]
        P_B -->|HTTPS| P_E
        P_E -->|spawn| P_L
        P_L -->|subprocess.Popen| P_C
        P_C --> P_DISK
    end

    subgraph EXE [Frozen .exe / no Python on host]
        direction TB
        E_U[Operator double-clicks mtd.exe]
        E_BUNDLE["dist/mtd/mtd.exe (~65 MB onedir)<br/>no Python · no Chrome · no MariaDB"]
        E_CLI["machine_translate_docx.cli<br/>+ bundled prompts/ + tiktoken BPE"]
        E_DISK["Log json file/<br/>next to .exe<br/>(MTD_FROZEN_ROOT)"]
        E_U --> E_BUNDLE
        E_BUNDLE --> E_CLI
        E_CLI --> E_DISK
    end

    DEV ~~~ PROD
    PROD ~~~ EXE
```

Key differences between the three surfaces:

| Aspect | Dev | Prod | Frozen .exe |
|---|---|---|---|
| HTTP shell | `local_launcher.py` | `server.js` + Express | (none — CLI direct) |
| Path-traversal check | yes | yes (P0-1 fix, 2026-05-16) | n/a |
| Chrome required | yes (Google / DeepL) | yes | only if engine is not chatgpt+api |
| OpenAI API key | env var | env var (subprocess only) | env var or runtime prompt |
| Cache location | `runtime_dir/cache/` | `uploads/` + cache | `Log json file/` only |
| Failure alerts | yes | yes | yes (if env vars set) |
| Telemetry | local stdout | server log + alerts | local stdout |

---

## Maintenance

Update this file when:
- a new sub-context is added to `RuntimeContext` → bump section 1
- a new engine joins `engines/` → bump sections 1 + 4
- a new failure path lands → bump section 3
- a new deployment surface ships → bump section 5

Last refreshed: 2026-05-16 (after the cli.py 3-phase shrink + Sprint A/B/C audit follow-up).
