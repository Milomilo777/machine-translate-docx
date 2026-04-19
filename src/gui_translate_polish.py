import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import sys
import threading
import json
import traceback

# Add project root to path for module imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from src.docx_translate_polish.core.config import TranslationConfig, google_translate_lang_codes
    from src.docx_translate_polish.pipeline import TranslationPipeline
except ImportError:
    try:
        from docx_translate_polish.core.config import TranslationConfig, google_translate_lang_codes
        from docx_translate_polish.pipeline import TranslationPipeline
    except ImportError:
        print("ERROR: Could not import docx_translate_polish module. Ensure you are running from the project root.")
        sys.exit(1)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class GuiTranslatePolish(ctk.CTk):
    """
    Thin GUI for the Docx Translate & Polish workflow.
    Coordinates between user input and the isolated backend module.
    """
    def __init__(self):
        super().__init__()

        self.settings_file = "gui_mt_settings.json"
        self.current_process = None
        self.pipeline = None

        # Load languages from backend definitions
        self.languages = google_translate_lang_codes
        self.lang_display_names = sorted(list(self.languages.values()))

        self.settings = self.load_settings()

        self.title("SMTV Docx Translation & Polish Lab")
        self.geometry("750x920")
        self.minsize(600, 800)

        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(7, weight=1)

        # UI Components
        self._create_header()
        self._create_file_picker()
        self._create_dictionary_picker()
        self._create_settings_frame()
        self._create_model_frame()
        self._create_execution_frame()
        self._create_log_frame()

        self.log_message("GUI initialized and ready.")

    def _create_header(self):
        lbl = ctk.CTkLabel(self, text="Translation & Localization Lab", font=ctk.CTkFont(size=24, weight="bold"))
        lbl.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

    def _create_file_picker(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Source DOCX File", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w")

        entry_frame = ctk.CTkFrame(frame, fg_color="transparent")
        entry_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        entry_frame.grid_columnconfigure(0, weight=1)

        self.file_entry = ctk.CTkEntry(entry_frame, height=40)
        self.file_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.file_entry.insert(0, self.settings.get("last_docx", ""))

        btn = ctk.CTkButton(entry_frame, text="Browse", width=100, height=40, command=self.browse_docx)
        btn.grid(row=0, column=1)

    def _create_dictionary_picker(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Excel Dictionary (Optional / Future Feature)", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w")

        entry_frame = ctk.CTkFrame(frame, fg_color="transparent")
        entry_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        entry_frame.grid_columnconfigure(0, weight=1)

        self.dict_entry = ctk.CTkEntry(entry_frame, height=40)
        self.dict_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.dict_entry.insert(0, self.settings.get("last_dict", ""))

        btn = ctk.CTkButton(entry_frame, text="Browse", width=100, height=40, fg_color="#2c3e50", command=self.browse_dict)
        btn.grid(row=0, column=1)

    def _create_settings_frame(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Language Configuration", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")

        # Source Lang
        ctk.CTkLabel(frame, text="Source Language").grid(row=1, column=0, padx=15, pady=(5, 0), sticky="w")
        self.src_lang_cb = ctk.CTkComboBox(frame, values=["Auto"] + self.lang_display_names, state="readonly", height=35)
        self.src_lang_cb.set(self.settings.get("source_lang", "English"))
        self.src_lang_cb.grid(row=2, column=0, padx=15, pady=(5, 15), sticky="ew")

        # Dest Lang
        ctk.CTkLabel(frame, text="Destination Language").grid(row=1, column=1, padx=15, pady=(5, 0), sticky="w")
        self.dest_lang_cb = ctk.CTkComboBox(frame, values=self.lang_display_names, state="readonly", height=35)
        self.dest_lang_cb.set(self.settings.get("dest_lang", "Persian"))
        self.dest_lang_cb.grid(row=2, column=1, padx=15, pady=(5, 15), sticky="ew")

    def _create_model_frame(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=4, column=0, padx=20, pady=10, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="AI Model Selection", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")

        # Model Mapping
        self.model_map = {
            "ChatGPT 5.4": "gpt-5.4",
            "ChatGPT 5.4 Mini": "gpt-5.4-mini"
        }

        # Model Selection
        ctk.CTkLabel(frame, text="Model").grid(row=1, column=0, padx=15, pady=(5, 0), sticky="w")
        self.model_cb = ctk.CTkComboBox(frame, values=list(self.model_map.keys()), state="readonly", height=35)
        self.model_cb.set(self.settings.get("model_label", "ChatGPT 5.4"))
        self.model_cb.grid(row=2, column=0, padx=15, pady=(5, 15), sticky="ew")

        # Reasoning Selection
        ctk.CTkLabel(frame, text="Reasoning (Future Feature)").grid(row=1, column=1, padx=15, pady=(5, 0), sticky="w")
        self.reasoning_cb = ctk.CTkComboBox(frame, values=["medium", "high", "xhigh"], state="readonly", height=35)
        self.reasoning_cb.set(self.settings.get("reasoning", "medium"))
        self.reasoning_cb.grid(row=2, column=1, padx=15, pady=(5, 15), sticky="ew")

    def _create_execution_frame(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=5, column=0, padx=20, pady=10, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(frame, text="Workflow Options", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, columnspan=3, padx=15, pady=(15, 10), sticky="w")

        # Splitting Mode
        ctk.CTkLabel(frame, text="Splitting Mode").grid(row=1, column=0, padx=15, pady=(5, 0), sticky="w")
        self.split_mode_cb = ctk.CTkComboBox(frame, values=["classic", "ai"], state="readonly", height=35)
        self.split_mode_cb.set(self.settings.get("splitting_mode", "classic"))
        self.split_mode_cb.grid(row=2, column=0, padx=15, pady=(5, 20), sticky="ew")

        # Polish Engine Placeholder
        ctk.CTkLabel(frame, text="Polish Engine (Future)").grid(row=1, column=1, padx=15, pady=(5, 0), sticky="w")
        self.polish_engine_cb = ctk.CTkComboBox(frame, values=["Internal", "External AI"], state="readonly", height=35)
        self.polish_engine_cb.set("Internal")
        self.polish_engine_cb.grid(row=2, column=1, padx=15, pady=(5, 20), sticky="ew")

        # Action Button
        self.run_btn = ctk.CTkButton(frame, text="START PIPELINE", height=50, font=ctk.CTkFont(size=14, weight="bold"), command=self.start_pipeline)
        self.run_btn.grid(row=2, column=2, padx=15, pady=(5, 20), sticky="ew")

    def _create_log_frame(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=6, column=0, padx=20, pady=10, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        lbl_frame = ctk.CTkFrame(frame, fg_color="transparent")
        lbl_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))
        lbl_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(lbl_frame, text="Execution Log", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w")

        btn = ctk.CTkButton(lbl_frame, text="Copy Debug Log", width=120, height=25, font=ctk.CTkFont(size=11), command=self.copy_log)
        btn.grid(row=0, column=1, sticky="e")

        self.log_text = ctk.CTkTextbox(frame, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_text.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")

    def log_message(self, msg, level="info"):
        prefix = f"[{level.upper()}] "
        self.log_text.insert("end", f"{prefix}{msg}\n")
        self.log_text.see("end")

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    return json.load(f)
            except: pass
        return {}

    def save_settings(self):
        data = {
            "last_docx": self.file_entry.get(),
            "last_dict": self.dict_entry.get(),
            "source_lang": self.src_lang_cb.get(),
            "dest_lang": self.dest_lang_cb.get(),
            "model_label": self.model_cb.get(),
            "reasoning": self.reasoning_cb.get(),
            "splitting_mode": self.split_mode_cb.get()
        }
        try:
            with open(self.settings_file, "w") as f:
                json.dump(data, f)
        except: pass

    def browse_docx(self):
        path = filedialog.askopenfilename(filetypes=[("Word Files", "*.docx")])
        if path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, path)

    def browse_dict(self):
        path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
        if path:
            self.dict_entry.delete(0, "end")
            self.dict_entry.insert(0, path)

    def copy_log(self):
        self.clipboard_clear()
        self.clipboard_append(self.log_text.get("1.0", "end"))
        self.log_message("Log copied to clipboard.")

    def get_lang_code(self, display_name):
        for code, name in self.languages.items():
            if name == display_name: return code
        return "en"

    def start_pipeline(self):
        if self.current_process and self.current_process.is_alive():
            messagebox.showwarning("Process Running", "A task is already in progress.")
            return

        file_path = self.file_entry.get()
        if not file_path or not os.path.exists(file_path):
            messagebox.showerror("Error", "Select a valid DOCX file.")
            return

        self.save_settings()
        self.run_btn.configure(state="disabled", text="RUNNING...")

        self.current_process = threading.Thread(target=self.execute_pipeline, args=(file_path,))
        self.current_process.daemon = True
        self.current_process.start()

    def execute_pipeline(self, file_path):
        try:
            src_name = self.src_lang_cb.get()
            dest_name = self.dest_lang_cb.get()

            src_lang = "en" if src_name == "Auto" else self.get_lang_code(src_name)
            dest_lang = self.get_lang_code(dest_name)

            model_id = self.model_map.get(self.model_cb.get(), "gpt-5.4")
            splitting_mode = self.split_mode_cb.get()

            # Initialize Backend Config - FIX: default_model instead of model
            config = TranslationConfig(
                openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
                default_model=model_id
            )

            self.log_message(f"Starting Pipeline: {os.path.basename(file_path)}")
            self.log_message(f"Config: Model={model_id}, Split={splitting_mode}, Target={dest_lang}")

            # Instantiate Pipeline
            self.pipeline = TranslationPipeline(config=config)

            # Execute Pipeline
            output_path = self.pipeline.run(
                input_path=file_path,
                src_lang=src_lang,
                dest_lang=dest_lang,
                splitting_mode=splitting_mode
            )

            self.log_message(f"SUCCESS: Result saved to {output_path}")
            messagebox.showinfo("Success", f"Translation complete!\n\nFile saved to:\n{output_path}")

        except Exception as e:
            err_msg = traceback.format_exc()
            print(err_msg)
            self.log_message(f"CRITICAL ERROR: {str(e)}", "error")
            messagebox.showerror("Pipeline Error", f"An error occurred:\n{str(e)}")
        finally:
            self.run_btn.configure(state="normal", text="START PIPELINE")

if __name__ == "__main__":
    app = GuiTranslatePolish()
    app.mainloop()
