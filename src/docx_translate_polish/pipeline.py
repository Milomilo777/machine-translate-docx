"""Translation orchestration pipeline."""
import os
from typing import Optional, List, Callable
from .core.config import TranslationConfig
from .core.logger import PipelineFileLogger
from .docx_io.reader import DocxReader
from .docx_io.writer import DocxWriter
from .processing.noise_filter import NoiseFilter
from .translation.chunker import Chunker
from .translation.openai_engine import OpenAITranslator
from .translation.splitter import OpenAISubtitleSplitter

class TranslationPipeline:
    """Orchestrates the full DOCX translation and polishing workflow."""

    def __init__(self, config: Optional[TranslationConfig] = None):
        self.config = config or TranslationConfig()
        self._pipeline_logger = None  # will be created per run
        self.reader = DocxReader()
        self.noise_filter = NoiseFilter()
        self.chunker = Chunker()
        self.translator = OpenAITranslator(
            model=self.config.default_model,
            reasoning_effort=self.config.reasoning_effort
        )
        self.splitter = OpenAISubtitleSplitter(model=self.config.default_model)

    def run(self, input_path: str, src_lang: str, dest_lang: str,
            output_path: Optional[str] = None, splitting_mode: str = "classic",
            reasoning_effort: str = "medium",
            progress_callback: Optional[Callable[[str], None]] = None) -> str:
        """
        Executes the translation pipeline.
        Returns: Path to the generated output file.
        """
        if not output_path:
            stem, ext = os.path.splitext(input_path)
            output_path = f"{stem}_PER{ext}"

        self._pipeline_logger = PipelineFileLogger(output_docx_path=str(output_path))
        self._pipeline_logger.set_meta(
            model=self.config.default_model,
            reasoning_effort=reasoning_effort,
            src_lang=src_lang,
            dest_lang=dest_lang,
            splitting_mode=splitting_mode,
            source_file=str(input_path),
        )

        def log_info(msg):
            self._pipeline_logger.log_event("INFO", msg)
            if progress_callback:
                progress_callback(f"[INFO] {msg}")

        log_info("Pipeline started")
        log_info(f"Engine: {self.config.default_model} | Reasoning: {reasoning_effort}")
        log_info(f"Splitting: {splitting_mode} | Chunking: {'ON' if self.config.chunk_enabled else 'OFF'}")
        log_info(f"Starting pipeline: {input_path} -> {output_path}")

        self.translator.set_filename(os.path.basename(input_path))
        self.translator.set_reasoning_effort(reasoning_effort)
        self.splitter.set_filename(os.path.basename(input_path))

        # Step 1: Load and Extract
        doc = self.reader.load(input_path)
        cells = self.reader.extract_cells()
        log_info(f"Extracted {len(cells)} cells from table.")

        # Step 2: Noise Filter & Skip Check
        processed_cells = []
        for cell_data in cells:
            clean_text, is_gray, is_red = self.noise_filter.filter_cell(
                cell_data['cell_obj'], cell_data['row_n']
            )

            cell_data.update({
                'clean_text': clean_text,
                'is_gray': is_gray,
                'is_red': is_red
            })

            if is_gray:
                log_info(f"Skipping gray cell at row {cell_data['row_n']}")
                continue

            if cell_data['is_already_translated']:
                log_info(f"Skipping already translated cell at row {cell_data['row_n']}")
                continue

            if not clean_text:
                continue

            processed_cells.append(cell_data)

        # Step 3: Chunking
        phrases = self.chunker.build_phrases(processed_cells)

        blocks = []
        if self.config.chunk_enabled:
            log_info("Chunking requested but using single-block fallback for now.")
            blocks = [phrases]
        else:
            blocks = [phrases]

        log_info(f"Grouped into {len(phrases)} phrases and {len(blocks)} API blocks.")

        # Step 4, 5, 6: Translate, Split, and Write
        writer = DocxWriter(doc)

        for block_idx, block in enumerate(blocks):
            block_lines = [p['text'] for p in block]

            log_info(f"Translating block {block_idx+1}/{len(blocks)} ({len(block_lines)} lines)...")
            response_json, translated_block = self.translator.translate(
                src_lang, dest_lang, "\n".join(block_lines), logger=self._pipeline_logger
            )

            if not translated_block:
                log_info(f"Translation failed for block {block_idx+1}")
                continue

            translated_lines = translated_block.split("\n")

            # Re-map translated lines back to phrases and rows
            line_idx = 0
            for phrase in block:
                phrase_translation = " ".join(translated_lines[line_idx : line_idx + 1])
                line_idx += 1

                if splitting_mode == "ai":
                    row_translations = self.splitter.split_phrase(
                        src_lang, dest_lang, phrase['text'], phrase_translation, logger=self._pipeline_logger
                    )
                else:
                    row_translations = self.splitter.classic_split(
                        phrase_translation, len(phrase['rows'])
                    )

                for i, row_n in enumerate(phrase['rows']):
                    writer.write_translation(row_n, row_translations[i], dest_lang)

        # Step 7: Save
        writer.save(output_path)
        log_info(f"Pipeline finished. Output: {output_path}")
        log_saved = self._pipeline_logger.save()
        print(f"[LOG] Black-box log saved: {log_saved}")
        return output_path
