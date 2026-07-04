import re
from typing import cast, Tuple, Optional
from accessibility_checker.extractor import XmlNodeBoundsExtractor
from accessibility_checker.ui_element import is_inside_navigation_view
import math

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

    def passes_spacing_exception(self, element, interactive_elements):
        """Excecao de espacamento do SC 2.5.8: um alvo menor que 24x24dp passa
        se um circulo de 24dp de diametro centrado no seu bounding box nao
        intersecta o bounding box de nenhum outro alvo nem o circulo de outro
        alvo subdimensionado.
        https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
        """
        radius_px = 12 * self.device_density
        min_size_px = 24 * self.device_density
        cx, cy = self._element_center(element)

        for other in interactive_elements:
            if other == element:
                continue
            if not other.get('clickable', False):
                continue
            if other['width'] <= 0 or other['height'] <= 0:
                continue
            if self._contains(other, element):
                # Container clicavel que envolve o alvo (linha/celula pai):
                # tratado como alvo aninhado, nao como alvo adjacente.
                # Decisao pragmatica; documentar na dissertacao.
                continue

            # Circulo do alvo vs bounding box do outro alvo
            if self._circle_intersects_rect(cx, cy, radius_px, other['bounds_tuple']):
                return False

            # Circulo vs circulo, quando o outro tambem e subdimensionado
            if other['width'] < min_size_px or other['height'] < min_size_px:
                ox, oy = self._element_center(other)
                if math.hypot(cx - ox, cy - oy) < 2 * radius_px:
                    return False
        return True

    def _element_center(self, element):
        left, top, right, bottom = element['bounds_tuple']
        return (left + right) / 2.0, (top + bottom) / 2.0

    def _contains(self, outer, inner):
        ol, ot, orr, ob = outer['bounds_tuple']
        il, it, ir, ib = inner['bounds_tuple']
        return ol <= il and ot <= it and orr >= ir and ob >= ib

    def _circle_intersects_rect(self, cx, cy, radius, rect):
        left, top, right, bottom = rect
        nearest_x = max(left, min(cx, right))
        nearest_y = max(top, min(cy, bottom))
        return math.hypot(cx - nearest_x, cy - nearest_y) < radius

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
                if element.get("in_adapter_view"):
                    # Itens de AdapterView sao alcancaveis via selecao
                    # do container pelo d-pad; nao e falha de teclado.
                    continue
                failure = {
                    "type": "Gesture-Only Navigation",
                    "class": node_class,
                    "resource_id": resource_id,
                    "bounds": list(bounds_tuple),
                    "content-desc": content_desc,
                    "text": text,
                    "Success Criterion": "2.1.1 Keyboard",
                    "Level": "A",
                    "Recommendation": "Defina 'focusable=true' (ou "
                                      "android:focusable no layout) para que o "
                                      "elemento seja alcançável por teclado, "
                                      "switch access e d-pad."
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
        """
        Detecta rótulos ambíguos (ex.: 'clique aqui', 'saiba mais', 'learn more') em:
          (A) elementos interativos com esse rótulo
          (B) elementos de texto cujo rótulo é ambíguo e está contido por um contêiner interativo (wrapper)
        Não aplica filtro de navigation_view_bounds aqui.
        """
        import unicodedata

        failures = []
        seen = set()

        components = self.extractor.extract_ui_components()

        def parse_bounds(bstr):
            m = re.findall(r'\d+', bstr or '')
            return tuple(map(int, m)) if len(m) == 4 else None

        def contains(outer, inner, pad=2):
            (x1, y1, x2, y2) = outer
            (a1, b1, a2, b2) = inner
            return (x1 - pad) <= a1 and (y1 - pad) <= b1 and (x2 + pad) >= a2 and (y2 + pad) >= b2

        def fold_text(s: str) -> str:
            # NFKC -> minúsculas -> remove acentos -> colapsa não-alfanumérico/esp.
            s = unicodedata.normalize("NFKC", (s or "")).lower().strip()
            s = ''.join(ch for ch in unicodedata.normalize('NFD', s) if unicodedata.category(ch) != 'Mn')
            s = re.sub(r'[\s\W]+', ' ', s).strip()
            return s

        AMBIG_EXACT = {
            "clique aqui", "saiba mais", "leia mais", "ver mais", "veja mais",
            "mais informacoes", "mais detalhes", "detalhes",
            "more", "learn more", "read more", "details", "here", "tap here", "click here",
        }
        AMBIG_RE = re.compile(
            r"\b(clique aqui|tap here|click here|saiba mais|leia mais|ver mais|veja mais|"
            r"read more|learn more|mais informacoes|mais detalhes|details)\b"
        )
        SINGLE_WEAK = {"detalhes", "more", "details", "here"}

        def is_ambiguous(label: str) -> bool:
            if not label:
                return False
            if ICON_GLYPH_PATTERN.match(label.strip()):
                return False
            f = fold_text(label)
            if not f:
                return False
            if f in AMBIG_EXACT:
                return True
            if AMBIG_RE.search(f):
                # heurística anti-falso-positivo: se frase é longa e só contém token fraco
                toks = f.split()
                if len(toks) > 3 and any(t in SINGLE_WEAK for t in toks):
                    return False
                return True
            return False

        nodes = []
        for c in components:
            b = parse_bounds(c.get('bounds'))
            if not b or b == (0, 0, 0, 0):
                continue
            node = {
                'class': c.get('class', ''),
                'resource_id': c.get('resource-id', '') or c.get('resource_id', ''),
                'text': (c.get('text') or '').strip(),
                'desc': (c.get('content-desc') or '').strip(),
                'clickable': bool(c.get('clickable', False)),
                'focusable': bool(c.get('focusable', False)),
                'checkable': bool(c.get('checkable', False)),
                'bounds': b,
            }
            node['label'] = node['text'] if node['text'] else node['desc']
            nodes.append(node)

        interactive = [n for n in nodes if n['clickable'] or n['focusable'] or n['checkable']]
        textual = [n for n in nodes if n['label']]

        for n in interactive:
            if is_ambiguous(n['label']):
                key = (n['bounds'], fold_text(n['label']))
                if key in seen:
                    continue
                seen.add(key)
                failures.append({
                    "type": "Link Purpose Failure",
                    "class": n['class'],
                    "resource_id": n['resource_id'],
                    "bounds": list(n['bounds']),
                    "text": n['text'],
                    "content-desc": n['desc'],
                    "Success Criterion": "2.4.4 Link Purpose (In Context)",
                    "Level": "A",
                    "Recommendation": "Use um rótulo descritivo (ex.: “Detalhes do pedido”, “Ajuda de pagamento”) em vez de frases genéricas."
                })

        for t in textual:
            if not is_ambiguous(t['label']):
                continue
            for w in interactive:
                if w is t:
                    continue
                if contains(w['bounds'], t['bounds']):
                    key = (w['bounds'], fold_text(t['label']))
                    if key in seen:
                        continue
                    seen.add(key)
                    failures.append({
                        "type": "Link Purpose Failure",
                        "class": w['class'],
                        "resource_id": w['resource_id'],
                        "bounds": list(w['bounds']),
                        "text": t['text'] or w['text'],
                        "content-desc": t['desc'] or w['desc'],
                        "Success Criterion": "2.4.4 Link Purpose (In Context)",
                        "Level": "A",
                        "Recommendation": "Forneça um rótulo específico (ex.: “Detalhes do pedido”) no contêiner clicável."
                    })
                    break

        print(f"[LINK] interativos={len(interactive)} textuais={len(textual)} falhas={len(failures)}")

        self.failures.extend(failures)

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

        components = self.extractor.extract_ui_components()

        focus_candidates = []
        for c in components:
            clickable = c.get('clickable', False)
            focusable = c.get('focusable', False)
            checkable = c.get('checkable', False)

            if not (focusable or clickable or checkable):
                continue

            bounds = c.get('bounds', '')
            m = re.findall(r'\d+', bounds)
            if len(m) != 4:
                continue
            x1, y1, x2, y2 = map(int, m)
            if (x1, y1, x2, y2) == (0, 0, 0, 0):
                continue

            focus_candidates.append({
                'class': c.get('class', ''),
                'resource_id': c.get('resource-id', ''),
                'bounds_tuple': (x1, y1, x2, y2),
            })

        focus_order = focus_candidates[:]
        visual_order = self.get_visual_order_by_rows_and_columns(focus_candidates)

        idx_in_visual = {id(elem): i for i, elem in enumerate(visual_order)}

        for idx, focus_elem in enumerate(focus_order):
            expected_visual_elem = visual_order[idx]

            same_obj = (focus_elem is expected_visual_elem)
            same_value = (focus_elem == expected_visual_elem)

            if not (same_obj or same_value):
                focus_idx_in_visual = idx_in_visual.get(id(focus_elem), -1)
                if focus_idx_in_visual == -1:
                    continue  # não achou no mapa por algum motivo

                if abs(focus_idx_in_visual - idx) >= 1:
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
                            "class": expected_visual_elem['class'],
                            "resource_id": expected_visual_elem['resource_id'],
                            "bounds": list(expected_visual_elem['bounds_tuple']),
                        },
                        "Success Criterion": "2.4.3 Focus Order",
                        "Level": "A",
                        "Recommendation": "Ajuste a ordem de foco para corresponder à ordem visual lógica dos elementos."
                    }
                    failures.append(failure)

        self.failures.extend(failures)

    def get_visual_order_by_rows_and_columns(self, elements):
        rows = self.group_elements_into_rows(elements)
        visual_order = []
        for row in rows:
            sorted_row = sorted(row, key=lambda e: e['bounds_tuple'][0])
            visual_order.extend(sorted_row)
        return visual_order

    def group_elements_into_rows(self, elements, row_threshold_dp=24):
        row_threshold = row_threshold_dp * self.device_density
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
            if width_px <= 0 or height_px <= 0:
                # Elemento com bounds colapsado (largura ou altura nula): nao tem
                # alvo visivel para avaliar, ignora para nao gerar falso positivo.
                continue
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
            if width_px <= 0 or height_px <= 0:
                # Elemento com bounds colapsado (largura ou altura nula): nao tem
                # alvo visivel para avaliar, ignora para nao gerar falso positivo.
                continue
            if self.is_inline_element(element):
                continue
            if self.has_equivalent_target(element, interactive_elements):
                continue
            if self.is_controlled_by_user_agent(element):
                continue
            if width_px < min_size_px or height_px < min_size_px:
                if self.passes_spacing_exception(element, interactive_elements):
                    continue

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