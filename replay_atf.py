#!/usr/bin/env python3
"""Replay das exploracoes do a11y-argus com o atf-harness ativo.

Para cada APK do apks.csv que ja tem output_dir_<apk>/default (a exploracao
original do argus), reproduz a mesma sequencia de eventos (UtgReplayPolicy)
com o AtfScanPlugin escaneando cada estado unico. Ao final, gera o
state_map_atf.json que liga cada result_N do argus ao JSON do ATF do mesmo
estado, pronto para o compare_argus_atf.py.

Uso:
    python replay_atf.py                # todos os APKs do apks.csv
    python replay_atf.py --apk <path>   # um APK especifico

Requisitos:
- Emulador ligado, MESMO AVD/densidade das capturas originais
- APKs do atf-harness instalados (installDebug installDebugAndroidTest)
- font_scale sera fixado em 1.0 (o comparativo usa apenas a escala default)
"""

import argparse
import csv
import json
import os
import subprocess
import threading
import time

from droidbot.droidbot import DroidBot
from droidbot.plugins.atf_scan_plugin import AtfScanPlugin, HARNESS_PKG

# Reaproveita os helpers do pipeline existente
from automate_accessibility import (
    get_package_name,
    get_connected_device_serial,
    estimate_timeout_by_apk_and_activities,
    countdown_and_stop,
    set_font_scale,
    wait_device_settled,
    ensure_device_language,
)

# Replay tende a ser mais lento que a captura original (cada evento espera
# o estado casar); margem sobre o timeout estimado da exploracao.
REPLAY_TIMEOUT_FACTOR = 1.5


def harness_installed(device_serial):
    out = subprocess.run(
        ["adb", "-s", device_serial, "shell", "pm", "list", "packages",
         HARNESS_PKG],
        capture_output=True, text=True).stdout
    return HARNESS_PKG in out


def load_recorded_structures(states_dir):
    """{state_str: structure_str} dos estados da captura original."""
    idx = {}
    if not os.path.isdir(states_dir):
        return idx
    for name in os.listdir(states_dir):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(states_dir, name), encoding="utf-8") as f:
                s = json.load(f)
            structure = s.get("state_str_content_free")
            if structure:  # arquivos antigos sem o campo nao sobrescrevem
                idx[s.get("state_str")] = structure
        except Exception:
            continue
    return idx


def load_live_scans(atf_dir, package_name=None):
    """{structure_str: [state_str_live, ...]} dos scans do replay, a partir
    dos .state.json salvos pelo plugin. Descarta scans cujo
    foreground_package nao e o app alvo (janela de corrida entre a captura
    de estado e o scan)."""
    live, foreign = {}, []
    if not os.path.isdir(atf_dir):
        return live, foreign
    for name in os.listdir(atf_dir):
        if not name.endswith(".state.json"):
            continue
        try:
            with open(os.path.join(atf_dir, name), encoding="utf-8") as f:
                s = json.load(f)
        except Exception:
            continue
        state_str = s.get("state_str")
        structure = s.get("state_str_content_free") or state_str
        scan_path = os.path.join(atf_dir, f"{state_str}.json")
        if not os.path.isfile(scan_path):
            continue
        if package_name:
            with open(scan_path, encoding="utf-8") as f:
                fg = json.load(f).get("foreground_package", "")
            if fg != package_name:
                foreign.append(state_str)
                continue
        live.setdefault(structure, []).append(state_str)
    return live, foreign


def generate_state_map(output_root, package_name=None):
    """Mapeia {state_str_do_scan_atf: result_N}. Tenta primeiro o match
    exato por state_str; quando a tela tem conteudo dinamico (state_str
    muda a cada execucao), casa pela estrutura (state_str_content_free),
    que e estavel entre execucoes."""
    results_dir = os.path.join(output_root, "results")
    atf_dir = os.path.join(output_root, "atf")
    if not os.path.isdir(results_dir):
        return None

    recorded = load_recorded_structures(
        os.path.join(output_root, "default", "states"))
    live, foreign = load_live_scans(atf_dir, package_name)

    state_map, missing, by_structure = {}, [], 0
    for entry in sorted(os.listdir(results_dir)):
        errors_path = os.path.join(results_dir, entry, "errors.json")
        if not os.path.isfile(errors_path):
            continue
        with open(errors_path, encoding="utf-8") as f:
            screen_id = json.load(f).get("screen_id")
        if not screen_id:
            continue

        # 1) match exato: o proprio state_str tem scan
        if os.path.isfile(os.path.join(atf_dir, f"{screen_id}.json")):
            state_map[screen_id] = entry
            continue

        # 2) fallback estrutural: mesmo layout, texto dinamico diferente
        structure = recorded.get(screen_id)
        candidates = live.get(structure, []) if structure else []
        if candidates:
            state_map[candidates.pop(0)] = entry
            by_structure += 1
        else:
            missing.append((entry, screen_id))

    map_path = os.path.join(output_root, "state_map_atf.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(state_map, f, indent=2)

    print(f"[REPLAY_ATF] state_map: {len(state_map)} estados casados "
          f"({by_structure} por estrutura), {len(missing)} sem scan ATF, "
          f"{len(foreign)} descartados (foreground fora do app) "
          f"-> {map_path}")
    for entry, sid in missing:
        print(f"[REPLAY_ATF]   sem correspondencia: {entry} ({sid[:12]}...)")
    return map_path


def replay_apk(apk_path, device_serial):
    apk_name = os.path.splitext(os.path.basename(apk_path))[0]
    output_root = f"output_dir_{apk_name}"
    default_dir = os.path.join(output_root, "default")
    events_dir = os.path.join(default_dir, "events")

    if not os.path.isdir(events_dir):
        print(f"[WARNING] {apk_name}: sem exploracao original em "
              f"{events_dir}, pulando.")
        return

    package_name = get_package_name(apk_path)

    atf_dir = os.path.join(output_root, "atf")
    if os.path.isdir(atf_dir) and any(
            f.endswith(".json") for f in os.listdir(atf_dir)):
        print(f"[INFO] {apk_name}: pasta atf ja tem scans. Pulando replay. "
              f"(apague {atf_dir} para reexecutar)")
        generate_state_map(output_root, package_name)
        return
    est_timeout, fw = estimate_timeout_by_apk_and_activities(apk_path)
    timeout_value = int(est_timeout * REPLAY_TIMEOUT_FACTOR)

    # Replay executa no maximo os eventos gravados; margem pequena para
    # eventos de setup que a policy injeta.
    event_count = len([f for f in os.listdir(events_dir)
                       if f.endswith(".json")]) + 10

    print(f"\n===== Replay ATF para {apk_name} "
          f"({event_count - 10} eventos gravados, timeout {timeout_value}s) =====")

    set_font_scale(device_serial, "1.0")
    time.sleep(3)
    if not wait_device_settled(device_serial):
        print("[WARNING] DroidBotIME nao registrou; tentando mesmo assim")

    replay_run_dir = os.path.join(output_root, "atf_replay_run")
    droidbot = DroidBot(
        app_path=apk_path,
        device_serial=device_serial,
        is_emulator=False,
        output_dir=replay_run_dir,
        timeout=timeout_value,
        policy_name="replay",
        replay_output=default_dir,
        grant_perm=True,
        event_interval=1,
        event_count=event_count,
        plugins=[AtfScanPlugin(output_root, target_package=package_name)],
    )
    finished = threading.Event()
    timer_thread = threading.Thread(target=countdown_and_stop,
                                    args=(droidbot, timeout_value, finished))
    timer_thread.daemon = True
    timer_thread.start()
    droidbot.start()
    finished.set()  # sinaliza o timer: terminou antes do teto

    generate_state_map(output_root, package_name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", default=None,
                        help="um APK especifico (default: todos do apks.csv)")
    parser.add_argument("--apks-csv", default="apks.csv")
    args = parser.parse_args()

    device_serial = get_connected_device_serial()
    if not device_serial:
        print("[FATAL] Nenhum dispositivo encontrado.")
        return

    if not ensure_device_language(device_serial, "en-US"):
        print("[FATAL] Device fora do locale do protocolo (en-US). "
              "O state_str depende dos textos da UI: replay em locale "
              "diferente das capturas nao casa os estados. Ajuste o idioma "
              "e rode novamente.")
        return

    if not harness_installed(device_serial):
        print("[FATAL] atf-harness nao instalado no device. Rode "
              "'gradlew installDebug installDebugAndroidTest' no projeto "
              "atf-harness antes.")
        return

    if args.apk:
        apk_paths = [args.apk]
    else:
        with open(args.apks_csv, encoding="utf-8") as f:
            apk_paths = [row[0].strip() for row in csv.reader(f) if row]

    for apk_path in apk_paths:
        if not os.path.exists(apk_path):
            print(f"[WARNING] APK nao encontrada: {apk_path}, pulando.")
            continue
        replay_apk(apk_path, device_serial)


if __name__ == "__main__":
    main()
