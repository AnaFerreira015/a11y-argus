import os
import sys
import threading
import time
import json
import shutil
import subprocess
import csv
from colorama import Fore, Style

# adiciona o droidbot (submódulo) ao PYTHONPATH
sys.path.append(os.path.join(os.path.dirname(__file__), 'droidbot'))

from droidbot.droidbot import DroidBot
from droidbot.plugins.screen_capture_plugin import ScreenCapturePlugin

import main as argus_main

font_scales = {
    "small_text": "0.85",
    "default": "1.0",
    "large_text": "1.3"
}

DROIDBOT_IME = "io.github.ylimit.droidbotapp/.DroidBotIME"

def get_device_locale(device_serial):
    for cmd in (["getprop", "persist.sys.locale"],
                ["settings", "get", "system", "system_locales"]):
        out = subprocess.run(["adb", "-s", device_serial, "shell"] + cmd,
                             capture_output=True, text=True).stdout.strip()
        if out and out != "null":
            return out
    return ""


def ensure_device_language(device_serial, locale="en-US"):
    """Garante que o device esta no locale do protocolo experimental.
    O state_str do DroidBot depende dos textos da UI, entao capturas e
    replays precisam compartilhar o mesmo idioma. Tenta ajustar via root
    (imagens AOSP/Google APIs); em imagens com Play Store, orienta o
    ajuste manual."""
    current = get_device_locale(device_serial)
    if current.replace("_", "-").lower().startswith(locale.lower()):
        return True

    print(f"[INFO] Locale atual '{current}', ajustando para {locale}...")
    subprocess.run(["adb", "-s", device_serial, "root"],
                   capture_output=True, text=True)
    r = subprocess.run(
        ["adb", "-s", device_serial, "shell",
         f"setprop persist.sys.locale {locale}"],
        capture_output=True, text=True)
    if r.returncode != 0 or "not allowed" in (r.stderr or "").lower():
        print(f"[ERRO] Sem acesso root para ajustar o locale (imagem com "
              f"Play Store?). Ajuste manualmente: Settings > System > "
              f"Languages > English (United States), e rode novamente.")
        return False

    subprocess.run(["adb", "-s", device_serial, "reboot"])
    subprocess.run(["adb", "-s", device_serial, "wait-for-device"],
                   timeout=180)
    deadline = time.time() + 180
    while time.time() < deadline:
        boot = subprocess.run(
            ["adb", "-s", device_serial, "shell", "getprop",
             "sys.boot_completed"],
            capture_output=True, text=True).stdout.strip()
        if boot == "1":
            break
        time.sleep(3)

    current = get_device_locale(device_serial)
    return current.replace("_", "-").lower().startswith(locale.lower())

def wait_device_settled(device_serial, timeout=60):
    """Espera o sistema reindexar o IME do companion apos a configuration
    change do font_scale. Se o companion nao esta instalado (primeira run),
    nao ha o que esperar: o proprio droidbot o instala no connect."""
    pkgs = subprocess.run(
        ["adb", "-s", device_serial, "shell", "pm", "list", "packages",
         "io.github.ylimit.droidbotapp"],
        capture_output=True, text=True).stdout
    if "io.github.ylimit.droidbotapp" not in pkgs:
        return True
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = subprocess.run(
            ["adb", "-s", device_serial, "shell", "ime", "list", "-a", "-s"],
            capture_output=True, text=True).stdout
        if DROIDBOT_IME in out:
            return True
        time.sleep(2)
    return False

def get_number_of_permissions(apk_path):
    try:
        result = subprocess.run([
            "aapt", "dump", "permissions", apk_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return len([line for line in result.stdout.splitlines() if "uses-permission" in line])
    except Exception as e:
        print(f"[WARNING] Falha ao contar permissões: {e}")
        return 0

def count_activities_in_apk(apk_path):
    try:
        result = subprocess.run([
            "aapt", "dump", "xmltree", apk_path, "AndroidManifest.xml"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        return len([line for line in result.stdout.splitlines() if 'E: activity' in line])
    except Exception as e:
        print(f"[WARNING] Falha ao contar activities: {e}")
        return 1

def estimate_timeout_by_apk_and_activities(apk_path):
    perms = get_number_of_permissions(apk_path)
    acts = count_activities_in_apk(apk_path)

    base_timeout = 60
    # base_timeout = 300
    timeout = base_timeout + (perms * 5) + (acts * 10)
    timeout = min(timeout, 600)
    print(f"[INFO] Timeout estimado: {timeout}s ({perms} permissões, {acts} activities)")
    return timeout

def get_screen_files(screen_id, output_root, font_type):
    """
    Retorna os caminhos da imagem e do XML do screen_id NA ESCALA PEDIDA.
    O state_str nao inclui bounds, entao a mesma tela tem o mesmo id nas
    tres escalas; buscar em ordem fixa retornava sempre os arquivos do
    default para qualquer escala.
    """
    prints_dir = os.path.join(output_root, font_type, "prints")
    xmls_dir = os.path.join(output_root, font_type, "xmls")

    screenshot_path = os.path.join(prints_dir, f"screen_{font_type}_{screen_id}.png")
    xml_path = os.path.join(xmls_dir, f"ui_dump_{font_type}_{screen_id}.xml")

    if os.path.exists(screenshot_path) and os.path.exists(xml_path):
        return {
            "font_type": font_type,
            "screenshot": screenshot_path,
            "xml": xml_path
        }
    return None

def countdown_and_stop(droidbot_instance, timeout, finished_event=None):
    for remaining in range(timeout, 0, -1):
        if finished_event is not None and finished_event.is_set():
            return  # droidbot terminou antes do teto; timer se encerra
        mins, secs = divmod(remaining, 60)
        color = Fore.GREEN if remaining > 180 else Fore.YELLOW if remaining > 60 else Fore.RED
        print(f"{color}Tempo restante: {mins:02d} min {secs:02d} seg{Style.RESET_ALL}")
        time.sleep(1)
    print(f"\n{Fore.RED}Tempo limite atingido, encerrando DroidBot...{Style.RESET_ALL}")
    droidbot_instance.stop()

def create_folders(*folders):
    for folder in folders:
        os.makedirs(folder, exist_ok=True)

def set_font_scale(device_serial, scale):
    subprocess.run(["adb", "-s", device_serial, "shell", "settings", "put", "system", "font_scale", scale], check=True)
    print(f"[INFO] Tamanho da fonte alterado para {scale} no dispositivo {device_serial}")

def get_screen_id_from_state_json(state_json_path):
    if not os.path.exists(state_json_path):
        print(f"[WARNING] Arquivo de estado não encontrado: {state_json_path}")
        return None
    with open(state_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("state_str")

def state_belongs_to_app(state_json_path, package_name):
    """Le o foreground_activity do state JSON (funciona tanto para os
    arquivos do core quanto para os do ScreenCapturePlugin, ambos gravam
    o campo)."""
    if not package_name:
        return True
    try:
        with open(state_json_path, encoding="utf-8") as f:
            fg = json.load(f).get("foreground_activity") or ""
        return package_name in fg
    except Exception:
        return False

def is_app_screen(state_json_path, expected_package):
    if not os.path.exists(state_json_path):
        return False
    with open(state_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    foreground_activity = data.get("foreground_activity", "")
    return expected_package in foreground_activity

def get_sorted_states(states_dir):
    state_files = [f for f in os.listdir(states_dir) if f.startswith("state_") and f.endswith(".json")]
    state_files.sort()
    return state_files

def save_errors_with_screen_id(errors, result_dir, screen_id):
    output_data = {"screen_id": screen_id, "errors": errors}
    os.makedirs(result_dir, exist_ok=True)
    output_file = os.path.join(result_dir, "errors.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
    print(f"[INFO] Arquivo de erros salvo em {output_file} com ID da tela: {screen_id}")

def run_argus_analysis(image_paths, xml_paths, state_json_path, result_dir):
    print(f"[INFO] Executando análise Argus-a11y para {image_paths['default']} (com múltiplos tamanhos de fonte)")
    screen_id = get_screen_id_from_state_json(state_json_path)
    errors = argus_main.main(
        image_paths=image_paths,
        xml_paths=xml_paths,
        result_dir=result_dir,
        screen_id=screen_id,
        return_errors=True
    )
    if errors:
        save_errors_with_screen_id(errors, result_dir, screen_id)
    print(f"[INFO] Argus-a11y finalizado para {result_dir}")

def run_droidbot(apk_path, device_serial, output_dir, font_type, timeout_value, package_name):
    droidbot = DroidBot(
        app_path=apk_path,
        device_serial=device_serial,
        is_emulator=False,
        output_dir=output_dir,
        timeout=timeout_value,
        policy_name="dfs_greedy",
        grant_perm=True,
        event_interval=1,
        event_count=100,
        plugins=[ScreenCapturePlugin(output_dir, font_type, target_package=package_name)]
    )
    finished = threading.Event()
    timer_thread = threading.Thread(target=countdown_and_stop,
                                    args=(droidbot, timeout_value, finished))
    timer_thread.daemon = True
    timer_thread.start()
    droidbot.start()
    finished.set()


def get_connected_device_serial():
    try:
        result = subprocess.run(["adb", "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        lines = result.stdout.strip().split("\n")[1:]
        devices = [line.split()[0] for line in lines if "device" in line and not any(x in line for x in ["unauthorized", "offline"])]
        if not devices:
            print("[ERRO] Nenhum dispositivo ADB autorizado foi encontrado.")
            return None
        return devices[0]
    except Exception as e:
        print(f"[ERRO] Falha ao obter dispositivos conectados: {e}")
        return None

def extract_foreground_activity(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("foreground_activity")

def build_state_map_by_index(output_root, package_name=None):
    """
    Gera um state_map confiável, com base na ordem dos arquivos capturados por fonte.
    Garante que os screen_ids (state_str) não se repitam para evitar associações incorretas.
    Estados fora do app alvo são excluídos ANTES do pareamento por índice,
    senão uma captura de launcher presente em só uma das escalas desloca
    os índices e desalinha o pareamento dali em diante.
    """

    state_dirs = {k: os.path.join(output_root, k, "states") for k in font_scales}
    state_files = {
        k: sorted([
            f for f in os.listdir(state_dirs[k])
            if f.endswith(".json")
            and state_belongs_to_app(os.path.join(state_dirs[k], f), package_name)
        ]) for k in font_scales
    }

    min_len = min(len(files) for files in state_files.values())
    print(f"[INFO] Gerando state_map com base em {min_len} capturas por fonte.")

    used_ids = set()
    state_map = []

    for i in range(min_len):
        entry = {"index": i}
        duplicate = False

        for font_type in font_scales:
            path = os.path.join(state_dirs[font_type], state_files[font_type][i])
            state_id = get_screen_id_from_state_json(path)

            if state_id in used_ids:
                duplicate = True
                break

            entry[font_type] = state_id

        if not duplicate:
            state_map.append(entry)
            for font_type in font_scales:
                used_ids.add(entry[font_type])
        else:
            print(f"[INFO] Ignorando index {i} por repetição de tela.")

    map_path = os.path.join(output_root, "state_map.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(state_map, f, indent=4, ensure_ascii=False)

    print(f"[INFO] state_map final gerado com {len(state_map)} telas únicas.")
    return state_map

def find_state_file_by_id(state_dir, state_id):
    for fname in os.listdir(state_dir):
        if fname.endswith(".json"):
            path = os.path.join(state_dir, fname)
            if get_screen_id_from_state_json(path) == state_id:
                return path
    return None

def clean_output_dir(path):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)

def get_package_name(apk_path):
    try:
        result = subprocess.run(["aapt", "dump", "badging", apk_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in result.stdout.splitlines():
            if line.startswith("package:"):
                parts = line.split("'")
                if len(parts) >= 2:
                    return parts[1]
    except Exception as e:
        print(f"[ERRO] Não foi possível extrair o package name: {e}")
    return None

def has_valid_droidbot_output(output_root):
    for font_type in font_scales:
        font_dir = os.path.join(output_root, font_type)
        states_dir = os.path.join(font_dir, "states")
        prints_dir = os.path.join(font_dir, "prints")
        xmls_dir = os.path.join(font_dir, "xmls")

        if not all(os.path.exists(d) for d in [states_dir, prints_dir, xmls_dir]):
            return False

        has_json = any(f.endswith(".json") for f in os.listdir(states_dir)) if os.path.exists(states_dir) else False
        has_png = any(f.endswith(".png") for f in os.listdir(prints_dir)) if os.path.exists(prints_dir) else False
        has_xml = any(f.endswith(".xml") for f in os.listdir(xmls_dir)) if os.path.exists(xmls_dir) else False

        if not (has_json and has_png and has_xml):
            return False

    return True

def run_pipeline():
    print("==== Pipeline DroidBot + Argus-a11y ====")

    apks_csv_path = "apks.csv"

    with open(apks_csv_path, "r", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        apk_paths = [row[0].strip() for row in reader if row]

    for apk_path in apk_paths:
        if not os.path.exists(apk_path):
            print(f"[WARNING] APK não encontrada: {apk_path}, pulando.")
            continue

        apk_name = os.path.splitext(os.path.basename(apk_path))[0]
        output_root = f"output_dir_{apk_name}"
        results_dir = os.path.join(output_root, "results")

        package_name = get_package_name(apk_path)
        if not package_name:
            print(f"[WARNING] Não foi possível extrair o package name do APK: {apk_path}, pulando.")
            continue

        if not has_valid_droidbot_output(output_root):
            device_serial = get_connected_device_serial()
            if not device_serial:
                print("[FATAL] Nenhum dispositivo válido encontrado. Conecte um dispositivo e tente novamente.")
                continue

            print(f"[INFO] Dispositivo detectado: {device_serial}")
            if not ensure_device_language(device_serial, "en-US"):
                print("[FATAL] Nao foi possivel garantir o locale en-US. Abortando este APK.")
                continue
            timeout_value = estimate_timeout_by_apk_and_activities(apk_path)

            try:
                for font_type, scale in font_scales.items():
                    print(f"\n===== Executando DroidBot com fonte '{font_type}' (escala {scale}) para {apk_name} =====")
                    set_font_scale(device_serial, scale)
                    time.sleep(3)

                    if not wait_device_settled(device_serial):
                        print(f"[WARNING] DroidBotIME nao registrou apos mudanca de escala; "
                              f"tentando mesmo assim para '{font_type}'")

                    output_dir = os.path.join(output_root, font_type)
                    clean_output_dir(output_dir)
                    run_droidbot(apk_path, device_serial, output_dir, font_type, timeout_value, package_name)
            except Exception as e:
                print(f"[ERRO] Falha na captura de {apk_name}: {e}")
                with open("apks_falhas.csv", "a", encoding="utf-8") as f:
                    f.write(f"{apk_path},{e}\n")
                continue
        else:
            print(f"[INFO] Pasta {output_root} já existe. Pulando execução do DroidBot.")

        if os.path.exists(results_dir):
            print(f"[INFO] Removendo pasta de resultados antiga: {results_dir}")
            shutil.rmtree(results_dir)
        os.makedirs(results_dir, exist_ok=True)

        print(f"\n[INFO] Captura finalizada para {apk_name}. Iniciando análise...")

        prints_dirs = {k: os.path.join(output_root, k, "prints") for k in font_scales}
        xmls_dirs = {k: os.path.join(output_root, k, "xmls") for k in font_scales}
        states_dir = os.path.join(output_root, "default", "states")

        if not os.path.exists(prints_dirs["default"]):
            print(f"[WARNING] Diretório de prints não encontrado: {prints_dirs['default']}")
            continue

        state_map = build_state_map_by_index(output_root, package_name)

        has_results = False

        for entry in state_map:
            index = entry["index"]
            state_id_default = entry["default"]
            state_json_path = find_state_file_by_id(os.path.join(output_root, "default", "states"), state_id_default)

            if not state_json_path:
                print(f"[WARNING] Não foi possível localizar o state JSON para index {index}")
                continue

            if not is_app_screen(state_json_path, package_name):
                print(f"[INFO] Ignorando index {index} — foreground fora do app ({package_name})")
                continue

            image_paths = {}
            xml_paths = {}

            for font_type in font_scales:
                screen_id = entry[font_type]
                files = get_screen_files(screen_id, output_root, font_type)
                if not files:
                    print(f"[WARNING] Arquivos não encontrados para screen_id {screen_id} ({font_type})")
                    continue
                image_paths[font_type] = files["screenshot"]
                xml_paths[font_type] = files["xml"]

            if len(image_paths) < len(font_scales) or len(xml_paths) < len(font_scales):
                print(f"[WARNING] Arquivos faltando para index {index}, pulando.")
                continue

            result_path = os.path.join(results_dir, f"result_{index}")
            run_argus_analysis(image_paths, xml_paths, state_json_path, result_path)
            print(f"[OK] Resultado salvo para index {index} na pasta {result_path}")
            has_results = True

        if not has_results:
            print(f"[INFO] Nenhum resultado válido para {apk_name}. Removendo pasta {output_root}")
            shutil.rmtree(output_root, ignore_errors=True)

if __name__ == "__main__":
    run_pipeline()