# pylint: disable=all
import customtkinter as ctk
from tkinter import filedialog
import os
import subprocess
import threading
import sys
import platform
import json

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class MachineTranslatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.settings_file = "mt_settings.json"
        self.current_process = None

        self.lang_map = {
            "Persian": "fa", "English": "en", "German": "de", "French": "fr",
            "Spanish": "es", "Arabic": "ar", "Russian": "ru", "Chinese": "zh-CN",
            "Polish": "pl", "Portuguese": "pt-pt", "Thai": "th", "Hungarian": "hu",
            "Hindi": "hi", "Hebrew": "he", "Korean": "ko", "Indonesian": "id",
            "Bulgarian": "bg", "Vietnamese": "vi", "Japanese": "ja", "Malay": "ms", "Punjabi": "pa"
        }

        self.settings = self.load_settings()

        self.title("SMTV Translation & Localization Lab")
        self.geometry("700x920")
        self.minsize(600, 800)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(6, weight=1)

        self.title_label = ctk.CTkLabel(self, text="Translation & Localization Lab", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        self.file_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.file_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.file_frame.grid_columnconfigure(0, weight=1)

        self.file_label = ctk.CTkLabel(self.file_frame, text="DOCX File", font=ctk.CTkFont(size=14, weight="bold"))
        self.file_label.grid(row=0, column=0, padx=0, pady=(0, 5), sticky="w")

        self.file_entry_frame = ctk.CTkFrame(self.file_frame, fg_color="transparent")
        self.file_entry_frame.grid(row=1, column=0, sticky="ew")
        self.file_entry_frame.grid_columnconfigure(0, weight=1)

        self.file_entry = ctk.CTkEntry(self.file_entry_frame, placeholder_text="Select a DOCX file...", height=40, font=ctk.CTkFont(size=13))
        self.file_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        self.browse_button = ctk.CTkButton(self.file_entry_frame, text="Browse", width=100, height=40, command=self.browse_file, font=ctk.CTkFont(size=13, weight="bold"))
        self.browse_button.grid(row=0, column=1)

        self.dict_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.dict_frame.grid(row=2, column=0, padx=20, pady=0, sticky="ew")
        self.dict_frame.grid_columnconfigure(0, weight=1)

        self.dict_label = ctk.CTkLabel(self.dict_frame, text="Excel Dictionary (Optional)", font=ctk.CTkFont(size=14, weight="bold"))
        self.dict_label.grid(row=0, column=0, padx=0, pady=(0, 5), sticky="w")

        self.dict_entry_frame = ctk.CTkFrame(self.dict_frame, fg_color="transparent")
        self.dict_entry_frame.grid(row=1, column=0, sticky="ew")
        self.dict_entry_frame.grid_columnconfigure(0, weight=1)

        self.dict_entry = ctk.CTkEntry(self.dict_entry_frame, placeholder_text="Select an XLSX dictionary file...", height=40, font=ctk.CTkFont(size=13))
        self.dict_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.dict_entry.insert(0, self.settings.get("dict_path", ""))

        self.browse_dict_button = ctk.CTkButton(self.dict_entry_frame, text="Browse", width=100, height=40, fg_color="#2c3e50", command=self.browse_dict, font=ctk.CTkFont(size=13, weight="bold"))
        self.browse_dict_button.grid(row=0, column=1)

        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        self.settings_frame.grid_columnconfigure(0, weight=1)
        self.settings_frame.grid_columnconfigure(1, weight=1)

        self.settings_label = ctk.CTkLabel(self.settings_frame, text="Settings", font=ctk.CTkFont(size=16, weight="bold"))
        self.settings_label.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")

        self.source_lang_label = ctk.CTkLabel(self.settings_frame, text="Source Language", font=ctk.CTkFont(size=13))
        self.source_lang_label.grid(row=1, column=0, padx=15, pady=(5, 5), sticky="w")
        self.source_lang_dropdown = ctk.CTkComboBox(self.settings_frame, values=["Auto"] + list(self.lang_map.keys()), state="readonly", height=35)
        self.source_lang_dropdown.set(self.settings.get("source_lang", "Auto"))
        self.source_lang_dropdown.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="ew")

        self.dest_lang_label = ctk.CTkLabel(self.settings_frame, text="Destination Language", font=ctk.CTkFont(size=13))
        self.dest_lang_label.grid(row=1, column=1, padx=15, pady=(5, 5), sticky="w")
        self.dest_lang_dropdown = ctk.CTkComboBox(self.settings_frame, values=list(self.lang_map.keys()), state="readonly", height=35)
        self.dest_lang_dropdown.set(self.settings.get("dest_lang", "Persian"))
        self.dest_lang_dropdown.grid(row=2, column=1, padx=15, pady=(0, 10), sticky="ew")

        self.engine_label = ctk.CTkLabel(self.settings_frame, text="Translation Engine (For Raw Translation)", font=ctk.CTkFont(size=13))
        self.engine_label.grid(row=3, column=0, columnspan=2, padx=15, pady=(5, 5), sticky="w")
        self.engine_dropdown = ctk.CTkComboBox(self.settings_frame, values=["DeepL", "Google", "Comet (Logged-in)", "Perplexity - Chrome", "ChatGPT (API)", "ChatGPT (Web)"], state="readonly", height=35)
        self.engine_dropdown.set("ChatGPT (API)")
        self.engine_dropdown.grid(row=4, column=0, columnspan=2, padx=15, pady=(0, 15), sticky="ew")

        self.options_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.options_frame.grid(row=4, column=0, padx=20, pady=10, sticky="ew")

        self.split_sentences_checkbox = ctk.CTkCheckBox(self.options_frame, text="Split sentences", font=ctk.CTkFont(size=13))
        self.split_sentences_checkbox.select()
        if self.settings.get("split", True) is False:
            self.split_sentences_checkbox.deselect()
        self.split_sentences_checkbox.grid(row=0, column=0, padx=0, pady=5, sticky="w")

        self.show_browser_checkbox = ctk.CTkCheckBox(self.options_frame, text="Show Browser (Debug)", font=ctk.CTkFont(size=13))
        self.show_browser_checkbox.select()
        self.show_browser_checkbox.grid(row=1, column=0, padx=0, pady=5, sticky="w")

        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.grid(row=5, column=0, padx=20, pady=15, sticky="ew")
        self.action_frame.grid_columnconfigure(0, weight=1)
        self.action_frame.grid_columnconfigure(1, weight=1)

        self.btn_translate = ctk.CTkButton(self.action_frame, text="1. Translate (Raw)", height=45, font=ctk.CTkFont(size=15, weight="bold"), command=lambda: self.run_action("translate"))
        self.btn_translate.grid(row=0, column=0, padx=(0, 10), pady=(0, 10), sticky="ew")

        self.stop_button = ctk.CTkButton(self.action_frame, text="Stop Process", height=45, fg_color="#c0392b", hover_color="#e74c3c", font=ctk.CTkFont(size=15, weight="bold"), command=self.stop_translation, state="disabled")
        self.stop_button.grid(row=0, column=1, pady=(0, 10), sticky="ew")

        self.btn_polish = ctk.CTkButton(self.action_frame, text="2. Polish Translation (AI)", height=45, fg_color="#8e44ad", hover_color="#9b59b6", font=ctk.CTkFont(size=15, weight="bold"), command=lambda: self.run_action("polish"))
        self.btn_polish.grid(row=1, column=0, padx=(0, 10), sticky="ew")

        self.btn_align = ctk.CTkButton(self.action_frame, text="3. Align & Double (AI)", height=45, fg_color="#27ae60", hover_color="#2ecc71", font=ctk.CTkFont(size=15, weight="bold"), command=lambda: self.run_action("align"))
        self.btn_align.grid(row=1, column=1, sticky="ew")

        self.operation_buttons = [self.btn_translate, self.btn_polish, self.btn_align]

        self.log_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.log_frame.grid(row=6, column=0, padx=20, pady=(10, 20), sticky="nsew")
        self.log_frame.grid_columnconfigure(0, weight=1)
        self.log_frame.grid_rowconfigure(1, weight=1)

        self.log_label = ctk.CTkLabel(self.log_frame, text="Output Log", font=ctk.CTkFont(size=14, weight="bold"))
        self.log_label.grid(row=0, column=0, padx=0, pady=(0, 5), sticky="w")

        self.copy_log_button = ctk.CTkButton(self.log_frame, text="Copy Log", width=80, height=24, command=self.copy_log)
        self.copy_log_button.grid(row=0, column=0, sticky="e")

        self.log_textbox = ctk.CTkTextbox(self.log_frame, wrap="word", font=ctk.CTkFont(size=12))
        self.log_textbox.grid(row=1, column=0, sticky="nsew")
        self.log_textbox.configure(state="normal")
        self.log_textbox.bind("<Key>", self.prevent_typing)

        self.log_message("Welcome to SMTV Translation & Localization Lab!")
        self.log_message("Ready. You can select and copy text (Ctrl+C) from this log anytime.")

    def prevent_typing(self, event):
        if event.keysym in ("Up", "Down", "Left", "Right", "Prior", "Next", "Home", "End", "Control_L", "Control_R"):
            return None
        if event.state & 0x0004:
            if event.keysym.lower() in ("c", "a"):
                return None
        return "break"

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_settings(self):
        self.settings = {
            "source_lang": self.source_lang_dropdown.get(),
            "dest_lang": self.dest_lang_dropdown.get(),
            "engine": self.engine_dropdown.get(),
            "dict_path": self.dict_entry.get().strip(),
            "last_dir": self.settings.get("last_dir", ""),
            "split": bool(self.split_sentences_checkbox.get())
        }
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            self.log_message(f"Error saving settings: {e}")

    def browse_file(self):
        initial_dir = self.settings.get("last_dir", os.path.expanduser("~"))
        filename = filedialog.askopenfilename(initialdir=initial_dir, title="Select DOCX File", filetypes=[("Word Documents", "*.docx"), ("All Files", "*.*")])
        if filename:
            self.file_entry.delete(0, 'end')
            self.file_entry.insert(0, filename)
            self.settings["last_dir"] = os.path.dirname(filename)
            self.save_settings()
            self.log_message(f"Selected: {os.path.basename(filename)}")

    def browse_dict(self):
        initial_dir = self.settings.get("last_dir", os.path.expanduser("~"))
        filename = filedialog.askopenfilename(initialdir=initial_dir, title="Select Excel Dictionary", filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")])
        if filename:
            self.dict_entry.delete(0, 'end')
            self.dict_entry.insert(0, filename)
            self.save_settings()
            self.log_message(f"Dictionary: {os.path.basename(filename)}")

    def copy_log(self):
        self.clipboard_clear()
        self.clipboard_append(self.log_textbox.get("1.0", "end-1c"))
        self.log_message("📋 Log successfully copied to clipboard!")

    def log_message(self, message):
        def _update():
            self.log_textbox.insert("end", str(message) + "\n")
            self.log_textbox.see("end")
        self.after(0, _update)

    def stop_translation(self):
        if self.current_process is not None:
            try:
                self.current_process.kill()
                self.log_message("\n🛑 Process Stopped!")
            except Exception as e:
                self.log_message(f"⚠️ Error stopping: {e}")

    def toggle_buttons_state(self, state):
        for btn in self.operation_buttons:
            btn.configure(state=state)
        self.stop_button.configure(state="normal" if state == "disabled" else "disabled")

    def run_action(self, action_type="translate"):
        file_path = self.file_entry.get().strip()
        dict_path = self.dict_entry.get().strip()

        if not file_path or not os.path.exists(file_path):
            self.log_message("⚠️ Valid DOCX file required!")
            return

        self.save_settings()
        s_lang_full = self.source_lang_dropdown.get()
        d_lang_full = self.dest_lang_dropdown.get()
        s_lang = "Auto" if s_lang_full == "Auto" else self.lang_map.get(s_lang_full, "en")
        d_lang = self.lang_map.get(d_lang_full, "fa")

        engine_selection = self.engine_dropdown.get()

        if action_type in ["polish", "align"]:
            engine_to_use = "chatgpt"
            method_to_use = "api"
            suffix_name = f"AI_{action_type.title()}"
            self.log_message(f"🚀 Action: {action_type.upper()} via API")
        else:
            suffix_name = engine_selection.replace(" ", "_").replace("(", "").replace(")", "")
            if engine_selection == "DeepL": engine_to_use = "deepl"; method_to_use = "phrasesblock"
            elif engine_selection == "Google": engine_to_use = "google"; method_to_use = "javascript"
            elif engine_selection == "Comet (Logged-in)": engine_to_use = "comet"; method_to_use = "phrasesblock"
            elif engine_selection == "Perplexity - Chrome": engine_to_use = "perplexity"; method_to_use = "phrasesblock"
            elif engine_selection == "ChatGPT (API)": engine_to_use = "chatgpt"; method_to_use = "api"
            elif engine_selection == "ChatGPT (Web)": engine_to_use = "chatgpt"; method_to_use = "phrasesblock"
            else: engine_to_use = "google"; method_to_use = "javascript"
            self.log_message(f"🚀 Action: RAW TRANSLATION ({engine_selection})")

        # Ensure default model is gpt-5-mini for AI actions, and gpt-5.4 for raw translation
        if action_type in ["polish", "align"]:
            aimodel_to_use = "gpt-5-mini"
        else:
            aimodel_to_use = "gpt-5.4"

        script_path = os.path.join("src", "machine-translate-docx.py")
        if not os.path.exists(script_path): script_path = "machine-translate-docx.py"
        if not os.path.exists(script_path):
            self.log_message("⚠️ Backend script not found!")
            return

        cmd = [
            sys.executable, script_path,
            "--docxfile", file_path,
            "--destlang", d_lang,
            "--silent", "--exitonsuccess",
            "--engine", engine_to_use,
            "--enginemethod", method_to_use,
            "--action", action_type,
            "--aimodel", aimodel_to_use
        ]

        if s_lang != "Auto": cmd.extend(["--srclang", s_lang])
        if self.split_sentences_checkbox.get(): cmd.append("--split")
        if self.show_browser_checkbox.get(): cmd.append("--showbrowser")
        if dict_path and os.path.exists(dict_path): cmd.extend(["--xlsxreplacefile", dict_path])

        self.toggle_buttons_state("disabled")
        threading.Thread(target=self.run_process, args=(cmd, suffix_name), daemon=True).start()

    def get_unique_path(self, path):
        if not os.path.exists(path): return path
        base, ext = os.path.splitext(path)
        counter = 1
        while True:
            new_path = f"{base}_{counter:02d}{ext}"
            if not os.path.exists(new_path): return new_path
            counter += 1

    def run_process(self, cmd, suffix_name):
        saved_filename = None
        file_renamed_successfully = False
        try:
            self.current_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
                text=True, bufsize=1, encoding='utf-8', errors='replace', cwd=os.getcwd()
            )

            for line in self.current_process.stdout:
                if line:
                    stripped_line = line.strip()
                    self.log_message(stripped_line)
                    if "Saved file name:" in stripped_line:
                        _, _, path_part = stripped_line.partition("Saved file name:")
                        if path_part:
                            saved_filename = path_part.strip()
                            if not file_renamed_successfully and os.path.exists(saved_filename):
                                file_dir = os.path.dirname(saved_filename)
                                file_name = os.path.basename(saved_filename)
                                name_no_ext, ext = os.path.splitext(file_name)
                                target_name = f"{name_no_ext}_{suffix_name}{ext}"
                                target_path = self.get_unique_path(os.path.join(file_dir, target_name))
                                try:
                                    os.rename(saved_filename, target_path)
                                    self.log_message(f"📄 Renamed to: {os.path.basename(target_path)}")
                                    file_renamed_successfully = True
                                    if platform.system() == 'Windows': os.startfile(file_dir)
                                except Exception as e:
                                    self.log_message(f"⚠️ Rename Error: {e}")

            self.current_process.wait()
            if self.current_process.returncode == 0:
                self.log_message("\n✅ Finished Successfully!")
            elif self.current_process.returncode not in [-9, 15]:
                self.log_message(f"\n❌ Process Error (Code {self.current_process.returncode})")
        except Exception as e:
            self.log_message(f"\n❌ Error: {str(e)}")
        finally:
             self.current_process = None
             self.after(0, lambda: self.toggle_buttons_state("normal"))

if __name__ == "__main__":
    app = MachineTranslatorApp()
    app.mainloop()
