# accessibility_checker/__init__.py

from .ui_element import UIElement, check_overlapping_elements, check_duplicate_text
from .ocr import OcrText, OcrInfo
from .extractor import XmlNodeBoundsExtractor
from .contrast import ContrastChecker
from .accessibility import AccessibilityChecker
from .error_highlighter import ErrorHighlighter
