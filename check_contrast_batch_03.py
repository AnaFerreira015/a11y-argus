import os
import re
import json
import glob
import cv2
import numpy as np
import xml.etree.ElementTree as ET


def extract_text_bounds(xml_file, image_width=720, image_height=1600):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    elements = []

    for node in root.iter('node'):
        text = (node.get('text') or node.get('content-desc') or '').strip()
        bounds = node.get('bounds', '')
        if not text or not bounds:
            continue

        match = re.match(r'\[(\d+),(\d+)]\[(\d+),(\d+)]', bounds)
        if not match:
            continue

        x1, y1, x2, y2 = map(int, match.groups())
        width, height = x2 - x1, y2 - y1
        if width <= 1 or height <= 1:
            continue
        if x2 <= 0 or y2 <= 0 or x1 >= image_width or y1 >= image_height:
            continue

        elements.append((text, (x1, y1, x2, y2), height))

    return elements


def is_region_visible(image, bounds, threshold=15):
    x1, y1, x2, y2 = bounds
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(image.shape[1], x2)
    y2 = min(image.shape[0], y2)
    region = image[y1:y2, x1:x2]

    if region.size == 0:
        return False

    std_dev = np.std(region, axis=(0, 1))
    return np.mean(std_dev) > threshold


def relative_luminance(color):
    def transform(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = color
    return 0.2126 * transform(r) + 0.7152 * transform(g) + 0.0722 * transform(b)


def contrast_ratio(color1, color2):
    lum1 = relative_luminance(color1)
    lum2 = relative_luminance(color2)
    return (max(lum1, lum2) + 0.05) / (min(lum1, lum2) + 0.05)


def get_average_color(image, bounds):
    x1, y1, x2, y2 = bounds
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(image.shape[1], x2)
    y2 = min(image.shape[0], y2)
    region = image[y1:y2, x1:x2]
    if region.size == 0:
        return (255, 255, 255)
    avg_color = region.mean(axis=(0, 1))
    return tuple(map(int, avg_color))

def parse_utg_state_mapping(utg_path, xml_dir, serial):
    with open(utg_path, 'r', encoding='utf-8') as f:
        raw = f.read()
        match = re.search(r'var\s+utg\s*=\s*(\{.*\})', raw, re.DOTALL)
        if not match:
            raise ValueError("Não foi possível extrair o JSON de utg.js")
        json_str = match.group(1)
        utg_data = json.loads(json_str)

    # Arquivos XML existentes
    xml_files = sorted(glob.glob(os.path.join(xml_dir, f"ui_dump_{serial}_*.xml")))

    # Mapeia index do XML → state_id da posição correspondente no UTG
    index_to_state = {}
    for i, xml_file in enumerate(xml_files):
        match = re.search(r'_(\d{3})\.xml$', xml_file)
        if match and i < len(utg_data["nodes"]):
            index = match.group(1)
            state_id = utg_data["nodes"][i]["state_str"]
            index_to_state[index] = state_id

    return index_to_state


def analyze_contrast_for_app(app_name, serial):
    base_dir = os.path.join("output", app_name)
    xml_dir = os.path.join(base_dir, "default", "xmls")
    img_dir = os.path.join(base_dir, "default", "prints")
    results_base = os.path.join(base_dir, "results")
    os.makedirs(results_base, exist_ok=True)

    utg_path = os.path.join(base_dir, "default", "utg.js")
    index_to_state = parse_utg_state_mapping(utg_path, xml_dir, serial)

    for index_str, state_id in index_to_state.items():
        xml_path = os.path.join(xml_dir, f"ui_dump_{serial}_{index_str}.xml")
        img_path = os.path.join(img_dir, f"screen_{serial}_{index_str}.png")

        if not os.path.isfile(xml_path) or not os.path.isfile(img_path):
            print(f"[⏭️] Arquivos ausentes para índice {index_str}, pulando.")
            continue

        print(f"\n🔍 Processando índice {index_str} (state_id: {state_id})")

        image = cv2.imread(img_path)
        elements = extract_text_bounds(xml_path, image.shape[1], image.shape[0])
        tela_erros = []

        for text, bounds, font_size_px in elements:
            if not is_region_visible(image, bounds):
                continue

            font_size_pt = (font_size_px * 72) / 320
            threshold = 3.0 if font_size_pt >= 18 else 4.5

            text_color = get_average_color(image, bounds)
            margin = 4
            bg_bounds = (
                bounds[0] - margin,
                bounds[1] - margin,
                bounds[2] + margin,
                bounds[3] + margin
            )
            background_color = get_average_color(image, bg_bounds)

            contrast = contrast_ratio(text_color, background_color)

            if contrast < threshold:
                tela_erros.append({
                    "screen_id": state_id,
                    "error_type": "Contrast Failure",
                    "text": text,
                    "bounds": bounds,
                    "contrast": round(contrast, 2),
                    "font_size_pt": round(font_size_pt, 1),
                    "Success Criterion": "1.4.3 Contrast (Minimum)",
                    "Level": "AA",
                    "Level Status": "Failure"
                })

        output_dir = os.path.join(results_base, state_id)
        os.makedirs(output_dir, exist_ok=True)

        if tela_erros:
            output_img = os.path.join(output_dir, "low_contrast_text.png")
            output_json = os.path.join(output_dir, "contrast_failures.json")

            for erro in tela_erros:
                x1, y1, x2, y2 = erro["bounds"]
                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)

            cv2.imwrite(output_img, image)
            with open(output_json, "w", encoding="utf-8") as f:
                json.dump(tela_erros, f, indent=4, ensure_ascii=False)

            print(f"[📸] Salvo: {output_img}")
            print(f"[📝] Json: {output_json}")
        else:
            print("[✅] Nenhum problema de contraste detectado.")