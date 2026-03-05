import docx

class DocxParser:
    def extract_paragraphs(self, file_path: str) -> list[str]:
        document = docx.Document(file_path)
        paragraphs = []
        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                paragraphs.append(paragraph.text)
        return paragraphs
