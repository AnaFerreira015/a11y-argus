import xml.etree.ElementTree as ET
import os
from collections import defaultdict


def extract_elements(xml_file):
    """
    Extrai os elementos relevantes do XML, incluindo resource-id, texto e content-desc.
    Retorna um dicionário agrupado pelo resource-id ou content-desc.
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()

    elements = defaultdict(list)

    for node in root.iter('node'):
        resource_id = node.get('resource-id', '').strip()
        content_desc = node.get('content-desc', '').strip()
        text = node.get('text', '').strip()
        element_class = node.get('class', '').strip()

        identifier = resource_id if resource_id else content_desc  # Prioriza resource-id se existir
        if identifier:
            elements[identifier].append((text, content_desc, element_class, xml_file))

    return elements


def compare_identification(elements_list):
    """
    Compara as identificações dos mesmos elementos em diferentes telas.
    Retorna um relatório de inconsistências.
    """
    inconsistencies = {}

    for identifier, elements in elements_list.items():
        unique_texts = {e[0] for e in elements}  # Conjunto de textos únicos
        unique_descriptions = {e[1] for e in elements}  # Conjunto de descrições únicas

        if len(unique_texts) > 1 or len(unique_descriptions) > 1:
            inconsistencies[identifier] = elements

    return inconsistencies


def generate_report(inconsistencies):
    """
    Gera um relatório de inconsistências de identificação e exibe na tela.
    """
    if not inconsistencies:
        print("✅ Nenhuma inconsistência encontrada. Todos os componentes têm identificações consistentes!")
        return

    print("\n⚠️ Inconsistências encontradas na identificação de componentes:\n")
    for identifier, elements in inconsistencies.items():
        print(f"🔹 Componente: {identifier}")
        for text, content_desc, element_class, xml_file in elements:
            print(f"   📄 Arquivo: {os.path.basename(xml_file)}")
            print(f"   🏷️ Texto: '{text}' | 📌 Content-desc: '{content_desc}' | 🏷️ Classe: {element_class}\n")
        print("----------------------------------------------------")


# 🛠 **Lista de arquivos XML das telas a serem analisadas**
xml_files = [
    "C:\\Users\\dasil\\Downloads\\teste\\ui_dump_default_002.xml",
    "C:\\Users\\dasil\\Downloads\\teste\\ui_dump_small_text_002.xml",
    "C:\\Users\\dasil\\Downloads\\teste\\ui_dump_large_text_002.xml"
]

# 📥 **Extração de dados**
all_elements = defaultdict(list)

for xml_file in xml_files:
    elements = extract_elements(xml_file)
    for identifier, values in elements.items():
        all_elements[identifier].extend(values)

# 🔍 **Comparação de identificações**
inconsistencies = compare_identification(all_elements)

# 📄 **Geração do relatório**
generate_report(inconsistencies)
