# Contributor guide

Welcome to the project! This guide covers everything you need to get started:
preparing the environment, obtaining the APKs, running the pipeline, and
contributing code. The manual evaluation part (spreadsheet, TP/FP/FN) has its
own document: [Manual evaluation protocol](MANUAL_EVALUATION.md).

If any question or error blocks you for more than 30 minutes, ask. Many
environment issues have been solved before and the answer may be one line.

## 1. Environment

Follow [SETUP.md](../SETUP.md) in order. It was validated step by step on
Windows and covers Python, JDK 17, Android Studio/SDK, Tesseract OCR, and the
emulator creation. Do not skip the PATH steps: most first-run errors come
from there.

When cloning, use the submodule flag (DroidBot lives inside this repository
as a Git submodule):

```bash
git clone --recurse-submodules https://github.com/AnaFerreira015/a11y-argus.git
```

If the `droidbot/` folder is empty, run `git submodule update --init --recursive`.

## 2. Shared Drive folder (Execution Artifacts)

You have been given access to the **Execution Artifacts** folder on Google
Drive. It contains:

| Item | What it is | What to do |
|---|---|---|
| `apps/` | The APKs of the current evaluation set | Download and place it in the **root of your cloned repository**, keeping the name `apps/` |
| `total_apps/` | Extra APKs, reserved for expanding the set | Do not use for now; it only comes into play if we agree to grow the set |
| `apks.local.csv` | Reference list with absolute paths from the original machine | Reference only; **do not use this file to run anything** |

The file the pipeline actually reads is the `apks.csv` **versioned in the
repository**, which uses relative paths (`apps/AppName.apk`). That is why the
`apps/` folder from Drive must sit exactly at the repository root: relative
paths resolve from there on any computer.

Quick check that everything is in place:

```bash
python -c "import csv,os; rows=[r[0] for r in csv.reader(open('apks.csv', encoding='utf-8-sig')) if r]; missing=[p for p in rows if not os.path.exists(p)]; print(f'{len(rows)} APKs listed, {len(missing)} missing'); [print('  missing:', p) for p in missing[:10]]"
```

If it prints "0 missing", you are ready to run.

## 3. Running the pipeline

With the emulator open (the same AVD described in SETUP.md) and the `apps/`
folder in place:

```bash
python automate_accessibility.py
```

What to expect:

- For each APK, DroidBot installs the app and explores it on its own
  **three times**, once per font scale (0.85, 1.0, 1.3). You will see the app
  opening and screens being navigated automatically; do not interact with the
  emulator during a run.
- After the three explorations, the accessibility analysis runs and produces
  the `output_dir_<apk_name>/` folder.
- The pipeline is **resumable**: if you interrupt it (Ctrl+C) or something
  fails, run it again; APKs with valid output are skipped. Failures are
  logged to `apks_falhas.csv`.

Output structure for each app:

```
output_dir_<apk_name>/
├── default/  small_text/  large_text/   # captures per font scale
│   ├── prints/   # screenshots per screen
│   ├── xmls/     # UI hierarchy per screen
│   └── states/   # DroidBot states
└── results/
    ├── result_0/
    │   ├── errors.json      # accessibility findings for the screen
    │   └── output_images/   # screenshots with findings highlighted
    ├── result_1/
    └── ...
```

The `results/` folders are the input for your manual evaluation; the
`errors.json` format and what to do with it are described in the
[evaluation protocol](MANUAL_EVALUATION.md).

## 4. Git workflow (important)

Project rules:

1. **Never commit to `main`**, neither in a11y-argus nor in custom-droibot.
2. All work happens on **your own branch**, with a descriptive name:
   `git checkout -b feat/short-name` or `fix/short-name`.
3. Contributions land through **pull requests targeting `main`**.
4. Before starting any work and before opening a PR, **update your local
   base**:

```bash
git checkout main
git pull origin main
git submodule update --init --recursive
git checkout your-branch
git merge main
```

5. Commit messages **in English**, with a short imperative title ("Fix X",
   "Add Y") and, when the change is not obvious, a context paragraph
   explaining the why.

### Special care: the droidbot submodule

`droidbot/` is a Git repository inside the repository. If you change anything
in there, the order matters:

1. Commit and **push your branch from inside `droidbot/` first**;
2. Only then, in a11y-argus, commit the submodule "bump" (the pointer to the
   new commit) on your branch there.

If you push only a11y-argus, the pointer will reference a commit that exists
only on your machine, and anyone else's clone breaks with
`fatal: remote error: upload-pack: not our ref`. A protection we recommend
configuring once:

```bash
git config --global push.recurseSubmodules check
```

With this, Git refuses to push the parent repository if the submodule has
unpublished commits.

Location detail: DroidBot's source code lives in `droidbot/droidbot/`
(repository/package). The plugins used by the pipeline are in
`droidbot/droidbot/plugins/`; there are stale copies in other paths that are
not imported by anything. When in doubt about which file is the "live" one,
check the import at the top of `automate_accessibility.py`.

## 5. Next step

With the environment running and at least one app processed end to end, move
on to the [Manual evaluation protocol](MANUAL_EVALUATION.md), which is where
the actual evaluation work happens.
