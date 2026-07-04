# accessibility_checker/extractor.py
import re
from lxml import etree
from accessibility_checker.ocr import OcrInfo
from accessibility_checker.ui_element import UIElement  # Para criar objetos UIElement

# Subclasses de AdapterView do framework: os itens desses containers sao
# alcancaveis por d-pad via mecanismo de selecao do proprio container,
# entao clickable sem focusable neles nao implica inacessibilidade por
# teclado. RecyclerView fica deliberadamente fora: seus itens participam
# da busca de foco normal e precisam ser focaveis individualmente.
ADAPTER_VIEW_CLASSES = {
    "android.widget.ListView",
    "android.widget.GridView",
    "android.widget.Spinner",
    "android.widget.ExpandableListView",
    "android.widget.Gallery",
    "android.widget.StackView",
    "android.widget.AdapterViewFlipper",
    "android.widget.AdapterViewAnimator",
}

def has_adapter_view_ancestor(node):
    parent = node.getparent()
    while parent is not None:
        if parent.get("class") in ADAPTER_VIEW_CLASSES:
            return True
        parent = parent.getparent()
    return False

class XmlNodeBoundsExtractor:
    def __init__(self, xml_file_path, image):
        self.xml_file_path = xml_file_path
        self.image = image
        self.nodes_with_bounds = []

    def extract_bounds(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()
        node_types = ["android.widget.TextView", "android.widget.Button", "android.widget.EditText"]
        for node in root.iter("node"):
            node_class = node.get("class")
            text = node.get("text", "").strip()
            content_desc = node.get("content-desc", "").strip()
            bounds = node.get("bounds")
            if node_class in node_types and (text or content_desc):
                self.nodes_with_bounds.append({
                    "class": node_class,
                    "text": text,
                    "content-desc": content_desc,
                    "bounds": bounds
                })
        return self.nodes_with_bounds

    def extract_non_textual_nodes(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()
        non_textual_nodes = []
        non_textual_classes = [
            "android.widget.ImageView",
            "android.widget.ImageButton",
            "android.widget.VideoView",
            "android.widget.CheckBox",
            "android.widget.Switch"
        ]
        for node in root.iter("node"):
            node_class = node.get("class")
            bounds = node.get("bounds")
            content_desc = node.get("content-desc", "").strip()
            resource_id = node.get("resource-id", "").strip()
            clickable = node.get("clickable", "false") == "true"
            important = node.get("importantForAccessibility", "").strip()
            if node_class in non_textual_classes:
                non_textual_nodes.append({
                    "class": node_class,
                    "bounds": bounds,
                    "content-desc": content_desc,
                    "resource_id": resource_id,
                    "clickable": clickable,
                    "importantForAccessibility": important
                })
        return non_textual_nodes

    def extract_interactive_elements(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()
        interactive_elements = []
        for node in root.iter("node"):
            node_class = node.get("class")
            bounds = node.get("bounds")
            text = node.get("text", "").strip()
            content_desc = node.get("content-desc", "").strip()
            resource_id = node.get("resource-id", "").strip()
            clickable = node.get("clickable", "false") == "true"
            focusable = node.get("focusable", "false") == "true"
            if clickable or focusable:
                interactive_elements.append({
                    "class": node_class,
                    "bounds": bounds,
                    "text": text,
                    "content-desc": content_desc,
                    "resource_id": resource_id,
                    "clickable": clickable,
                    "focusable": focusable,
                    "in_adapter_view": has_adapter_view_ancestor(node)
                })
        return interactive_elements

    def extract_focusable_elements(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()

        focusable_elements = []

        # Função recursiva para percorrer a árvore e manter a ordem
        def traverse(node, focusable_elements):
            for child in node:
                # Utiliza (child.get("atributo") or "") para garantir uma string
                node_class = (child.get("class") or "").strip()
                resource_id = (child.get("resource-id") or "").strip()
                text = (child.get("text") or "").strip()
                content_desc = (child.get("content-desc") or "").strip()
                bounds = child.get("bounds") or ""
                clickable = (child.get("clickable") or "false") == "true"
                focusable = (child.get("focusable") or "false") == "true"

                if focusable and bounds:
                    # Certifique-se de que os bounds existam antes de convertê-los
                    bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))
                    focusable_elements.append({
                        "class": node_class,
                        "resource_id": resource_id,
                        "text": text,
                        "content-desc": content_desc,
                        "bounds": bounds,
                        "bounds_tuple": bounds_tuple,
                        "node": child
                    })

                # Chamada recursiva para percorrer os filhos
                traverse(child, focusable_elements)

        traverse(root, focusable_elements)
        return focusable_elements

    def extract_interactive_elements_with_dimensions(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()

        interactive_elements = []

        for node in root.iter("node"):
            node_class = node.get("class")
            resource_id = node.get("resource-id", "").strip()
            content_desc = node.get("content-desc", "").strip()
            bounds = node.get("bounds")
            clickable = node.get("clickable", "false") == "true"
            focusable = node.get("focusable", "false") == "true"
            text = node.get("text", "").strip()

            if clickable or focusable:
                # Obter as coordenadas do bounds
                bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))
                x1, y1, x2, y2 = bounds_tuple
                width = x2 - x1
                height = y2 - y1

                interactive_elements.append({
                    "class": node_class,
                    "resource_id": resource_id,
                    "content-desc": content_desc,
                    "bounds": bounds,
                    "bounds_tuple": bounds_tuple,
                    "width": width,
                    "height": height,
                    "clickable": clickable,
                    "focusable": focusable,
                    "text": text
                })

        return interactive_elements

    def get_ocr_info_instances(self, precision=0.3):
        ocr_info_list = []
        for node in self.nodes_with_bounds:
            try:
                x1, y1, x2, y2 = OcrInfo.parse_bound_boxes(node['bounds'])
            except Exception as e:
                print(f"Erro nos bounds: {node['bounds']} - {e}")
                continue
            h, w = self.image.shape[:2]
            xa, xb = max(0, min(x1, x2)), min(w, max(x1, x2))
            ya, yb = max(0, min(y1, y2)), min(h, max(y1, y2))
            if xb <= xa or yb <= ya:
                print(f"Ignorando bounds fora da imagem: {node['bounds']}")
                continue

            crop = self.image[ya:yb, xa:xb]
            if crop.size == 0:
                print(f"Ignorando recorte vazio: {node['bounds']}")
                continue

            ocr_info = OcrInfo(crop, precision=precision, bounds=(x1, y1, x2, y2))
            ocr_info_list.append(ocr_info)
        return ocr_info_list

    def extract_ui_components(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()
        ui_components = []
        for node in root.iter("node"):
            node_class = node.get("class")
            bounds = node.get("bounds")
            text = node.get("text", "").strip()
            content_desc = node.get("content-desc", "").strip()
            resource_id = node.get("resource-id", "").strip()
            clickable = node.get("clickable", "false") == "true"
            checkable = node.get("checkable", "false") == "true"
            checked = node.get("checked", "false") == "true"
            enabled = node.get("enabled", "false") == "true"
            focusable = node.get("focusable", "false") == "true"
            selected = node.get("selected", "false") == "true"
            ui_components.append({
                "class": node_class,
                "bounds": bounds,
                "text": text,
                "content-desc": content_desc,
                "resource_id": resource_id,
                "clickable": clickable,
                "checkable": checkable,
                "checked": checked,
                "enabled": enabled,
                "focusable": focusable,
                "selected": selected
            })
        return ui_components

    def extract_ui_components_as_elements(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()
        ui_elements = []
        for node in root.iter("node"):
            node_class = node.get("class")
            bounds = node.get("bounds")
            text = node.get("text", "").strip()
            content_desc = node.get("content-desc", "").strip()
            resource_id = node.get("resource-id", "").strip()
            bounds_tuple = tuple(map(int, re.findall(r'\d+', str(bounds))))
            ui_element = UIElement(
                id=resource_id or node_class,
                content=text or content_desc,
                bounds=bounds_tuple,
                node=node
            )
            ui_elements.append(ui_element)
        return ui_elements

    def extract_input_fields_and_errors(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()
        input_fields = []
        nodes = [node for node in root.iter("node")]
        for idx, node in enumerate(nodes):
            node_class = node.get("class")
            resource_id = node.get("resource-id", "").strip()
            text = node.get("text", "").strip()
            content_desc = node.get("content-desc", "").strip()
            bounds = node.get("bounds")
            focused = node.get("focused", "false") == "true"
            enabled = node.get("enabled", "false") == "true"
            if node_class == "android.widget.EditText":
                field = {
                    "class": node_class,
                    "resource_id": resource_id,
                    "text": text,
                    "content-desc": content_desc,
                    "bounds": bounds,
                    "focused": focused,
                    "enabled": enabled,
                    "error_message": None
                }
                if idx + 1 < len(nodes):
                    next_node = nodes[idx + 1]
                    next_class = next_node.get("class")
                    next_text = next_node.get("text", "").strip()
                    if next_class == "android.widget.TextView" and next_text:
                        field["error_message"] = next_text
                        field["error_bounds"] = next_node.get("bounds")
                input_fields.append(field)
        return input_fields

    def extract_input_fields_and_labels(self):
        tree = etree.parse(self.xml_file_path)
        root = tree.getroot()
        input_fields = []
        nodes = [node for node in root.iter("node")]
        for idx, node in enumerate(nodes):
            node_class = node.get("class")
            resource_id = node.get("resource-id", "").strip()
            text = node.get("text", "").strip()
            content_desc = node.get("content-desc", "").strip()
            hint = node.get("hint", "").strip()
            bounds = node.get("bounds")
            if node_class == "android.widget.EditText":
                field = {
                    "class": node_class,
                    "resource_id": resource_id,
                    "text": text,
                    "content-desc": content_desc,
                    "hint": hint,
                    "bounds": bounds,
                    "label": None,
                    "label_bounds": None
                }
                label_for = node.get("labelFor", "").strip()
                if label_for:
                    for possible_label in nodes:
                        if possible_label.get("resource-id", "").strip() == label_for:
                            field["label"] = possible_label.get("text", "").strip()
                            field["label_bounds"] = possible_label.get("bounds")
                            break
                else:
                    if idx > 0:
                        prev_node = nodes[idx - 1]
                        if prev_node.get("class") == "android.widget.TextView":
                            field["label"] = prev_node.get("text", "").strip()
                            field["label_bounds"] = prev_node.get("bounds")
                input_fields.append(field)
        return input_fields
