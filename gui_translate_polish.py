import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import sys
import threading
import json
import traceback
import time
from datetime import datetime

# sys.path bootstrap
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

try:
    from docx_translate_polish.core.config import TranslationConfig, google_translate_lang_codes
    from docx_translate_polish.pipeline import TranslationPipeline
except ImportError:
    print("ERROR: Could not import docx_translate_polish module from src/ folder.")
    sys.exit(1)

MODELS = [
    {"label": "ChatGPT 5.4",      "id": "gpt-5.4"},
    {"label": "ChatGPT 5.4 Mini", "id": "gpt-5.4-mini"},
]
REASONING_LEVELS = ["medium", "high", "xhigh"]

class SMTVTranslatePolishApp(ctk.CTk):
    """
    Elite SMTV GUI for the Docx Translate + Polish + Split workflow.
    Fully isolated from business logic.
    """
    def __init__(self):
        super().__init__()

        self.state_file = "gui_translate_polish_state.json"
        self.settings_file = "translate_polish_settings.json"
        self.stop_event = threading.Event()

        # Load languages from backend config
        self.languages_dict = google_translate_lang_codes
        self.lang_display_names = sorted(list(self.languages_dict.values()))

        self.setup_ui()
        self.load_all_data()

    def setup_ui(self):
        self.title("SMTV · Translate + Polish + Split")
        self.geometry("850x950")
        ctk.set_appearance_mode("dark")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(7, weight=1)

        # Row 0 — Title
        self.title_label = ctk.CTkLabel(self, text="SMTV · Translate + Polish + Split", font=ctk.CTkFont(size=22, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Row 1 — DOCX File
        self.file_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.file_frame.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        self.file_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.file_frame, text="DOCX File", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w")
        self.file_entry = ctk.CTkEntry(self.file_frame, height=35)
        self.file_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        self.browse_file_btn = ctk.CTkButton(self.file_frame, text="Browse", width=80, command=self.browse_docx)
        self.browse_file_btn.grid(row=1, column=1, padx=5)
        self.clear_file_btn = ctk.CTkButton(self.file_frame, text="✕", width=30, fg_color="#c0392b", hover_color="#e74c3c", command=lambda: self.file_entry.delete(0, 'end'))
        self.clear_file_btn.grid(row=1, column=2)

        # Row 2 — Excel Dictionary (Optional)
        self.dict_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.dict_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        self.dict_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.dict_frame, text="Excel Dictionary (Optional)", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w")
        self.dict_entry = ctk.CTkEntry(self.dict_frame, height=35)
        self.dict_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        self.browse_dict_btn = ctk.CTkButton(self.dict_frame, text="Browse", width=80, command=self.browse_dict)
        self.browse_dict_btn.grid(row=1, column=1, padx=5)
        self.clear_dict_btn = ctk.CTkButton(self.dict_frame, text="✕", width=30, fg_color="#c0392b", hover_color="#e74c3c", command=lambda: self.dict_entry.delete(0, 'end'))
        self.clear_dict_btn.grid(row=1, column=2)

        # Row 3 — Engine Configuration panel
        self.engine_panel = ctk.CTkFrame(self)
        self.engine_panel.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        self.engine_panel.grid_columnconfigure(1, weight=1)

        engine_options = []
        for m in MODELS:
            for r in REASONING_LEVELS:
                engine_options.append(f"{m['label']} [{r}]")

        # Row A: Translate
        self.badge_tr = ctk.CTkLabel(self.engine_panel, text=" Translate Engine ", fg_color="#1a5276", text_color="white", corner_radius=6)
        self.badge_tr.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.engine_tr_cb = ctk.CTkComboBox(self.engine_panel, values=engine_options, width=400)
        self.engine_tr_cb.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Row B: Polish
        self.badge_pl = ctk.CTkLabel(self.engine_panel, text=" Polish Engine ", fg_color="#7d3c98", text_color="white", corner_radius=6)
        self.badge_pl.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.engine_pl_cb = ctk.CTkComboBox(self.engine_panel, values=["Coming soon..."], state="disabled", width=400)
        self.engine_pl_cb.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        # Row C: Splitting
        self.badge_sp = ctk.CTkLabel(self.engine_panel, text=" Splitting Engine ", fg_color="#196f3d", text_color="white", corner_radius=6)
        self.badge_sp.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.engine_sp_cb = ctk.CTkComboBox(self.engine_panel, values=["Coming soon..."], state="disabled", width=400)
        self.engine_sp_cb.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        # Splitting Mode selector
        self.sm_label = ctk.CTkLabel(self.engine_panel, text="Splitting Mode:", font=ctk.CTkFont(weight="bold"))
        self.sm_label.grid(row=3, column=0, padx=10, pady=(15, 10), sticky="w")
        self.split_mode_cb = ctk.CTkComboBox(self.engine_panel, values=["classic", "ai"])
        self.split_mode_cb.grid(row=3, column=1, padx=10, pady=(15, 10), sticky="w")

        # Row 4 — Language Configuration panel
        self.lang_panel = ctk.CTkFrame(self)
        self.lang_panel.grid(row=4, column=0, padx=20, pady=10, sticky="ew")
        self.lang_panel.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(self.lang_panel, text="Source Language:").grid(row=0, column=0, padx=15, pady=15, sticky="w")
        self.src_lang_cb = ctk.CTkComboBox(self.lang_panel, values=self.lang_display_names)
        self.src_lang_cb.grid(row=0, column=1, padx=(0, 15), pady=15, sticky="ew")

        ctk.CTkLabel(self.lang_panel, text="Destination Language:").grid(row=0, column=2, padx=15, pady=15, sticky="w")
        self.dest_lang_cb = ctk.CTkComboBox(self.lang_panel, values=self.lang_display_names)
        self.dest_lang_cb.grid(row=0, column=3, padx=(0, 15), pady=15, sticky="ew")

        # Row 5 — Action row
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.grid(row=5, column=0, padx=20, pady=10, sticky="ew")
        self.action_frame.grid_columnconfigure(0, weight=1)

        self.run_btn = ctk.CTkButton(self.action_frame, text="▶ Translate (Raw)", height=45, font=ctk.CTkFont(size=15, weight="bold"), command=self.start_pipeline)
        self.run_btn.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.stop_btn = ctk.CTkButton(self.action_frame, text="Stop", width=100, height=45, fg_color="#c0392b", hover_color="#e74c3c", command=self.request_stop)
        self.stop_btn.grid(row=0, column=1)

        # Row 6 — Progress bar + labels
        self.prog_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.prog_frame.grid(row=6, column=0, padx=20, pady=10, sticky="ew")
        self.prog_frame.grid_columnconfigure(0, weight=1)

        self.prog_bar = ctk.CTkProgressBar(self.prog_frame)
        self.prog_bar.set(0)
        self.prog_bar.grid(row=0, column=0, sticky="ew")

        self.prog_label = ctk.CTkLabel(self.prog_frame, text="0%", font=ctk.CTkFont(size=12))
        self.prog_label.grid(row=0, column=1, padx=(10, 0))

        self.status_label = ctk.CTkLabel(self.prog_frame, text="Ready", font=ctk.CTkFont(size=12, slant="italic"))
        self.status_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))

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
        messagebox.showinfo("Clipboard", "Log copied to clipboard.")

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
        # State
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                    if os.path.exists(state.get("last_docx", "")):
                        self.file_entry.insert(0, state["last_docx"])
                    if os.path.exists(state.get("last_dict", "")):
                        self.dict_entry.insert(0, state["last_dict"])
            except: pass

        # Settings
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
        self.log_message("Stop requested. Current module build does not support live cancellation.", "WARN")

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
        self.prog_bar.set(0.15)
        self.prog_label.configure(text="15%")

        model_id, reasoning = self.parse_engine_selection(self.engine_tr_cb.get())
        sm = self.split_mode_cb.get()
        self.status_label.configure(text=f"{os.path.basename(file_path)} | {model_id} | split={sm}")

        threading.Thread(target=self.worker_thread, args=(file_path, model_id, sm), daemon=True).start()

    def worker_thread(self, file_path, model_id, splitting_mode):
        try:
            src_code = self.get_code(self.src_lang_cb.get())
            dest_code = self.get_code(self.dest_lang_cb.get())

            # TranslationConfig (STRICT signature)
            config = TranslationConfig(
                openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
                default_model=model_id
            )

            pipeline = TranslationPipeline(config=config)

            self.log_message(f"Starting pipeline: {os.path.basename(file_path)}")
            self.after(0, lambda: self.prog_bar.set(0.5))
            self.after(0, lambda: self.prog_label.configure(text="50%"))

            # pipeline.run (STRICT signature)
            output_path = pipeline.run(
                input_path=file_path,
                src_lang=src_code,
                dest_lang=dest_code,
                splitting_mode=splitting_mode
            )

            self.log_message(f"Pipeline completed successfully. Output: {output_path}")
            self.after(0, lambda: self.prog_bar.set(1.0))
            self.after(0, lambda: self.prog_label.configure(text="100%"))
            self.after(0, lambda: self.status_label.configure(text="Finished"))

            messagebox.showinfo("Success", f"Process complete!\nFile saved: {output_path}")

        except Exception as e:
            tb = traceback.format_exc()
            self.log_message(f"CRITICAL ERROR: {str(e)}\n{tb}", "ERROR")
            messagebox.showerror("Error", f"An unexpected error occurred: {str(e)}")
        finally:
            self.after(0, lambda: self.run_btn.configure(state="normal"))

if __name__ == "__main__":
    app = SMTVTranslatePolishApp()
    app.mainloop()
