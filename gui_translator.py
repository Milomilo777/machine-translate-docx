import customtkinter as ctk
from tkinter import filedialog
import os
import subprocess
import threading
import sys
import platform

# Set appearance mode and default color theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class MachineTranslatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configure window
        self.title("Machine Translator")
        self.geometry("700x850")
        self.minsize(600, 750)

        # Configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        # Title Label
        self.title_label = ctk.CTkLabel(
            self,
            text="Machine Translator",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # File Selection Frame
        self.file_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.file_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.file_frame.grid_columnconfigure(0, weight=1)

        self.file_label = ctk.CTkLabel(
            self.file_frame,
            text="DOCX File",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.file_label.grid(row=0, column=0, padx=0, pady=(0, 5), sticky="w")

        self.file_entry_frame = ctk.CTkFrame(self.file_frame, fg_color="transparent")
        self.file_entry_frame.grid(row=1, column=0, sticky="ew")
        self.file_entry_frame.grid_columnconfigure(0, weight=1)

        self.file_entry = ctk.CTkEntry(
            self.file_entry_frame,
            placeholder_text="Select a DOCX file...",
            height=40,
            font=ctk.CTkFont(size=13)
        )
        self.file_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        self.browse_button = ctk.CTkButton(
            self.file_entry_frame,
            text="Browse",
            width=100,
            height=40,
            command=self.browse_file,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.browse_button.grid(row=0, column=1)

        # Settings Frame
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.settings_frame.grid_columnconfigure(0, weight=1)
        self.settings_frame.grid_columnconfigure(1, weight=1)

        self.settings_label = ctk.CTkLabel(
            self.settings_frame,
            text="Settings",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.settings_label.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")

        # Source Language
        self.source_lang_label = ctk.CTkLabel(
            self.settings_frame,
            text="Source Language",
            font=ctk.CTkFont(size=13)
        )
        self.source_lang_label.grid(row=1, column=0, padx=15, pady=(5, 5), sticky="w")

        self.source_lang_dropdown = ctk.CTkComboBox(
            self.settings_frame,
            values=["Auto", "en", "fa", "de", "fr", "es", "ar", "ru", "zh-CN"],
            state="readonly",
            height=35,
            font=ctk.CTkFont(size=13)
        )
        self.source_lang_dropdown.set("Auto")
        self.source_lang_dropdown.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="ew")

        # Destination Language
        self.dest_lang_label = ctk.CTkLabel(
            self.settings_frame,
            text="Destination Language",
            font=ctk.CTkFont(size=13)
        )
        self.dest_lang_label.grid(row=1, column=1, padx=15, pady=(5, 5), sticky="w")

        self.dest_lang_dropdown = ctk.CTkComboBox(
            self.settings_frame,
            values=["fa", "en", "de", "fr", "es", "ar", "ru", "zh-CN", "pl", "pt-pt", "th", "hu", "hi", "he", "ko", "id", "bg", "vi", "ja", "ms", "pa"],
            state="readonly",
            height=35,
            font=ctk.CTkFont(size=13)
        )
        self.dest_lang_dropdown.set("fa")
        self.dest_lang_dropdown.grid(row=2, column=1, padx=15, pady=(0, 10), sticky="ew")

        # Translation Engine
        self.engine_label = ctk.CTkLabel(
            self.settings_frame,
            text="Translation Engine",
            font=ctk.CTkFont(size=13)
        )
        self.engine_label.grid(row=3, column=0, columnspan=2, padx=15, pady=(5, 5), sticky="w")

        self.engine_dropdown = ctk.CTkComboBox(
            self.settings_frame,
            values=["chatgpt", "google", "deepl", "yandex", "perplexity"],
            state="readonly",
            height=35,
            font=ctk.CTkFont(size=13)
        )
        self.engine_dropdown.set("chatgpt")
        self.engine_dropdown.grid(row=4, column=0, columnspan=2, padx=15, pady=(0, 5), sticky="ew")

        # Method
        self.method_label = ctk.CTkLabel(
            self.settings_frame,
            text="Method",
            font=ctk.CTkFont(size=13)
        )
        self.method_label.grid(row=5, column=0, columnspan=2, padx=15, pady=(5, 5), sticky="w")

        self.method_dropdown = ctk.CTkComboBox(
            self.settings_frame,
            values=["api", "javascript", "phrasesblock", "singlephrase"],
            state="readonly",
            height=35,
            font=ctk.CTkFont(size=13)
        )
        self.method_dropdown.set("api")
        self.method_dropdown.grid(row=6, column=0, columnspan=2, padx=15, pady=(0, 15), sticky="ew")


        # Options Frame
        self.options_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.options_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        self.options_label = ctk.CTkLabel(
            self.options_frame,
            text="Options",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.options_label.grid(row=0, column=0, padx=0, pady=(0, 10), sticky="w")

        self.split_sentences_checkbox = ctk.CTkCheckBox(
            self.options_frame,
            text="Split sentences",
            font=ctk.CTkFont(size=13),
            checkbox_height=22,
            checkbox_width=22
        )
        self.split_sentences_checkbox.select()  # Checked by default
        self.split_sentences_checkbox.grid(row=1, column=0, padx=0, pady=5, sticky="w")

        self.show_browser_checkbox = ctk.CTkCheckBox(
            self.options_frame,
            text="Show Browser (Debug)",
            font=ctk.CTkFont(size=13),
            checkbox_height=22,
            checkbox_width=22
        )
        # self.show_browser_checkbox.select()
        self.show_browser_checkbox.grid(row=2, column=0, padx=0, pady=5, sticky="w")

        # Translate Button
        self.translate_button = ctk.CTkButton(
            self,
            text="Translate",
            height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self.translate_file
        )
        self.translate_button.grid(row=4, column=0, padx=20, pady=15, sticky="ew")

        # Log Output Frame
        self.log_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.log_frame.grid(row=5, column=0, padx=20, pady=(10, 20), sticky="nsew")
        self.log_frame.grid_columnconfigure(0, weight=1)
        self.log_frame.grid_rowconfigure(1, weight=1)

        self.log_label = ctk.CTkLabel(
            self.log_frame,
            text="Output Log",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.log_label.grid(row=0, column=0, padx=0, pady=(0, 5), sticky="w")

        self.log_textbox = ctk.CTkTextbox(
            self.log_frame,
            wrap="word",
            font=ctk.CTkFont(size=12),
            state="disabled"
        )
        self.log_textbox.grid(row=1, column=0, sticky="nsew")

        # Initialize with welcome message
        self.log_message("Welcome to Machine Translator!")
        self.log_message("Select a DOCX file and configure settings to begin.")

    def browse_file(self):
        """Open file dialog to select a DOCX file"""
        filename = filedialog.askopenfilename(
            title="Select DOCX File",
            filetypes=[("Word Documents", "*.docx"), ("All Files", "*.*")]
        )
        if filename:
            self.file_entry.delete(0, 'end')
            self.file_entry.insert(0, filename)
            self.log_message(f"Selected file: {os.path.basename(filename)}")

    def log_message(self, message):
        """Add a message to the log textbox (thread-safe)"""
        def _update():
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", str(message) + "\n")
            self.log_textbox.configure(state="disabled")
            self.log_textbox.see("end")

        self.after(0, _update)

    def translate_file(self):
        """Handle translation process"""
        file_path = self.file_entry.get()

        if not file_path:
            self.log_message("⚠️ Error: Please select a DOCX file first!")
            return

        if not os.path.exists(file_path):
            self.log_message("⚠️ Error: Selected file does not exist!")
            return

        # Get settings
        source_lang = self.source_lang_dropdown.get()
        dest_lang = self.dest_lang_dropdown.get()
        engine = self.engine_dropdown.get()
        method = self.method_dropdown.get()
        split_sentences = self.split_sentences_checkbox.get()
        show_browser = self.show_browser_checkbox.get()

        # Log translation start
        self.log_message("\n" + "="*50)
        self.log_message("🚀 Starting translation...")
        self.log_message(f"Source: {source_lang} -> Destination: {dest_lang}")
        self.log_message(f"Engine: {engine}")
        self.log_message(f"Method: {method}")
        self.log_message(f"Split: {split_sentences}")
        self.log_message("="*50)

        # Build command
        # Assumes src/machine-translate-docx.py is in the current directory or src subdirectory relative to CWD
        script_path = os.path.join("src", "machine-translate-docx.py")
        if not os.path.exists(script_path):
             self.log_message(f"⚠️ Error: Script not found at {script_path}")
             # Fallback to checking if it is in the root
             if os.path.exists("machine-translate-docx.py"):
                 script_path = "machine-translate-docx.py"
                 self.log_message(f"ℹ️ Found script at root: {script_path}")
             else:
                 return

        cmd = [sys.executable, script_path]
        cmd.extend(["--docxfile", file_path])
        cmd.extend(["--destlang", dest_lang])
        cmd.extend(["--engine", engine])

        if source_lang != "Auto":
             cmd.extend(["--srclang", source_lang])

        if split_sentences:
            cmd.append("--split")

        if method and method != "":
             cmd.extend(["--enginemethod", method])

        if show_browser:
            cmd.append("--showbrowser")

        # Run in thread
        threading.Thread(target=self.run_process, args=(cmd,), daemon=True).start()

    def run_process(self, cmd):
        self.translate_button.configure(state="disabled")
        try:
            self.log_message(f"Running command...")

            # Using Popen to capture output in real-time
            # Windows needs shell=False usually for list args, but depends on execution.
            # Using shell=False is safer with list args.

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                cwd=os.getcwd() # Run from current directory
            )

            for line in process.stdout:
                self.log_message(line.strip())

            process.wait()

            if process.returncode == 0:
                self.log_message("\n✅ Translation Completed Successfully!")
            else:
                self.log_message(f"\n❌ Translation Failed with return code {process.returncode}")

        except Exception as e:
            self.log_message(f"\n❌ Error running process: {str(e)}")
        finally:
            # Re-enable button
             self.after(0, lambda: self.translate_button.configure(state="normal"))


if __name__ == "__main__":
    app = MachineTranslatorApp()
    app.mainloop()
