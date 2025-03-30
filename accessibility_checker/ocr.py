import re
import pytesseract
from pytesseract import Output
from typing import Tuple
import cv2

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class OcrText:
    def __init__(self, text: str, width: int, height: int, precision: float, bounds: Tuple[int, int, int, int]) -> None:
        self.text = text
        self.width = width
        self.height = height
        self.precision = precision
        self.bounds = bounds

    def compare_to(self, other: 'OcrText') -> bool:
        return self.text.strip().lower() == other.text.strip().lower() and (
                self.width != other.width or self.height != other.height
        )

    def __str__(self):
        return f"OcrText(text={self.text}, width={self.width}, height={self.height}, bounds={self.bounds}, precision={self.precision})"

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

    @staticmethod
    def bounds_are_similar(bounds1, bounds2, tolerance=5):
        """Verifica se os bounds são semelhantes dentro de uma tolerância."""
        return all(abs(b1 - b2) <= tolerance for b1, b2 in zip(bounds1, bounds2))

    def check_no_increase(self, other: 'OcrInfo') -> dict | bool:
        for ocr_text_1, ocr_text_2 in zip(self.data, other.data):
            if ocr_text_2.width <= ocr_text_1.width and ocr_text_2.height <= ocr_text_1.height:
                return {
                    'type': 'Unresponsive View - no increase',
                    'phrase': self.phrase,
                    'bounds': self.bounds,
                    'Success Criterion': '1.4.4 Resize Text',
                    'Level': 'AA'
                }
        return False

    def check_no_reduction(self, other: 'OcrInfo') -> dict | bool:
        for ocr_text_1, ocr_text_2 in zip(self.data, other.data):
            if ocr_text_2.width == ocr_text_1.width and ocr_text_2.height == ocr_text_1.height:
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
    def process_ocr(img, precision=0.3):
        # Conversão para escala de cinza
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Aplicação de técnicas de pré-processamento
        gray = cv2.bilateralFilter(gray, 11, 17, 17)
        gray = cv2.medianBlur(gray, 3)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Configurações do pytesseract
        custom_config = r'--oem 3 --psm 6'  # Assume bloco de texto uniforme

        # Extração de dados com OCR
        results = pytesseract.image_to_data(thresh, config=custom_config, output_type=Output.DICT)

        # Validação da precisão
        if not (0 <= precision <= 1):
            raise ValueError("A precisão precisa ser um valor entre 0 e 1.")

        parsed = []
        n_boxes = len(results['level'])
        for i in range(n_boxes):
            if results['conf'][i] == '-1':  # Ignora resultados sem confiança
                continue
            if float(results['conf'][i]) < (precision * 100):
                continue

            # Calcula bounds (posição real do texto na tela)
            x, y, w, h = results['left'][i], results['top'][i], results['width'][i], results['height'][i]
            bounds = (x, y, x + w, y + h)

            parsed.append(OcrText(
                text=results['text'][i],
                width=w,
                height=h,
                precision=float(results['conf'][i]) / 100,
                bounds=bounds
            ))

        return parsed
