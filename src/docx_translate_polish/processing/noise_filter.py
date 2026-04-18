"""Text noise filtering and cleaning."""
import re
from typing import Tuple, List, Optional
from lxml import etree
from docx.enum.text import WD_COLOR_INDEX
from ..core.config import shading_color_ignore_text

class NoiseFilter:
    """Filters unwanted formatting and noise from cell text."""

    def _get_shading_color(self, element_xml: str, tag: str) -> Optional[str]:
        try:
            xml_obj = etree.fromstring(element_xml)
            namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            for e in xml_obj.findall(f'.//w:{tag}/w:shd', namespaces):
                return e.attrib.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}fill')
        except:
            pass
        return None

    def filter_cell(self, cell, row_n: int) -> Tuple[str, bool, bool]:
        """
        Cleans text and identifies if a cell is 'gray' (ignored) or 'red'.
        Returns: (clean_text, is_gray, is_red)
        """
        clean_text_parts = []
        cell_is_gray = None
        cell_is_red = None

        for paragraph in cell.paragraphs:
            p_shading = self._get_shading_color(paragraph._element.xml, "pPr")
            if p_shading in shading_color_ignore_text:
                cell_is_gray = True
                continue

            for run in paragraph.runs:
                r_shading = self._get_shading_color(run._element.xml, "rPr")

                # Check for ignored colors/styles
                is_ignored_style = (
                    run.font.highlight_color in [
                        WD_COLOR_INDEX.GRAY_25, WD_COLOR_INDEX.GRAY_50,
                        WD_COLOR_INDEX.PINK, WD_COLOR_INDEX.RED
                    ] or
                    run.font.strike or
                    run.font.double_strike or
                    r_shading in shading_color_ignore_text
                )

                if is_ignored_style:
                    if cell_is_gray is None: cell_is_gray = True
                    continue
                else:
                    if run.text.strip():
                        if cell_is_gray is None: cell_is_gray = False
                        else: cell_is_gray = cell_is_gray and False

                # Check for red text
                if str(run.font.color.rgb) == "FF0000":
                    if cell_is_red is None: cell_is_red = True
                elif run.text.strip():
                    if cell_is_red is None: cell_is_red = False
                    else: cell_is_red = cell_is_red and False

                clean_text_parts.append(run.text)

        raw_text = "".join(clean_text_parts)

        # Normalization
        # Remove <pause>, <enter>
        text = re.sub(r'(?i)<pause>|<enter>', ' ', raw_text)
        # Replace \r, \n, \u2028, \u2029 with single space
        text = re.sub(r'[\r\n\u2028\u2029]', ' ', text)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        # Replace curly apostrophe with straight
        text = text.replace('’', "'")

        return text.strip(), bool(cell_is_gray), bool(cell_is_red)
