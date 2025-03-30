import xml.etree.ElementTree as ET
import re
import cv2


def extract_text_bounds(xml_file):
    """
    Extrai textos e seus bounds do arquivo XML.
    Retorna um dicionário com o texto como chave e os bounds como valor.
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()

    text_bounds = {}

    for node in root.iter('node'):
        text = node.get('text', '').strip()
        bounds = node.get('bounds', '')

        if text and bounds:
            text_bounds[text] = parse_bounds(bounds)

    return text_bounds


def parse_bounds(bounds):
    """
    Converte a string de bounds no formato '[x1,y1][x2,y2]' em uma tupla de coordenadas inteiras.
    """
    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    if match:
        return tuple(map(int, match.groups()))
    return None


def compare_text_sizes(normal_bounds, other_bounds):
    """
    Compara os tamanhos dos textos nos dois conjuntos de bounds.
    Retorna os textos que não tiveram alteração no tamanho da fonte, junto com seus bounds.
    """
    unchanged_texts = []

    for text, normal_bound in normal_bounds.items():
        if text in other_bounds:
            other_bound = other_bounds[text]

            normal_width = normal_bound[2] - normal_bound[0]
            normal_height = normal_bound[3] - normal_bound[1]

            other_width = other_bound[2] - other_bound[0]
            other_height = other_bound[3] - other_bound[1]

            if normal_width == other_width and normal_height == other_height:
                unchanged_texts.append((text, normal_bound))

    return unchanged_texts


def draw_rectangles_cv2(image_path, unchanged_texts, output_path):
    """
    Usa OpenCV para desenhar retângulos vermelhos ao redor dos textos que não mudaram de tamanho na imagem.
    Salva a imagem apenas se houver marcações a serem feitas.
    """
    if not unchanged_texts:
        return  # Não gera imagem se não houver textos para marcar

    # Carregar a imagem com OpenCV
    image = cv2.imread(image_path)

    # Cor e espessura dos retângulos (vermelho, espessura 2px)
    color = (0, 255, 0)  # Verde em BGR
    thickness = 3

    # Desenhar retângulos ao redor dos textos inalterados
    for text, bounds in unchanged_texts:
        x1, y1, x2, y2 = bounds
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)

    # Salvar a nova imagem apenas se houver marcações
    cv2.imwrite(output_path, image)
    print(f"Imagem salva em: {output_path}")


# Caminhos dos arquivos XML e imagens
xml_normal = "C:\\Users\\dasil\\Downloads\\teste\\ui_dump_default_002.xml"
xml_small = "C:\\Users\\dasil\\Downloads\\teste\\ui_dump_small_text_002.xml"
xml_large = "C:\\Users\\dasil\\Downloads\\teste\\ui_dump_large_text_002.xml"

image_normal = "C:\\Users\\dasil\\Downloads\\teste\\screen_default_002.png"
image_small = "C:\\Users\\dasil\\Downloads\\teste\\screen_small_text_002.png"
image_large = "C:\\Users\\dasil\\Downloads\\teste\\screen_large_text_002.png"

output_small = "C:\\Users\\dasil\\Downloads\\teste\\marked_small_text_cv2.png"
output_large = "C:\\Users\\dasil\\Downloads\\teste\\marked_large_text_cv2.png"

# Extração de dados dos arquivos XML
normal_text_bounds = extract_text_bounds(xml_normal)
small_text_bounds = extract_text_bounds(xml_small)
large_text_bounds = extract_text_bounds(xml_large)

# Identificação de textos sem alteração de tamanho
unchanged_texts_small = compare_text_sizes(normal_text_bounds, small_text_bounds)
unchanged_texts_large = compare_text_sizes(normal_text_bounds, large_text_bounds)

# Desenhar retângulos nas imagens correspondentes usando OpenCV
draw_rectangles_cv2(image_small, unchanged_texts_small, output_small)
draw_rectangles_cv2(image_large, unchanged_texts_large, output_large)
