import os
import re
import json
import cv2
import xml.etree.ElementTree as ET


ACCEPTED_CLASSES = {
    "android.widget.TextView",
    "android.widget.Button",
    "android.widget.EditText",
    "android.widget.CheckBox",
    "android.widget.RadioButton",
    "android.widget.Switch",
    "android.widget.ToggleButton"
}

def mark_resize_issues_on_image(image_path, errors, output_path):
    """
    Marca na imagem os elementos que não redimensionaram corretamente.
    """
    if not errors:
        return

    image = cv2.imread(image_path)
    if image is None:
        print(f"[WARNING] Imagem não encontrada: {image_path}")
        return

    for err in errors:
        x1, y1, x2, y2 = err["bounds"]
        label = f"{err['element']}: {err['original_height']}px → {err['new_height']}px"
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(image, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (0, 0, 255), 1)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, image)
    print(f"[INFO] Imagem com marcações salva em: {output_path}")

def extract_elements(xml_path):
    elements = {}
    tree = ET.parse(xml_path)
    root = tree.getroot()
    for node in root.iter('node'):
        class_name = node.get('class', '').strip()
        if class_name not in ACCEPTED_CLASSES:
            continue
        resource_id = node.get('resource-id', '').strip()
        content_desc = node.get('content-desc', '').strip()
        text = node.get('text', '').strip()
        bounds = node.get('bounds', '')
        key = resource_id or content_desc or text
        if key and bounds:
            match = re.findall(r'\d+', bounds)
            if len(match) == 4:
                x1, y1, x2, y2 = map(int, match)
                height = y2 - y1
                elements[key] = {
                    'bounds': [x1, y1, x2, y2],
                    'height': height,
                    'class': class_name
                }
    return elements


def check_resize(default, variant, type_check, tolerance=0.07):
    errors = []
    for key in default:
        if key in variant:
            h1 = default[key]['height']
            h2 = variant[key]['height']
            ratio = h2 / h1 if h1 else 0
            if abs(ratio - 1) < tolerance:
                errors.append({
                    "type": f"Resize Text - no {type_check}",
                    "element": key,
                    "bounds": default[key]['bounds'],
                    "original_height": h1,
                    "new_height": h2,
                    "component_class": default[key]['class'],
                    "Success Criterion": "1.4.4 Resize Text",
                    "Level": "AA"
                })
    return errors


def run_resize_analysis(xml_paths, output_path, image_path=None, marked_image_path=None):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    default_elements = extract_elements(xml_paths["default"])
    large_elements = extract_elements(xml_paths["large_text"])
    small_elements = extract_elements(xml_paths["small_text"])

    resize_errors = []
    resize_errors += check_resize(default_elements, large_elements, "increase")
    resize_errors += check_resize(default_elements, small_elements, "reduction")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resize_errors, f, indent=4, ensure_ascii=False)

    print(f"[INFO] Análise de Resize Text finalizada. Resultado salvo em: {output_path}")

    # 🔴 Marca na imagem base os problemas encontrados
    if image_path and marked_image_path:
        mark_resize_issues_on_image(image_path, resize_errors, marked_image_path)



if __name__ == "__main__":
    print("Este script deve ser chamado pelo automate_accessibility.py com os caminhos dos XMLs.")
