# Setting up and running a11y-argus (Windows)

A guide to configure and run **a11y-argus** from scratch on a Windows laptop using
PyCharm. The steps below were validated on a clean install (Windows + PyCharm +
Android Studio emulator).

a11y-argus uses **custom-droibot** (a DroidBot fork) as a **git submodule**, in the
`droidbot/` folder. These are not two independent projects: you set up a11y-argus
and custom-droibot comes along, in the same virtual environment. The flow is:
droidbot explores the app on the device and captures screens (screenshot + UI dump
\+ state), and argus analyzes those captures against accessibility criteria (WCAG),
including comparing font scales.

---

## 1. Software to install (with versions)

| Software | Version | Notes |
|---|---|---|
| Python | **3.12** (any 3.12.x) | 3.11 also works. Do not use 3.13 (risk of missing wheels) or 3.10 and earlier (`ipython~=9.0.2` requires Python 3.11+). Check "Add python.exe to PATH" in the installer. |
| Git for Windows | latest | Required to clone with the submodule. |
| PyCharm | Community | Sufficient. |
| JDK | **17** (Temurin/Adoptium) | 11 also works, but 17 is the recommended LTS. |
| Android Studio | latest | Used for the SDK (adb, build-tools) and the emulator. |
| Tesseract OCR | 5.x (UB Mannheim build) | Install with the **Portuguese** language pack. See the hardcoded-path note below. |

### Note: on Windows, only the `.exe` Python installer works
Download the **Windows installer (64-bit)** from python.org
(`python-3.12.x-amd64.exe`). The `.tgz` file is source code for Linux and does not
work here.

### Note: the Tesseract path is hardcoded in the code
`accessibility_checker/ocr.py` points Tesseract to the default path:

```python
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

So install Tesseract at the **default** path (`C:\Program Files\Tesseract-OCR`).
If you install it elsewhere, update that line.

### Note: the SDK path must have no spaces
When installing Android Studio, set the **Android SDK Location** with no spaces,
e.g. `C:\Android\Sdk`. The default path under `C:\Users\<your name>\...` may contain
a space (in the username), which breaks the NDK tools.

---

## 2. Environment variables

Configure under "Edit the system environment variables" → "Environment Variables".
After any change, open a **new** terminal (and restart PyCharm so its embedded
terminal picks up the updated PATH).

**JAVA_HOME** (new system variable), pointing to the JDK root, e.g.:

```
C:\Program Files\Eclipse Adoptium\jdk-17.0.18
```

**Add to PATH** (system `Path` variable):

```
%JAVA_HOME%\bin
C:\Android\Sdk\platform-tools
C:\Android\Sdk\build-tools\<version>
C:\Program Files\Tesseract-OCR
```

Notes:
- `platform-tools` provides **adb**.
- `build-tools\<version>` provides **aapt** (e.g. `C:\Android\Sdk\build-tools\35.0.0`;
  use the latest version subfolder available). `aapt` is **not** in `platform-tools`.
  It is mandatory: the pipeline uses `aapt dump badging` to get each APK's package
  name. Without aapt on PATH, APKs are silently skipped.

### Verification

Open a new terminal and check:

```
python --version      # Python 3.12.x
java --version        # 17.0.x
adb --version
aapt version
tesseract --version
tesseract --list-langs # should list 'por' and 'eng'
```

In CMD use `echo %JAVA_HOME%`; in PowerShell use `echo $env:JAVA_HOME`.

---

## 3. Clone the project (with the submodule)

custom-droibot is a submodule. Clone with `--recurse-submodules`:

```
git clone --recurse-submodules https://github.com/AnaFerreira015/a11y-argus.git
```

If you already cloned without the submodule (empty `droidbot/` folder):

```
cd a11y-argus
git submodule update --init --recursive
```

Confirm that `a11y-argus/droidbot/setup.py` exists.

---

## 4. Python environment (venv) in PyCharm

1. **Open** the `a11y-argus` folder in PyCharm.
2. Settings → Project → Python Interpreter → Add Interpreter → Add Local →
   **Virtualenv** → Base interpreter = **Python 3.12** → OK. This creates `.venv`.
3. Open PyCharm's embedded terminal (shows `(.venv)` in the prompt).

### Install dependencies

```
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e ./droidbot --config-settings editable_mode=compat
```

Notes:
- `requirements.txt` already ships with the `droidbot~=1.0.2b4` and `pip~=23.2.1`
  lines **commented out**. droidbot does not exist at that version on PyPI (it comes
  from the submodule), and the pip pin broke the install. Do not uncomment them.
- `--config-settings editable_mode=compat` is required. Without it, the `droidbot`
  command fails with `ModuleNotFoundError: No module named 'start'`, because modern
  setuptools, in the default editable mode, does not expose droidbot's root-level
  `start.py`.

### Python environment check

```
python -c "import cv2, numpy, pandas, sklearn, frida, pytesseract; print('ok')"
droidbot -h
```

The first should print `ok`. `droidbot -h` should show the help with its options.
The several `SyntaxWarning: invalid escape sequence` lines printed before the help
are harmless (regex without an `r` prefix on Python 3.12) and do not prevent
execution.

---

## 5. Emulator (AVD)

In Android Studio: Device Manager → Create Device.

- **Device:** Pixel 8 (avoid "Resizable (Experimental)").
- **System image:** API **34** ("UpsideDownCake", Android 14), ABI **x86_64**,
  Services **Google APIs**.

Important: use **Google APIs**, **not** "Google Play". frida-server needs to run as
root, and "Google Play" images block `adb root`. "Google APIs" images allow root with
no hacks. Download the image (download icon) before finishing.

Start the emulator and confirm:

```
adb devices
adb shell getprop sys.boot_completed   # should return 1
```

If the emulator hangs on the Google logo on first boot, wait a few minutes; if it
persists, use "Wipe Data" from the AVD menu (clears the saved state). Note that wipe
data also removes frida-server, so you will need to push it again (section 6).

---

## 6. frida-server (on the device)

The frida-server version **must match exactly** the `frida` package version in the
venv (a version mismatch is the most common cause of instrumentation failure).

1. Find the installed version:

```
python -c "import frida; print(frida.__version__)"
```

2. Download the matching frida-server (example for 16.6.6):

```
https://github.com/frida/frida/releases/download/16.6.6/frida-server-16.6.6-android-x86_64.xz
```

3. Decompress with Python (produces a `frida-server` file, no extension):

```
python -c "import lzma,shutil; shutil.copyfileobj(lzma.open('frida-server-16.6.6-android-x86_64.xz'), open('frida-server','wb'))"
```

4. Push as root and run:

```
adb root
adb push frida-server /data/local/tmp/
adb shell chmod 755 /data/local/tmp/frida-server
adb shell "/data/local/tmp/frida-server &"
```

5. Confirm it is running:

```
adb shell pidof frida-server   # should return a number (PID)
```

frida-server is **not persistent**: it dies when the emulator restarts. Before each
session, restart it with `adb root` and the command from step 4 (the binary is
already in `/data/local/tmp`, so you do not need to download or decompress it again).

---

## 7. Per-session checklist

Before each run, make sure:

1. Emulator is up: `adb devices` lists the device as `device`.
2. frida-server is running: `adb shell pidof frida-server` returns a number.
   If not, restart it (section 6, step 4).
3. venv is active in PyCharm's terminal (`(.venv)` in the prompt).

---

## 8. Running

### Minimal test (validates the environment, capture only)

Runs droidbot alone on a simple APK, without the argus analysis. Use quotes if the
path contains spaces:

```
droidbot -a "C:\Projects\a11y-argus\apps\<app>.apk" -o test_output -count 10 -is_emulator -grant_perm
```

Success = the app is installed, droidbot interacts with the screen, and the
`test_output` folder is generated with states, prints, and the UTG (`index.html` +
`utg.js`).

### Full pipeline (capture across font scales + analysis)

1. Edit `apks.csv` with one absolute APK path per line, for example:

```
C:\Projects\a11y-argus\apps\App One.apk
C:\Projects\a11y-argus\apps\App Two.apk
```

2. Run:

```
python automate_accessibility.py
```

For each APK, the pipeline runs droidbot at three font scales (`small_text`,
`default`, `large_text`), captures everything, and analyzes it. Output goes to
`output_dir_<apk_name>/results/result_N`, one subfolder per analyzed screen.

Notes:
- If an `output_dir_<apk>` folder already exists with valid capture, the pipeline
  skips droidbot and redoes only the analysis (fast).
- At the end, the emulator font may stay large (the loop ends on `large_text` and
  does not reset). This is cosmetic. To restore it:
  `adb shell settings put system font_scale 1.0`.

---

## 9. Known pitfalls (troubleshooting)

- **APKs skipped with no clear error:** almost always `aapt` not on PATH. The
  pipeline uses `aapt dump badging` for the package name; without aapt the APK is
  ignored. Check with `aapt version`.

- **`droidbot: error: unrecognized arguments`:** an APK path with spaces and no
  quotes on the droidbot command line. Wrap the whole path in quotes. (In the
  `automate_accessibility.py` pipeline this is not an issue: it uses `subprocess`
  with an argument list, which handles spaces correctly.)

- **`ModuleNotFoundError: No module named 'start'` when running droidbot:** reinstall
  with `pip install -e ./droidbot --config-settings editable_mode=compat`.

- **`cv2.error ... !_src.empty() in function 'cv::cvtColor'`:** an empty image crop
  reaching OCR (inverted or off-screen bounds, common at the `large_text` scale).
  Already handled in `get_ocr_info_instances` (bounds clamping and discarding of
  degenerate crops).

- **A PATH command "not recognized" only in PyCharm's terminal:** the terminal
  inherited the old PATH. Close and reopen the terminal; if it persists, restart
  PyCharm entirely.

- **PowerShell vs CMD:** to read variables, PowerShell uses `$env:NAME`, CMD uses
  `%NAME%`. The `python`, `git`, `pip`, `adb`, `aapt` commands work the same in both.

- **`adb root` refused:** the emulator image is "Google Play". Create an AVD with a
  "Google APIs" image.

---

## Validated versions summary

- Python 3.12
- JDK 17 (Temurin)
- Android SDK at `C:\Android\Sdk` (platform-tools + build-tools on PATH)
- Tesseract 5.x (UB Mannheim) at `C:\Program Files\Tesseract-OCR`, with the `por` language
- Emulator: Pixel 8, API 34, x86_64, Google APIs
- frida (pip) and frida-server at the same version (e.g. 16.6.6)
