import re

import cv2
import os
import shutil
import json
from lxml import etree
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional, cast

from accessibility_checker.ui_element import UIElement, check_overlapping_elements, check_duplicate_text, is_inside_navigation_view
from accessibility_checker.extractor import XmlNodeBoundsExtractor
from accessibility_checker.ocr import OcrInfo
from accessibility_checker.contrast import ContrastChecker
from accessibility_checker.accessibility import AccessibilityChecker, is_relevant_error_scope
from accessibility_checker.error_highlighter import ErrorHighlighter, union_bounds
from accessibility_checker.ui_element import CONTAINER_CLASSES

def generate_ignore_ids_for_overlap(xml_path):
    """
    Gera uma lista de resource-id e classes que devem ser ignoradas para avaliação de sobreposição
    segundo o critério 1.4.12 Text Spacing (apenas elementos textuais são relevantes).
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    ignore_ids = set()
    ignore_classes = set()

    IGNORED_IDS_MANUAL = {
        "RNE__ICON__Component",
        "RNE__ICON__CONTAINER_ACTION",
        "listItemTitle"
    }

    # Classes que indicam elementos com conteúdo textual
    TEXTUAL_CLASSES = {
        "android.widget.TextView",
        "android.widget.Button",
        "android.widget.EditText",
        "android.widget.CheckBox",
        "android.widget.RadioButton",
        "android.widget.Switch",
        "android.widget.ToggleButton"
    }

    for node in root.iter("node"):
        resource_id = node.get("resource-id", "").strip()
        class_name = node.get("class", "").strip()
        bounds = node.get("bounds", "")
        text = node.get("text", "").strip()
        content_desc = node.get("content-desc", "").strip()

        if resource_id in IGNORED_IDS_MANUAL:
            continue

        # Parse bounds
        match = re.findall(r'\d+', bounds)
        if len(match) != 4:
            continue
        x1, y1, x2, y2 = map(int, match)
        if (x1, y1, x2, y2) == (0, 0, 0, 0):
            continue  # invisível

        # Se não for classe textual OU não tiver texto ou content-desc, ignorar
        if class_name not in TEXTUAL_CLASSES or (not text and not content_desc):
            if resource_id:
                ignore_ids.add(resource_id)
            if class_name:
                ignore_classes.add(class_name)

    return sorted(ignore_ids), sorted(ignore_classes)

def save_overlapping_elements(errors: List[Tuple[List[UIElement], Tuple[int, int, int, int]]], screen_id: str,
                              output_path: str):
    """
    Salva os erros de sobreposição de elementos no formato agrupado por região de sobreposição.

    :param errors: Lista de tuplas contendo elementos sobrepostos e a bounding box comum
    :param screen_id: ID da tela analisada
    :param output_path: Caminho para salvar o JSON de erros
    """
    error_list = []

    for overlapping_group, bounds in errors:
        elements_data = []
        for element in overlapping_group:
            element_id = element.id or (element.node.get("class", "") if element.node is not None else "")
            element_class = element.node.get("class", "") if element.node is not None else ""
            elements_data.append({
                "element": element_id,
                "class": element_class
            })

        error_list.append({
            "type": "Overlapping Elements",
            "elements": elements_data,
            "bounds": list(bounds),
            "Success Criterion": "1.4.12 Text Spacing",
            "Level": "AA"
        })

    # Gera o dicionário final
    output_data = {
        "screen_id": screen_id,
        "errors": error_list
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)

def is_visual_element_for_overlap(element: UIElement, ignore_ids: List[str], ignore_classes: List[str]) -> bool:
    """Retorna True se o elemento for visualmente relevante para checagem de sobreposição."""

    if element.id in ignore_ids or (
            element.node is not None and element.node.get("class", "") in ignore_classes
    ):
        return False

    if not element or not element.bounds:
        return False

    # Ignora elementos com texto/content-desc vazio
    if not element.content or not element.content.strip():
        return False

    # Ignora elementos invisíveis
    if element.bounds == (0, 0, 0, 0):
        return False

    # Ignora containers genéricos
    if element.node is not None:
        element_class = element.node.get("class", "")
        if element_class in CONTAINER_CLASSES:
            return False

    return True

def process_overlapping_elements(ui_elements, xml_root, ignore_ids, ignore_classes, navigation_view_bounds: Optional[Tuple[int, int, int, int]] = None):
    overlapping_elements = check_overlapping_elements(ui_elements, xml_root)
    error_dict = {}

    for elem1, elem2 in overlapping_elements:
        if not is_visual_element_for_overlap(elem1, ignore_ids, ignore_classes) or not is_visual_element_for_overlap(elem2, ignore_ids, ignore_classes):
            continue

        combined_bounds = union_bounds(elem1.bounds, elem2.bounds)

        if navigation_view_bounds is not None:
            if not is_inside_navigation_view(elem1.bounds, navigation_view_bounds):
                continue
            if not is_inside_navigation_view(elem2.bounds, navigation_view_bounds):
                continue

        if combined_bounds not in error_dict:
            error_dict[combined_bounds] = set()

        error_dict[combined_bounds].update([elem1, elem2])

    # Retorna uma lista no formato [(elementos, bounds)]
    errors = [(list(elements), bounds) for bounds, elements in error_dict.items()]
    return errors

# def check_resize_text_by_bounds(xml_paths, navigation_view_bounds: Optional[Tuple[int, int, int, int]] = None) -> list:
#     def extract_elements(xml_file):
#         tree = ET.parse(xml_file)
#         root = tree.getroot()
#         elements = {}
#
#         accepted_classes = {
#             "android.widget.TextView",
#             "android.widget.EditText",
#             "android.widget.CheckBox",
#             "android.widget.RadioButton",
#             "android.widget.Switch",
#             "android.widget.ToggleButton"
#         }
#
#         for node in root.iter('node'):
#             element_class = node.get('class', '').strip()
#             if element_class not in accepted_classes:
#                 continue
#
#             rid = node.get('resource-id', '').strip()
#             text = node.get('text', '').strip()
#             desc = node.get('content-desc', '').strip()
#             bounds = node.get('bounds', '')
#             key = rid or desc or text
#             if key and bounds:
#                 if (text and re.match(r'^[^\w\s]+$', text)) and not desc:
#                     continue  # Ignora glifos (ícones visuais) sem content-desc
#
#                 match = re.findall(r'\d+', bounds)
#                 if len(match) == 4:
#                     x1, y1, x2, y2 = map(int, match)
#
#                     # Filtro por navigation_view_bounds, se fornecido
#                     if navigation_view_bounds and is_inside_navigation_view((x1, y1, x2, y2), navigation_view_bounds):
#                         continue
#
#                     height = y2 - y1
#                     elements[key] = {
#                         'bounds': (x1, y1, x2, y2),
#                         'height': height,
#                         'class': element_class
#                     }
#         return elements
#
#     default = extract_elements(xml_paths["default"])
#     small = extract_elements(xml_paths["small_text"])
#     large = extract_elements(xml_paths["large_text"])
#
#     tolerance = 0.07
#     resize_errors = []
#
#     for key in default:
#         if key in large:
#             h_def = default[key]['height']
#             h_large = large[key]['height']
#             ratio = h_large / h_def if h_def else 0
#             if abs(ratio - 1) < tolerance:
#                 resize_errors.append({
#                     'type': 'Resize Text - no increase',
#                     'element': key,
#                     'bounds': default[key]['bounds'],
#                     'original_height': h_def,
#                     'new_height': h_large,
#                     'component_class': default[key]['class'],
#                     'Success Criterion': '1.4.4 Resize Text',
#                     'Level': 'AA'
#                 })
#
#         if key in small:
#             h_def = default[key]['height']
#             h_small = small[key]['height']
#             ratio = h_small / h_def if h_def else 0
#             if abs(ratio - 1) < tolerance:
#                 resize_errors.append({
#                     'type': 'Resize Text - no reduction',
#                     'element': key,
#                     'bounds': default[key]['bounds'],
#                     'original_height': h_def,
#                     'new_height': h_small,
#                     'component_class': default[key]['class'],
#                     'Success Criterion': '1.4.4 Resize Text',
#                     'Level': 'AA'
#                 })
#
#     return resize_errors

def check_resize_text_by_bounds(
    xml_paths: dict,
    navigation_view_bounds: Optional[Tuple[int, int, int, int]] = None
) -> list:
    """
    Verifica se os elementos textuais aumentam e/ou reduzem corretamente ao aplicar o redimensionamento de texto.
    - Aumento é obrigatório segundo WCAG (critério 1.4.4).
    - Redução não é obrigatória, mas é uma verificação opcional útil.

    :param xml_paths: Dicionário com caminhos dos XMLs ['default', 'small_text', 'large_text']
    :param navigation_view_bounds: Bounds do menu (se aplicável) para filtrar elementos dentro dele.
    :return: Lista de erros detectados.
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
                continue

            rid = node.get('resource-id', '').strip()
            text = node.get('text', '').strip()
            desc = node.get('content-desc', '').strip()
            bounds = node.get('bounds', '')
            key = rid or desc or text
            if key and bounds:
                if (text and re.match(r'^[^\w\s]+$', text)) and not desc:
                    continue  # Ignora glifos (ícones visuais) sem content-desc

                match = re.findall(r'\d+', bounds)
                if len(match) == 4:
                    x1, y1, x2, y2 = map(int, match)

                    if navigation_view_bounds and not is_inside_navigation_view((x1, y1, x2, y2), navigation_view_bounds):
                        continue

                    width = x2 - x1
                    height = y2 - y1

                    elements[key] = {
                        'bounds': (x1, y1, x2, y2),
                        'width': width,
                        'height': height,
                        'class': element_class
                    }
        return elements

    # Extrai os elementos dos três XMLs
    default = extract_elements(xml_paths["default"])
    small = extract_elements(xml_paths["small_text"])
    large = extract_elements(xml_paths["large_text"])

    # Parâmetros de validação
    expected_increase_ratio = 2.0   # Espera-se que o texto dobre (200%) no modo grande
    expected_reduction_ratio = 0.5  # Espera-se que o texto reduza pela metade (50%) no modo pequeno
    tolerance = 0.2                 # ±20% de margem

    resize_errors = []

    for key in default:
        elem_default = default[key]
        h_def = elem_default['height']

        # ----- Verificação de AUMENTO (default -> large_text) -----
        if key in large:
            h_large = large[key]['height']
            ratio = h_large / h_def if h_def else 0

            if not (expected_increase_ratio - tolerance <= ratio <= expected_increase_ratio + tolerance):
                resize_errors.append({
                    'type': 'Resize Text - insufficient increase',
                    'element': key,
                    'bounds': elem_default['bounds'],
                    'original_height': h_def,
                    'new_height': h_large,
                    'component_class': elem_default['class'],
                    'description': 'O texto não aumentou adequadamente na configuração de texto grande.',
                    'Success Criterion': '1.4.4 Resize Text',
                    'Level': 'AA'
                })

        # ----- Verificação de REDUÇÃO (default -> small_text) -----
        if key in small:
            h_small = small[key]['height']
            ratio = h_small / h_def if h_def else 0

            if not (expected_reduction_ratio - tolerance <= ratio <= expected_reduction_ratio + tolerance):
                resize_errors.append({
                    'type': 'Resize Text - insufficient reduction',
                    'element': key,
                    'bounds': elem_default['bounds'],
                    'original_height': h_def,
                    'new_height': h_small,
                    'component_class': elem_default['class'],
                    'description': 'O texto não reduziu adequadamente na configuração de texto pequeno. (Essa verificação é opcional, não faz parte do critério WCAG)',
                    'Success Criterion': 'Optional Check - Text Reduction',
                    'Level': 'Advisory'
                })

    return resize_errors


def main(image_paths, xml_paths, result_dir, screen_id=None, return_errors=False):
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

    # Sobreposição
    xml_root = etree.parse(xml_paths[base_key]).getroot()

    # def find_navigation_view_bounds(xml_root) -> Optional[Tuple[int, int, int, int]]:
    #     """
    #     Tenta encontrar o menu lateral (Navigation View) baseado em heurísticas de resource-id e class.
    #     """
    #     # Heurística 1: procura por resource-id que contenha 'navigation' ou 'nav'
    #     candidates = xml_root.xpath(".//node[contains(@resource-id, 'navigation') or contains(@resource-id, 'nav')]")
    #
    #     # Heurística 2: procura por classes conhecidas
    #     if not candidates:
    #         known_menu_classes = [
    #             "com.google.android.material.navigation.NavigationView",
    #             "androidx.drawerlayout.widget.DrawerLayout",
    #             "androidx.recyclerview.widget.RecyclerView",
    #             "android.widget.ListView"
    #         ]
    #         candidates = xml_root.xpath(
    #             "|".join([f".//node[@class='{cls}']" for cls in known_menu_classes])
    #         )
    #
    #     for node in candidates:
    #         bounds_str = node.attrib.get("bounds", "")
    #         match = re.findall(r'\d+', bounds_str)
    #         if len(match) == 4:
    #             x1, y1, x2, y2 = map(int, match)
    #             return (x1, y1, x2, y2)
    #
    #     return None
    #
    # navigation_view_bounds = find_navigation_view_bounds(xml_root)
    def extract_menu_bounds_from_items(xml_path: str) -> Optional[Tuple[int, int, int, int]]:
        """
        Extrai os bounds que englobam todos os itens de menu no XML, assumindo que estão em
        android.widget.CheckedTextView dentro de androidx.appcompat.widget.LinearLayoutCompat.

        :param xml_path: Caminho para o XML
        :return: Um tuple (x1, y1, x2, y2) englobando os itens de menu ou None
        """
        bounds_list = []

        def find_items(node):
            if node.attrib.get("class") == "androidx.appcompat.widget.LinearLayoutCompat":
                for child in node.findall("node"):
                    if child.attrib.get("class") == "android.widget.CheckedTextView":
                        bounds_str = child.attrib.get("bounds", "")
                        if bounds_str:
                            match = re.findall(r'\d+', bounds_str)
                            if len(match) == 4:
                                bounds = tuple(map(int, match))
                                bounds_list.append(bounds)
            for child in node.findall("node"):
                find_items(child)

        tree = ET.parse(xml_path)
        root = tree.getroot()
        find_items(root)

        if bounds_list:
            x1 = min(b[0] for b in bounds_list)
            y1 = min(b[1] for b in bounds_list)
            x2 = max(b[2] for b in bounds_list)
            y2 = max(b[3] for b in bounds_list)
            return (x1, y1, x2, y2)

        return None


    navigation_view_bounds = extract_menu_bounds_from_items(xml_paths[base_key])
    print(f"[DEBUG] Bounds do menu detectadas: {navigation_view_bounds}")

    # Contraste
    contrast_checker = ContrastChecker(image_paths[base_key])
    bounds_texts = contrast_checker.load_bounds_from_xml(xml_paths[base_key])
    contrast_failures = contrast_checker.check_text_contrast_with_tolerance(bounds_texts, device_density, navigation_view_bounds)

    # # Filtra falhas de contraste dentro da navigation_view, se aplicável
    # contrast_failures_filtered = []
    # for err in contrast_failures:
    #     raw_bounds = err.get("bounds", [])
    #     if isinstance(raw_bounds, (list, tuple)) and len(raw_bounds) == 4 and all(
    #             isinstance(x, int) for x in raw_bounds):
    #         bounds_tuple = cast(Tuple[int, int, int, int], tuple(raw_bounds))
    #         if navigation_view_bounds is None or is_inside_navigation_view(bounds_tuple, navigation_view_bounds):
    #             contrast_failures_filtered.append(err)
    # contrast_failures = contrast_failures_filtered

    contrast_failures = [
        err for err in contrast_failures
        if isinstance(err.get("bounds", []), (list, tuple)) and
           len(err["bounds"]) == 4 and all(isinstance(x, int) for x in err["bounds"])
    ]

    contrast_failures = [
        f for f in contrast_failures
        if is_relevant_error_scope(
            cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))),
            navigation_view_bounds
        )
    ]

    # Acessibilidade
    accessibility_checker = AccessibilityChecker(
        extractor_default,
        device_density=device_density,
        navigation_view_bounds=navigation_view_bounds
    )

    accessibility_checker.run_all_checks()
    accessibility_failures = accessibility_checker.get_failures()

    # Gera listas de elementos e classes que devem ser ignorados na checagem de sobreposição
    ignore_ids, ignore_classes = generate_ignore_ids_for_overlap(xml_paths[base_key])

    # Processa sobreposições considerando os elementos ignorados
    overlap_error_groups = process_overlapping_elements(
        ui_elements, xml_root, ignore_ids, ignore_classes, navigation_view_bounds
    )

    overlap_errors_flat = []
    for group, bounds in overlap_error_groups:
        for element in group:
            overlap_errors_flat.append({
                'type': 'Overlapping Elements',
                'element': element.id,
                'class': (
                    element.node.get('class', '')
                    if element.node is not None and element.node.get('class')
                    else element.id if element.id and element.id.startswith("android.")
                    else ''
                ),
                'bounds': list(bounds),
                'Success Criterion': '1.4.12 Text Spacing',
                'Level': 'AA'
            })

    # Se tiver screen_id, salva também o JSON separado para debug
    if screen_id:
        save_overlapping_elements(overlap_error_groups, screen_id, os.path.join(result_dir, "overlapping_errors.json"))

    # Texto duplicado
    # duplicate_texts = check_duplicate_text(ui_elements, xml_root)
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

    # Verificação do critério 1.4.4 Resize Text com base nos bounds**
    resize_errors = check_resize_text_by_bounds(xml_paths, navigation_view_bounds=navigation_view_bounds)

    # for err in resize_errors:
    #     highlighter.highlight_error(err)

    # **Unir todos erros**
    all_errors = (
            overlap_errors_flat +
            contrast_failures +
            accessibility_failures +
            duplicate_errors +
            resize_errors
    )

    if not all_errors:
        print(f"[INFO] Nenhum erro encontrado para screen_id {screen_id}, ignorando geração de resultados.")
        shutil.rmtree(result_dir, ignore_errors=True)
        return [] if return_errors else None

    # Aplica filtro e destaca apenas os erros dentro da navigation_view, se ela existir
    filtered_errors = []
    for error in all_errors:
        raw_bounds = error.get("bounds")
        if isinstance(raw_bounds, (list, tuple)) and len(raw_bounds) == 4 and all(
                isinstance(x, int) for x in raw_bounds):
            bounds_tuple = cast(Tuple[int, int, int, int], tuple(raw_bounds))
            if navigation_view_bounds:
                if not is_inside_navigation_view(bounds_tuple, navigation_view_bounds):
                    print(f"[DEBUG] Erro fora do menu: {error['type']} em {bounds_tuple}")
                    continue
            print(f"[DEBUG] Erro dentro do menu: {error['type']} em {bounds_tuple}")
            highlighter.highlight_error(error)
            filtered_errors.append(error)

    # Se não houver erros após filtro, não gera a pasta de resultados
    if not filtered_errors:
        print(f"[INFO] Nenhum erro relevante encontrado para {screen_id}. Ignorando result_dir.")
        shutil.rmtree(result_dir, ignore_errors=True)
        return [] if return_errors else None

    # Salva JSON e imagens se houver erros válidos
    error_file = os.path.join(result_dir, "errors.json")
    with open(error_file, "w", encoding="utf-8") as f:
        json.dump(filtered_errors, f, indent=4, ensure_ascii=False)

    highlighter.save_images(os.path.join(result_dir, "output_images"))

    print(f"[INFO] Resultados salvos em {result_dir}")
    if return_errors:
        return filtered_errors

if __name__ == "__main__":
    print("Este script deve ser chamado via pipeline, passando os caminhos dinâmicos.")