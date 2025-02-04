# accessibility_checker/ocr.py
import re
import pytesseract
from pytesseract import Output
from typing import Tuple

class OcrText:
    def __init__(self, text: str, width: int, height: int, precision: float) -> None:
        self.text = text
        self.width = width
        self.height = height
        self.precision = precision

    def compare_to(self, other: 'OcrText') -> bool:
        if self.text != other.text:
            return False
        if self.width != other.width or self.height != other.height:
            return True
        return False

    def __str__(self):
        return f"OcrText(text={self.text}, width={self.width}, height={self.height}, precision={self.precision})"

    def __repr__(self):
        return self.__str__()

class OcrInfo:
    def __init__(self, img, precision=0.7, bounds: Tuple[int, int, int, int] = None):
        self._image = img.copy()
        self._data = self.process_ocr(self._image, precision)
        self.bounds = bounds

    @property
    def phrase(self):
        return ' '.join(obj.text for obj in self._data)

    @staticmethod
    def parse_bound_boxes(bound_str: str) -> Tuple[int, int, int, int]:
        match = re.findall(r'\d+', bound_str)
        if len(match) != 4:
            raise ValueError("Formato de bounds inválido. Esperado: '[x1, y1][x2, y2]'")
        return tuple(map(int, match))

    def check_no_increase(self, other: 'OcrInfo') -> dict | bool:
        for text1, text2 in zip(self._data, other._data):
            if text2.width <= text1.width and text2.height <= text1.height:
                return {
                    'type': 'Unresponsive View - no increase',
                    'phrase': self.phrase,
                    'bounds': self.bounds,
                    'Success Criterion': '1.4.4 Resize Text',
                    'Level': 'AA'
                }
        return False

    def check_no_reduction(self, other: 'OcrInfo') -> dict | bool:
        for text1, text2 in zip(self._data, other._data):
            if text2.width == text1.width and text2.height == text1.height:
                return {
                    'type': 'Unresponsive View - without reduction',
                    'phrase': self.phrase,
                    'bounds': self.bounds,
                    'Success Criterion': '1.4.4 Resize Text',
                    'Level': 'AA'
                }
        return False

    def compare_processed_data(self, other: 'OcrInfo') -> bool:
        if self.phrase != other.phrase:
            return True
        for text1, text2 in zip(self._data, other._data):
            if text1.compare_to(text2):
                return True
        return False

    @property
    def data(self):
        return self._data

    @property
    def image(self):
        return self._image

    @staticmethod
    def process_ocr(img, precision=0.7):
        results = pytesseract.image_to_data(img, output_type=Output.DICT)
        if not (0 <= precision <= 1):
            raise ValueError("A precisão precisa ser um valor entre 0 e 1.")
        parsed = []
        n_boxes = len(results['level'])
        for i in range(n_boxes):
            if results['conf'][i] < (precision * 100):
                continue
            parsed.append(OcrText(
                text=results['text'][i],
                width=results['width'][i],
                height=results['height'][i],
                precision=results['conf'][i] / 100
            ))
        return parsed
