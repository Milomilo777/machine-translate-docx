"""
gui_translate_polish.py
GUI for docx_translate_polish module — SMTV Translation Lab
"""
import os
import sys
import threading
import json
from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk

# ── Path setup ────────────────────────────────────────────────────────────────
_src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

# ── GUI state persistence ─────────────────────────────────────────────────────
_GUI_STATE_FILE = Path(__file__).parent / "gui_translate_polish_state.json"

def _load_gui_state() -> dict:
    try:
        return json.loads(_GUI_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_gui_state(updates: dict):
    state = _load_gui_state()
    state.update(updates)
    try:
        _GUI_STATE_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass

# ── Model / Reasoning — SINGLE SOURCE OF TRUTH ───────────────────────────────
# NOTE: These will be moved to module config once config.py is finalised.
# GUI reads these only — no logic here.
MODELS = [
    {"label": "ChatGPT 5.4",        "id": "chatgpt-5.4"},
    {"label": "ChatGPT 5.4 Mini",   "id": "chatgpt-5.4-mini"},
]
REASONING_LEVELS = ["medium", "high", "xhigh"]
DEFAULT_MODEL_LABEL    = "ChatGPT 5.4"
DEFAULT_REASONING      = "medium"

def _menu_values() -> list:
    return [f"{m['label']}  [{r}]" for m in MODELS for r in REASONING_LEVELS]

def _default_value() -> str:
    return f"{DEFAULT_MODEL_LABEL}  [{DEFAULT_REASONING}]"

def _parse_selection(label: str) -> tuple:
    for m in MODELS:
        if m["label"] in label:
            for r in REASONING_LEVELS:
                if f"[{r}]" in label:
                    return m["id"], r
    return MODELS[0]["id"], DEFAULT_REASONING

# ── Engine rows config ────────────────────────────────────────────────────────
ENGINE_ROWS = [
    {"key": "translate", "label": "Translate Engine", "color": "#1a5276", "enabled": True},
    {"key": "polish",    "label": "Polish Engine",    "color": "#5b2c6f", "enabled": False},
    {"key": "split",     "label": "Splitting Engine", "color": "#1e6b3a", "enabled": False},
]

# ── App ───────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class TranslatePolishApp(ctk.CTk):
    SETTINGS_FILE = "translate_polish_settings.json"

    def __init__(self):
        super().__init__()
        self.settings   = self._load_settings()
        self._stop_flag = threading.Event()
        self._engine_vars: dict = {}

        self.title("SMTV · docx_translate_polish")
        self.geometry("720x1020")
        self.minsize(620, 820)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(8, weight=1)  # log row expands

        self._build_title()        # row 0
        self._build_file_row()     # row 1
        self._build_dict_row()     # row 2
        self._build_engines()      # row 3
        self._build_action_row()   # row 4
        self._build_progress()     # row 5
        self._build_status_bar()   # row 6
        self._build_log()          # row 8

        self._restore_last_state()
        self._log("✅  GUI ready — docx_translate_polish")
        self._log("ℹ️   All model config is read from module. No logic in GUI.")

    # ── UI BUILDERS ───────────────────────────────────────────────────────────

    def _build_title(self):
        ctk.CTkLabel(
            self,
            text="SMTV · Translate + Polish + Split",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(16, 2), sticky="w")

    def _build_file_row(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid(row=1, column=0, padx=20, pady=(4, 2), sticky="ew")
        f.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(f, text="DOCX File",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=0, column=0, sticky="w", pady=(0, 3))

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew")
        row.grid_columnconfigure(0, weight=1)

        self.file_entry = ctk.CTkEntry(
            row, placeholder_text="Select a DOCX file…",
            height=36, font=ctk.CTkFont(size=13),
        )
        self.file_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        ctk.CTkButton(
            row, text="Browse", width=90, height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._browse_docx,
        ).grid(row=0, column=1)

        # clear button
        ctk.CTkButton(
            row, text="✕", width=36, height=36,
            fg_color="#3a3a3a", hover_color="#555",
            font=ctk.CTkFont(size=13),
            command=lambda: self.file_entry.delete(0, "end"),
        ).grid(row=0, column=2, padx=(4, 0))

    def _build_dict_row(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid(row=2, column=0, padx=20, pady=(2, 6), sticky="ew")
        f.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(f, text="Excel Dictionary  (Optional)",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=0, column=0, sticky="w", pady=(0, 3))

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew")
        row.grid_columnconfigure(0, weight=1)

        self.dict_entry = ctk.CTkEntry(
            row, placeholder_text="Select an XLSX dictionary file…",
            height=36, font=ctk.CTkFont(size=13),
        )
        self.dict_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        ctk.CTkButton(
            row, text="Browse", width=90, height=36,
            fg_color="#2c3e50", hover_color="#3d5166",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._browse_dict,
        ).grid(row=0, column=1)

        ctk.CTkButton(
            row, text="✕", width=36, height=36,
            fg_color="#3a3a3a", hover_color="#555",
            font=ctk.CTkFont(size=13),
            command=lambda: self.dict_entry.delete(0, "end"),
        ).grid(row=0, column=2, padx=(4, 0))

    def _build_engines(self):
        outer = ctk.CTkFrame(self)
        outer.grid(row=3, column=0, padx=20, pady=(2, 6), sticky="ew")
        outer.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            outer, text="Engine Configuration",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, padx=14, pady=(10, 6), sticky="w")

        values  = _menu_values()
        default = _default_value()

        for i, eng in enumerate(ENGINE_ROWS, start=1):
            badge = ctk.CTkLabel(
                outer, text=eng["label"],
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="white",
                fg_color=eng["color"],
                corner_radius=6, width=138,
            )
            badge.grid(row=i, column=0, padx=(14, 8), pady=5, sticky="w")

            saved = self.settings.get(f"engine_{eng['key']}", default)
            var   = ctk.StringVar(value=saved)
            self._engine_vars[eng["key"]] = var

            combo = ctk.CTkComboBox(
                outer, values=values, variable=var,
                state="readonly" if eng["enabled"] else "disabled",
                height=32, font=ctk.CTkFont(size=12),
            )
            combo.grid(row=i, column=1, padx=(0, 10), pady=5, sticky="ew")

            if not eng["enabled"]:
                ctk.CTkLabel(
                    outer, text="coming soon",
                    font=ctk.CTkFont(size=11), text_color="#666666",
                ).grid(row=i, column=2, padx=(0, 14), sticky="w")

        ctk.CTkFrame(outer, height=1, fg_color="#444444").grid(
            row=len(ENGINE_ROWS) + 1, column=0, columnspan=3,
            padx=14, pady=(8, 10), sticky="ew",
        )

    def _build_action_row(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid(row=4, column=0, padx=20, pady=(0, 6), sticky="ew")
        f.grid_columnconfigure(0, weight=1)

        self.btn_translate = ctk.CTkButton(
            f, text="▶  Translate (Raw)", height=48,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#1a5276", hover_color="#2471a3",
            command=self._on_translate,
        )
        self.btn_translate.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self.btn_stop = ctk.CTkButton(
            f, text="⏹  Stop", height=48, width=110,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#922b21", hover_color="#c0392b",
            state="disabled",
            command=self._on_stop,
        )
        self.btn_stop.grid(row=0, column=1, sticky="ew")

    def _build_progress(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid(row=5, column=0, padx=20, pady=(0, 2), sticky="ew")
        f.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(f, height=10)
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        self.progress_bar.set(0)

        self.progress_lbl = ctk.CTkLabel(
            f, text="Idle", font=ctk.CTkFont(size=11), text_color="#888888"
        )
        self.progress_lbl.grid(row=1, column=0, sticky="w", pady=(2, 0))

    def _build_status_bar(self):
        """One-line status strip showing last file + model used."""
        self.status_bar = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=11), text_color="#777777",
            anchor="w",
        )
        self.status_bar.grid(row=6, column=0, padx=22, pady=(0, 4), sticky="ew")

    def _build_log(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid(row=8, column=0, padx=20, pady=(4, 18), sticky="nsew")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)

        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text="Debug Log",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            hdr, text="Copy Debug Log", width=110, height=26,
            font=ctk.CTkFont(size=12),
            command=self._copy_log,
        ).grid(row=0, column=1, padx=(0, 6), sticky="e")

        ctk.CTkButton(
            hdr, text="Clear", width=60, height=26,
            font=ctk.CTkFont(size=12),
            fg_color="#3a3a3a", hover_color="#555555",
            command=self._clear_log,
        ).grid(row=0, column=2, sticky="e")

        self.log_box = ctk.CTkTextbox(
            f, wrap="word",
            font=ctk.CTkFont(family="Consolas", size=12),
            height=340,
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.log_box.configure(state="normal")
        self.log_box.bind("<Key>", self._prevent_typing)

    # ── STATE / SETTINGS ──────────────────────────────────────────────────────

    def _restore_last_state(self):
        state = _load_gui_state()

        last_docx = state.get("last_docx", "")
        if last_docx and Path(last_docx).exists():
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, last_docx)

        last_dict = state.get("last_dict", "")
        if last_dict and Path(last_dict).exists():
            self.dict_entry.delete(0, "end")
            self.dict_entry.insert(0, last_dict)

    def _load_settings(self) -> dict:
        try:
            p = Path(self.SETTINGS_FILE)
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_settings(self):
        data = {f"engine_{k}": v.get() for k, v in self._engine_vars.items()}
        try:
            Path(self.SETTINGS_FILE).write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    # ── FILE BROWSE ───────────────────────────────────────────────────────────

    def _browse_docx(self):
        initial = _load_gui_state().get("last_dir_docx", os.path.expanduser("~"))
        path = filedialog.askopenfilename(
            initialdir=initial, title="Select DOCX File",
            filetypes=[("Word Documents", "*.docx"), ("All Files", "*.*")],
        )
        if path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, path)
            _save_gui_state({"last_docx": path,
                             "last_dir_docx": os.path.dirname(path)})
            self._log(f"📄  Selected DOCX: {os.path.basename(path)}")

    def _browse_dict(self):
        initial = _load_gui_state().get("last_dir_dict", os.path.expanduser("~"))
        path = filedialog.askopenfilename(
            initialdir=initial, title="Select Excel Dictionary",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
        )
        if path:
            self.dict_entry.delete(0, "end")
            self.dict_entry.insert(0, path)
            _save_gui_state({"last_dict": path,
                             "last_dir_dict": os.path.dirname(path)})
            self._log(f"📚  Dictionary: {os.path.basename(path)}")

    # ── TRANSLATE ACTION ──────────────────────────────────────────────────────

    def _on_translate(self):
        file_path = self.file_entry.get().strip()
        if not file_path or not os.path.exists(file_path):
            self._log("⚠️  Please select a valid DOCX file first.")
            return

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            self._log("⚠️  OPENAI_API_KEY not found in environment variables.")
            return

        model_id, reasoning = _parse_selection(
            self._engine_vars["translate"].get()
        )
        dict_path = self.dict_entry.get().strip() or None

        self._save_settings()
        self._stop_flag.clear()
        self._set_busy(True)
        self.progress_bar.set(0)
        self._set_progress("Starting…")

        fname = os.path.basename(file_path)
        self.status_bar.configure(
            text=f"Processing: {fname}   |   {model_id}  [{reasoning}]"
        )

        self._log("━" * 52)
        self._log("🚀  Translate (Raw) — docx_translate_polish")
        self._log(f"📄  File     : {fname}")
        self._log(f"📚  Dict     : {os.path.basename(dict_path) if dict_path else '—'}")
        self._log(f"🤖  Model    : {model_id}")
        self._log(f"🧠  Reasoning: {reasoning}")
        self._log("━" * 52)

        threading.Thread(
            target=self._translate_thread,
            args=(file_path, api_key, model_id, reasoning, dict_path),
            daemon=True,
        ).start()

    def _translate_thread(self, file_path, api_key, model_id, reasoning, dict_path):
        try:
            from docx_translate_polish.core.config import TranslationConfig
            from docx_translate_polish.pipeline import TranslationPipeline

            self._log("✅  Module imported.")
            self._set_progress("Module loaded…")

            cfg = TranslationConfig(
                openai_api_key=api_key,
                model=model_id,
                reasoning=reasoning,
                xlsx_dict_path=dict_path,
            )

            def _cb(msg: str, pct=None):
                self._log(f"   {msg}")
                if pct is not None:
                    self.after(0, lambda p=pct: self.progress_bar.set(p))
                    self.after(0, lambda m=msg: self._set_progress(m))
                if self._stop_flag.is_set():
                    raise InterruptedError("Stopped by user.")

            pipeline = TranslationPipeline(cfg, progress_callback=_cb)
            output   = pipeline.run(file_path)
            self.after(0, lambda: self._on_done(output))

        except InterruptedError:
            self.after(0, lambda: self._log("🛑  Stopped by user."))
            self.after(0, lambda: self._set_busy(False))
            self.after(0, lambda: self.status_bar.configure(text="Stopped."))
        except ImportError as e:
            self.after(0, lambda: self._log(f"❌  Import error: {e}"))
            self.after(0, lambda: self._log(
                "ℹ️   Make sure src/docx_translate_polish is reachable."
            ))
            self.after(0, lambda: self._set_busy(False))
        except Exception as e:
            self.after(0, lambda: self._log(f"❌  {type(e).__name__}: {e}"))
            self.after(0, lambda: self._set_busy(False))

    def _on_done(self, output_path: str):
        self.progress_bar.set(1.0)
        self._set_progress("Done ✅")
        self._log("━" * 52)
        self._log("✅  Translation complete!")
        self._log(f"💾  Output : {os.path.basename(output_path)}")
        self._log(f"📁  Path   : {output_path}")
        self._log("━" * 52)
        self.status_bar.configure(
            text=f"Done ✅  →  {os.path.basename(output_path)}"
        )
        self._set_busy(False)

    def _on_stop(self):
        self._stop_flag.set()
        self._log("🛑  Stop requested…")

    # ── UI HELPERS ────────────────────────────────────────────────────────────

    def _set_busy(self, busy: bool):
        self.btn_translate.configure(state="disabled" if busy else "normal")
        self.btn_stop.configure(state="normal" if busy else "disabled")

    def _set_progress(self, msg: str):
        self.after(0, lambda: self.progress_lbl.configure(text=msg))

    def _log(self, message: str):
        def _up():
            self.log_box.insert("end", str(message) + "\n")
            self.log_box.see("end")
        self.after(0, _up)

    def _copy_log(self):
        self.clipboard_clear()
        self.clipboard_append(self.log_box.get("1.0", "end-1c"))
        self._log("📋  Debug log copied to clipboard.")

    def _clear_log(self):
        self.log_box.delete("1.0", "end")

    def _prevent_typing(self, event):
        nav = ("Up", "Down", "Left", "Right", "Prior",
               "Next", "Home", "End", "Control_L", "Control_R")
        if event.keysym in nav:
            return None
        if event.state & 0x0004 and event.keysym.lower() in ("c", "a"):
            return None
        return "break"


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = TranslatePolishApp()
    app.mainloop()
