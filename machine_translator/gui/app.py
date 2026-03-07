# pylint: disable=all
import os
import sys
import subprocess
import threading
import time
import re
import customtkinter as ctk
from tkinter import filedialog
from typing import Optional, List
from machine_translator.core.config import AppConfig
from machine_translator.core.logger import setup_logger
from machine_translator.utils.helpers import sanitize_filename, open_file

logger = setup_logger()

class MachineTranslatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.config = AppConfig()

        # Validate dependency script
        try:
            self.legacy_script = self.config.get_legacy_script_path()
        except FileNotFoundError:
            self.legacy_script = None
            logger.error("Legacy script 'machine-translate-docx.py' not found.")

        self.setup_ui()

    def setup_ui(self):
        ctk.set_appearance_mode(self.config.theme)
        ctk.set_default_color_theme(self.config.color_theme)

        self.title(self.config.app_name)
        self.geometry("700x800")
        self.minsize(600, 700)

        # Grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        # Components
        self._create_header()
        self._create_file_input()
        self._create_settings()
        self._create_options()
        self._create_translate_button()
        self._create_logs()

        self.log_message(f"Welcome to {self.config.app_name} v{self.config.version}!")
        if self.legacy_script:
             self.log_message(f"Backend script linked: {os.path.basename(self.legacy_script)}")
        else:
             self.log_message("ERROR: Backend script not found! Please check installation.", "error")

    def _create_header(self):
        lbl = ctk.CTkLabel(self, text=self.config.app_name, font=ctk.CTkFont(size=24, weight="bold"))
        lbl.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

    def _create_file_input(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        lbl = ctk.CTkLabel(frame, text="DOCX File", font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=0, column=0, padx=0, pady=(0, 5), sticky="w")

        entry_frame = ctk.CTkFrame(frame, fg_color="transparent")
        entry_frame.grid(row=1, column=0, sticky="ew")
        entry_frame.grid_columnconfigure(0, weight=1)

        self.file_entry = ctk.CTkEntry(entry_frame, placeholder_text="Select a DOCX file...", height=40)
        self.file_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        btn = ctk.CTkButton(entry_frame, text="Browse", width=100, height=40, command=self.browse_file)
        btn.grid(row=0, column=1)

    def _create_settings(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Settings", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w"
        )

        # Source Lang
        ctk.CTkLabel(frame, text="Source Language").grid(row=1, column=0, padx=15, pady=5, sticky="w")
        self.source_lang = ctk.CTkComboBox(frame, values=self.config.source_languages, state="readonly", height=35)
        self.source_lang.set("Auto")
        self.source_lang.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="ew")

        # Dest Lang
        ctk.CTkLabel(frame, text="Destination Language").grid(row=1, column=1, padx=15, pady=5, sticky="w")
        self.dest_lang = ctk.CTkComboBox(frame, values=self.config.destination_languages, state="readonly", height=35)
        self.dest_lang.set("fa")
        self.dest_lang.grid(row=2, column=1, padx=15, pady=(0, 10), sticky="ew")

        # Engine
        ctk.CTkLabel(frame, text="Translation Engine").grid(row=3, column=0, columnspan=2, padx=15, pady=5, sticky="w")
        self.engine = ctk.CTkComboBox(frame, values=self.config.engines, state="readonly", height=35)
        self.engine.set("ChatGPT (API)")
        self.engine.grid(row=4, column=0, columnspan=2, padx=15, pady=(0, 15), sticky="ew")

    def _create_options(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(frame, text="Options", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, pady=(0, 10), sticky="w"
        )

        self.split_sentences = ctk.CTkCheckBox(frame, text="Split sentences")
        self.split_sentences.select()
        self.split_sentences.grid(row=1, column=0, pady=5, sticky="w")

        self.show_browser = ctk.CTkCheckBox(frame, text="Show Browser (Debug)")
        self.show_browser.grid(row=2, column=0, pady=5, sticky="w")

    def _create_translate_button(self):
        self.translate_btn = ctk.CTkButton(
            self, text="Translate", height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self.start_translation
        )
        self.translate_btn.grid(row=4, column=0, padx=20, pady=15, sticky="ew")

    def _create_logs(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=5, column=0, padx=20, pady=(10, 20), sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Output Log", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, pady=(0, 5), sticky="w"
        )

        self.log_box = ctk.CTkTextbox(frame, wrap="word", state="disabled")
        self.log_box.grid(row=1, column=0, sticky="nsew")

    def log_message(self, msg: str, level: str = "info"):
        def _update():
            self.log_box.configure(state="normal")
            prefix = "🔴 " if level == "error" else ""
            self.log_box.insert("end", f"{prefix}{str(msg)}\n")
            self.log_box.configure(state="disabled")
            self.log_box.see("end")
        self.after(0, _update)

    def browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("Word Documents", "*.docx")])
        if f:
            self.file_entry.delete(0, 'end')
            self.file_entry.insert(0, f)
            self.log_message(f"Selected: {os.path.basename(f)}")

    def start_translation(self):
        if not self.legacy_script:
            self.log_message("Cannot start: Backend script missing.", "error")
            return

        path = self.file_entry.get()
        if not path or not os.path.exists(path):
            self.log_message("Please select a valid file.", "error")
            return

        cmd = [sys.executable, self.legacy_script]

        # Build Args
        cmd.extend(["--docxfile", path])
        cmd.extend(["--destlang", self.dest_lang.get()])

        src = self.source_lang.get()
        if src != "Auto":
            cmd.extend(["--srclang", src])

        if self.split_sentences.get():
            cmd.append("--split")

        if self.show_browser.get():
            cmd.append("--showbrowser")

        engine = self.engine.get()
        if engine == "Google":
            cmd.extend(["--engine", "google"])
        elif engine == "Perplexity":
            cmd.extend(["--engine", "perplexity"])
        elif "ChatGPT" in engine:
            cmd.extend(["--engine", "chatgpt"])
            method = "api" if "API" in engine else "phrasesblock"
            cmd.extend(["--enginemethod", method])

        self.log_message("="*40)
        self.log_message(f"Starting Translation: {os.path.basename(path)}")
        self.log_message(f"Engine: {engine} -> {self.dest_lang.get()}")

        self.translate_btn.configure(state="disabled")
        threading.Thread(target=self._run_process, args=(cmd, engine), daemon=True).start()

    def _run_process(self, cmd, engine_name):
        saved_filename = None
        try:
            # Use stdin pipe to feed newline if needed
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                cwd=self.config.base_dir # Run from root
            )

            # Prevent EOFError on input()
            try:
                process.stdin.write('\n')
                process.stdin.flush()
            except:
                pass

            for line in process.stdout:
                if line:
                    stripped = line.strip()
                    self.log_message(stripped)
                    if "Saved file name: " in stripped:
                        parts = stripped.split("Saved file name: ")
                        if len(parts) > 1:
                            saved_filename = parts[1].strip()

            process.wait()

            if process.returncode == 0:
                self.log_message("✅ Translation Complete!")
                if saved_filename and os.path.exists(saved_filename):
                    self._rename_output(saved_filename, engine_name)
            else:
                self.log_message(f"❌ Failed with code {process.returncode}", "error")

        except Exception as e:
            self.log_message(f"❌ Exception: {e}", "error")
        finally:
            self.after(0, lambda: self.translate_btn.configure(state="normal"))

    def _rename_output(self, original_path: str, engine_name: str):
        try:
            suffix = sanitize_filename(engine_name)
            dir_name = os.path.dirname(original_path)
            base_name = os.path.basename(original_path)
            name, ext = os.path.splitext(base_name)

            new_name = f"{name}_{suffix}{ext}"
            new_path = os.path.join(dir_name, new_name)

            os.rename(original_path, new_path)
            self.log_message(f"Renamed to: {new_name}")
        except Exception as e:
            self.log_message(f"Rename failed: {e}", "error")

if __name__ == "__main__":
    app = MachineTranslatorApp()
    app.mainloop()
