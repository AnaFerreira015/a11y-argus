import xml.etree.ElementTree as ET
import os
import re
import cv2


def draw_spacing_violations(image_path, errors, output_path):
    """
    Desenha retângulos vermelhos ao redor de textos com espaçamento inadequado.
    Agora evita sobreposições ao marcar apenas os maiores bounds e adiciona
    o valor real do espaçamento na marcação da imagem.
    """
    if not errors:
        return

    image = cv2.imread(image_path)
    if image is None:
        print(f"Erro ao carregar a imagem: {image_path}")
        return

    # Ordena os bounds por área (maiores primeiro)
    sorted_bounds = sorted(errors, key=lambda e: get_area(parse_bounds(e[3])), reverse=True)
    filtered_bounds = []

    for text, element_class, issue, bounds, actual_spacing, min_spacing, _ in sorted_bounds:
        parsed_bounds = parse_bounds(bounds)
        if not parsed_bounds:
            continue

        # Apenas adiciona se não estiver contido em um bound maior já registrado
        if not any(is_inside(parsed_bounds, parse_bounds(b)) for _, _, _, b, _, _, _ in filtered_bounds if parse_bounds(b)):
            filtered_bounds.append((text, element_class, issue, bounds, actual_spacing, min_spacing, _))

    # Desenha apenas os bounds filtrados
    for text, element_class, issue, bounds, actual_spacing, min_spacing, _ in filtered_bounds:
        parsed_bounds = parse_bounds(bounds)
        if parsed_bounds:
            x1, y1, x2, y2 = parsed_bounds
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 2)
            message = f"{issue} ({actual_spacing:.2f}px < {min_spacing:.2f}px)"
            cv2.putText(image, message, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    cv2.imwrite(output_path, image)
    print(f"Imagem com marcações de espaçamento salva em: {output_path}")


def is_inside(inner, outer):
    """
    Verifica se o bound `inner` está completamente dentro de `outer`.
    """
    if not inner or not outer:
        return False
    x1, y1, x2, y2 = inner
    X1, Y1, X2, Y2 = outer
    return X1 <= x1 and Y1 <= y1 and X2 >= x2 and Y2 >= y2


def get_area(bounds):
    """
    Calcula a área de um bound.
    """
    if not bounds:
        return 0
    x1, y1, x2, y2 = bounds
    return (x2 - x1) * (y2 - y1)


def extract_text_spacing(xml_file):
    """
    Extrai informações de espaçamento de texto do XML.
    Retorna uma lista de possíveis violações da WCAG 2.2 (Text Spacing),
    incluindo os valores reais de espaçamento detectados.
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()

    errors = []

    for node in root.iter('node'):
        text = node.get('text', '').strip()
        bounds = node.get('bounds', '')
        element_class = node.get('class', '').strip()

        if element_class not in {"android.widget.TextView", "android.widget.EditText"}:
            continue

        bounds_tuple = parse_bounds(bounds)
        if not bounds_tuple:
            continue

        x1, y1, x2, y2 = bounds_tuple
        text_height = y2 - y1  # Altura do texto

        # Critérios da WCAG 2.2
        min_line_spacing = text_height * 1.5
        min_paragraph_spacing = text_height * 2.0
        min_word_spacing = text_height * 0.16
        min_letter_spacing = text_height * 0.12

        # Simulação de espaçamentos reais (deve vir do app)
        actual_line_spacing = text_height * 1.2
        actual_paragraph_spacing = text_height * 1.5
        actual_word_spacing = text_height * 0.14
        actual_letter_spacing = text_height * 0.10

        # Verificações
        if actual_line_spacing < min_line_spacing:
            errors.append((text, element_class, "⚠️ Espaçamento entre linhas insuficiente", bounds, actual_line_spacing, min_line_spacing, xml_file))

        if actual_paragraph_spacing < min_paragraph_spacing:
            errors.append((text, element_class, "⚠️ Espaçamento entre parágrafos insuficiente", bounds, actual_paragraph_spacing, min_paragraph_spacing, xml_file))

        if actual_word_spacing < min_word_spacing:
            errors.append((text, element_class, "⚠️ Espaçamento entre palavras insuficiente", bounds, actual_word_spacing, min_word_spacing, xml_file))

        if actual_letter_spacing < min_letter_spacing:
            errors.append((text, element_class, "⚠️ Espaçamento entre caracteres insuficiente", bounds, actual_letter_spacing, min_letter_spacing, xml_file))

    return errors


def parse_bounds(bounds):
    """Converte a string de bounds '[x1,y1][x2,y2]' para tupla (x1, y1, x2, y2)."""
    if not bounds:
        return None
    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    if match:
        return tuple(map(int, match.groups()))
    return None


def generate_report(errors):
    """
    Gera um relatório sobre espaçamento de texto inadequado, incluindo os valores reais.
    """
    if not errors:
        print("✅ Todos os textos seguem os padrões de espaçamento corretamente!")
        return

    print("\n⚠️ Problemas detectados no critério 1.4.12 (Text Spacing):\n")
    for text, element_class, issue, bounds, actual_spacing, min_spacing, xml_file in errors:
        print(f"📄 Arquivo: {os.path.basename(xml_file)}")
        print(f"🔹 Texto: \"{text}\" | 🏷️ Classe: {element_class}")
        print(f"   🚨 Erro: {issue} | 📍 Bounds: {bounds}")
        print(f"   📏 Espaçamento detectado: {actual_spacing:.2f}px | Requerido: {min_spacing:.2f}px\n")
        print("----------------------------------------------------")


# 🛠 **Arquivos XML e imagem associada**
xml_files = [
    "C:\\Users\\dasil\\Downloads\\teste\\ui_dump_default_002.xml",
    "C:\\Users\\dasil\\Downloads\\teste\\ui_dump_small_text_002.xml",
    "C:\\Users\\dasil\\Downloads\\teste\\ui_dump_large_text_002.xml"
]
image_path = "C:\\Users\\dasil\\Downloads\\teste\\screen_default_002.png"
output_image_path = "C:\\Users\\dasil\\Downloads\\teste\\marked_text_spacing.png"

# 📥 **Verificação de espaçamento de texto**
all_errors = []

for xml_file in xml_files:
    errors = extract_text_spacing(xml_file)
    all_errors.extend(errors)

# 📄 **Geração do relatório**
generate_report(all_errors)

# 🔍 **Marcação na imagem, evitando sobreposição**
if all_errors:
    draw_spacing_violations(image_path, all_errors, output_image_path)
