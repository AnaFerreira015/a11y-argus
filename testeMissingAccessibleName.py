import xml.etree.ElementTree as ET
import os
import cv2
import re

RELEVANT_CLASSES = {
    "android.widget.Button",
    "android.widget.EditText",
    "android.widget.CheckBox",
    "android.widget.RadioButton",
    "android.widget.Switch",
    "android.widget.SeekBar",
    "android.widget.Spinner",
    "android.widget.CompoundButton",
    "android.widget.CheckedTextView",
    "android.widget.ImageButton",
    "android.widget.ToggleButton"
}

def extract_interactive_elements(xml_file):
    """
    Extrai elementos interativos relevantes para o critério 4.1.2 da WCAG 2.2
    e verifica se possuem Name, Role e Value.
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()

    errors = []

    for node in root.iter('node'):
        element_class = node.get('class', '').strip()

        if element_class not in RELEVANT_CLASSES:
            continue  # Ignora elementos que não são relevantes

        resource_id = node.get('resource-id', '').strip()
        content_desc = node.get('content-desc', '').strip()
        text = node.get('text', '').strip()
        bounds = node.get('bounds', '')

        checkable = node.get('checkable', 'false') == 'true'
        checked = node.get('checked', 'false') == 'true'
        selected = node.get('selected', 'false') == 'true'

        # Verificações do critério 4.1.2
        name = text if text else content_desc
        if not name:
            errors.append((resource_id, element_class, "❌ Faltando Name", bounds, xml_file))

        if not element_class:
            errors.append((resource_id, "UNKNOWN", "❌ Faltando Role", bounds, xml_file))

        if checkable and not (checked or selected):
            errors.append((resource_id, element_class, "⚠️ Elemento checkável sem valor", bounds, xml_file))

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
    Desenha retângulos vermelhos ao redor dos elementos com problemas na imagem.
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
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 3)  # Vermelho
            cv2.putText(image, error_type, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

    cv2.imwrite(output_path, image)
    print(f"Imagem salva com marcação: {output_path}")


def generate_report(errors):
    """
    Gera um relatório sobre elementos que não possuem Name, Role ou Value adequadamente.
    """
    if not errors:
        print("✅ Todos os elementos interativos possuem Name, Role e Value corretamente!")
        return

    print("\n⚠️ Problemas detectados no critério 4.1.2 (Name, Role, Value):\n")
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
output_image = "C:\\Users\\dasil\\Downloads\\teste\\marked_name_role_value.png"

# 📥 **Verificação de elementos interativos**
all_errors = []

for xml_file in xml_files:
    errors = extract_interactive_elements(xml_file)
    all_errors.extend(errors)

# 📄 **Geração do relatório**
generate_report(all_errors)

# 🔍 **Gerar imagem com marcações se houver erros**
if all_errors:
    draw_rectangles(image_files[0], all_errors, output_image)
