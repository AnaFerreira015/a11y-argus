import os
import re
import time
import json
import glob
import subprocess
from droidbot import DroidBot
from droidbot.plugins.screen_capture_plugin import ScreenCapturePlugin
from main import run_resize_analysis

FONT_SCALES = {
    "small_text": "0.85",
    "default": "1.0",
    "large_text": "1.3"
}

def find_xml_by_index(path_dir, index):
    pattern = os.path.join(path_dir, f"ui_dump_*_{index}.xml")
    matches = glob.glob(pattern)
    return matches[0] if matches else None

def find_default_image(path_dir, index):
    pattern = os.path.join(path_dir, f"screen_*_{index}.png")
    matches = glob.glob(pattern)
    return matches[0] if matches else None

def set_font_scale(serial, scale):
    subprocess.run(["adb", "-s", serial, "shell", "settings", "put", "system", "font_scale", scale], check=True)
    print(f"[INFO] Escala de fonte ajustada para {scale}")

def create_folders(*paths):
    for path in paths:
        os.makedirs(path, exist_ok=True)

def run_droidbot(apk_path, serial, output_dir):
    plugin = ScreenCapturePlugin(output_dir, serial)
    bot = DroidBot(
        app_path=apk_path,
        device_serial=serial,
        is_emulator=False,
        output_dir=output_dir,
        timeout=60,
        policy_name="dfs_greedy",
        event_interval=1,
        event_count=100,
        grant_perm=True,
        plugins=[plugin]
    )
    bot.start()

def run_pipeline():
    apk_path = input("📦 Caminho completo do APK: ").strip('"')
    serial = input("🔌 Serial do dispositivo (adb devices): ").strip()
    app_name = os.path.splitext(os.path.basename(apk_path))[0]

    base_output = f"output_{app_name}"
    results_dir = os.path.join(base_output, "results")
    create_folders(results_dir)

    # 1. Executa DroidBot para cada tipo de fonte
    for font_type, scale in FONT_SCALES.items():
        print(f"\n🔍 Executando DroidBot com fonte '{font_type}'...")
        set_font_scale(serial, scale)
        output_dir = os.path.join(base_output, font_type)
        create_folders(output_dir)
        run_droidbot(apk_path, serial, output_dir)

    print("\n✅ Execução do DroidBot finalizada.")

    # 2. Assume que capturas possuem mesmos índices (screen_001, etc.)
    print("\n🧠 Iniciando análise de Resize Text...")

    xml_dirs = {k: os.path.join(base_output, k, "xmls") for k in FONT_SCALES}
    output_files = os.listdir(xml_dirs["default"])
    output_files = [f for f in output_files if f.endswith(".xml")]

    for f in sorted(output_files):
        match = re.search(r'(\d{3})\.xml$', f)
        if not match:
            continue
        index = match.group(1)

        xml_paths = {}
        for font_type in FONT_SCALES:
            xml_dir = xml_dirs[font_type]
            found_xml = find_xml_by_index(xml_dir, index)
            if not found_xml:
                print(f"[WARNING] XML não encontrado para {font_type} - index {index}")
                break
            xml_paths[font_type] = found_xml

        if len(xml_paths) < 3:
            print(f"[WARNING] XMLs incompletos para index {index}, pulando.")
            continue

        # Encontrar imagem
        prints_dir = os.path.join(base_output, "default", "prints")
        default_img_path = find_default_image(prints_dir, index)
        marked_img_path = os.path.join(results_dir, "output_images", f"screen_marked_{index}.png")

        if default_img_path:
            result_path = os.path.join(results_dir, f"resize_text_{index}.json")
            run_resize_analysis(xml_paths, result_path, image_path=default_img_path, marked_image_path=marked_img_path)
        else:
            print(f"[WARNING] Imagem padrão não encontrada para index {index}")

    print(f"\n✅ Análise concluída! Resultados disponíveis em: {results_dir}")


if __name__ == "__main__":
    run_pipeline()
