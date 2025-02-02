from UIElement import UIElement, check_overlapping_elements, check_duplicate_text

import json
from typing import Dict, Tuple, List
import pytesseract
from pytesseract import Output
import cv2
import os
from lxml import etree
import re
import numpy as np
from sklearn.cluster import KMeans
import subprocess

os.environ['LOKY_MAX_CPU_COUNT'] = '8'

class ErrorHighlighter:
    def __init__(self, image_path: str):
        self.original_image = cv2.imread(image_path)
        self.image_copies = {}

        self.error_colors = {
            'Unresponsive View - no increase': (0, 255, 0),
            'Unresponsive View - without reduction': (0, 255, 0),
            'Contrast Failure': (255, 0, 0),
            'Missing Content Description': (0, 0, 255),
            'Non-essential Content Description': (255, 0, 255),
            'Link Purpose Failure': (0, 0, 255),
            'Missing Accessible Name': (128, 0, 128),
            'Missing State Information': (255, 165, 0),
            'Missing Error Description': (0, 0, 255),
            'Missing Label or Instruction': (0, 0, 255),
            'Empty Label': (0, 0, 128),
            'Empty Hint': (0, 0, 128),
            'Focus Order Failure': (0, 0, 255),
            'Target Size Failure': (255, 0, 0),
            'Target Size Failure (Minimum)': (255, 0, 0),
        }

    def highlight_error(self, error_info: dict):
        error_type = error_info['type'].strip()
        bounds = error_info['bounds']

        # Obter ou criar a cópia da imagem para este tipo de erro
        if error_type not in self.image_copies:
            self.image_copies[error_type] = self.original_image.copy()

        image_copy = self.image_copies[error_type]

        x1, y1, x2, y2 = bounds
        height, width, _ = self.original_image.shape

        # Garantir que os bounds estejam dentro dos limites da imagem
        x1 = max(0, min(x1, width - 1))
        x2 = max(0, min(x2, width - 1))
        y1 = max(0, min(y1, height - 1))
        y2 = max(0, min(y2, height - 1))

        color = self.error_colors.get(error_type, (0, 0, 0))  # Cor padrão preta se o tipo não for encontrado
        thickness = 3

        cv2.rectangle(image_copy, (x1, y1), (x2, y2), color, thickness)
        cv2.putText(image_copy, error_type.replace('_', ' '), (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    def save_images(self, output_folder: str = "output_images"):
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        for error_type, image in self.image_copies.items():
            # Remover caracteres inválidos do nome do arquivo
            safe_error_type = re.sub(r'[<>:"/\\|?*]', '_', error_type)
            file_name = safe_error_type.replace(' ', '_') + ".png"
            output_path = os.path.join(output_folder, file_name)
            cv2.imwrite(output_path, image)
            print(f"Image saved at: {output_path}")

class OcrText:
    def __init__(self, text: str, width: int, height: int, precision: float) -> None:
        self.text = text
        self.width = width
        self.height = height
        self.precision = precision

    def compare_to(self, other: 'OcrText') -> bool:
        if self.text != other.text:
            return False

        diff_width = self.width - other.width
        diff_height = self.height - other.height

        if diff_width != 0 or diff_height != 0:
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
        return ' '.join((obj.text for obj in self.data))

    def get_bound_boxes(self, x1, y1, x2, y2):
        return f"[{x1}, {y1}][{x2}, {y2}]"

    @staticmethod
    def parse_bound_boxes(bound_str: str) -> Tuple[int, int, int, int]:
        # print(f"bound_str: {bound_str}")
        match = re.findall(r'\d+', bound_str)
        assert len(match) == 4, "Formato de bounds inválido. Esperado: '[x1, y1][x2, y2]'"
        x1, y1, x2, y2 = map(int, match)
        return x1, y1, x2, y2

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

        for ocr_text_1, ocr_text_2 in zip(self.data, other.data):
            if ocr_text_1.compare_to(ocr_text_2):
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
        results = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        assert 0 <= precision <= 1, ValueError("A precisão precisa ser um valor entre 0 e 1.")
        n_boxes_found = len(results['level'])
        parsed = []
        for idx_box in range(n_boxes_found):
            if results['conf'][idx_box] < (precision * 100):
                continue
            parsed.append(OcrText(
                text=results['text'][idx_box],
                width=results['width'][idx_box],
                height=results['height'][idx_box],
                precision=results['conf'][idx_box] / 100
            ))
        return parsed

class XmlNodeBoundsExtractor:
    def __init__(self, xml_file_path, image):
        self.xml_file_path = xml_file_path
        self.image = image
        self.nodes_with_bounds = []

    def extract_bounds(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()

        node_types = [
            "android.widget.TextView", "android.widget.Button", "android.widget.EditText"
        ]

        for node in root.iter("node"):
            node_class = node.get("class")
            text = node.get("text", "").strip()
            content_desc = node.get("content-desc", "").strip()
            bounds = node.get("bounds")

            if node_class in node_types and (text or content_desc):
                self.nodes_with_bounds.append({
                    "class": node_class,
                    "text": text,
                    "content-desc": content_desc,
                    "bounds": bounds
                })

        return self.nodes_with_bounds

    def extract_non_textual_nodes(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()

        non_textual_nodes = []

        # Lista de classes que geralmente representam conteúdo não textual
        non_textual_classes = [
            "android.widget.ImageView",
            "android.widget.ImageButton",
            "android.widget.VideoView",
            "android.widget.CheckBox",
            "android.widget.Switch",
            # Adicione outras classes conforme necessário
        ]

        for node in root.iter("node"):
            node_class = node.get("class")
            bounds = node.get("bounds")
            content_desc = node.get("content-desc", "").strip()
            resource_id = node.get("resource-id", "").strip()
            clickable = node.get("clickable", "false") == "true"
            important_for_accessibility = node.get("importantForAccessibility", "").strip()

            if node_class in non_textual_classes:
                non_textual_nodes.append({
                    "class": node_class,
                    "bounds": bounds,
                    "content-desc": content_desc,
                    "resource_id": resource_id,
                    "clickable": clickable,
                    "important_for_accessibility": important_for_accessibility
                })

        return non_textual_nodes

    def extract_interactive_elements(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()

        interactive_elements = []

        for node in root.iter("node"):
            node_class = node.get("class")
            bounds = node.get("bounds")
            text = node.get("text", "").strip()
            content_desc = node.get("content-desc", "").strip()
            resource_id = node.get("resource-id", "").strip()
            clickable = node.get("clickable", "false") == "true"
            focusable = node.get("focusable", "false") == "true"

            print(f"[DEBUG] Processando nó: class={node_class}, bounds={bounds}, text='{text}', "
                  f"content-desc='{content_desc}', clickable={clickable}, focusable={focusable}")

            if clickable or focusable:
                interactive_elements.append({
                    "class": node_class,
                    "bounds": bounds,
                    "text": text,
                    "content-desc": content_desc,
                    "resource_id": resource_id,
                    "clickable": clickable,
                    "focusable": focusable
                })

        return interactive_elements

    def get_ocr_info_instances(self):
        ocr_info_list = []
        for node in self.nodes_with_bounds:
            # print(f"node['bounds']: {node['bounds']}")
            x1, y1, x2, y2 = OcrInfo.parse_bound_boxes(node['bounds'])

            if x1 == x2 or y1 == y2:
                print(f"Ignorando bounds inválidos: {node['bounds']}")
                continue

            ocr_info = OcrInfo(self.image[y1:y2, x1:x2], bounds=(x1, y1, x2, y2))
            # print(f"ocr_info: {ocr_info.data}")

            ocr_info_list.append(ocr_info)
        return ocr_info_list

    def extract_ui_components(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()

        ui_components = []

        for node in root.iter("node"):
            node_class = node.get("class")
            bounds = node.get("bounds")
            text = node.get("text", "").strip()
            content_desc = node.get("content-desc", "").strip()
            resource_id = node.get("resource-id", "").strip()
            clickable = node.get("clickable", "false") == "true"
            checkable = node.get("checkable", "false") == "true"
            checked = node.get("checked", "false") == "true"
            enabled = node.get("enabled", "false") == "true"
            focusable = node.get("focusable", "false") == "true"
            selected = node.get("selected", "false") == "true"

            ui_components.append({
                "class": node_class,
                "bounds": bounds,
                "text": text,
                "content-desc": content_desc,
                "resource_id": resource_id,
                "clickable": clickable,
                "checkable": checkable,
                "checked": checked,
                "enabled": enabled,
                "focusable": focusable,
                "selected": selected
            })

        return ui_components

    def extract_ui_components_as_elements(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()
        print("[DEBUG] Nós encontrados no XML:", len(list(root.iter("node"))))

        ui_elements = []

        for node in root.iter("node"):
            print("[DEBUG] Processando nó:", etree.tostring(node))
            node_class = node.get("class")
            bounds = node.get("bounds")
            text = node.get("text", "").strip()
            content_desc = node.get("content-desc", "").strip()
            resource_id = node.get("resource-id", "").strip()

            # Converta os bounds para tupla, garantindo que 'bounds' seja convertido para string
            bounds_tuple = tuple(map(int, re.findall(r'\d+', str(bounds))))

            # Crie um objeto UIElement
            ui_element = UIElement(
                id=resource_id or node_class,
                content=text or content_desc,
                bounds=bounds_tuple
            )
            ui_elements.append(ui_element)

        return ui_elements

    def extract_input_fields_and_errors(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()

        input_fields = []
        error_messages = []

        # Primeiro, coletar todos os nós
        nodes = [node for node in root.iter("node")]

        for idx, node in enumerate(nodes):
            node_class = node.get("class")
            resource_id = node.get("resource-id", "").strip()
            text = node.get("text", "").strip()
            content_desc = node.get("content-desc", "").strip()
            bounds = node.get("bounds")
            focused = node.get("focused", "false") == "true"
            enabled = node.get("enabled", "false") == "true"

            if node_class == "android.widget.EditText":
                input_field = {
                    "class": node_class,
                    "resource_id": resource_id,
                    "text": text,
                    "content-desc": content_desc,
                    "bounds": bounds,
                    "focused": focused,
                    "enabled": enabled,
                    "error_message": None
                }

                # Verificar se o próximo irmão é um TextView com mensagem de erro
                if idx + 1 < len(nodes):
                    next_node = nodes[idx + 1]
                    next_node_class = next_node.get("class")
                    next_text = next_node.get("text", "").strip()
                    if next_node_class == "android.widget.TextView" and next_text:
                        # Podemos supor que este TextView é uma mensagem de erro associada
                        input_field["error_message"] = next_text
                        input_field["error_bounds"] = next_node.get("bounds")

                input_fields.append(input_field)

        return input_fields

    def extract_input_fields_and_labels(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()

        input_fields = []

        # Primeiro, coletar todos os nós
        nodes = [node for node in root.iter("node")]

        for idx, node in enumerate(nodes):
            node_class = node.get("class")
            resource_id = node.get("resource-id", "").strip()
            text = node.get("text", "").strip()
            content_desc = node.get("content-desc", "").strip()
            hint = node.get("hint", "").strip()
            bounds = node.get("bounds")

            if node_class == "android.widget.EditText":
                input_field = {
                    "class": node_class,
                    "resource_id": resource_id,
                    "text": text,
                    "content-desc": content_desc,
                    "hint": hint,
                    "bounds": bounds,
                    "label": None,
                    "label_bounds": None
                }

                # Verificar se há um rótulo associado usando o atributo labelFor
                label_for = node.get("labelFor", "").strip()
                if label_for:
                    # Procurar o nó com este resource_id
                    for possible_label in nodes:
                        if possible_label.get("resource-id", "").strip() == label_for:
                            input_field["label"] = possible_label.get("text", "").strip()
                            input_field["label_bounds"] = possible_label.get("bounds")
                            break
                else:
                    # Se não houver labelFor, procurar TextViews próximos que possam ser rótulos
                    # Verificar o nó anterior
                    if idx > 0:
                        prev_node = nodes[idx - 1]
                        if prev_node.get("class") == "android.widget.TextView":
                            input_field["label"] = prev_node.get("text", "").strip()
                            input_field["label_bounds"] = prev_node.get("bounds")
                input_fields.append(input_field)

        return input_fields

    def extract_focusable_elements(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()

        focusable_elements = []

        # Função recursiva para percorrer a árvore e manter a ordem
        def traverse(node, focusable_elements):
            for child in node:
                # Utiliza (child.get("atributo") or "") para garantir uma string
                node_class = (child.get("class") or "").strip()
                resource_id = (child.get("resource-id") or "").strip()
                text = (child.get("text") or "").strip()
                content_desc = (child.get("content-desc") or "").strip()
                bounds = child.get("bounds") or ""
                clickable = (child.get("clickable") or "false") == "true"
                focusable = (child.get("focusable") or "false") == "true"

                if focusable and bounds:
                    # Certifique-se de que os bounds existam antes de convertê-los
                    bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))
                    focusable_elements.append({
                        "class": node_class,
                        "resource_id": resource_id,
                        "text": text,
                        "content-desc": content_desc,
                        "bounds": bounds,
                        "bounds_tuple": bounds_tuple,
                        "node": child  # Manter referência para atributos adicionais
                    })

                # Chamada recursiva para percorrer os filhos
                traverse(child, focusable_elements)

        traverse(root, focusable_elements)
        return focusable_elements

    def extract_interactive_elements_with_dimensions(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()

        interactive_elements = []

        for node in root.iter("node"):
            node_class = node.get("class")
            resource_id = node.get("resource-id", "").strip()
            content_desc = node.get("content-desc", "").strip()
            bounds = node.get("bounds")
            clickable = node.get("clickable", "false") == "true"
            focusable = node.get("focusable", "false") == "true"
            text = node.get("text", "").strip()

            if clickable or focusable:
                # Obter as coordenadas do bounds
                bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))
                x1, y1, x2, y2 = bounds_tuple
                width = x2 - x1
                height = y2 - y1

                interactive_elements.append({
                    "class": node_class,
                    "resource_id": resource_id,
                    "content-desc": content_desc,
                    "bounds": bounds,
                    "bounds_tuple": bounds_tuple,
                    "width": width,
                    "height": height,
                    "clickable": clickable,
                    "focusable": focusable,
                    "text": text
                })

        return interactive_elements

    def __str__(self):
        result = "Nodes with bounds:\n"
        for node in self.nodes_with_bounds:
            result += f"Class: {node['class']}, Text: {node['text']}, Content-desc: {node['content-desc']}, Bounds: {node['bounds']}\n"
        return result

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

    def load_bounds_from_xml(self, xml_file):
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

                # Ajustar coordenadas
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

    # def check_text_contrast_with_tolerance(self, bounds_texts, min_contrast=4.5):
    #     contrast_failures = []
    #
    #     for (bounds, text, text_color, bg_color) in bounds_texts:
    #         contrast_ratio = self.calculate_contrast_ratio(text_color, bg_color)
    #         if contrast_ratio < min_contrast:
    #             failure = {
    #                 "type": "Contrast Failure",
    #                 "phrase": text,
    #                 "bounds": list(bounds),
    #                 "Contrast Ratio": f"{contrast_ratio:.2f}:1",
    #                 "Level Status": {
    #                     "AA": "Fail",
    #                     "AAA": "Fail"
    #                 },
    #                 "Success Criterion": "1.4.3 Contrast (Minimum)",
    #                 "Level": "AA"
    #             }
    #             contrast_failures.append(failure)
    #     return contrast_failures

    def check_text_contrast_with_tolerance(self, bounds_texts, device_density, default_min_contrast=4.5):
        """
        Verifica o contraste dos textos considerando o tamanho estimado (altura do bounding box)
        em dp para definir se o texto é grande ou normal.

        Se a altura (em dp) for maior ou igual a 18dp, o texto é considerado grande e exige um
        contraste mínimo de 3:1. Caso contrário, o mínimo exigido é 4.5:1.

        :param bounds_texts: Lista de tuplas (bounds, text, text_color, bg_color).
        :param device_density: Fator de densidade do dispositivo (obtido pela função get_device_density()).
        :param default_min_contrast: Contraste mínimo padrão para textos normais.
        :return: Lista de dicionários com falhas de contraste.
        """
        contrast_failures = []
        for (bounds, text, text_color, bg_color) in bounds_texts:
            x1, y1, x2, y2 = bounds
            height_pixels = y2 - y1
            # Converter a altura para dp (density-independent pixels)
            height_dp = height_pixels / device_density

            print(f"[DEBUG] Altura: {height_dp} dp")

            # Definir o contraste mínimo com base no tamanho do texto (WCAG: 18pt ou 14pt negrito)
            # Aqui, usamos 18dp como limiar para textos grandes (valor de exemplo)
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
                    "Level Status": {
                        "AA": "Fail",
                        "AAA": "Fail"
                    },
                    "Success Criterion": "1.4.3 Contrast (Minimum)",
                    "Level": "AA",
                    "Details": f"Texto com altura estimada de {height_dp:.1f}dp (equivalente a {height_pixels}px) requer um contraste mínimo de {required_contrast}:1."
                }
                contrast_failures.append(failure)
        return contrast_failures

    @staticmethod
    def load_existing_errors(file_path):
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as json_file:
                try:
                    return json.load(json_file)
                except json.JSONDecodeError:
                    print("Error reading existing JSON file.")
                    return []
        return []

    @staticmethod
    def save_errors_to_json(errors, file_path):
        with open(file_path, "w", encoding="utf-8") as json_file:
            json.dump(errors, json_file, ensure_ascii=False, indent=4)
        print("Errors saved in", file_path)

class AccessibilityChecker:
    def __init__(self, extractor: XmlNodeBoundsExtractor, device_density=1.0):
        self.extractor = extractor
        self.device_density = device_density
        self.failures = []

    def check_gesture_navigation(self):
        """Verifica se elementos interativos não dependem exclusivamente de gestos para serem acionados,
        garantindo que sejam acessíveis por teclado ou leitores de tela (conforme critério 2.5.1)."""
        failures = []
        interactive_elements = self.extractor.extract_interactive_elements()

        print(f"[DEBUG] Elementos interativos extraídos: {interactive_elements}")

        for element in interactive_elements:
            bounds = element.get('bounds', '')
            bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))
            node_class = element.get('class', '')
            resource_id = element.get('resource_id', '')
            clickable = element.get('clickable', False)
            focusable = element.get('focusable', False)
            content_desc = element.get('content-desc', '')
            text = element.get('text', '')

            print(f"[DEBUG] Verificando elemento: class={node_class}, bounds={bounds}, "
                  f"clickable={clickable}, focusable={focusable}, content-desc='{content_desc}', text='{text}'")

            # Se o elemento é clicável mas não é focável, ele depende exclusivamente de gestos para interação.
            if clickable and not focusable:
                failure = {
                    "type": "Gesture-Only Navigation",
                    "class": node_class,
                    "resource_id": resource_id,
                    "bounds": list(bounds_tuple),
                    "content-desc": content_desc,
                    "text": text,
                    "Success Criterion": "2.5.1 Pointer Gestures",
                    "Level": "A",
                    "Recommendation": ("Certifique-se de que o elemento seja acessível por teclado ou leitor de tela. "
                                       "Para isso, defina 'focusable=true' no elemento ou forneça uma alternativa "
                                       "que permita sua ativação sem depender exclusivamente de gestos.")
                }
                print(f"[DEBUG] Falha detectada: {failure}")
                failures.append(failure)

        self.failures.extend(failures)

    def check_non_text_content(self):
        failures = []
        non_textual_nodes = self.extractor.extract_non_textual_nodes()
        for node in non_textual_nodes:
            content_desc = node['content-desc']
            bounds = node['bounds']
            node_class = node['class']
            clickable = node['clickable']
            resource_id = node['resource_id']
            important_for_accessibility = node.get('important_for_accessibility', '').strip()

            # Converter bounds para tupla de inteiros
            bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))

            # Elementos significativos (por exemplo, interativos) devem ter content-desc
            if clickable or resource_id:
                if not content_desc:
                    failure = {
                        "type": "Missing Content Description",
                        "class": node_class,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "1.1.1 Non-text Content",
                        "Level": "A",
                        "Recommendation": "Adicione uma descrição de conteúdo que descreva a finalidade deste elemento interativo."
                    }
                    failures.append(failure)
            else:
                # Elementos não significativos devem ter content-desc vazia ou serem ignorados pelas tecnologias assistivas
                if content_desc and content_desc.strip() != '':
                    failure = {
                        "type": "Non-essential Content Description Should Be Empty",
                        "class": node_class,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "1.1.1 Non-text Content",
                        "Level": "A",
                        "Recommendation": "Defina a descrição de conteúdo como uma string vazia ou marque o elemento como não importante para acessibilidade."
                    }
                    failures.append(failure)
                # Opcionalmente, verificar se importantForAccessibility está definido adequadamente
                if important_for_accessibility.lower() not in ['no', 'no-hide-descendants']:
                    failure = {
                        "type": "Non-essential Element Not Marked as Not Important for Accessibility",
                        "class": node_class,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "1.1.1 Non-text Content",
                        "Level": "A",
                        "Recommendation": "Defina o atributo 'importantForAccessibility' como 'no' para elementos decorativos serem ignorados pelas tecnologias assistivas."
                    }
                    failures.append(failure)
        self.failures.extend(failures)

    def check_link_purpose(self):
        failures = []
        interactive_elements = self.extractor.extract_interactive_elements()
        for element in interactive_elements:
            text = element['text']
            content_desc = element['content-desc']
            bounds = element['bounds']
            node_class = element['class']

            # Converter bounds para tupla de inteiros
            bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))

            # Verificar se o texto ou content-desc é descritivo
            link_text = text or content_desc
            if link_text.lower() in ["clique aqui", "saiba mais", "mais informações"]:
                failure = {
                    "type": "Link Purpose Failure",
                    "class": node_class,
                    "bounds": list(bounds_tuple),
                    "text": text,
                    "content-desc": content_desc,
                    "Success Criterion": "2.4.4 Link Purpose (In Context)",
                    "Level": "A"
                }
                failures.append(failure)
        self.failures.extend(failures)

    def check_name_role_value(self):
        failures = []
        ui_components = self.extractor.extract_ui_components()
        for component in ui_components:
            node_class = component.get('class', '')
            bounds = component.get('bounds', '')
            text = component.get('text', '')
            content_desc = component.get('content-desc', '')
            resource_id = component.get('resource_id', '')
            clickable = component.get('clickable', False)
            checkable = component.get('checkable', False)
            checked = component.get('checked', None)  # Pode ser None se não estiver definido
            enabled = component.get('enabled', None)
            focusable = component.get('focusable', False)
            selected = component.get('selected', None)

            # Converter bounds para uma tupla de inteiros
            bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))

            # Considera o componente interativo se for clicável, focável ou checkable
            is_interactive = clickable or focusable or checkable

            if is_interactive:
                # Verifica se existe um nome acessível (texto ou content-desc)
                accessible_name = text or content_desc
                if not accessible_name:
                    failures.append({
                        "type": "Missing Accessible Name",
                        "class": node_class,
                        "resource_id": resource_id,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "4.1.2 Name, Role, Value",
                        "Level": "A",
                        "Details": "Elemento interativo sem nome acessível."
                    })

                # Verifica se o componente é checkable: o atributo 'checked' deve ser booleano
                if checkable:
                    if not isinstance(checked, bool):
                        failures.append({
                            "type": "Missing or Invalid State Information",
                            "class": node_class,
                            "resource_id": resource_id,
                            "bounds": list(bounds_tuple),
                            "Success Criterion": "4.1.2 Name, Role, Value",
                            "Level": "A",
                            "Details": "Elemento checkable sem estado 'checked' definido corretamente."
                        })

                # Verifica se o estado 'enabled' está definido e é booleano
                if not isinstance(enabled, bool):
                    failures.append({
                        "type": "Missing Enabled State",
                        "class": node_class,
                        "resource_id": resource_id,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "4.1.2 Name, Role, Value",
                        "Level": "A",
                        "Details": "Elemento interativo sem estado 'enabled' definido corretamente."
                    })

                # Se o componente define 'selected', este também deve ser booleano
                if 'selected' in component and not isinstance(selected, bool):
                    failures.append({
                        "type": "Invalid Selected State",
                        "class": node_class,
                        "resource_id": resource_id,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "4.1.2 Name, Role, Value",
                        "Level": "A",
                        "Details": "Elemento interativo com estado 'selected' inválido."
                    })

                # (Opcional) Você pode definir o role com base na classe, por exemplo:
                # role = "button" se node_class == "android.widget.Button", etc.
                # Se desejar, adicione uma verificação se o role não for detectado.
        self.failures.extend(failures)

    def check_error_identification(self):
        failures = []
        input_fields = self.extractor.extract_input_fields_and_errors()
        for field in input_fields:
            node_class = field['class']
            resource_id = field['resource_id']
            bounds = field['bounds']
            error_message = field.get('error_message')
            error_bounds = field.get('error_bounds')

            # Converter bounds para tupla de inteiros
            bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))

            if error_message is None:
                # Se um erro foi cometido, mas nenhuma mensagem de erro é apresentada
                # Aqui, precisamos determinar se um erro deveria ser detectado
                # Isso requer contexto adicional ou simulação de entradas inválidas
                continue  # Não podemos concluir sem informações adicionais
            else:
                # Verificar se a mensagem de erro é apresentada em texto
                if not error_message.strip():
                    failure = {
                        "type": "Missing Error Description",
                        "class": node_class,
                        "resource_id": resource_id,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "3.3.1 Error Identification",
                        "Level": "A"
                    }
                    failures.append(failure)
                else:
                    # Opcionalmente, registrar que uma mensagem de erro foi detectada
                    error_bounds_tuple = tuple(map(int, re.findall(r'\d+', error_bounds)))
                    failure = {
                        "type": "Error Message Detected",
                        "class": node_class,
                        "resource_id": resource_id,
                        "bounds": list(bounds_tuple),
                        "error_bounds": list(error_bounds_tuple),
                        "error_message": error_message,
                        "Success Criterion": "3.3.1 Error Identification",
                        "Level": "A"
                    }
                    # Neste caso, não é uma falha, mas podemos registrar para análise
        self.failures.extend(failures)

    def check_labels_or_instructions(self):
        failures = []
        input_fields = self.extractor.extract_input_fields_and_labels()
        for field in input_fields:
            node_class = field['class']
            resource_id = field['resource_id']
            bounds = field['bounds']
            label = field.get('label')
            label_bounds = field.get('label_bounds')
            hint = field.get('hint')

            # Converter bounds para tupla de inteiros
            bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))

            # Verificar se há um rótulo ou instrução
            if not label and not hint:
                failure = {
                    "type": "Missing Label or Instruction",
                    "class": node_class,
                    "resource_id": resource_id,
                    "bounds": list(bounds_tuple),
                    "Success Criterion": "3.3.2 Labels or Instructions",
                    "Level": "A"
                }
                failures.append(failure)
            else:
                # Opcionalmente, verificar se o rótulo está vazio ou não descritivo
                if label and not label.strip():
                    failure = {
                        "type": "Empty Label",
                        "class": node_class,
                        "resource_id": resource_id,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "3.3.2 Labels or Instructions",
                        "Level": "A"
                    }
                    failures.append(failure)
                if hint and not hint.strip():
                    failure = {
                        "type": "Empty Hint",
                        "class": node_class,
                        "resource_id": resource_id,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "3.3.2 Labels or Instructions",
                        "Level": "A"
                    }
                    failures.append(failure)
        self.failures.extend(failures)

    @staticmethod
    def get_visual_order(elements):
        # Ordenar elementos com base nas coordenadas superiores esquerdas (y1, x1)
        return sorted(elements, key=lambda e: (e['bounds_tuple'][1], e['bounds_tuple'][0]))

    def check_focus_order(self):
        failures = []
        focusable_elements = self.extractor.extract_focusable_elements()

        # Obter a ordem de foco (assumindo a ordem em que os elementos são definidos no XML)
        focus_order = focusable_elements

        # Obter a ordem visual agrupando elementos por linhas e colunas
        visual_order = self.get_visual_order_by_rows_and_columns(focusable_elements)

        # Comparar as ordens e verificar se as diferenças afetam o significado e a operabilidade
        for idx, focus_elem in enumerate(focus_order):
            if idx < len(visual_order):
                visual_elem = visual_order[idx]
                if focus_elem != visual_elem:
                    # Avaliar se a diferença é significativa
                    if self.is_significant_focus_order_issue(focus_elem, visual_elem):
                        failure = {
                            "type": "Focus Order Failure",
                            "bounds": list(focus_elem['bounds_tuple']),
                            "index": idx,
                            "focus_element": {
                                "class": focus_elem['class'],
                                "resource_id": focus_elem['resource_id'],
                                "bounds": list(focus_elem['bounds_tuple']),
                            },
                            "expected_element": {
                                "class": visual_elem['class'],
                                "resource_id": visual_elem['resource_id'],
                                "bounds": list(visual_elem['bounds_tuple']),
                            },
                            "Success Criterion": "2.4.3 Focus Order",
                            "Level": "A",
                            "Recommendation": "Ajuste a ordem de foco para corresponder à ordem visual lógica dos elementos."
                        }
                        failures.append(failure)
            else:
                # Se o número de elementos focáveis exceder o número de elementos visuais, registrar falha
                failure = {
                    "type": "Focus Order Exceeds Visual Elements",
                    "bounds": list(focus_elem['bounds_tuple']),
                    "index": idx,
                    "focus_element": {
                        "class": focus_elem['class'],
                        "resource_id": focus_elem['resource_id'],
                        "bounds": list(focus_elem['bounds_tuple']),
                    },
                    "Success Criterion": "2.4.3 Focus Order",
                    "Level": "A",
                    "Recommendation": "Verifique se todos os elementos focáveis são visíveis e seguem a ordem lógica."
                }
                failures.append(failure)

        self.failures.extend(failures)

    def get_visual_order_by_rows_and_columns(self, elements):
        # Agrupar elementos em linhas com base em suas posições verticais
        rows = self.group_elements_into_rows(elements)
        visual_order = []
        for row in rows:
            # Ordenar elementos na linha por coordenada x (da esquerda para a direita)
            sorted_row = sorted(row, key=lambda e: e['bounds_tuple'][0])
            visual_order.extend(sorted_row)
        return visual_order

    def group_elements_into_rows(self, elements, row_threshold=30):
        # Ordenar elementos pela coordenada y (de cima para baixo)
        sorted_elements = sorted(elements, key=lambda e: e['bounds_tuple'][1])

        rows = []
        current_row = []
        current_y = None

        for element in sorted_elements:
            y_top = element['bounds_tuple'][1]
            y_bottom = element['bounds_tuple'][3]
            element_center_y = (y_top + y_bottom) / 2

            if current_y is None:
                current_y = element_center_y
                current_row.append(element)
            else:
                if abs(element_center_y - current_y) <= row_threshold:
                    current_row.append(element)
                else:
                    rows.append(current_row)
                    current_row = [element]
                    current_y = element_center_y

        if current_row:
            rows.append(current_row)

        return rows

    def is_significant_focus_order_issue(self, focus_elem, visual_elem):
        # Avaliar se a diferença afeta o significado e a operabilidade
        # Exemplo: se os elementos estão em seções diferentes ou se a diferença é maior que uma posição
        focus_index = self.get_element_index_in_visual_order(focus_elem)
        expected_index = self.get_element_index_in_visual_order(visual_elem)
        if abs(focus_index - expected_index) > 1:
            return True
        return False

    def get_element_index_in_visual_order(self, element):
        visual_order = self.get_visual_order_by_rows_and_columns(self.extractor.extract_focusable_elements())
        for idx, elem in enumerate(visual_order):
            if elem == element:
                return idx
        return -1

    def check_target_size_enhanced(self):
        failures = []
        min_size_dp = 44
        min_size_px = min_size_dp * self.device_density  # Converter dp para pixels

        interactive_elements = self.extractor.extract_interactive_elements_with_dimensions()

        for element in interactive_elements:
            # Considerar apenas elementos clicáveis ou focáveis
            if not (element.get('clickable', False) or element.get('focusable', False)):
                continue  # Pular elementos que não são interativos

            width_px = element['width']
            height_px = element['height']
            bounds_tuple = element['bounds_tuple']
            node_class = element['class']
            resource_id = element['resource_id']
            text = element.get('text', '')
            content_desc = element.get('content-desc', '')

            # Exceção 1: Elementos inline dentro de frases ou parágrafos
            if self.is_inline_element(element):
                continue  # Pular elementos inline

            # Exceção 2: Se existe um alvo equivalente maior na página
            if self.has_equivalent_target(element, interactive_elements):
                continue  # Pular se houver um alvo equivalente maior

            # Exceção 3: O tamanho do alvo é controlado pelo agente do usuário
            if self.is_controlled_by_user_agent(element):
                continue  # Pular elementos controlados pelo agente do usuário

            # Verificar se o tamanho do alvo é menor que o mínimo exigido
            if width_px < min_size_px or height_px < min_size_px:
                failure = {
                    "type": "Target Size Failure",
                    "class": node_class,
                    "resource_id": resource_id,
                    "bounds": list(bounds_tuple),
                    "width": width_px,
                    "height": height_px,
                    "Success Criterion": "2.5.5 Target Size (Enhanced)",
                    "Level": "AAA",
                    "Details": f"O tamanho do alvo é {width_px}px por {height_px}px, que é menor que o mínimo exigido de {min_size_px}px."
                }
                failures.append(failure)
        self.failures.extend(failures)

    def is_inline_element(self, element):
        node_class = element['class']
        text = element.get('text', '')
        content_desc = element.get('content-desc', '')

        # Verificar se o elemento é um TextView com texto, sugerindo que está dentro de um parágrafo ou frase
        if node_class == 'android.widget.TextView' and (text or content_desc):
            # Aqui você pode adicionar lógica adicional para confirmar se está realmente em linha
            return True  # Considera como elemento inline
        return False

    def has_equivalent_target(self, element, interactive_elements):
        for other_element in interactive_elements:
            if other_element == element:
                continue  # Pular o mesmo elemento

            # Verificar se os elementos executam a mesma função (por exemplo, mesmo resource_id ou ação)
            if self.is_equivalent_function(element, other_element):
                # Verificar se o outro elemento atende ao tamanho mínimo
                if other_element['width'] >= 44 * self.device_density and other_element[
                    'height'] >= 44 * self.device_density:
                    return True  # Existe um alvo equivalente maior
        return False

    def is_equivalent_function(self, elem1, elem2):
        # Comparar baseando-se no resource_id ou outra propriedade que indique funcionalidade equivalente
        if elem1['resource_id'] and elem1['resource_id'] == elem2['resource_id']:
            return True
        if elem1.get('action') and elem1['action'] == elem2.get('action'):
            return True
        return False

    def is_controlled_by_user_agent(self, element):
        node_class = element['class']
        # Lista de classes que são controladas pelo agente do usuário
        user_agent_controlled_classes = [
            'android.widget.ScrollView',
            'android.widget.EditText',
            # Adicione outras classes conforme necessário
        ]
        if node_class in user_agent_controlled_classes:
            return True
        return False

    def check_target_size_minimum(self):
        failures = []
        min_size_dp = 24
        min_size_px = min_size_dp * self.device_density  # Converter dp para pixels

        interactive_elements = self.extractor.extract_interactive_elements_with_dimensions()

        for element in interactive_elements:
            if not element.get('clickable', False):
                continue  # Pular elementos não clicáveis

            width_px = element['width']
            height_px = element['height']
            bounds_tuple = element['bounds_tuple']
            node_class = element['class']
            resource_id = element['resource_id']

            if self.is_inline_element(element):
                continue  # Pular elementos em linha

            if self.has_equivalent_target(element, interactive_elements):
                continue  # Pular se houver um alvo equivalente maior

            if self.is_controlled_by_user_agent(element):
                continue  # Pular se for controlado pelo agente do usuário

            if width_px < min_size_px or height_px < min_size_px:
                failure = {
                    "type": "Target Size Failure (Minimum)",
                    "class": node_class,
                    "resource_id": resource_id,
                    "bounds": list(bounds_tuple),
                    "width": width_px,
                    "height": height_px,
                    "Success Criterion": "2.5.8 Target Size (Minimum)",
                    "Level": "AA",
                    "Details": f"O tamanho do alvo é {width_px}px por {height_px}px, que é menor que o mínimo exigido de {min_size_px}px."
                }
                failures.append(failure)
        self.failures.extend(failures)

    @staticmethod
    def get_device_density():
        try:
            # Executa o comando adb para obter a densidade do dispositivo
            result = subprocess.check_output(['adb', 'shell', 'wm', 'density']).decode('utf-8')
            # Extrai o valor da densidade do resultado
            match = re.search(r'Physical density: (\d+)', result)
            if match:
                density = int(match.group(1))
                # Converte a densidade para um fator (dpi dividido por 160)
                density_factor = density / 160.0
                print(f"Device density: {density} dpi, Density factor: {density_factor}")
                return density_factor
            else:
                print("Não foi possível obter a densidade do dispositivo. Usando valor padrão.")
                return 1.0  # Valor padrão
        except Exception as e:
            print(f"Erro ao obter a densidade do dispositivo: {e}")
            return 1.0  # Valor padrão

    def run_all_checks(self):
        self.check_non_text_content()
        self.check_link_purpose()
        self.check_name_role_value()
        self.check_error_identification()
        self.check_labels_or_instructions()
        self.check_focus_order()
        self.check_target_size_enhanced()
        self.check_target_size_minimum()
        self.check_gesture_navigation()

    def get_failures(self):
        return self.failures

# Exemplo de uso
if __name__ == "__main__":
    # Paths para imagens e arquivos XML
    image_paths = {
        "default": r"C:\Users\dasil\OneDrive\Documentos\droidbot-results-test\xmls\Suntimes Widget\screen_default.png",
        "large_text": r"C:\Users\dasil\OneDrive\Documentos\droidbot-results-test\xmls\Suntimes Widget\screen_large_text.png",
        "small_text": r"C:\Users\dasil\OneDrive\Documentos\droidbot-results-test\xmls\Suntimes Widget\screen_small_text.png"
    }

    xml_paths = {
        "default": r"C:\Users\dasil\OneDrive\Documentos\droidbot-results-test\xmls\Suntimes Widget\ui_dump_default.xml",
        "large_text": r"C:\Users\dasil\OneDrive\Documentos\droidbot-results-test\xmls\Suntimes Widget\ui_dump_large_text.xml",
        "small_text": r"C:\Users\dasil\OneDrive\Documentos\droidbot-results-test\xmls\Suntimes Widget\ui_dump_small_text.xml"
    }

    # Obter a densidade do dispositivo
    device_density = AccessibilityChecker.get_device_density()
    print(f"Device density: {device_density}")

    # Instâncias de extração para cada configuração
    extractor_default = XmlNodeBoundsExtractor(xml_paths["default"], cv2.imread(image_paths["default"]))
    extractor_large = XmlNodeBoundsExtractor(xml_paths["large_text"], cv2.imread(image_paths["large_text"]))
    extractor_small = XmlNodeBoundsExtractor(xml_paths["small_text"], cv2.imread(image_paths["small_text"]))

    # Extraindo bounds
    bounds_default = extractor_default.extract_bounds()
    bounds_large = extractor_large.extract_bounds()
    bounds_small = extractor_small.extract_bounds()

    # Obtendo instâncias de OcrInfo
    ocr_info_instances_default = extractor_default.get_ocr_info_instances()
    ocr_info_instances_large = extractor_large.get_ocr_info_instances()
    ocr_info_instances_small = extractor_small.get_ocr_info_instances()

    # Preparando para verificar erros
    all_errors = ContrastChecker.load_existing_errors("errors.json")
    highlighter = ErrorHighlighter(image_paths["default"])
    contrast_checker = ContrastChecker(image_paths["default"])

    # Verificando problemas de contraste
    bounds_texts = contrast_checker.load_bounds_from_xml(xml_paths["default"])
    contrast_failures = contrast_checker.check_text_contrast_with_tolerance(bounds_texts, device_density)
    # contrast_failures = contrast_checker.check_text_contrast_with_tolerance(bounds_texts)

    # Criando uma instância do AccessibilityChecker
    accessibility_checker = AccessibilityChecker(extractor_default, device_density=device_density)
    accessibility_checker.run_all_checks()
    accessibility_failures = accessibility_checker.get_failures()

    # Extração de elementos
    ui_elements = extractor_default.extract_ui_components_as_elements()
    print("[DEBUG] UI Elements extraídos:", ui_elements)
    xml_root = etree.parse(xml_paths["default"]).getroot()

    # Verificação de sobreposição
    overlapping_elements = check_overlapping_elements(ui_elements, xml_root)

    print("Elementos sobrepostos:")
    for elem1, elem2 in overlapping_elements:
        # print(f"{elem1.id} está sobreposto com {elem2.id}")
        # Criar o erro no formato de dicionário
        overlap_error = {
            'type': 'Overlapping Elements',
            'elements': [elem1.id, elem2.id],
            'bounds': [elem1.bounds, elem2.bounds],
            'Success Criterion': '1.4.12 Text Spacing',
            'Level': 'AA'
        }

        # Adicionar o erro à lista de erros se ainda não estiver nela
        if overlap_error not in all_errors:
            all_errors.append(overlap_error)

        # Destacar o erro na imagem
        highlighter.highlight_error({
            'type': 'Overlapping Elements',
            'bounds': elem1.bounds
        })

    # Verificação de textos duplicados
    duplicate_texts = check_duplicate_text(ui_elements, xml_root)
    print("Elementos com texto duplicado:")
    for elem in duplicate_texts:
        print(f"{elem.id} com texto: '{elem.content}'")
        # Criar o erro no formato de dicionário
        duplicate_error = {
            'type': 'Duplicate Text',
            'element': elem.id,
            'content': elem.content,
            'bounds': elem.bounds,
            'Success Criterion': '3.2.4 Consistent Identification',
            'Level': 'AA'
        }

        # Adicionar o erro à lista de erros se ainda não estiver nela
        if duplicate_error not in all_errors:
            all_errors.append(duplicate_error)

        # Destacar o erro na imagem
        highlighter.highlight_error({
            'type': 'Duplicate Text',
            'bounds': elem.bounds
        })

    # Processando falhas de contraste
    if contrast_failures:
        for failure in contrast_failures:
            if failure not in all_errors:
                all_errors.append(failure)
                # Destacar o erro de contraste na imagem
                highlighter.highlight_error(failure)

    # Processando falhas de acessibilidade
    if accessibility_failures:
        for failure in accessibility_failures:
            if failure not in all_errors:
                all_errors.append(failure)
                # Destacar o erro na imagem
                highlighter.highlight_error(failure)
                # if "Target Size Failure" in failure["type"]:
                #     print(f"{failure['type']}: {failure}")

    # Iterando por cada conjunto de instâncias de OCR
    for ocr_info_default, ocr_info_large, ocr_info_small in zip(
        ocr_info_instances_default, ocr_info_instances_large, ocr_info_instances_small
    ):
        # Verificando falhas de aumento
        if not ocr_info_default.compare_processed_data(ocr_info_large):
            increase_error = ocr_info_default.check_no_increase(ocr_info_large)
            if increase_error and increase_error not in all_errors:
                highlighter.highlight_error(increase_error)
                all_errors.append(increase_error)
                print("Increase Error:", increase_error)

        # Verificando falhas de redução
        if not ocr_info_default.compare_processed_data(ocr_info_small):
            reduction_error = ocr_info_default.check_no_reduction(ocr_info_small)
            if reduction_error and reduction_error not in all_errors:
                highlighter.highlight_error(reduction_error)
                all_errors.append(reduction_error)
                print("Reduction Error:", reduction_error)

    # Após processar todos os erros, salvar as imagens para cada tipo de erro
    highlighter.save_images()

    # Salvando todos os erros no arquivo JSON
    ContrastChecker.save_errors_to_json(all_errors, "errors.json")
