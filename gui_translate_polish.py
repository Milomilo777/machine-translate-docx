"""GUI for the extracted docx_translate_polish module.

Designed to stay thin: UI collects selections and calls the module pipeline.
Current branch compatibility:
- TranslationConfig(openai_api_key=..., default_model=...)
- TranslationPipeline.run(input_path, src_lang, dest_lang, output_path=None, splitting_mode='classic')
"""
import json
import os
import sys
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

# --- Path bootstrap -----------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# --- State files --------------------------------------------------------------
SETTINGS_FILE = BASE_DIR / "translate_polish_settings.json"
GUI_STATE_FILE = BASE_DIR / "gui_translate_polish_state.json"


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json(path: Path, data: dict):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# --- Module-driven language map ----------------------------------------------
def load_language_map() -> dict:
    try:
        from docx_translate_polish.core.config import TranslationConfig

        cfg = TranslationConfig()
        code_to_name = cfg.google_translate_lang_codes
        preferred = ["fa", "en", "de", "fr", "es", "ar", "ru", "zh-cn", "pl", "pt", "th", "hi", "he", "ja", "ko", "id", "vi", "tr", "it", "uk"]
        items = list(code_to_name.items())
        items.sort(key=lambda kv: (preferred.index(kv[0]) if kv[0] in preferred else 9999, kv[1]))
        result = {}
        for code, name in items:
            display_name = name
            if code == "fa":
                display_name = "Persian"
            elif code == "en":
                display_name = "English"
            elif code == "de":
                display_name = "German"
            elif code == "fr":
                display_name = "French"
            elif code == "es":
                display_name = "Spanish"
            elif code == "ar":
                display_name = "Arabic"
            elif code == "ru":
                display_name = "Russian"
            elif code == "pl":
                display_name = "Polish"
            elif code == "th":
                display_name = "Thai"
            elif code == "hi":
                display_name = "Hindi"
            elif code in ("iw", "he"):
                display_name = "Hebrew"
                code = "iw"
            elif code == "ja":
                display_name = "Japanese"
            elif code == "ko":
                display_name = "Korean"
            elif code == "id":
                display_name = "Indonesian"
            elif code == "vi":
                display_name = "Vietnamese"
            elif code == "zh-cn":
                display_name = "Chinese (Simplified)"
            result[display_name] = code
        return result
    except Exception:
        return {
            "Persian": "fa",
            "English": "en",
            "German": "de",
            "French": "fr",
            "Spanish": "es",
            "Arabic": "ar",
            "Russian": "ru",
            "Chinese (Simplified)": "zh-cn",
            "Polish": "pl",
            "Portuguese": "pt",
            "Thai": "th",
            "Hindi": "hi",
            "Hebrew": "iw",
            "Japanese": "ja",
            "Korean": "ko",
            "Indonesian": "id",
            "Vietnamese": "vi",
        }


# --- Model menus --------------------------------------------------------------
MODELS = [
    {"label": "ChatGPT 5.4", "id": "gpt-5.4"},
    {"label": "ChatGPT 5.4 Mini", "id": "gpt-5.4-mini"},
]
REASONING_LEVELS = ["medium", "high", "xhigh"]
ENGINE_ROWS = [
    ("translate", "Translate Engine", "#1a5276"),
    ("polish", "Polish Engine", "#7d3c98"),
    ("split", "Splitting Engine", "#196f3d"),
]
SPLITTING_MODES = ["classic", "ai"]


def engine_menu_values():
    return [f"{m['label']} [{r}]" for m in MODELS for r in REASONING_LEVELS]


def parse_engine_selection(value: str):
    for model in MODELS:
        if model["label"] in value:
            for reasoning in REASONING_LEVELS:
                if f"[{reasoning}]" in value:
                    return model["id"], reasoning
    return MODELS[0]["id"], REASONING_LEVELS[0]


class TranslatePolishApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.settings = load_json(SETTINGS_FILE)
        self.gui_state = load_json(GUI_STATE_FILE)
        self.lang_map = load_language_map()
        self.lang_names = list(self.lang_map.keys())
        self._thread = None
        self._stop_requested = False

        self.title("SMTV · docx_translate_polish")
        self.geometry("760x980")
        self.minsize(660, 820)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(7, weight=1)

        self._build_title()
        self._build_file_row()
        self._build_dictionary_row()
        self._build_language_row()
        self._build_engine_panel()
        self._build_actions()
        self._build_progress()
        self._build_log()
        self._restore_state()

        self.log("✅ GUI ready — docx_translate_polish")
        self.log("ℹ️ GUI is now aligned to the extracted module API.")

    # --- UI ------------------------------------------------------------------
    def _build_title(self):
        title = ctk.CTkLabel(
            self,
            text="SMTV · Translate + Polish + Split",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        title.grid(row=0, column=0, padx=20, pady=(16, 8), sticky="w")

    def _build_file_row(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=1, column=0, padx=20, pady=(0, 4), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="DOCX File", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w", pady=(0, 4))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew")
        row.grid_columnconfigure(0, weight=1)

        self.file_entry = ctk.CTkEntry(row, height=36, placeholder_text="Select a DOCX file…")
        self.file_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        ctk.CTkButton(row, text="Browse", width=92, height=36, command=self.browse_docx).grid(row=0, column=1)
        ctk.CTkButton(row, text="✕", width=36, height=36, fg_color="#444", hover_color="#666", command=lambda: self.file_entry.delete(0, "end")).grid(row=0, column=2, padx=(4, 0))

    def _build_dictionary_row(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=2, column=0, padx=20, pady=(0, 4), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Excel Dictionary (Optional)", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w", pady=(0, 4))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew")
        row.grid_columnconfigure(0, weight=1)

        self.dict_entry = ctk.CTkEntry(row, height=36, placeholder_text="Select an XLSX dictionary file…")
        self.dict_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        ctk.CTkButton(row, text="Browse", width=92, height=36, fg_color="#2c3e50", hover_color="#3f5973", command=self.browse_dict).grid(row=0, column=1)
        ctk.CTkButton(row, text="✕", width=36, height=36, fg_color="#444", hover_color="#666", command=lambda: self.dict_entry.delete(0, "end")).grid(row=0, column=2, padx=(4, 0))

    def _build_language_row(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=3, column=0, padx=20, pady=(4, 6), sticky="ew")
        frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(frame, text="Source Language", font=ctk.CTkFont(size=13)).grid(row=0, column=0, padx=14, pady=(10, 4), sticky="w")
        ctk.CTkLabel(frame, text="Destination Language", font=ctk.CTkFont(size=13)).grid(row=0, column=1, padx=14, pady=(10, 4), sticky="w")

        self.source_lang_var = ctk.StringVar(value=self.settings.get("source_lang", "English"))
        self.dest_lang_var = ctk.StringVar(value=self.settings.get("dest_lang", "Persian"))

        self.source_lang_dropdown = ctk.CTkComboBox(frame, values=self.lang_names, variable=self.source_lang_var, state="readonly", height=32)
        self.source_lang_dropdown.grid(row=1, column=0, padx=14, pady=(0, 10), sticky="ew")

        self.dest_lang_dropdown = ctk.CTkComboBox(frame, values=self.lang_names, variable=self.dest_lang_var, state="readonly", height=32)
        self.dest_lang_dropdown.grid(row=1, column=1, padx=14, pady=(0, 10), sticky="ew")

    def _build_engine_panel(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=4, column=0, padx=20, pady=(0, 6), sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Module Configuration", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, columnspan=3, padx=14, pady=(10, 6), sticky="w")

        self.engine_vars = {}
        values = engine_menu_values()
        default_engine = self.settings.get("engine_translate", "ChatGPT 5.4 [medium]")

        for idx, (key, label, color) in enumerate(ENGINE_ROWS, start=1):
            ctk.CTkLabel(frame, text=label, text_color="white", fg_color=color, corner_radius=6, width=135, font=ctk.CTkFont(size=12, weight="bold")).grid(row=idx, column=0, padx=(14, 10), pady=5, sticky="w")
            var = ctk.StringVar(value=self.settings.get(f"engine_{key}", default_engine))
            self.engine_vars[key] = var
            ctk.CTkComboBox(frame, values=values, variable=var, state="readonly", height=32).grid(row=idx, column=1, padx=(0, 10), pady=5, sticky="ew")
            note = "used now" if key == "translate" else "stored now; module wiring later"
            ctk.CTkLabel(frame, text=note, text_color="#888", font=ctk.CTkFont(size=11)).grid(row=idx, column=2, padx=(0, 14), sticky="w")

        ctk.CTkLabel(frame, text="Splitting Mode", font=ctk.CTkFont(size=13)).grid(row=idx + 1, column=0, padx=(14, 10), pady=(10, 4), sticky="w")
        self.splitting_mode_var = ctk.StringVar(value=self.settings.get("splitting_mode", "classic"))
        self.splitting_mode_dropdown = ctk.CTkComboBox(frame, values=SPLITTING_MODES, variable=self.splitting_mode_var, state="readonly", height=32)
        self.splitting_mode_dropdown.grid(row=idx + 1, column=1, padx=(0, 10), pady=(10, 8), sticky="ew")
        ctk.CTkLabel(frame, text="active in current module", text_color="#888", font=ctk.CTkFont(size=11)).grid(row=idx + 1, column=2, padx=(0, 14), sticky="w")

    def _build_actions(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=5, column=0, padx=20, pady=(0, 6), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=0)

        self.translate_btn = ctk.CTkButton(frame, text="▶ Translate (Raw)", height=46, font=ctk.CTkFont(size=15, weight="bold"), fg_color="#1a5276", hover_color="#2471a3", command=self.on_translate)
        self.translate_btn.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self.stop_btn = ctk.CTkButton(frame, text="Stop", width=100, height=46, fg_color="#922b21", hover_color="#b03a2e", command=self.on_stop, state="disabled")
        self.stop_btn.grid(row=0, column=1, sticky="ew")

    def _build_progress(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=6, column=0, padx=20, pady=(0, 8), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(frame, height=10)
        self.progress.grid(row=0, column=0, sticky="ew")
        self.progress.set(0)

        self.progress_label = ctk.CTkLabel(frame, text="Idle", text_color="#888", anchor="w", font=ctk.CTkFont(size=11))
        self.progress_label.grid(row=1, column=0, sticky="ew", pady=(2, 0))

        self.status_label = ctk.CTkLabel(frame, text="", text_color="#777", anchor="w", font=ctk.CTkFont(size=11))
        self.status_label.grid(row=2, column=0, sticky="ew", pady=(2, 0))

    def _build_log(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=7, column=0, padx=20, pady=(0, 18), sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(frame, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        head.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(head, text="Debug Log", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(head, text="Copy Debug Log", width=120, height=26, command=self.copy_log).grid(row=0, column=1, padx=(0, 6))
        ctk.CTkButton(head, text="Clear", width=60, height=26, fg_color="#444", hover_color="#666", command=self.clear_log).grid(row=0, column=2)

        self.log_box = ctk.CTkTextbox(frame, wrap="word", font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.log_box.bind("<Key>", self._prevent_typing)

    # --- State ---------------------------------------------------------------
    def _restore_state(self):
        last_docx = self.gui_state.get("last_docx", "")
        if last_docx and Path(last_docx).exists():
            self.file_entry.insert(0, last_docx)

        last_dict = self.gui_state.get("last_dict", "")
        if last_dict and Path(last_dict).exists():
            self.dict_entry.insert(0, last_dict)

        if self.source_lang_var.get() not in self.lang_names:
            self.source_lang_var.set("English" if "English" in self.lang_names else self.lang_names[0])
        if self.dest_lang_var.get() not in self.lang_names:
            self.dest_lang_var.set("Persian" if "Persian" in self.lang_names else self.lang_names[0])

    def save_state(self):
        settings = {
            "source_lang": self.source_lang_var.get(),
            "dest_lang": self.dest_lang_var.get(),
            "splitting_mode": self.splitting_mode_var.get(),
        }
        for key, var in self.engine_vars.items():
            settings[f"engine_{key}"] = var.get()
        save_json(SETTINGS_FILE, settings)

        gui_state = {
            "last_docx": self.file_entry.get().strip(),
            "last_dict": self.dict_entry.get().strip(),
        }
        save_json(GUI_STATE_FILE, gui_state)

    # --- Events --------------------------------------------------------------
    def browse_docx(self):
        initial = str(Path(self.gui_state.get("last_docx", BASE_DIR)).parent) if self.gui_state.get("last_docx") else str(BASE_DIR)
        path = filedialog.askopenfilename(initialdir=initial, title="Select DOCX File", filetypes=[("Word Documents", "*.docx"), ("All Files", "*.*")])
        if path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, path)
            self.gui_state["last_docx"] = path
            save_json(GUI_STATE_FILE, self.gui_state)
            self.log(f"📄 Selected DOCX: {os.path.basename(path)}")

    def browse_dict(self):
        initial = str(Path(self.gui_state.get("last_dict", BASE_DIR)).parent) if self.gui_state.get("last_dict") else str(BASE_DIR)
        path = filedialog.askopenfilename(initialdir=initial, title="Select Excel Dictionary", filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")])
        if path:
            self.dict_entry.delete(0, "end")
            self.dict_entry.insert(0, path)
            self.gui_state["last_dict"] = path
            save_json(GUI_STATE_FILE, self.gui_state)
            self.log(f"📚 Dictionary: {os.path.basename(path)}")

    def on_translate(self):
        file_path = self.file_entry.get().strip()
        dict_path = self.dict_entry.get().strip()
        if not file_path or not os.path.exists(file_path):
            self.log("⚠️ Please select a valid DOCX file first.")
            return

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            self.log("⚠️ OPENAI_API_KEY not found in environment variables.")
            return

        model_id, reasoning = parse_engine_selection(self.engine_vars["translate"].get())
        src_lang_name = self.source_lang_var.get()
        dest_lang_name = self.dest_lang_var.get()
        src_lang = self.lang_map[src_lang_name]
        dest_lang = self.lang_map[dest_lang_name]
        splitting_mode = self.splitting_mode_var.get()

        self.save_state()
        self._stop_requested = False
        self.set_busy(True)
        self.progress.set(0.08)
        self.set_progress("Loading module…")
        self.status_label.configure(text=f"{os.path.basename(file_path)}  |  {model_id}  |  split={splitting_mode}")

        self.log("━" * 56)
        self.log("🚀 Translate (Raw) — docx_translate_polish")
        self.log(f"📄 File       : {os.path.basename(file_path)}")
        self.log(f"🌐 Source     : {src_lang_name} ({src_lang})")
        self.log(f"🌐 Destination: {dest_lang_name} ({dest_lang})")
        self.log(f"🤖 Model      : {model_id}")
        self.log(f"🧠 Reasoning  : {reasoning}")
        self.log(f"✂️ Split Mode : {splitting_mode}")
        if dict_path:
            self.log(f"📚 Dictionary : {os.path.basename(dict_path)}")
            self.log("ℹ️ Current extracted module build does not consume dictionary path yet.")
        else:
            self.log("📚 Dictionary : —")
        self.log("ℹ️ Polish/Splitting engine selectors are stored for future module wiring.")
        self.log("━" * 56)

        self._thread = threading.Thread(
            target=self._translate_thread,
            args=(file_path, api_key, model_id, src_lang, dest_lang, splitting_mode),
            daemon=True,
        )
        self._thread.start()

    def _translate_thread(self, file_path, api_key, model_id, src_lang, dest_lang, splitting_mode):
        try:
            from docx_translate_polish.core.config import TranslationConfig
            from docx_translate_polish.pipeline import TranslationPipeline

            self.after(0, lambda: self.progress.set(0.22))
            self.after(0, lambda: self.set_progress("Creating pipeline…"))

            config = TranslationConfig(
                openai_api_key=api_key,
                default_model=model_id,
            )
            pipeline = TranslationPipeline(config)

            self.after(0, lambda: self.progress.set(0.4))
            self.after(0, lambda: self.set_progress("Running translation…"))
            output_path = pipeline.run(
                input_path=file_path,
                src_lang=src_lang,
                dest_lang=dest_lang,
                splitting_mode=splitting_mode,
            )

            if self._stop_requested:
                self.after(0, lambda: self.log("🛑 Stop was requested, but current module build does not support live cancellation."))

            self.after(0, lambda: self._on_done(output_path))
        except Exception as e:
            self.after(0, lambda: self._on_error(e))

    def _on_done(self, output_path: str):
        self.progress.set(1.0)
        self.set_progress("Done ✅")
        self.log("━" * 56)
        self.log("✅ Translation complete!")
        self.log(f"💾 Output: {os.path.basename(output_path)}")
        self.log(f"📁 Path  : {output_path}")
        self.log("━" * 56)
        self.status_label.configure(text=f"Done ✅  →  {os.path.basename(output_path)}")
        self.set_busy(False)

    def _on_error(self, exc: Exception):
        self.progress.set(0)
        self.set_progress("Failed ❌")
        self.log(f"❌ {type(exc).__name__}: {exc}")
        self.status_label.configure(text="Failed.")
        self.set_busy(False)

    def on_stop(self):
        self._stop_requested = True
        self.log("🛑 Stop requested. Current module build cannot cancel an in-flight run yet.")

    # --- Helpers -------------------------------------------------------------
    def set_busy(self, busy: bool):
        self.translate_btn.configure(state="disabled" if busy else "normal")
        self.stop_btn.configure(state="normal" if busy else "disabled")

    def set_progress(self, text: str):
        self.progress_label.configure(text=text)

    def log(self, message: str):
        def _append():
            self.log_box.insert("end", str(message) + "\n")
            self.log_box.see("end")
        self.after(0, _append)

    def copy_log(self):
        self.clipboard_clear()
        self.clipboard_append(self.log_box.get("1.0", "end-1c"))
        self.log("📋 Debug log copied to clipboard.")

    def clear_log(self):
        self.log_box.delete("1.0", "end")

    def _prevent_typing(self, event):
        nav = {"Up", "Down", "Left", "Right", "Prior", "Next", "Home", "End", "Control_L", "Control_R"}
        if event.keysym in nav:
            return None
        if event.state & 0x0004 and event.keysym.lower() in {"c", "a"}:
            return None
        return "break"


if __name__ == "__main__":
    app = TranslatePolishApp()
    app.mainloop()
