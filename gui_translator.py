import os
import sys
import threading
import json
import subprocess
import time
from typing import List, Optional, Dict, Any
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

# ── src path setup ────────────────────────────────────────────────────────────
import sys as _sys
import os as _os
_src_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "src")
if _src_path not in _sys.path:
    _sys.path.insert(0, _src_path)

from src.utils.pipeline_guard import validate_selected_steps
import json as _json_state
from pathlib import Path as _PathState

_GUI_STATE_FILE = _PathState(__file__).parent / "gui_state.json"


def _load_gui_state() -> dict:
    try:
        return _json_state.loads(
            _GUI_STATE_FILE.read_text(encoding="utf-8")
        )
    except Exception:
        return {}


def _save_gui_state(key: str, value: str):
    state = _load_gui_state()
    state[key] = str(value)
    try:
        _GUI_STATE_FILE.write_text(
            _json_state.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


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
            "Bulgarian": "bg", "Vietnamese": "vi", "Japanese": "ja",
            "Malay": "ms", "Punjabi": "pa",
        }

        self.settings = self.load_settings()

        self.title("SMTV Translation & Localization Lab")
        self.geometry("700x1380")
        self.minsize(600, 800)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(9, weight=1)

        # ── Title ─────────────────────────────────────────────────────────────
        # ── DOCX file ─────────────────────────────────────────────────────────
        self.file_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.file_frame.grid(row=1, column=0, padx=20, pady=(4, 2), sticky="ew")
        self.file_frame.grid_columnconfigure(0, weight=1)

        self.file_label = ctk.CTkLabel(
            self.file_frame, text="DOCX File",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.file_label.grid(row=0, column=0, padx=0, pady=(0, 5), sticky="w")

        self.file_entry_frame = ctk.CTkFrame(self.file_frame, fg_color="transparent")
        self.file_entry_frame.grid(row=1, column=0, sticky="ew")
        self.file_entry_frame.grid_columnconfigure(0, weight=1)

        self.file_entry = ctk.CTkEntry(
            self.file_entry_frame, placeholder_text="Select a DOCX file...",
            height=36, font=ctk.CTkFont(size=13),
        )
        self.file_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        self.browse_button = ctk.CTkButton(
            self.file_entry_frame, text="Browse", width=100, height=36,
            command=self.browse_file, font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.browse_button.grid(row=0, column=1)

        # ── Dictionary ────────────────────────────────────────────────────────
        self.dict_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.dict_frame.grid(row=2, column=0, padx=20, pady=(2, 2), sticky="ew")
        self.dict_frame.grid_columnconfigure(0, weight=1)

        self.dict_label = ctk.CTkLabel(
            self.dict_frame, text="Excel Dictionary (Optional)",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.dict_label.grid(row=0, column=0, padx=0, pady=(0, 5), sticky="w")

        self.dict_entry_frame = ctk.CTkFrame(self.dict_frame, fg_color="transparent")
        self.dict_entry_frame.grid(row=1, column=0, sticky="ew")
        self.dict_entry_frame.grid_columnconfigure(0, weight=1)

        self.dict_entry = ctk.CTkEntry(
            self.dict_entry_frame, placeholder_text="Select an XLSX dictionary file...",
            height=36, font=ctk.CTkFont(size=13),
        )
        self.dict_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.dict_entry.insert(0, self.settings.get("dict_path", ""))

        _state = _load_gui_state()
        _last = _state.get("last_docx", "")
        if _last and _PathState(_last).exists():
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, _last)

        self.browse_dict_button = ctk.CTkButton(
            self.dict_entry_frame, text="Browse", width=100, height=36,
            fg_color="#2c3e50", command=self.browse_dict,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.browse_dict_button.grid(row=0, column=1)

        # ── Settings ──────────────────────────────────────────────────────────
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.grid(row=3, column=0, padx=20, pady=(6, 4), sticky="ew")
        self.settings_frame.grid_columnconfigure(0, weight=1)
        self.settings_frame.grid_columnconfigure(1, weight=1)

        self.source_lang_label = ctk.CTkLabel(
            self.settings_frame, text="Source Language",
            font=ctk.CTkFont(size=13),
        )
        self.source_lang_label.grid(row=0, column=0, padx=15, pady=(3, 3), sticky="w")
        self.source_lang_dropdown = ctk.CTkComboBox(
            self.settings_frame, values=["Auto"] + list(self.lang_map.keys()),
            state="readonly", height=32,
        )
        self.source_lang_dropdown.set(self.settings.get("source_lang", "Auto"))
        self.source_lang_dropdown.grid(row=1, column=0, padx=15, pady=(0, 8), sticky="ew")

        self.dest_lang_label = ctk.CTkLabel(
            self.settings_frame, text="Destination Language",
            font=ctk.CTkFont(size=13),
        )
        self.dest_lang_label.grid(row=0, column=1, padx=15, pady=(3, 3), sticky="w")
        self.dest_lang_dropdown = ctk.CTkComboBox(
            self.settings_frame, values=list(self.lang_map.keys()),
            state="readonly", height=32,
        )
        self.dest_lang_dropdown.set(self.settings.get("dest_lang", "Persian"))
        self.dest_lang_dropdown.grid(row=1, column=1, padx=15, pady=(0, 8), sticky="ew")

        self.engine_label = ctk.CTkLabel(
            self.settings_frame,
            text="Translation Engine (For Raw Translation)",
            font=ctk.CTkFont(size=13),
        )
        self.engine_label.grid(
            row=2, column=0, columnspan=2, padx=15, pady=(3, 3), sticky="w",
        )
        self.engine_dropdown = ctk.CTkComboBox(
            self.settings_frame,
            values=["DeepL", "Google", "Comet (Logged-in)", "Perplexity - Chrome",
                    "ChatGPT (API)", "ChatGPT (Web)"],
            state="readonly", height=32,
        )
        self.engine_dropdown.set(self.settings.get("engine", "ChatGPT (API)"))
        self.engine_dropdown.grid(
            row=3, column=0, columnspan=2, padx=15, pady=(0, 13), sticky="ew",
        )

        self.aimodel_label = ctk.CTkLabel(
            self.settings_frame,
            text="AI Model",
            font=ctk.CTkFont(size=13),
        )
        self.aimodel_label.grid(
            row=4, column=0, columnspan=2, padx=15, pady=(3, 3), sticky="w",
        )
        self.aimodel_dropdown = ctk.CTkComboBox(
            self.settings_frame,
            values=["gpt-5.4-mini", "gpt-5.4"],
            state="readonly", height=32,
        )
        self.aimodel_dropdown.set(self.settings.get("aimodel", "gpt-5.4"))  #"gpt-5.4-mini"))
        self.aimodel_dropdown.grid(
            row=5, column=0, columnspan=2, padx=15, pady=(0, 13), sticky="ew",
        )

        # ── Options ───────────────────────────────────────────────────────────
        self.options_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.options_frame.grid(row=4, column=0, padx=20, pady=10, sticky="ew")

        self.split_sentences_checkbox = ctk.CTkCheckBox(
            self.options_frame, text="Split sentences",
            font=ctk.CTkFont(size=13),
        )
        self.split_sentences_checkbox.select()
        if self.settings.get("split", True) is False:
            self.split_sentences_checkbox.deselect()
        self.split_sentences_checkbox.grid(row=0, column=0, padx=0, pady=5, sticky="w")

        # ── Action buttons ────────────────────────────────────────────────────
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.grid(row=5, column=0, padx=20, pady=15, sticky="ew")
        self.action_frame.grid_columnconfigure(0, weight=1)
        self.action_frame.grid_columnconfigure(1, weight=1)

        self.btn_translate = ctk.CTkButton(
            self.action_frame, text="1. Translate (Raw)", height=45,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=lambda: self.run_action("translate"),
        )
        self.btn_translate.grid(row=0, column=0, padx=(0, 10), pady=(0, 10), sticky="ew")

        self.stop_button = ctk.CTkButton(
            self.action_frame, text="Stop Process", height=45,
            fg_color="#c0392b", hover_color="#e74c3c",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self.stop_translation, state="disabled",
        )
        self.stop_button.grid(row=0, column=1, pady=(0, 10), sticky="ew")

        self.btn_polish = ctk.CTkButton(
            self.action_frame, text="2. Translate + Polish", height=45, width=180,
            fg_color="#8e44ad", hover_color="#9b59b6",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=lambda: self.run_action("polish"),
        )
        self.btn_polish.grid(row=1, column=0, padx=(0, 10), sticky="w")

        self.withsource_var = ctk.StringVar(value="on")
        self.withsourcecheckbox = ctk.CTkCheckBox(
            self.action_frame,
            text="with source",
            variable=self.withsource_var,
            onvalue="on",
            offvalue="off",
            font=ctk.CTkFont(size=12),
        )
        self.withsourcecheckbox.grid(row=1, column=1, sticky="w", padx=8)

        self.btn_pipe15 = ctk.CTkButton(
            self.action_frame,
            text="🔄 Pipe 1.5\n(Translate+Polish\n+Align+Double)",
            height=45, fg_color="#2E4057", text_color="white",
            font=("Segoe UI", 9, "bold"), cursor="hand2",
            command=lambda: self.run_action("pipe_1_5"),
        )
        self.btn_pipe15.grid(row=2, column=0, columnspan=2, padx=(0, 0), sticky="ew")

        self.btn_align = ctk.CTkButton(
            self.action_frame, text="3. Align (AI)", height=45,
            fg_color="#27ae60", hover_color="#2ecc71",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=lambda: self.run_action("align"),
        )
        self.btn_align.grid(row=3, column=0, padx=(0, 10), pady=(10, 0), sticky="ew")

        self.btn_double = ctk.CTkButton(
            self.action_frame, text="4. Double (AI)", height=45,
            fg_color="#1a7a45", hover_color="#1e9e58",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=lambda: self.run_action("double"),
        )
        self.btn_double.grid(row=3, column=1, padx=(0, 0), pady=(10, 0), sticky="ew")

        self.btn_align_double = ctk.CTkButton(
            self.action_frame, text="5. align + double (AI)", height=45,
            fg_color="#1a5276", hover_color="#1f618d",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=lambda: self.run_action("align_double"),
        )
        self.btn_align_double.grid(
            row=4, column=0, columnspan=2, padx=5, pady=(10, 0), sticky="ew",
        )

        # Pipe 1.5 stage checkboxes
        self.pipe15_steps_frame = ctk.CTkFrame(self.action_frame, fg_color="transparent")
        self.pipe15_steps_frame.grid(
            row=5, column=0, columnspan=2, padx=5, pady=(5, 0), sticky="ew",
        )
        ctk.CTkLabel(
            self.pipe15_steps_frame, text="Pipe 1.5 stages:",
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(0, 8))

        self.c1_var = ctk.StringVar(value="on")
        self.c2_var = ctk.StringVar(value="on")
        self.c3_var = ctk.StringVar(value="on")
        self.c4_var = ctk.StringVar(value="on")

        ctk.CTkCheckBox(
            self.pipe15_steps_frame, text="C1 Translate (EN→FA)",
            variable=self.c1_var, onvalue="on", offvalue="off",
        ).pack(side="left", padx=5)
        ctk.CTkCheckBox(
            self.pipe15_steps_frame, text="C2 Polish (FA)",
            variable=self.c2_var, onvalue="on", offvalue="off",
        ).pack(side="left", padx=5)
        ctk.CTkCheckBox(
            self.pipe15_steps_frame, text="C3 Align",
            variable=self.c3_var, onvalue="on", offvalue="off",
        ).pack(side="left", padx=5)
        ctk.CTkCheckBox(
            self.pipe15_steps_frame, text="C4 Double",
            variable=self.c4_var, onvalue="on", offvalue="off",
        ).pack(side="left", padx=5)

        self.btn_pipeline = ctk.CTkButton(
            self.action_frame,
            text="🔁 Run Full Pipeline (1 → 2 → 3 → 4)",
            height=50, fg_color="#e67e22", hover_color="#f39c12",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=lambda: self.run_action("pipe_1_5"),
        )
        self.btn_pipeline.grid(row=6, column=0, columnspan=2, pady=(10, 0), sticky="ew")

        # ── Separator ─────────────────────────────────────────────────────────
        self.hd_separator = ctk.CTkFrame(
            self.action_frame, height=1, fg_color="#555555",
        )
        self.hd_separator.grid(
            row=7, column=0, columnspan=2, padx=5, pady=(12, 0), sticky="ew",
        )
        self.hd_section_label = ctk.CTkLabel(
            self.action_frame,
            text="── Para Bridge (Step 7) ──",
            font=ctk.CTkFont(size=11), text_color="#888888",
        )
        self.hd_section_label.grid(row=8, column=0, columnspan=2, pady=(4, 6))

        # ── Button 7: Para Bridge ─────────────────────────────────────────────
        self.btn_hybrid_double = ctk.CTkButton(
            self.action_frame,
            text="7. Para Bridge\n(Smart Redistributor)",
            height=48, fg_color="#0d7377", hover_color="#14a085",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self.run_para_bridge_action,
        )
        self.btn_hybrid_double.grid(
            row=9, column=0, columnspan=2, padx=5, pady=(0, 4), sticky="ew",
        )

        self.operation_buttons = [
            self.btn_translate, self.btn_polish, self.btn_pipe15,
            self.btn_align, self.btn_double, self.btn_align_double,
            self.btn_pipeline, self.btn_hybrid_double,
        ]

        # ── Log ───────────────────────────────────────────────────────────────
        self.log_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.log_frame.grid(row=9, column=0, padx=20, pady=(10, 20), sticky="nsew")
        self.log_frame.grid_columnconfigure(0, weight=1)
        self.log_frame.grid_rowconfigure(1, weight=1)

        self.log_label = ctk.CTkLabel(
            self.log_frame, text="Output Log",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.log_label.grid(row=0, column=0, padx=0, pady=(0, 5), sticky="w")

        self.copy_log_button = ctk.CTkButton(
            self.log_frame, text="Copy Log", width=80, height=24,
            command=self.copy_log,
        )
        self.copy_log_button.grid(row=0, column=0, sticky="e")

        self.log_textbox = ctk.CTkTextbox(
            self.log_frame, wrap="word", font=ctk.CTkFont(size=12), height=230,
        )
        self.log_textbox.grid(row=1, column=0, sticky="nsew")
        self.log_textbox.configure(state="normal")
        self.log_textbox.bind("<Key>", self.prevent_typing)

        self.log_message("Welcome to SMTV Translation & Localization Lab!")
        self.log_message("Ready. You can select and copy text (Ctrl+C) from this log anytime.")

    # ── UI helpers ────────────────────────────────────────────────────────────

    def prevent_typing(self, event):
        if event.keysym in ("Up", "Down", "Left", "Right", "Prior", "Next",
                            "Home", "End", "Control_L", "Control_R"):
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
            "dest_lang":   self.dest_lang_dropdown.get(),
            "engine":      self.engine_dropdown.get(),
            "aimodel":     self.aimodel_dropdown.get(),
            "dict_path":   self.dict_entry.get().strip(),
            "last_dir":    self.settings.get("last_dir", ""),
            "split":       bool(self.split_sentences_checkbox.get()),
        }
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            self.log_message(f"Error saving settings: {e}")

    def browse_file(self):
        initial_dir = self.settings.get("last_dir", os.path.expanduser("~"))
        filename = filedialog.askopenfilename(
            initialdir=initial_dir, title="Select DOCX File",
            filetypes=[("Word Documents", "*.docx"), ("All Files", "*.*")],
        )
        if filename:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, filename)
            self.settings["last_dir"] = os.path.dirname(filename)
            self.save_settings()
            self.log_message(f"Selected: {os.path.basename(filename)}")
            _save_gui_state("last_docx", str(filename))

    def browse_dict(self):
        initial_dir = self.settings.get("last_dir", os.path.expanduser("~"))
        filename = filedialog.askopenfilename(
            initialdir=initial_dir, title="Select Excel Dictionary",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
        )
        if filename:
            self.dict_entry.delete(0, "end")
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
        self.stop_button.configure(
            state="normal" if state == "disabled" else "disabled",
        )

    # ── Button 7: Para Bridge ─────────────────────────────────────────────────

    def run_para_bridge_action(self):
        file_path = self.file_entry.get().strip()
        if not file_path or not os.path.exists(file_path):
            self.log_message("⚠️ Valid DOCX file required!")
            return

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            self.log_message("⚠️ OPENAI_API_KEY not found in Windows environment!")
            return

        self.log_message("━" * 48)
        self.log_message("🔀 Para Bridge — starting...")
        self.log_message(f"📄 File : {os.path.basename(file_path)}")
        self.log_message(f"🤖 Model: gpt-5.4-mini  (fallback: gpt-5.4)")
        self.log_message("━" * 48)

        self.toggle_buttons_state("disabled")

        threading.Thread(
            target=self._run_para_bridge_thread,
            args=(file_path, api_key),
            daemon=True,
        ).start()

    def _run_para_bridge_thread(self, file_path: str, api_key: str):
        try:
            import sys as _sys, os as _os
            _pb = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "para_bridge")
            if _pb not in _sys.path:
                _sys.path.insert(0, _pb)

            from job_runner_para_bridge import run as run_para_bridge

            config = {
                "llm": {
                    "api_key":             api_key,
                    "primary_model":       "gpt-5.4-mini",
                    "soft_fallback_model": "gpt-5.4",
                },
                "bridge": {
                    "max_chars_per_row": 52,
                    "output_column":     3,
                },
                "paths": {
                    "prompt_para_bridge": str(
                        Path(__file__).parent / "para_bridge" / "prompt_para_bridge.txt"
                    ),
                },
            }

            stats = run_para_bridge(
                input_path=file_path,
                config=config,
                log_fn=self.log_message,
            )

            self.after(0, lambda: self._on_para_bridge_done(stats))

        except ImportError as e:
            self.after(0, lambda: self.log_message(f"❌ Import error: {e}"))
            self.after(0, lambda: self.toggle_buttons_state("normal"))
        except Exception as e:
            self.after(0, lambda: self.log_message(
                f"❌ Unexpected error: {type(e).__name__}: {e}"
            ))
            self.after(0, lambda: self.toggle_buttons_state("normal"))

    def _on_para_bridge_done(self, stats: dict):
        self.log_message("━" * 48)
        self.log_message("✅ Para Bridge completed!")
        self.log_message(
            f"   Paragraphs : {stats.get('total_paragraphs', 0)} total  "
            f"({stats.get('success', 0)} ✅  "
            f"{stats.get('skipped', 0)} ⏭   "
            f"{stats.get('failed', 0)} ❌)"
        )
        self.log_message(f"   Rows written: {stats.get('total_rows_written', 0)}")
        out = stats.get("output_file", "")
        self.log_message(f"   Output : {os.path.basename(out)}")
        self.log_message(
            f"   Log    : {os.path.basename(out.replace('.docx', '-log.json'))}"
        )
        self.log_message(f"   Time   : {stats.get('elapsed_total_s', 0):.1f}s")
        self.log_message("━" * 48)
        self.toggle_buttons_state("normal")

    # ── Actions (buttons 1-5 + pipeline) ─────────────────────────────────────

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
        engine_to_use = "chatgpt"
        method_to_use = "api"
        aimodel_to_use = self.aimodel_dropdown.get()
        suffix_name = f"AI_{action_type.title()}"

        if action_type == "polish":
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                self.log_message("⚠️ OPENAI_API_KEY not found in Windows environment!")
                return

            self.log_message("━" * 48)
            self.log_message("🚀 Action: POLISH via direct Persian_translate_polish pipeline")
            self.log_message(f"📄 File : {os.path.basename(file_path)}")
            self.log_message(f"🤖 Model: {aimodel_to_use}")
            self.log_message("━" * 48)

            self.toggle_buttons_state("disabled")
            threading.Thread(
                target=self._run_persian_translate_polish_thread,
                args=(file_path, dict_path, d_lang, aimodel_to_use, api_key),
                daemon=True,
            ).start()
            return

        script_path = os.path.join("src", "machine-translate-docx.py")
        if not os.path.exists(script_path):
            script_path = "machine-translate-docx.py"
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
            "--aimodel", aimodel_to_use,
        ]

        if action_type == "pipe_1_5":
            selected_steps = []
            if self.c1_var.get() == "on": selected_steps.append("C1")
            if self.c2_var.get() == "on": selected_steps.append("C2")
            if self.c3_var.get() == "on": selected_steps.append("C3")
            if self.c4_var.get() == "on": selected_steps.append("C4")

            if not selected_steps:
                self.log_message(
                    "⚠️ Error: حداقل یک مرحله را انتخاب کنید."
                )
                return

            if "C2" in selected_steps and "C3" not in selected_steps:
                messagebox.showerror(
                    "Invalid Selection",
                    "C2 cannot run without C3.\n"
                    "Please select C2+C3 or run the full pipeline.",
                )
                return

            doc_name = os.path.basename(file_path)
            errors = validate_selected_steps(
                selected_steps, file_path, "checkpoints/pipe15", doc_name,
            )
            if errors:
                for err in errors:
                    self.log_message(f"⚠️ {err}")
                return

            cmd.extend(["--pipe15-steps", ",".join(selected_steps)])

        if s_lang != "Auto":
            cmd.extend(["--srclang", s_lang])
        if self.split_sentences_checkbox.get():
            cmd.append("--split")
        cmd.append("--showbrowser")
        if action_type == "polish" and self.withsource_var.get() == "on":
            cmd.append("--with-source")
        if dict_path and os.path.exists(dict_path):
            cmd.extend(["--xlsxreplacefile", dict_path])

        self.toggle_buttons_state("disabled")
        threading.Thread(
            target=self.run_process, args=(cmd, suffix_name), daemon=True,
        ).start()

    def get_unique_path(self, path):
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        counter = 1
        while True:
            new_path = f"{base}_{counter:02d}{ext}"
            if not os.path.exists(new_path):
                return new_path
            counter += 1

    def run_process(self, cmd, suffix_name):
        saved_filename = None
        file_renamed_successfully = False
        try:
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True, bufsize=1, encoding="utf-8", errors="replace",
                cwd=os.getcwd(),
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
                                os.path.dirname(saved_filename)

            self.log_message(
                "📄 Action completed. Check the backend log above for the exact save path."
            )
            self.current_process.wait()
            if self.current_process.returncode == 0:
                self.log_message("\n✅ Finished Successfully!")
            elif self.current_process.returncode not in [-9, 15]:
                self.log_message(
                    f"\n❌ Process Error (Code {self.current_process.returncode})"
                )
        except Exception as e:
            self.log_message(f"\n❌ Error: {str(e)}")
        finally:
            self.current_process = None
            self.after(0, lambda: self.toggle_buttons_state("normal"))

    def _run_persian_translate_polish_thread(
        self,
        file_path: str,
        dict_path: str,
        dest_lang: str,
        model_name: str,
        api_key: str,
    ):
        try:
            from Persian_translate_polish import PipelineConfig, run_pipeline

            config = PipelineConfig(
                translate_model=model_name,
                polish_model=model_name,
                dest_lang=dest_lang,
                with_source=self.withsource_var.get() == "on",
                api_key=api_key,
                xlsxreplacefile=dict_path,
                xlsx_dict_path=dict_path,
            )

            stats = run_pipeline(config, file_path, log_fn=self.log_message)
            self.after(0, lambda: self._on_persian_translate_polish_done(stats))
        except SystemExit as e:
            self.after(0, lambda: self.log_message(f"❌ Persian_translate_polish exited: {e}"))
            self.after(0, lambda: self.toggle_buttons_state("normal"))
        except Exception as e:
            self.after(0, lambda: self.log_message(f"❌ Unexpected error: {type(e).__name__}: {e}"))
            self.after(0, lambda: self.toggle_buttons_state("normal"))

    def _on_persian_translate_polish_done(self, stats):
        self.log_message("━" * 48)
        self.log_message("✅ Persian_translate_polish completed!")
        self.log_message(f"   Output : {os.path.basename(stats.output_file)}")
        self.log_message(f"   Debug  : {os.path.basename(stats.debug_log_file)}")
        self.log_message(f"   Time   : {getattr(stats, 'elapsed_seconds', 0):.1f}s")
        self.log_message("━" * 48)
        self.toggle_buttons_state("normal")


if __name__ == "__main__":
    app = MachineTranslatorApp()
    app.mainloop()
