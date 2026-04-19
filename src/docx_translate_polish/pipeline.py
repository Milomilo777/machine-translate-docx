"""Translation orchestration pipeline."""
import os
from typing import Optional
from .core.config import TranslationConfig
from .core.logger import TranslationLogger
from .docx_io.reader import DocxReader
from .docx_io.writer import DocxWriter
from .processing.noise_filter import NoiseFilter
from .translation.chunker import Chunker
from .translation.openai_engine import OpenAITranslator
from .translation.splitter import DocxLineSplitter

class TranslationPipeline:
    """Orchestrates the full DOCX translation and polishing workflow."""

    def __init__(self, config: Optional[TranslationConfig] = None):
        self.config = config or TranslationConfig()
        self.logger = TranslationLogger()
        self.reader = DocxReader()
        self.noise_filter = NoiseFilter()
        self.chunker = Chunker()
        self.translator = OpenAITranslator(model=self.config.default_model)
        self.splitter = DocxLineSplitter(model=self.config.default_model)

    def run(self, input_path: str, src_lang: str, dest_lang: str,
            output_path: Optional[str] = None, splitting_mode: str = "classic") -> str:
        """
        Executes the translation pipeline.
        Returns: Path to the generated output file.
        """
        if not output_path:
            stem, ext = os.path.splitext(input_path)
            output_path = f"{stem}_{dest_lang}{ext}"

        self.logger.info(f"Starting pipeline: {input_path} -> {output_path}")
        self.translator.set_filename(os.path.basename(input_path))

        # Step 1: Load and Extract
        doc = self.reader.load(input_path)
        cells = self.reader.extract_cells()
        self.logger.info(f"Extracted {len(cells)} cells from table.")

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
                self.logger.info(f"Skipping gray cell at row {cell_data['row_n']}")
                continue

            if cell_data['is_already_translated']:
                self.logger.info(f"Skipping already translated cell at row {cell_data['row_n']}")
                continue

            if not clean_text:
                continue

            processed_cells.append(cell_data)

        # Step 3: Chunking
        phrases = self.chunker.build_phrases(processed_cells)
        blocks = self.chunker.split_into_token_blocks(
            phrases, self.config.max_translation_block_size
        )
        self.logger.info(f"Grouped into {len(phrases)} phrases and {len(blocks)} API blocks.")

        # Step 4, 5, 6: Translate, Split, and Write
        writer = DocxWriter(doc)

        for block in blocks:
            block_lines = [p['text'] for p in block]
            translated_block = self.translator.translate_with_retry(
                block_lines, src_lang, dest_lang
            )

            translated_lines = translated_block.split("\n")

            # Re-map translated lines back to phrases and rows
            line_idx = 0
            for phrase in block:
                # Get the slice of translated lines for this phrase
                phrase_expected_lines = phrase['nb_lines']
                phrase_translation = " ".join(translated_lines[line_idx : line_idx + 1])
                line_idx += 1

                # Split phrase translation into rows
                row_translations = self.splitter.split(
                    mode=splitting_mode,
                    translation=phrase_translation,
                    expected_lines=len(phrase['rows']),
                    src_lang=src_lang,
                    dest_lang=dest_lang,
                    source_text=phrase['text']
                )

                for i, row_n in enumerate(phrase['rows']):
                    writer.write_translation(row_n, row_translations[i], dest_lang)

        # Step 7: Save
        writer.save(output_path)
        self.logger.info(f"Pipeline completed. Output saved to {output_path}")

        return output_path
