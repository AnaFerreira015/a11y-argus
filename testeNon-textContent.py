import xml.etree.ElementTree as ET
import os
import cv2
import re


# Elementos que devem ter descrição alternativa
RELEVANT_CLASSES = {
    "android.widget.ImageView",
    "android.widget.ImageButton",
    "android.view.View"  # Só se for clicável
}


def extract_non_text_elements(xml_file):
    """
    Extrai elementos não textuais do XML e verifica se possuem descrição alternativa.
    Retorna uma lista de erros encontrados e seus bounds para marcação na imagem.
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()

    errors = []

    for node in root.iter('node'):
        element_class = node.get('class', '').strip()

        if element_class not in RELEVANT_CLASSES:
            continue  # Ignora elementos que não são imagens ou gráficos interativos

        resource_id = node.get('resource-id', '').strip()
        content_desc = node.get('content-desc', '').strip()
        bounds = node.get('bounds', '')
        clickable = node.get('clickable', 'false') == 'true'

        # Identifica se precisa de descrição
        needs_description = element_class in {"android.widget.ImageView", "android.widget.ImageButton"} or clickable

        if needs_description and not content_desc:
            errors.append((resource_id, element_class, "❌ Faltando descrição alternativa (content-desc)", bounds, xml_file))

    return errors


def parse_bounds(bounds):
    """Converte a string de bounds '[x1,y1][x2,y2]' para tupla (x1, y1, x2, y2)."""
    if not bounds:
        return None
    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    if match:
        return tuple(map(int, match.groups()))
    return None


def draw_rectangles(image_path, errors, output_path):
    """
    Desenha retângulos vermelhos ao redor dos elementos sem descrição alternativa.
    Salva a imagem apenas se houver marcações.
    """
    if not errors:
        return  # Não gera imagem se não houver erros

    image = cv2.imread(image_path)
    if image is None:
        print(f"Erro ao carregar a imagem: {image_path}")
        return

    for _, _, error_type, bounds, _ in errors:
        parsed_bounds = parse_bounds(bounds)
        if parsed_bounds:
            x1, y1, x2, y2 = parsed_bounds
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 0), 3)  # Vermelho
            cv2.putText(image, error_type, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

    cv2.imwrite(output_path, image)
    print(f"Imagem salva com marcação: {output_path}")


def generate_report(errors):
    """
    Gera um relatório sobre elementos não textuais sem descrição alternativa.
    """
    if not errors:
        print("✅ Todos os elementos visuais possuem descrição alternativa corretamente!")
        return

    print("\n⚠️ Problemas detectados no critério 1.1.1 (Non-text Content):\n")
    for resource_id, element_class, issue, bounds, xml_file in errors:
        print(f"📄 Arquivo: {os.path.basename(xml_file)}")
        print(f"🔹 Componente: {resource_id if resource_id else '[SEM ID]'} | 🏷️ Classe: {element_class}")
        print(f"   🚨 Erro: {issue} | 📍 Bounds: {bounds}\n")
        print("----------------------------------------------------")


# 🛠 **Arquivos XML e imagens associadas**
xml_files = [
    "C:\\Users\\dasil\\Downloads\\teste\\ui_dump_default_002.xml"
]
image_files = [
    "C:\\Users\\dasil\\Downloads\\teste\\screen_default_002.png"
]
output_image = "C:\\Users\\dasil\\Downloads\\teste\\marked_non_text_content.png"

# 📥 **Verificação de elementos visuais**
all_errors = []

for xml_file in xml_files:
    errors = extract_non_text_elements(xml_file)
    all_errors.extend(errors)

# 📄 **Geração do relatório**
generate_report(all_errors)

# 🔍 **Gerar imagem com marcações se houver erros**
if all_errors:
    draw_rectangles(image_files[0], all_errors, output_image)
