# Workflow Documentation

## Input Format
The system expects a 3-column DOCX table:
- **Column 0**: Row index / ID.
- **Column 1**: English source text.
- **Column 2**: Translation target (if empty, it will be populated).

## Execution Steps
1. **File Load**: `DocxReader` opens the document and validates the table structure.
2. **Cell Extraction**: Cells are extracted while checking for existing translations.
3. **Noise Filtering**: Formatting artifacts and unwanted shading are removed.
4. **Phrase Chunker**: Cells are grouped into logical phrases based on punctuation.
5. **Token Chunker**: Phrases are grouped into blocks that fit within LLM token limits.
6. **Translation**: `OpenAITranslator` sends blocks to the API with retry logic.
7. **Splitting**: `DocxLineSplitter` ensures the translated text matches the original line structure.
8. **Writing**: `DocxWriter` populates the target column with RTL/LTR awareness.
9. **Save**: The document is saved with a language-suffixed filename.

## Noise Filtering Logic
- Skips runs/paragraphs with specific shading colors defined in config.
- Skips runs with strike, double_strike, or specific highlight colors (RED, PINK, GRAY).
- Normalizes whitespace and removes control tags like `<pause>` or `<enter>`.

## Splitting Modes
- **AI Mode**: (Requires external splitting logic) Uses LLM to intelligently split text.
- **Classic Mode**: Deterministic split by newline with padding/trimming to match expected line counts.
