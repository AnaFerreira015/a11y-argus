# main.py
import cv2
import json
import re
from lxml import etree

from accessibility_checker.ui_element import UIElement, check_overlapping_elements, check_duplicate_text
from accessibility_checker.extractor import XmlNodeBoundsExtractor
from accessibility_checker.ocr import OcrInfo
from accessibility_checker.contrast import ContrastChecker
from accessibility_checker.accessibility import AccessibilityChecker
from accessibility_checker.error_highlighter import ErrorHighlighter

def union_bounds(bounds1, bounds2):
    x1 = min(bounds1[0], bounds2[0])
    y1 = min(bounds1[1], bounds2[1])
    x2 = max(bounds1[2], bounds2[2])
    y2 = max(bounds1[3], bounds2[3])
    return (x1, y1, x2, y2)

def main():
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
    # Obter densidade do dispositivo
    device_density = AccessibilityChecker.get_device_density()
    print(f"Device density: {device_density}")

    extractor_default = XmlNodeBoundsExtractor(xml_paths["default"], cv2.imread(image_paths["default"]))
    ocr_info_instances_default = extractor_default.get_ocr_info_instances()

    contrast_checker = ContrastChecker(image_paths["default"])
    bounds_texts = contrast_checker.load_bounds_from_xml(xml_paths["default"])
    contrast_failures = contrast_checker.check_text_contrast_with_tolerance(bounds_texts, device_density)

    accessibility_checker = AccessibilityChecker(extractor_default, device_density=device_density)
    accessibility_checker.run_all_checks()
    accessibility_failures = accessibility_checker.get_failures()

    ui_elements = extractor_default.extract_ui_components_as_elements()
    print("[DEBUG] UI Elements extraídos:", ui_elements)
    xml_root = etree.parse(xml_paths["default"]).getroot()
    overlapping_elements = check_overlapping_elements(ui_elements, xml_root)

    all_errors = []

    for elem1, elem2 in overlapping_elements:
        combined_bounds = union_bounds(elem1.bounds, elem2.bounds)
        overlap_error = {
            'type': 'Overlapping Elements',
            'elements': [elem1.id, elem2.id],
            'bounds': combined_bounds,
            'Success Criterion': '1.4.12 Text Spacing',
            'Level': 'AA'
        }
        if overlap_error not in all_errors:
            all_errors.append(overlap_error)

    duplicate_texts = check_duplicate_text(ui_elements, xml_root)
    for elem in duplicate_texts:
        duplicate_error = {
            'type': 'Duplicate Text',
            'element': elem.id,
            'content': elem.content,
            'bounds': elem.bounds,
            'Success Criterion': '3.2.4 Consistent Identification',
            'Level': 'AA'
        }
        if duplicate_error not in all_errors:
            all_errors.append(duplicate_error)

    all_errors.extend(contrast_failures)
    all_errors.extend(accessibility_failures)

    highlighter = ErrorHighlighter(image_paths["default"])
    for error in all_errors:
        highlighter.highlight_error(error)
    highlighter.save_images("output_images")
    ContrastChecker.save_errors_to_json(all_errors, "errors.json")

if __name__ == "__main__":
    main()
