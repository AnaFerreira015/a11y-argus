# a11y-argus

Dynamic accessibility analysis tool for Android applications. a11y-argus
automatically explores apps (via [DroidBot](https://github.com/AnaFerreira015/custom-droibot),
included as a submodule) and evaluates every visited screen against WCAG 2.2
success criteria, using the UI hierarchy (XML), screenshots, and OCR.

Exploration runs at three font scales (0.85, 1.0, and 1.3), enabling dynamic
checks such as text resizing (WCAG 1.4.4), in addition to contrast, touch
target size, alternative text, keyboard navigation, and others.

## Requirements and installation

The complete environment setup walkthrough (Python, JDK, Android SDK,
Tesseract OCR, emulator) is in [SETUP.md](SETUP.md).

Important: clone with submodules, otherwise the `droidbot/` folder comes empty:

```bash
git clone --recurse-submodules https://github.com/AnaFerreira015/a11y-argus.git
```

If you already cloned without the flag: `git submodule update --init --recursive`.

## Repository structure

```
a11y-argus/
├── apps/                      # evaluated APKs (not versioned; see below)
├── apks.csv                   # list of APKs to run (relative paths)
├── automate_accessibility.py  # pipeline: DroidBot (3 scales) + analysis
├── main.py                    # accessibility analysis of a single screen
├── accessibility_checker/     # detectors (contrast, target size, etc.)
├── replay_atf.py              # replays explorations with the atf-harness
│                              # (comparison with Accessibility Scanner/ATF)
├── tools/                     # replay and state diagnostics
├── droidbot/                  # submodule: DroidBot fork
└── docs/                      # contributor guides
```

APKs are not versioned. Project collaborators get access to the shared
**Execution Artifacts** folder on Google Drive, which contains a ready-to-use
`apps/` folder. See the [contributor guide](docs/CONTRIBUTOR_GUIDE.md).

## Running

With the emulator running and the APKs in `apps/`:

```bash
python automate_accessibility.py
```

For each APK in `apks.csv`, the pipeline runs the exploration at the three
font scales and produces the analysis in `output_dir_<apk_name>/results/`,
with one `result_<n>` per screen containing `errors.json` (findings) and
`output_images/` (screenshots with findings highlighted).

## Contributor documentation

- [Contributor guide](docs/CONTRIBUTOR_GUIDE.md): environment, Drive folder,
  Git workflow, and running the pipeline.
- [Manual evaluation protocol](docs/MANUAL_EVALUATION.md): how to validate
  the tool's findings and fill in the evaluation spreadsheet (TP/FP/FN).

## Contributing

Never commit directly to `main`. Create your own branch, keep it up to date
with `main`, and open a pull request. The detailed workflow, including the
special care required by the `droidbot/` submodule, is in the
[contributor guide](docs/CONTRIBUTOR_GUIDE.md).
