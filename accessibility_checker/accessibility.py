# accessibility_checker/accessibility.py
import re
from typing import cast, Tuple, Optional
from accessibility_checker.extractor import XmlNodeBoundsExtractor
from accessibility_checker.ui_element import is_inside_navigation_view

ICON_GLYPH_PATTERN = re.compile(r'^[^\w\s]+$')

class AccessibilityChecker:
    def __init__(self, extractor: XmlNodeBoundsExtractor, device_density=1.0, navigation_view_bounds: Optional[Tuple[int, int, int, int]] = None):
        self.extractor = extractor
        self.device_density = device_density
        self.failures = []
        self.navigation_view_bounds = navigation_view_bounds

    @staticmethod
    def get_device_density():
        import subprocess, re
        try:
            result = subprocess.check_output(['adb', 'shell', 'wm', 'density']).decode('utf-8')
            match = re.search(r'Physical density: (\d+)', result)
            if match:
                density = int(match.group(1))
                density_factor = density / 160.0
                print(f"Device density: {density} dpi, Density factor: {density_factor}")
                return density_factor
            else:
                print("Não foi possível obter a densidade do dispositivo. Usando valor padrão.")
                return 1.0
        except Exception as e:
            print(f"Erro ao obter a densidade do dispositivo: {e}")
            return 1.0

    def _is_outside_navigation_view(self, bounds: Tuple[int, int, int, int]) -> bool:
        if self.navigation_view_bounds is None:
            return True
        return not is_inside_navigation_view(bounds, self.navigation_view_bounds)

    # def is_relevant_error_scope(self, bounds):
    #     if self.navigation_view_bounds is None:
    #         return True
    #     return is_inside_navigation_view(bounds, self.navigation_view_bounds)

    # def is_relevant_error_scope(self, bounds: Tuple[int, int, int, int]) -> bool:
    #     if self.navigation_view_bounds is None:
    #         return True
    #     return is_inside_navigation_view(bounds, self.navigation_view_bounds)

    def check_gesture_navigation(self):
        failures = []
        interactive_elements = self.extractor.extract_interactive_elements()
        for element in interactive_elements:
            bounds = element.get('bounds', '')
            bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))
            node_class = element.get('class', '')
            resource_id = element.get('resource_id', '')
            clickable = element.get('clickable', False)
            focusable = element.get('focusable', False)
            content_desc = element.get('content-desc', '')
            text = element.get('text', '')
            if clickable and not focusable:
                failure = {
                    "type": "Gesture-Only Navigation",
                    "class": node_class,
                    "resource_id": resource_id,
                    "bounds": list(bounds_tuple),
                    "content-desc": content_desc,
                    "text": text,
                    "Success Criterion": "2.5.1 Pointer Gestures",
                    "Level": "A",
                    "Recommendation": "Defina 'focusable=true' ou forneça uma alternativa sem gestos."
                }
                failures.append(failure)
        # self.failures.extend(failures)
        self.failures.extend([
            f for f in failures
            if is_relevant_error_scope(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))),
                                       self.navigation_view_bounds)
        ])

    def check_non_text_content(self):
        failures = []
        non_textual_nodes = self.extractor.extract_non_textual_nodes()
        for node in non_textual_nodes:
            content_desc = node['content-desc']
            bounds = node['bounds']
            node_class = node['class']
            clickable = node['clickable']
            resource_id = node['resource_id']
            bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))
            if clickable or resource_id:
                if not content_desc:
                    failures.append({
                        "type": "Missing Content Description",
                        "class": node_class,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "1.1.1 Non-text Content",
                        "Level": "A",
                        "Recommendation": "Adicione uma descrição para este elemento interativo."
                    })
            else:
                if content_desc and content_desc.strip() != '':
                    failures.append({
                        "type": "Non-essential Content Description Should Be Empty",
                        "class": node_class,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "1.1.1 Non-text Content",
                        "Level": "A",
                        "Recommendation": "Defina o content-desc como vazio para elementos decorativos."
                    })

        # self.failures.extend([
        #     f for f in failures
        #     if self._is_outside_navigation_view(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))))
        # ])
        self.failures.extend([
            f for f in failures
            if is_relevant_error_scope(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))),
                                       self.navigation_view_bounds)
        ])

    def check_link_purpose(self):
        failures = []
        interactive_elements = self.extractor.extract_interactive_elements()
        for element in interactive_elements:
            text = element['text']
            content_desc = element['content-desc']
            bounds = element['bounds']
            node_class = element['class']
            bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))
            link_text = text or content_desc

            if not link_text.strip() or ICON_GLYPH_PATTERN.match(link_text.strip()):
                continue  # ignora glifos (ícones visuais)

            if link_text.lower() in ["clique aqui", "saiba mais", "mais informações"]:
                failures.append({
                    "type": "Link Purpose Failure",
                    "class": node_class,
                    "bounds": list(bounds_tuple),
                    "text": text,
                    "content-desc": content_desc,
                    "Success Criterion": "2.4.4 Link Purpose (In Context)",
                    "Level": "A"
                })
        # self.failures.extend([
        #     f for f in failures
        #     if self._is_outside_navigation_view(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))))
        # ])
        self.failures.extend([
            f for f in failures
            if is_relevant_error_scope(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))),
                                       self.navigation_view_bounds)
        ])

    def check_name_role_value(self):
        failures = []

        IGNORED_CLASSES_FOR_ACCESSIBLE_NAME = {
            "android.view.ViewGroup",
            "android.widget.LinearLayout",
            "android.widget.RelativeLayout",
            "android.widget.FrameLayout",
            "android.widget.ScrollView",
            "android.widget.HorizontalScrollView",
            "androidx.recyclerview.widget.RecyclerView",
            "androidx.coordinatorlayout.widget.CoordinatorLayout",
            "android.view.View",  # se não for clicável
            "android.widget.Space",
            "androidx.drawerlayout.widget.DrawerLayout",
            "androidx.appcompat.widget.Toolbar",
            "com.google.android.material.appbar.AppBarLayout",
            "com.google.android.material.navigation.NavigationView",
            "androidx.viewpager.widget.ViewPager"
        }

        ui_components = self.extractor.extract_ui_components()
        for component in ui_components:
            node_class = component.get('class', '')
            bounds = component.get('bounds', '')
            text = component.get('text', '')
            content_desc = component.get('content-desc', '')
            resource_id = component.get('resource-id', '')
            clickable = component.get('clickable', False)
            checkable = component.get('checkable', False)
            checked = component.get('checked', None)
            enabled = component.get('enabled', None)
            focusable = component.get('focusable', False)
            selected = component.get('selected', None)
            bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))
            is_interactive = clickable or focusable or checkable
            if is_interactive:
                if node_class in IGNORED_CLASSES_FOR_ACCESSIBLE_NAME:
                    continue

                accessible_name = text or content_desc
                if not accessible_name:
                    failures.append({
                        "type": "Missing Accessible Name",
                        "class": node_class,
                        "resource_id": resource_id,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "4.1.2 Name, Role, Value",
                        "Level": "A",
                        "Details": "Elemento interativo sem nome acessível."
                    })
                if checkable:
                    if not isinstance(checked, bool):
                        failures.append({
                            "type": "Missing or Invalid State Information",
                            "class": node_class,
                            "resource_id": resource_id,
                            "bounds": list(bounds_tuple),
                            "Success Criterion": "4.1.2 Name, Role, Value",
                            "Level": "A",
                            "Details": "Elemento checkable sem estado 'checked' corretamente definido."
                        })
                if not isinstance(enabled, bool):
                    failures.append({
                        "type": "Missing Enabled State",
                        "class": node_class,
                        "resource_id": resource_id,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "4.1.2 Name, Role, Value",
                        "Level": "A",
                        "Details": "Elemento interativo sem estado 'enabled' definido corretamente."
                    })
                if 'selected' in component and not isinstance(selected, bool):
                    failures.append({
                        "type": "Invalid Selected State",
                        "class": node_class,
                        "resource_id": resource_id,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "4.1.2 Name, Role, Value",
                        "Level": "A",
                        "Details": "Elemento interativo com estado 'selected' inválido."
                    })
        # self.failures.extend([
        #     f for f in failures
        #     if self._is_outside_navigation_view(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))))
        # ])
        self.failures.extend([
            f for f in failures
            if is_relevant_error_scope(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))),
                                       self.navigation_view_bounds)
        ])

    def check_error_identification(self):
        failures = []
        input_fields = self.extractor.extract_input_fields_and_errors()
        for field in input_fields:
            node_class = field['class']
            resource_id = field['resource_id']
            bounds = field['bounds']
            error_message = field.get('error_message')
            bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))
            if error_message is None:
                continue
            else:
                if not error_message.strip():
                    failures.append({
                        "type": "Missing Error Description",
                        "class": node_class,
                        "resource_id": resource_id,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "3.3.1 Error Identification",
                        "Level": "A"
                    })
                else:
                    failures.append({
                        "type": "Error Message Detected",
                        "class": node_class,
                        "resource_id": resource_id,
                        "bounds": list(bounds_tuple),
                        "error_message": error_message,
                        "Success Criterion": "3.3.1 Error Identification",
                        "Level": "A"
                    })
        # self.failures.extend([
        #     f for f in failures
        #     if self._is_outside_navigation_view(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))))
        # ])
        self.failures.extend([
            f for f in failures
            if is_relevant_error_scope(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))),
                                       self.navigation_view_bounds)
        ])

    def check_labels_or_instructions(self):
        failures = []
        input_fields = self.extractor.extract_input_fields_and_labels()
        for field in input_fields:
            node_class = field['class']
            resource_id = field['resource_id']
            bounds = field['bounds']
            label = field.get('label')
            hint = field.get('hint')
            bounds_tuple = tuple(map(int, re.findall(r'\d+', bounds)))
            if not label and not hint:
                failures.append({
                    "type": "Missing Label or Instruction",
                    "class": node_class,
                    "resource_id": resource_id,
                    "bounds": list(bounds_tuple),
                    "Success Criterion": "3.3.2 Labels or Instructions",
                    "Level": "A"
                })
            else:
                if label and not label.strip():
                    failures.append({
                        "type": "Empty Label",
                        "class": node_class,
                        "resource_id": resource_id,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "3.3.2 Labels or Instructions",
                        "Level": "A"
                    })
                if hint and not hint.strip():
                    failures.append({
                        "type": "Empty Hint",
                        "class": node_class,
                        "resource_id": resource_id,
                        "bounds": list(bounds_tuple),
                        "Success Criterion": "3.3.2 Labels or Instructions",
                        "Level": "A"
                    })
        # self.failures.extend([
        #     f for f in failures
        #     if self._is_outside_navigation_view(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))))
        # ])
        self.failures.extend([
            f for f in failures
            if is_relevant_error_scope(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))),
                                       self.navigation_view_bounds)
        ])

    def check_focus_order(self):
        failures = []
        focusable_elements = self.extractor.extract_focusable_elements()
        focus_order = focusable_elements
        visual_order = self.get_visual_order_by_rows_and_columns(focusable_elements)
        for idx, focus_elem in enumerate(focus_order):
            if idx < len(visual_order):
                visual_elem = visual_order[idx]
                if focus_elem != visual_elem:
                    if self.is_significant_focus_order_issue(focus_elem, visual_elem):
                        failure = {
                            "type": "Focus Order Failure",
                            "bounds": list(focus_elem['bounds_tuple']),
                            "index": idx,
                            "focus_element": {
                                "class": focus_elem['class'],
                                "resource_id": focus_elem['resource_id'],
                                "bounds": list(focus_elem['bounds_tuple']),
                            },
                            "expected_element": {
                                "class": visual_elem['class'],
                                "resource_id": visual_elem['resource_id'],
                                "bounds": list(visual_elem['bounds_tuple']),
                            },
                            "Success Criterion": "2.4.3 Focus Order",
                            "Level": "A",
                            "Recommendation": "Ajuste a ordem de foco para corresponder à ordem visual lógica dos elementos."
                        }
                        failures.append(failure)
            else:
                failure = {
                    "type": "Focus Order Exceeds Visual Elements",
                    "bounds": list(focus_elem['bounds_tuple']),
                    "index": idx,
                    "focus_element": {
                        "class": focus_elem['class'],
                        "resource_id": focus_elem['resource_id'],
                        "bounds": list(focus_elem['bounds_tuple']),
                    },
                    "Success Criterion": "2.4.3 Focus Order",
                    "Level": "A",
                    "Recommendation": "Verifique se todos os elementos focáveis são visíveis e organizados de forma lógica."
                }
                failures.append(failure)

        # self.failures.extend([
        #     f for f in failures
        #     if self._is_outside_navigation_view(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))))
        # ])
        self.failures.extend([
            f for f in failures
            if is_relevant_error_scope(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))),
                                       self.navigation_view_bounds)
        ])

    def get_visual_order_by_rows_and_columns(self, elements):
        rows = self.group_elements_into_rows(elements)
        visual_order = []
        for row in rows:
            sorted_row = sorted(row, key=lambda e: e['bounds_tuple'][0])
            visual_order.extend(sorted_row)
        return visual_order

    def group_elements_into_rows(self, elements, row_threshold=30):
        sorted_elements = sorted(elements, key=lambda e: e['bounds_tuple'][1])
        rows = []
        current_row = []
        current_y = None
        for element in sorted_elements:
            y_top = element['bounds_tuple'][1]
            y_bottom = element['bounds_tuple'][3]
            element_center_y = (y_top + y_bottom) / 2
            if current_y is None:
                current_y = element_center_y
                current_row.append(element)
            else:
                if abs(element_center_y - current_y) <= row_threshold:
                    current_row.append(element)
                else:
                    rows.append(current_row)
                    current_row = [element]
                    current_y = element_center_y
        if current_row:
            rows.append(current_row)
        return rows

    def is_significant_focus_order_issue(self, focus_elem, visual_elem):
        focus_index = self.get_element_index_in_visual_order(focus_elem)
        expected_index = self.get_element_index_in_visual_order(visual_elem)
        return abs(focus_index - expected_index) > 1

    def get_element_index_in_visual_order(self, element):
        visual_order = self.get_visual_order_by_rows_and_columns(self.extractor.extract_focusable_elements())
        for idx, elem in enumerate(visual_order):
            if elem == element:
                return idx
        return -1

    def check_target_size_enhanced(self):
        failures = []
        min_size_dp = 44
        min_size_px = min_size_dp * self.device_density
        interactive_elements = self.extractor.extract_interactive_elements_with_dimensions()
        for element in interactive_elements:
            if not (element.get('clickable', False) or element.get('focusable', False)):
                continue
            width_px = element['width']
            height_px = element['height']
            bounds_tuple = element['bounds_tuple']
            node_class = element['class']
            resource_id = element['resource_id']
            text = element.get('text', '')
            content_desc = element.get('content-desc', '')
            if self.is_inline_element(element):
                continue
            if self.has_equivalent_target(element, interactive_elements):
                continue
            if self.is_controlled_by_user_agent(element):
                continue
            if width_px < min_size_px or height_px < min_size_px:
                failures.append({
                    "type": "Target Size Failure",
                    "class": node_class,
                    "resource_id": resource_id,
                    "bounds": list(bounds_tuple),
                    "width": width_px,
                    "height": height_px,
                    "Success Criterion": "2.5.5 Target Size (Enhanced)",
                    "Level": "AAA",
                    "Details": f"Tamanho do alvo é {width_px}px x {height_px}px, menor que o mínimo exigido de {min_size_px}px."
                })
        # self.failures.extend([
        #     f for f in failures
        #     if self._is_outside_navigation_view(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))))
        # ])
        self.failures.extend([
            f for f in failures
            if is_relevant_error_scope(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))),
                                       self.navigation_view_bounds)
        ])

    def is_inline_element(self, element):
        node_class = element['class']
        text = element.get('text', '')
        content_desc = element.get('content-desc', '')
        return node_class == 'android.widget.TextView' and (text or content_desc)

    def has_equivalent_target(self, element, interactive_elements):
        for other in interactive_elements:
            if other == element:
                continue
            if self.is_equivalent_function(element, other):
                if other['width'] >= 44 * self.device_density and other['height'] >= 44 * self.device_density:
                    return True
        return False

    def is_equivalent_function(self, elem1, elem2):
        if elem1['resource_id'] and elem1['resource_id'] == elem2['resource_id']:
            return True
        if elem1.get('action') and elem1['action'] == elem2.get('action'):
            return True
        return False

    def is_controlled_by_user_agent(self, element):
        node_class = element['class']
        controlled_classes = ['android.widget.ScrollView', 'android.widget.EditText']
        return node_class in controlled_classes

    def check_target_size_minimum(self):
        failures = []
        min_size_dp = 24
        min_size_px = min_size_dp * self.device_density
        interactive_elements = self.extractor.extract_interactive_elements_with_dimensions()
        for element in interactive_elements:
            if not element.get('clickable', False):
                continue
            width_px = element['width']
            height_px = element['height']
            bounds_tuple = element['bounds_tuple']
            node_class = element['class']
            resource_id = element['resource_id']
            if self.is_inline_element(element):
                continue
            if self.has_equivalent_target(element, interactive_elements):
                continue
            if self.is_controlled_by_user_agent(element):
                continue
            if width_px < min_size_px or height_px < min_size_px:
                failures.append({
                    "type": "Target Size Failure (Minimum)",
                    "class": node_class,
                    "resource_id": resource_id,
                    "bounds": list(bounds_tuple),
                    "width": width_px,
                    "height": height_px,
                    "Success Criterion": "2.5.8 Target Size (Minimum)",
                    "Level": "AA",
                    "Details": f"Tamanho do alvo é {width_px}px x {height_px}px, menor que o mínimo exigido de {min_size_px}px."
                })
        # self.failures.extend([
        #     f for f in failures
        #     if self._is_outside_navigation_view(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))))
        # ])
        self.failures.extend([
            f for f in failures
            if is_relevant_error_scope(cast(Tuple[int, int, int, int], tuple(f.get("bounds", []))),
                                       self.navigation_view_bounds)
        ])

    def run_all_checks(self):
        self.check_non_text_content()
        self.check_link_purpose()
        self.check_name_role_value()
        self.check_error_identification()
        self.check_labels_or_instructions()
        self.check_focus_order()
        self.check_target_size_enhanced()
        self.check_target_size_minimum()
        self.check_gesture_navigation()

    def get_failures(self):
        return self.failures

def is_relevant_error_scope(bounds: Tuple[int, int, int, int], navigation_view_bounds: Optional[Tuple[int, int, int, int]]) -> bool:
    if navigation_view_bounds is None:
        return True
    return is_inside_navigation_view(bounds, navigation_view_bounds)