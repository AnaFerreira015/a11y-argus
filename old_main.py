import re

import cv2
import os
import shutil
import json
from lxml import etree
import xml.etree.ElementTree as ET

from accessibility_checker.ui_element import UIElement, check_overlapping_elements, check_duplicate_text
from accessibility_checker.extractor import XmlNodeBoundsExtractor
from accessibility_checker.ocr import OcrInfo
from accessibility_checker.contrast import ContrastChecker
from accessibility_checker.accessibility import AccessibilityChecker
from accessibility_checker.error_highlighter import ErrorHighlighter
from accessibility_checker.ui_element import CONTAINER_CLASSES

def union_bounds(bounds1, bounds2):
    x1 = min(bounds1[0], bounds2[0])
    y1 = min(bounds1[1], bounds2[1])
    x2 = max(bounds1[2], bounds2[2])
    y2 = max(bounds1[3], bounds2[3])
    return (x1, y1, x2, y2)

def process_overlapping_elements(ui_elements, xml_root):
    overlapping_elements = check_overlapping_elements(ui_elements, xml_root)
    error_dict = {}
    for elem1, elem2 in overlapping_elements:
        # Ignora se algum dos elementos for um container
        if elem1.id in CONTAINER_CLASSES or elem2.id in CONTAINER_CLASSES:
            continue
        # Une os bounds dos dois elementos (pode ser usado union_bounds ou similar)
        combined_bounds = union_bounds(elem1.bounds, elem2.bounds)
        # Usa a tupla de bounds como chave (você pode converter para string ou manter como tupla)
        if combined_bounds not in error_dict:
            error_dict[combined_bounds] = set()
        error_dict[combined_bounds].update([elem1.id, elem2.id])
    errors = []
    for bounds, elements in error_dict.items():
        error = {
            'type': 'Overlapping Elements',
            'elements': list(elements),
            'bounds': list(bounds),
            'Success Criterion': '1.4.12 Text Spacing',
            'Level': 'AA'
        }
        errors.append(error)
    return errors

def check_resize_text_by_bounds(xml_paths) -> list:
    """
    Verifica o critério 1.4.4 Resize Text com base na comparação de altura de texto entre as versões.
    Considera apenas elementos relevantes com texto visível ao usuário.
    """
    def extract_elements(xml_file):
        tree = ET.parse(xml_file)
        root = tree.getroot()
        elements = {}

        accepted_classes = {
            "android.widget.TextView",
            "android.widget.EditText",
            "android.widget.CheckBox",
            "android.widget.RadioButton",
            "android.widget.Switch",
            "android.widget.ToggleButton"
        }

        for node in root.iter('node'):
            element_class = node.get('class', '').strip()
            if element_class not in accepted_classes:
                continue  # Ignora elementos não textuais relevantes

            rid = node.get('resource-id', '').strip()
            text = node.get('text', '').strip()
            desc = node.get('content-desc', '').strip()
            bounds = node.get('bounds', '')
            key = rid or desc or text
            if key and bounds:
                match = re.findall(r'\d+', bounds)
                if len(match) == 4:
                    x1, y1, x2, y2 = map(int, match)
                    height = y2 - y1
                    elements[key] = {
                        'bounds': (x1, y1, x2, y2),
                        'height': height,
                        'class': element_class
                    }
        return elements

    default = extract_elements(xml_paths["default"])
    small = extract_elements(xml_paths["small_text"])
    large = extract_elements(xml_paths["large_text"])
    tolerance = 0.07
    resize_errors = []

    for key in default:
        if key in large:
            h_def = default[key]['height']
            h_large = large[key]['height']
            ratio = h_large / h_def if h_def else 0
            if abs(ratio - 1) < tolerance:
                resize_errors.append({
                    'type': 'Resize Text - no increase',
                    'element': key,
                    'bounds': default[key]['bounds'],
                    'original_height': h_def,
                    'new_height': h_large,
                    'component_class': default[key]['class'],
                    'Success Criterion': '1.4.4 Resize Text',
                    'Level': 'AA'
                })

        if key in small:
            h_def = default[key]['height']
            h_small = small[key]['height']
            ratio = h_small / h_def if h_def else 0
            if abs(ratio - 1) < tolerance:
                resize_errors.append({
                    'type': 'Resize Text - no reduction',
                    'element': key,
                    'bounds': default[key]['bounds'],
                    'original_height': h_def,
                    'new_height': h_small,
                    'component_class': default[key]['class'],
                    'Success Criterion': '1.4.4 Resize Text',
                    'Level': 'AA'
                })

    return resize_errors

def main(image_paths, xml_paths, result_dir, return_errors=False):
    print("[DEBUG] Entrou na função main do Argus-a11y")
    os.makedirs(result_dir, exist_ok=True)

    device_density = AccessibilityChecker.get_device_density()
    print(f"Device density: {device_density}")

    # Base (default)
    base_key = "default"
    large_key = "large_text"
    small_key = "small_text"

    # Instâncias de extração para cada configuração
    extractor_default = XmlNodeBoundsExtractor(xml_paths[base_key], cv2.imread(image_paths[base_key]))
    extractor_large = XmlNodeBoundsExtractor(xml_paths[large_key], cv2.imread(image_paths[large_key]))
    extractor_small = XmlNodeBoundsExtractor(xml_paths[small_key], cv2.imread(image_paths[small_key]))

    # Extraindo bounds
    bounds_default = extractor_default.extract_bounds()
    bounds_large = extractor_large.extract_bounds()
    bounds_small = extractor_small.extract_bounds()

    # Obtendo instâncias de OCR
    ocr_info_instances_default = extractor_default.get_ocr_info_instances()
    ocr_info_instances_large = extractor_large.get_ocr_info_instances()
    ocr_info_instances_small = extractor_small.get_ocr_info_instances()
    ui_elements = extractor_default.extract_ui_components_as_elements()

    # Criar dicionários de bounds do XML para verificar tamanho real dos componentes
    xml_bounds_default = {
        comp['resource_id']: tuple(map(int, re.findall(r'\d+', comp['bounds'])))
        for comp in extractor_default.extract_ui_components() if comp['resource_id']
    }
    xml_bounds_large = {
        comp['resource_id']: tuple(map(int, re.findall(r'\d+', comp['bounds'])))
        for comp in extractor_large.extract_ui_components() if comp['resource_id']
    }

    # Contraste
    contrast_checker = ContrastChecker(image_paths[base_key])
    bounds_texts = contrast_checker.load_bounds_from_xml(xml_paths[base_key])
    contrast_failures = contrast_checker.check_text_contrast_with_tolerance(bounds_texts, device_density)

    # Acessibilidade
    accessibility_checker = AccessibilityChecker(extractor_default, device_density=device_density)
    accessibility_checker.run_all_checks()
    accessibility_failures = accessibility_checker.get_failures()

    # Sobreposição
    xml_root = etree.parse(xml_paths[base_key]).getroot()
    overlap_errors = process_overlapping_elements(ui_elements, xml_root)

    # Texto duplicado
    duplicate_texts = check_duplicate_text(ui_elements, xml_root)
    duplicate_errors = [{
        'type': 'Duplicate Text',
        'element': elem.id,
        'content': elem.content,
        'bounds': elem.bounds,
        'Success Criterion': '3.2.4 Consistent Identification',
        'Level': 'AA'
    } for elem in duplicate_texts]

    # Destacar erros na imagem base
    highlighter = ErrorHighlighter(image_paths[base_key])

    # **🔹 Verificação do critério 1.4.4 Resize Text com base nos bounds**
    resize_errors = check_resize_text_by_bounds(xml_paths)
    for err in resize_errors:
        highlighter.highlight_error(err)

    # **Unir todos erros**
    all_errors = (
        overlap_errors +
        contrast_failures +
        accessibility_failures +
        duplicate_errors +
        resize_errors  # ✅ Unresponsive_errors REMOVIDO, pois resize_errors já cobre isso
    )

    for error in all_errors:
        highlighter.highlight_error(error)
    highlighter.save_images(os.path.join(result_dir, "output_images"))

    # Iterando por cada conjunto de instâncias de OCR
    for ocr_info_default, ocr_info_large, ocr_info_small in zip(
            ocr_info_instances_default, ocr_info_instances_large, ocr_info_instances_small
    ):
        # Verificando falhas de aumento via OCR
        if not ocr_info_default.compare_processed_data(ocr_info_large):
            increase_error = ocr_info_default.check_no_increase(ocr_info_large)
            if increase_error and increase_error not in resize_errors:
                highlighter.highlight_error(increase_error)
                resize_errors.append(increase_error)
                print("Increase Error:", increase_error)

        # Verificando falhas de redução via OCR
        if not ocr_info_default.compare_processed_data(ocr_info_small):
            reduction_error = ocr_info_default.check_no_reduction(ocr_info_small)
            if reduction_error and reduction_error not in resize_errors:
                highlighter.highlight_error(reduction_error)
                resize_errors.append(reduction_error)
                print("Reduction Error:", reduction_error)

    # Salvar erros em JSON final
    error_file = os.path.join(result_dir, "errors.json")
    with open(error_file, "w", encoding="utf-8") as f:
        json.dump(all_errors, f, indent=4, ensure_ascii=False)

    print(f"[INFO] Resultados salvos em {result_dir}")
    if return_errors:
        return all_errors

if __name__ == "__main__":
    print("Este script deve ser chamado via pipeline, passando os caminhos dinâmicos.")