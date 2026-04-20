import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import os
import json
import threading
import traceback
from datetime import datetime
from src.docx_translate_polish.pipeline import TranslationPipeline
from src.docx_translate_polish.core.config import TranslationConfig

# --- Configuration & UI Constants ---
MODELS = [
    {"label": "ChatGPT 5.4",      "id": "gpt-5.4"},
    {"label": "ChatGPT 5.4 Mini", "id": "gpt-5.4-mini"},
]
REASONING_LEVELS = ["medium", "high", "xhigh"]

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SMTVTranslatePolishApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SMTV | DOCX Translate & Polish Lab v1.0")
        self.geometry("1000x850")

        self.state_file = "gui_state.json"
        self.settings_file = "gui_settings.json"
        self.stop_event = threading.Event()

        # Load language data from config
        self.languages_dict = TranslationConfig().google_translate_lang_codes
        self.lang_display_names = sorted(list(self.languages_dict.values()))

        self._build_ui()
        self.load_all_data()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(7, weight=1)

        # Row 0 — Header
        self.header = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#1a1a1a")
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(self.header, text="DOCX TRANSLATE & POLISH LAB",
                                  font=ctk.CTkFont(family="Bahnschrift", size=24, weight="bold"))
        title_label.grid(row=0, column=0, padx=20, pady=15, sticky="w")

        # Row 1 — File selection
        self.file_panel = ctk.CTkFrame(self)
        self.file_panel.grid(row=1, column=0, padx=20, pady=(20, 10), sticky="ew")
        self.file_panel.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.file_panel, text="Source Document:").grid(row=0, column=0, padx=15, pady=15, sticky="w")
        self.file_entry = ctk.CTkEntry(self.file_panel, placeholder_text="Path to .docx table...")
        self.file_entry.grid(row=0, column=1, padx=(0, 10), pady=15, sticky="ew")
        self.file_btn = ctk.CTkButton(self.file_panel, text="Browse...", width=100, command=self.browse_docx)
        self.file_btn.grid(row=0, column=2, padx=(0, 15), pady=15)

        # Row 2 — Translation Dictionary (Optional)
        self.dict_panel = ctk.CTkFrame(self)
        self.dict_panel.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.dict_panel.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.dict_panel, text="Translation Dictionary (XTM):").grid(row=0, column=0, padx=15, pady=15, sticky="w")
        self.dict_entry = ctk.CTkEntry(self.dict_panel, placeholder_text="Optional .xlsx dictionary...")
        self.dict_entry.grid(row=0, column=1, padx=(0, 10), pady=15, sticky="ew")
        self.dict_btn = ctk.CTkButton(self.dict_panel, text="Browse...", width=100, command=self.browse_dict)
        self.dict_btn.grid(row=0, column=2, padx=(0, 15), pady=15)

        # Row 3 — Engine & Quality Panel
        self.engine_panel = ctk.CTkFrame(self)
        self.engine_panel.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(self.engine_panel, text="AI Engine:").grid(row=0, column=0, padx=15, pady=(15, 10), sticky="w")
        engine_options = [f"{m['label']} [{r}]" for m in MODELS for r in REASONING_LEVELS]
        self.engine_tr_cb = ctk.CTkComboBox(self.engine_panel, values=engine_options, width=280)
        self.engine_tr_cb.grid(row=0, column=1, padx=10, pady=(15, 10), sticky="w")

        ctk.CTkLabel(self.engine_panel, text="Splitting Mode:").grid(row=0, column=2, padx=15, pady=(15, 10), sticky="w")
        self.split_mode_cb = ctk.CTkComboBox(self.engine_panel, values=["classic", "ai"])
        self.split_mode_cb.grid(row=0, column=3, padx=10, pady=(15, 10), sticky="w")

        # Row 4 — Advanced Settings (Collapsible-like frame)
        self.adv_btn = ctk.CTkButton(self, text="▶ Advanced Settings", fg_color="transparent", anchor="w", command=self.toggle_advanced)
        self.adv_btn.grid(row=4, column=0, padx=20, pady=(5, 0), sticky="w")

        self.adv_panel = ctk.CTkFrame(self)
        self.adv_panel.grid_forget() # Initially hidden

        self.chunk_var = tk.BooleanVar(value=False)
        self.chunk_cb = ctk.CTkCheckBox(self.adv_panel, text="Enable chunking for large files", variable=self.chunk_var, command=self.toggle_chunk_input)
        self.chunk_cb.grid(row=0, column=0, padx=15, pady=10, sticky="w")

        ctk.CTkLabel(self.adv_panel, text="Lines per chunk:").grid(row=0, column=1, padx=(20, 5), pady=10)
        self.chunk_size_entry = ctk.CTkEntry(self.adv_panel, width=80)
        self.chunk_size_entry.insert(0, "100")
        self.chunk_size_entry.configure(state="disabled")
        self.chunk_size_entry.grid(row=0, column=2, padx=10, pady=10)

        ctk.CTkLabel(self.adv_panel, text="Default: entire file sent in one API call (recommended)", font=ctk.CTkFont(size=11, slant="italic")).grid(row=1, column=0, columnspan=3, padx=15, pady=(0, 10), sticky="w")

        # Row 5 — Language Configuration panel
        self.lang_panel = ctk.CTkFrame(self)
        self.lang_panel.grid(row=5, column=0, padx=20, pady=10, sticky="ew")
        self.lang_panel.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(self.lang_panel, text="Source Language:").grid(row=0, column=0, padx=15, pady=15, sticky="w")
        self.src_lang_cb = ctk.CTkComboBox(self.lang_panel, values=self.lang_display_names)
        self.src_lang_cb.grid(row=0, column=1, padx=(0, 15), pady=15, sticky="ew")

        ctk.CTkLabel(self.lang_panel, text="Destination Language:").grid(row=0, column=2, padx=15, pady=15, sticky="w")
        self.dest_lang_cb = ctk.CTkComboBox(self.lang_panel, values=self.lang_display_names)
        self.dest_lang_cb.grid(row=0, column=3, padx=(0, 15), pady=15, sticky="ew")

        # Row 6 — Action row
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.grid(row=6, column=0, padx=20, pady=10, sticky="ew")
        self.action_frame.grid_columnconfigure(0, weight=1)

        self.run_btn = ctk.CTkButton(self.action_frame, text="▶ Translate (Raw)", height=45, font=ctk.CTkFont(size=15, weight="bold"), command=self.start_pipeline)
        self.run_btn.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.stop_btn = ctk.CTkButton(self.action_frame, text="Stop", width=100, height=45, fg_color="#c0392b", hover_color="#e74c3c", command=self.request_stop)
        self.stop_btn.grid(row=0, column=1)

        # Row 7 — Debug Log
        self.log_panel = ctk.CTkFrame(self)
        self.log_panel.grid(row=7, column=0, padx=20, pady=(10, 20), sticky="nsew")
        self.log_panel.grid_columnconfigure(0, weight=1)
        self.log_panel.grid_rowconfigure(1, weight=1)

        self.log_header = ctk.CTkFrame(self.log_panel, fg_color="transparent")
        self.log_header.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        self.log_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.log_header, text="Debug Log", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w")

        self.copy_log_btn = ctk.CTkButton(self.log_header, text="Copy Debug Log", width=110, height=26, font=ctk.CTkFont(size=11), command=self.copy_log)
        self.copy_log_btn.grid(row=0, column=1, padx=5)

        self.clear_log_btn = ctk.CTkButton(self.log_header, text="Clear", width=60, height=26, font=ctk.CTkFont(size=11), command=self.clear_log)
        self.clear_log_btn.grid(row=0, column=2)

        self.log_text = ctk.CTkTextbox(self.log_panel, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_text.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # Progress bar overlay
        self.prog_bar = ctk.CTkProgressBar(self, width=600)
        self.prog_bar.set(0)
        self.prog_bar.grid(row=8, column=0, pady=(0, 20))

    def toggle_advanced(self):
        if self.adv_panel.winfo_viewable():
            self.adv_panel.grid_forget()
            self.adv_btn.configure(text="▶ Advanced Settings")
        else:
            self.adv_panel.grid(row=5, column=0, padx=20, pady=5, sticky="ew")
            # Shift language panel down
            self.lang_panel.grid(row=6, column=0, padx=20, pady=10, sticky="ew")
            self.action_frame.grid(row=7, column=0, padx=20, pady=10, sticky="ew")
            self.log_panel.grid(row=8, column=0, padx=20, pady=(10, 20), sticky="nsew")
            self.adv_btn.configure(text="▼ Advanced Settings")

    def toggle_chunk_input(self):
        if self.chunk_var.get():
            self.chunk_size_entry.configure(state="normal")
        else:
            self.chunk_size_entry.configure(state="disabled")

    def log_message(self, msg, level="INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{level}][{ts}] {msg}\n"
        self.after(0, lambda: self._safe_log(formatted))

    def _safe_log(self, text):
        self.log_text.insert("end", text)
        self.log_text.see("end")

    def clear_log(self):
        self.log_text.delete("1.0", "end")

    def copy_log(self):
        self.clipboard_clear()
        self.clipboard_append(self.log_text.get("1.0", "end"))
        self.log_message("✔ Log copied to clipboard.", "INFO")

    def browse_docx(self):
        path = filedialog.askopenfilename(filetypes=[("Word Documents", "*.docx")])
        if path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, path)

    def browse_dict(self):
        path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
        if path:
            self.dict_entry.delete(0, "end")
            self.dict_entry.insert(0, path)

    def load_all_data(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                    if os.path.exists(state.get("last_docx", "")):
                        self.file_entry.insert(0, state["last_docx"])
                    if os.path.exists(state.get("last_dict", "")):
                        self.dict_entry.insert(0, state["last_dict"])
            except: pass

        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    s = json.load(f)
                    self.src_lang_cb.set(s.get("src_lang", "English"))
                    self.dest_lang_cb.set(s.get("dest_lang", "Persian"))
                    self.engine_tr_cb.set(s.get("engine_tr", "ChatGPT 5.4 [medium]"))
                    self.split_mode_cb.set(s.get("splitting_mode", "classic"))
            except:
                self.src_lang_cb.set("English")
                self.dest_lang_cb.set("Persian")
                self.engine_tr_cb.set("ChatGPT 5.4 [medium]")
                self.split_mode_cb.set("classic")
        else:
            self.src_lang_cb.set("English")
            self.dest_lang_cb.set("Persian")
            self.engine_tr_cb.set("ChatGPT 5.4 [medium]")
            self.split_mode_cb.set("classic")

    def save_all_data(self):
        state = {
            "last_docx": self.file_entry.get(),
            "last_dict": self.dict_entry.get()
        }
        settings = {
            "src_lang": self.src_lang_cb.get(),
            "dest_lang": self.dest_lang_cb.get(),
            "engine_tr": self.engine_tr_cb.get(),
            "splitting_mode": self.split_mode_cb.get()
        }
        try:
            with open(self.state_file, "w") as f: json.dump(state, f)
            with open(self.settings_file, "w") as f: json.dump(settings, f)
        except: pass

    def request_stop(self):
        self.stop_event.set()
        self.log_message("Stop requested. Cancellation supported at block boundaries.", "WARN")

    def get_code(self, display_name):
        for code, name in self.languages_dict.items():
            if name == display_name: return code
        return "en"

    def parse_engine_selection(self, selection):
        model_id = "gpt-5.4"
        reasoning = "medium"
        for m in MODELS:
            if m["label"] in selection:
                model_id = m["id"]
                break
        for r in REASONING_LEVELS:
            if f"[{r}]" in selection:
                reasoning = r
                break
        return model_id, reasoning

    def start_pipeline(self):
        file_path = self.file_entry.get()
        if not file_path or not os.path.exists(file_path):
            messagebox.showerror("Error", "Please select a valid DOCX file.")
            return

        self.save_all_data()
        self.stop_event.clear()
        self.run_btn.configure(state="disabled")
        self.prog_bar.set(0)

        model_id, reasoning = self.parse_engine_selection(self.engine_tr_cb.get())
        sm = self.split_mode_cb.get()

        threading.Thread(target=self.worker_thread, args=(file_path, model_id, reasoning, sm), daemon=True).start()

    def worker_thread(self, file_path, model_id, reasoning_effort, splitting_mode):
        try:
            src_code = self.get_code(self.src_lang_cb.get())
            dest_code = self.get_code(self.dest_lang_cb.get())

            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                self.log_message("[ERROR] OPENAI_API_KEY is not set. Translation will fail.", "ERROR")
            else:
                masked = api_key[:8] + "..." + api_key[-4:]
                self.log_message(f"API key loaded: {masked}", "INFO")

            chunk_enabled = self.chunk_var.get()
            try:
                chunk_size = int(self.chunk_size_entry.get())
            except:
                chunk_size = 100

            config = TranslationConfig(
                openai_api_key=api_key,
                default_model=model_id,
                reasoning_effort=reasoning_effort,
                chunk_enabled=chunk_enabled,
                chunk_size=chunk_size
            )

            pipeline = TranslationPipeline(config=config)

            self.log_message(
                f"Engine: {model_id} | Reasoning: {reasoning_effort} | "
                f"Split: {splitting_mode} | "
                f"File: {os.path.basename(file_path)}"
            )

            output_path = pipeline.run(
                input_path=file_path,
                src_lang=src_code,
                dest_lang=dest_code,
                splitting_mode=splitting_mode,
                reasoning_effort=reasoning_effort,
                progress_callback=lambda msg: self.log_message(msg)
            )

            self.after(0, lambda: self.prog_bar.set(1.0))
            self.log_message(f"✔ Pipeline complete. Output saved to: {output_path}", "INFO")

        except Exception as e:
            tb = traceback.format_exc()
            self.log_message(f"CRITICAL ERROR: {str(e)}\n{tb}", "ERROR")
        finally:
            self.after(0, lambda: self.run_btn.configure(state="normal"))

if __name__ == "__main__":
    app = SMTVTranslatePolishApp()
    app.mainloop()
