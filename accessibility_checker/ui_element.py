# accessibility_checker/ui_element.py
import re
from typing import List, Tuple, Optional
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

IGNORED_DUPLICATE_IDS = {
    "org.schabi.newpipe:id/itemUploaderView",
    "org.schabi.newpipe:id/itemVideoTitleView",
    "org.schabi.newpipe:id/itemDurationView",
    "org.schabi.newpipe:id/itemAdditionalDetails",
    "org.schabi.newpipe:id/toolbar_search_clear_icon",
}

IGNORED_CLASSES_DUPLICATE_TEXT = {
    "androidx.constraintlayout.widget.ConstraintLayout",
    "androidx.recyclerview.widget.RecyclerView",
    "androidx.viewpager.widget.ViewPager",
    "android.widget.HorizontalScrollView",
    "android.widget.GridLayout",
    "android.widget.TableLayout",
    "androidx.coordinatorlayout.widget.CoordinatorLayout",
    "android.widget.ListView",
    "android.widget.ScrollView",  # caso não esteja no CONTAINER_CLASSES
}

def check_overlapping_elements(elements: List[UIElement], xml_root, tolerance: int = 5) -> List[Tuple[UIElement, UIElement]]:
    overlapping_pairs = []
    seen_pairs = set()

    for i, elem1 in enumerate(elements):
        if not elem1.content.strip():  # Apenas elementos que possuem texto
            continue

        for j, elem2 in enumerate(elements):
            if i >= j:
                continue
            if not elem2.content.strip():  # Apenas elementos que possuem texto
                continue

            if is_overlapping(elem1.bounds, elem2.bounds, tolerance) and not is_parent_or_child(elem1, elem2):
                pair_key = tuple(sorted([elem1.id, elem2.id]))
                if pair_key not in seen_pairs:
                    # print(f"[DEBUG] Sobreposição de texto detectada: {elem1.id} {elem1.bounds} <--> {elem2.id} {elem2.bounds}")
                    overlapping_pairs.append((elem1, elem2))
                    seen_pairs.add(pair_key)

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

def is_inside_navigation_view(error_bounds: Tuple[int, int, int, int], nav_bounds: Optional[Tuple[int, int, int, int]]) -> bool:
    if nav_bounds is None:
        return True  # Se não há navigation_view, não filtra nada
    x1, y1, x2, y2 = error_bounds
    nx1, ny1, nx2, ny2 = nav_bounds
    return x1 >= nx1 and y1 >= ny1 and x2 <= nx2 and y2 <= ny2

def is_within_context(bounds: Tuple[int, int, int, int], context_bounds: Tuple[int, int, int, int]) -> bool:
    x1, y1, x2, y2 = bounds
    cx1, cy1, cx2, cy2 = context_bounds
    return x1 >= cx1 and y1 >= cy1 and x2 <= cx2 and y2 <= cy2

def get_nearest_container_id(node) -> str:
    """
    Sobe na hierarquia até encontrar um container com resource-id ou content-desc.
    """
    while node is not None:
        rid = node.get("resource-id", "").strip()
        desc = node.get("content-desc", "").strip()
        if rid or desc:
            return rid or desc
        node = node.getparent()
    return ""  # Fallback: sem container identificável

def is_parent_or_child(elem1: UIElement, elem2: UIElement) -> bool:
    """
    Melhorado para evitar sobreposição detectada dentro de containers comuns.
    """
    if elem1.node is None or elem2.node is None:
        return False

    # Se ambos os elementos estão no mesmo container, não devem ser marcados
    if elem1.node.getparent() == elem2.node.getparent():
        return True

    # Verifica se um elemento é pai/filho do outro
    return elem1.node in list(elem2.node.iterancestors()) or elem2.node in list(elem1.node.iterancestors())

def check_duplicate_text(elements: List[UIElement], xml_root, context_bounds=None) -> List[UIElement]:
    """Verifica se há textos duplicados dentro do mesmo container e dentro do contexto visual (se fornecido)."""
    seen_content = {}
    duplicate_elements = []
    ICON_GLYPH_PATTERN = re.compile(r'^[^\w\s]+$')
    PRICE_PATTERN = re.compile(r'^[\u20ac\$\u00a3]?\s?\d+([.,]\d+)?\s*/\s*[\u20ac\$\u00a3]?\s?\d+([.,]\d+)?$')
    UNIT_PATTERN = re.compile(r'\b\d+(\.\d+)?\s?(ml|g|kg|l|km|cm|mm|m|ºC|°C|un|x)\b', re.IGNORECASE)

    for element in elements:
        if not element.content.strip():
            continue

        if not element.bounds or element.bounds == (0, 0, 0, 0):
            continue

        if element.id in IGNORED_DUPLICATE_IDS:
            continue

        # Ignora elementos que são containers genéricos (não são visuais de texto por si só)
        if element.node is not None:
            element_class = element.node.get("class", "")
            if element_class in CONTAINER_CLASSES or element_class in IGNORED_CLASSES_DUPLICATE_TEXT:
                continue

        # Ignora ícones como textos duplicados (ex: FontAwesome, Material Icons via fonte)
        if ICON_GLYPH_PATTERN.match(element.content.strip()):
            continue

        if PRICE_PATTERN.match(element.content.strip()):
            continue

        # Ignora textos que são apenas valores de unidades de medida
        if UNIT_PATTERN.match(element.content.strip()):
            continue

        # Considera apenas se estiver dentro do contexto visual (ex: design_navigation_view)
        if context_bounds and not is_inside_navigation_view(element.bounds, context_bounds):
            continue

        container_id = get_nearest_container_id(element.node)
        key = (element.content.strip(), container_id)

        # Já encontramos esse conteúdo no mesmo container
        if key in seen_content:
            # Ignora se for exatamente o mesmo botão replicado (ex: ícone "voltar")
            prev_elem = seen_content[key]
            prev_desc = prev_elem.node.get("content-desc", "").strip() if prev_elem.node is not None else ""
            curr_desc = element.node.get("content-desc", "").strip() if element.node is not None else ""
            prev_class = prev_elem.node.get("class", "") if prev_elem.node is not None else ""
            curr_class = element.node.get("class", "") if element.node is not None else ""

            # Ignora se for exatamente o mesmo botão replicado (ex: ícone "voltar")
            if (
                    prev_desc and curr_desc and prev_desc == curr_desc and
                    prev_class == curr_class and
                    prev_class in {"android.widget.Button", "android.widget.ImageButton"}
            ):
                continue

            # Ignora se text == content-desc em ambos (mesmo significado acessível)
            prev_text = prev_elem.node.get("text", "").strip() if prev_elem.node is not None else ""
            curr_text = element.node.get("text", "").strip() if element.node is not None else ""
            if (
                    prev_text == prev_desc == prev_elem.content.strip() and
                    curr_text == curr_desc == element.content.strip() and
                    prev_text == curr_text
            ):
                continue

            print(f"[DEBUG] Texto duplicado encontrado: '{element.content}' no container {container_id}")
            duplicate_elements.append(element)

        else:
            seen_content[key] = element

    return duplicate_elements

def get_parent_id(element_id: str, xml_root) -> str:
    node = xml_root.xpath(f".//node[@resource-id='{element_id}']")
    if node:
        parent = node[0].getparent()
        if parent is not None:
            return parent.attrib.get("resource-id", "")
    return ""
