import os
import csv
import subprocess
from droidbot import DroidBot
from droidbot.plugins.screen_capture_plugin import ScreenCapturePlugin
from check_contrast_batch_03 import analyze_contrast_for_app


def detect_device_serial():
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    lines = result.stdout.strip().splitlines()[1:]  # pula cabeçalho
    devices = [line.split()[0] for line in lines if "device" in line]
    if not devices:
        raise RuntimeError("Nenhum dispositivo conectado via ADB.")
    if len(devices) > 1:
        print(f"[⚠️] Vários dispositivos detectados, usando o primeiro: {devices[0]}")
    return devices[0]


def read_apk_paths_from_csv(csv_path):
    apk_paths = []
    with open(csv_path, newline='', encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if row and os.path.isfile(row[0]):
                apk_paths.append(row[0])
            else:
                print(f"[⚠️] APK inválido ignorado no CSV: {row}")
    return apk_paths


def run_droidbot(apk_path, serial, output_dir):
    print(f"📱 Executando DroidBot no dispositivo {serial} com APK: {apk_path}")
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
    print(f"✅ DroidBot finalizado. Resultados em: {output_dir}")


def main():
    csv_path = input("📄 Caminho do arquivo CSV com caminhos dos APKs: ").strip('"')
    apk_paths = read_apk_paths_from_csv(csv_path)

    if not apk_paths:
        print("❌ Nenhum APK válido encontrado.")
        return

    serial = detect_device_serial()

    for apk_path in apk_paths:
        app_name = os.path.splitext(os.path.basename(apk_path))[0]
        output_dir = os.path.join("output", app_name, "default")
        os.makedirs(output_dir, exist_ok=True)

        run_droidbot(apk_path, serial, output_dir)

        print(f"🔍 Iniciando verificação de contraste para: {app_name}")
        analyze_contrast_for_app(app_name, serial)


if __name__ == "__main__":
    main()
