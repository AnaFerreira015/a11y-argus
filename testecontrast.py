import os
import re
import glob
import cv2
import numpy as np
import xml.etree.ElementTree as ET


def extract_text_bounds(xml_file):
    """
    Extrai todos os elementos com texto ou content-desc e seus bounds do XML.
    Retorna uma lista de tuplas: (texto, bounds, altura).
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()
    elements = []

    for node in root.iter('node'):
        text = (node.get('text') or node.get('content-desc') or '').strip()
        bounds = node.get('bounds', '')
        if not text or not bounds:
            continue

        match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
        if not match:
            continue

        x1, y1, x2, y2 = map(int, match.groups())
        width, height = x2 - x1, y2 - y1
        if width <= 1 or height <= 1:
            continue

        elements.append((text, (x1, y1, x2, y2), height))

    return elements


def is_region_visible(image, bounds, threshold=15):
    """
    Verifica se a região tem variação de cor suficiente (não é toda preta/branca/etc).
    """
    x1, y1, x2, y2 = bounds
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(image.shape[1], x2)
    y2 = min(image.shape[0], y2)
    region = image[y1:y2, x1:x2]

    if region.size == 0:
        return False

    std_dev = np.std(region, axis=(0, 1))  # desvio padrão nas 3 cores
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


def detect_low_contrast_text(image_path, xml_path, output_path, dpi=320):
    image = cv2.imread(image_path)
    if image is None:
        print(f"[❌] Imagem não carregada: {image_path}")
        return

    elements = extract_text_bounds(xml_path)
    marked = False

    for text, bounds, font_size_px in elements:
        if not is_region_visible(image, bounds):
            continue  # ⛔️ pula se parece invisível ou escondido

        font_size_pt = (font_size_px * 72) / dpi
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
            x1, y1, x2, y2 = bounds
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            marked = True
            print(f"[⚠️ CONTRASTE BAIXO] '{text}' | Contraste: {contrast:.2f} | Fonte: {font_size_pt:.1f}pt")

    if marked:
        cv2.imwrite(output_path, image)
        print(f"[📸] Imagem salva: {output_path}")
    else:
        print("[✅] Nenhum problema de contraste detectado.")


# 🛠 Teste direto
if __name__ == "__main__":
    base = "C:\\Users\\dasil\\Downloads\\teste"
    index = "004"
    serial = "R9QW300D8WZ"

    xml_path = os.path.join(base, f"ui_dump_{serial}_{index}.xml")
    img_path = os.path.join(base, f"screen_{serial}_{index}.png")
    out_path = os.path.join(base, f"low_contrast_text_{index}.png")

    detect_low_contrast_text(img_path, xml_path, out_path)
