# ocr-test\plugins\screen_capture_plugin.py
import os
import time
from droidbot.plugin import Plugin

class ScreenCapturePlugin(Plugin):
    def __init__(self, output_dir, device):
        super().__init__()
        self.output_dir = output_dir
        self.device = device
        self.counter = 0
        self.prints_dir = os.path.join(output_dir, "prints")
        self.xmls_dir = os.path.join(output_dir, "xmls")
        os.makedirs(self.prints_dir, exist_ok=True)
        os.makedirs(self.xmls_dir, exist_ok=True)

    def on_device_ready(self, device):
        self.device = device

    def after_event(self, event, state):
        self.counter += 1
        print(f"[PLUGIN] Capturando tela {self.counter} após evento: {event}")

        screen_filename = os.path.join(self.prints_dir, f"screen_{self.counter:03d}.png")
        xml_filename = os.path.join(self.xmls_dir, f"ui_dump_{self.counter:03d}.xml")

        # Aguarda a tela estabilizar
        time.sleep(1.5)

        # Captura XML diretamente com nome exclusivo
        self.device.adb.shell(f"uiautomator dump /sdcard/ui_dump_{self.counter:03d}.xml")
        self.device.adb.pull(f"/sdcard/ui_dump_{self.counter:03d}.xml", xml_filename)

        # Captura Screenshot com nome exclusivo
        self.device.adb.shell("screencap -p /sdcard/screen.png")
        self.device.adb.shell(f"cp /sdcard/screen.png /sdcard/screen_{self.counter:03d}.png")
        self.device.adb.pull(f"/sdcard/screen_{self.counter:03d}.png", screen_filename)

        print(f"[PLUGIN - plugins] Tela {self.counter} capturada com sucesso.")

    def on_finish(self):
        print("[PLUGIN] Plugin de captura finalizado.")
