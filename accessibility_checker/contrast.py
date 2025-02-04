# accessibility_checker/contrast.py
import cv2
import json
import re
import subprocess
from sklearn.cluster import KMeans
from lxml import etree

class ContrastChecker:
    def __init__(self, image_path: str):
        self.image_path = image_path
        self.image = cv2.imread(image_path)

    @staticmethod
    def calculate_contrast_ratio(color1, color2):
        def relative_luminance(color):
            r, g, b = [channel / 255.0 for channel in color]
            r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
            g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
            b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        l1 = relative_luminance(color1)
        l2 = relative_luminance(color2)
        return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

    def load_bounds_from_xml(self, xml_file: str):
        img = cv2.imread(self.image_path)
        if img is None:
            print(f"Image at {self.image_path} could not be loaded.")
            return []
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        height, width, _ = rgb_img.shape
        print(f"Image dimensions: width={width}, height={height}")
        tree = etree.parse(xml_file)
        root = tree.getroot()
        bounds_texts = []
        for node in root.iter('node'):
            bounds = node.attrib.get('bounds')
            text = node.attrib.get('text') or node.attrib.get('content-desc')
            class_name = node.attrib.get('class')
            if bounds and class_name == "android.widget.TextView" and text:
                bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))
                x1, y1, x2, y2 = bounds_tuple
                x1 = max(0, min(x1, width - 1))
                x2 = max(0, min(x2, width - 1))
                y1 = max(0, min(y1, height - 1))
                y2 = max(0, min(y2, height - 1))
                if x1 >= x2 or y1 >= y2:
                    print(f"Adjusted bounds are invalid: {x1}, {y1}, {x2}, {y2}. Skipping this node.")
                    continue
                area_text = rgb_img[y1:y2, x1:x2]
                pixels = area_text.reshape(-1, 3)
                if pixels.size == 0:
                    print(f"No pixels found in area for bounds {bounds_tuple}. Skipping this node.")
                    continue
                try:
                    kmeans = KMeans(n_clusters=2, random_state=0, n_init=10, algorithm='lloyd').fit(pixels)
                    colors = kmeans.cluster_centers_
                    color1, color2 = map(lambda c: tuple(map(int, c)), colors)
                    luminance1 = 0.2126 * color1[0] + 0.7152 * color1[1] + 0.0722 * color1[2]
                    luminance2 = 0.2126 * color2[0] + 0.7152 * color2[1] + 0.0722 * color2[2]
                    text_color, bg_color = (color1, color2) if luminance1 < luminance2 else (color2, color1)
                    bounds_texts.append((bounds_tuple, text.strip(), text_color, bg_color))
                except Exception as e:
                    print(f"Exception occurred during KMeans clustering: {e}")
                    continue
        return bounds_texts

    def check_text_contrast_with_tolerance(self, bounds_texts, device_density, default_min_contrast=4.5):
        """
        Verifica o contraste dos textos considerando a altura estimada (em dp)
        para determinar se o texto é grande ou normal.
        Se a altura (em dp) for ≥ 18dp, o mínimo exigido é 3:1; caso contrário, 4.5:1.
        """
        contrast_failures = []
        for (bounds, text, text_color, bg_color) in bounds_texts:
            x1, y1, x2, y2 = bounds
            height_pixels = y2 - y1
            height_dp = height_pixels / device_density
            print(f"[DEBUG] Altura: {height_dp} dp")
            required_contrast = 3.0 if height_dp >= 18 else default_min_contrast
            print(f"[DEBUG] Contraste necessário: {required_contrast}")
            contrast_ratio = self.calculate_contrast_ratio(text_color, bg_color)
            print(f"[DEBUG] Proporção de contraste: {contrast_ratio}")
            if contrast_ratio < required_contrast:
                failure = {
                    "type": "Contrast Failure",
                    "phrase": text,
                    "bounds": list(bounds),
                    "Contrast Ratio": f"{contrast_ratio:.2f}:1",
                    "Level Status": {"AA": "Fail", "AAA": "Fail"},
                    "Success Criterion": "1.4.3 Contrast (Minimum)",
                    "Level": "AA",
                    "Details": f"Texto com altura estimada de {height_dp:.1f}dp (equivalente a {height_pixels}px) requer um contraste mínimo de {required_contrast}:1."
                }
                contrast_failures.append(failure)
        return contrast_failures

    @staticmethod
    def load_existing_errors(file_path: str):
        import os
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as json_file:
                try:
                    return json.load(json_file)
                except json.JSONDecodeError:
                    print("Error reading existing JSON file.")
                    return []
        return []

    @staticmethod
    def save_errors_to_json(errors, file_path: str):
        with open(file_path, "w", encoding="utf-8") as json_file:
            json.dump(errors, json_file, ensure_ascii=False, indent=4)
        print("Errors saved in", file_path)
