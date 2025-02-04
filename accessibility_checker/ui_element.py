# accessibility_checker/ui_element.py
from typing import List, Tuple
from lxml import etree

class UIElement:
    """Representa um elemento de interface do usuário."""
    def __init__(self, id: str, content: str, bounds: Tuple[int, int, int, int], node=None):
        """
        :param id: Identificador único do elemento.
        :param content: Texto acessível ou descrição.
        :param bounds: Limites do elemento como (x_min, y_min, x_max, y_max).
        :param node: (Opcional) Referência ao nó XML correspondente.
        """
        self.id = id
        self.content = content or ""
        self.bounds = bounds
        self.node = node

    def __repr__(self):
        return f"UIElement(id={self.id}, content='{self.content}', bounds={self.bounds})"

# Lista de classes consideradas containers e que podem ser ignoradas na verificação de sobreposição
CONTAINER_CLASSES = [
    "android.widget.FrameLayout",
    "android.widget.LinearLayout",
    "android.widget.ScrollView",
    "android.view.ViewGroup"
]

def check_overlapping_elements(elements: List[UIElement], xml_root, tolerance: int = 0) -> List[Tuple[UIElement, UIElement]]:
    """
    Verifica se há elementos de texto que se sobrepõem (ignorando relações pai-filho),
    aplicando um tolerance.
    """
    overlapping_pairs = []
    for i, elem1 in enumerate(elements):
        for j, elem2 in enumerate(elements):
            if i >= j:
                continue
            if is_overlapping(elem1.bounds, elem2.bounds, tolerance):
                if not is_parent_or_child(elem1, elem2):
                    overlapping_pairs.append((elem1, elem2))
    return overlapping_pairs

def is_overlapping(bounds1: Tuple[int, int, int, int], bounds2: Tuple[int, int, int, int], tolerance: int = 0) -> bool:
    x1_min, y1_min, x1_max, y1_max = bounds1
    x2_min, y2_min, x2_max, y2_max = bounds2

    # Se os elementos se tocam exatamente, não são considerados sobrepostos
    if x1_max == x2_min or x2_max == x1_min or y1_max == y2_min or y2_max == y1_min:
        return False

    return not (
        x1_max + tolerance <= x2_min or
        x2_max + tolerance <= x1_min or
        y1_max + tolerance <= y2_min or
        y2_max + tolerance <= y1_min
    )

def is_parent_or_child(elem1: UIElement, elem2: UIElement) -> bool:
    if elem1.node is None or elem2.node is None:
        return False
    return (elem1.node in list(elem2.node.iterancestors()) or
            elem2.node in list(elem1.node.iterancestors()))

def check_duplicate_text(elements: List[UIElement], xml_root) -> List[UIElement]:
    """Verifica se há textos duplicados, considerando o contexto (por exemplo, o pai)."""
    seen_content = {}
    duplicate_elements = []
    for element in elements:
        if not element.content.strip():
            continue
        parent_id = get_parent_id(element.id, xml_root)
        content_key = (element.content, parent_id)
        if content_key in seen_content:
            print(f"[DEBUG] Texto duplicado encontrado: '{element.content}' no elemento {element.id}")
            duplicate_elements.append(element)
        else:
            seen_content[content_key] = element
    return duplicate_elements

def get_parent_id(element_id: str, xml_root) -> str:
    node = xml_root.xpath(f".//node[@resource-id='{element_id}']")
    if node:
        parent = node[0].getparent()
        if parent is not None:
            return parent.attrib.get("resource-id", "")
    return ""
