# Manual evaluation protocol

This document explains how to manually validate a11y-argus findings and fill
in the evaluation spreadsheet. Read the concepts section before starting: it
defines the vocabulary the spreadsheet uses.

## 1. What we are measuring (and why)

a11y-argus reports *findings*: potential accessibility failures on app
screens. Like any automated tool, it can be right, it can flag something that
is not a real failure, or it can miss a real failure. The manual evaluation
exists to measure exactly that, by comparing what the tool said with what a
human evaluator confirms by looking at the screen.

Each evaluated finding receives a classification:

| Classification | Meaning | In one sentence |
|---|---|---|
| **True Positive (TP)** | Correct detection | The tool flagged a failure, and the failure **really exists**. A hit. |
| **False Positive (FP)** | False alarm | The tool flagged a failure, but on inspection it is **not a real failure**. |
| **False Negative (FN)** | Missed failure | A real failure exists on the screen, but the tool **did not flag it**. |

An analogy: think of a smoke detector. It beeps during a fire (TP: it beeped
and there was fire). It beeps because of shower steam (FP: it beeped with no
fire). A fire starts and it stays silent (FN: there was fire and it did not
beep). The fourth case, silence with no fire, is normal behavior and does not
go into the spreadsheet: we only record rows where the tool flagged something
**or** where a real failure exists.

Why all three matter: from TP and FP we compute the tool's **precision** (of
the things it flags, how many are real?); from TP and FN we compute **recall**
(of the real failures, how many does it find?). These are the two central
metrics of the evaluation.

## 2. Where the data is

For each processed app there is a folder `output_dir_<apk_name>/results/`
with one `result_<n>` subfolder per evaluated screen. Inside each:

- **`errors.json`**: the tool's findings for that screen. The `screen_id`
  field at the top identifies the screen; each item in the `errors` list is a
  finding, with `type` (failure type), the element's `bounds` (position as
  `[left, top, right, bottom]` in pixels), and fields that help locate the
  element (`element`, `resource_id`, `phrase`, `text`, depending on the type).
- **`output_images/`**: screenshots of the screen with the findings
  **visually highlighted**. This is your main reference for locating each
  finding.

The "clean" screenshots of each screen also exist in
`output_dir_<apk>/default/prints/`, useful when a highlight covers the
element.

## 3. The spreadsheet, column by column

| Column | What to fill in |
|---|---|
| **Application** | The **exact** APK file name, without the extension. E.g., for `apps/SAD_Mobile_18.3_APKPure.apk`, fill in `SAD_Mobile_18.3_APKPure`. Copy it from the `output_dir_<name>` folder name, never type it from memory. |
| **Screen (screen_id)** | The value of the `screen_id` field in that screen's `errors.json`. It is a long code (e.g., `ff5076c8de0e...`); copy and paste it whole. |
| **Failure Type** | The **exact** value of the finding's `type` field, copied from `errors.json`. E.g., `Contrast Failure`, `Target Size Failure (Minimum)`, `Missing Content Description`, `Resize Text - insufficient increase`. Do not translate or abbreviate. For FN rows (failures the tool missed), use the type the tool **would have used** for that failure, from the same list. |
| **Component** | Which element on the screen has the failure, in the most identifiable way possible: the `resource_id` when it exists (e.g., `al.boapps.sadmobile:id/serial_num`), otherwise the element's text (e.g., "HYRJE" button), otherwise a short, unambiguous description (e.g., "gear icon at the top right corner"). |
| **Argus Detected?** | `Yes` if the finding came from the tool (it is in `errors.json` and highlighted in the image). `No` only on FN rows, i.e., failures that **you** found and the tool did not report. |
| **Argus Finding Confirmed?** | `Yes` if, looking at the screen, the failure **really exists**; `No` if the flag does not hold up. On FN rows, it is always `Yes` (you only create the row because you confirmed a real failure). |
| **Argus Classification** | Derived from the two previous columns, per the table below. |

The classification is mechanical from the two Yes/No columns:

| Argus Detected? | Argus Finding Confirmed? | Argus Classification |
|---|---|---|
| Yes | Yes | TP |
| Yes | No | FP |
| No | Yes | FN |
| No | No | (does not become a row in the spreadsheet) |

## 4. Step by step per screen

For each `result_<n>` of an app:

1. Open `errors.json` and copy the `screen_id`.
2. Open the images in `output_images/` side by side with `errors.json`.
3. **For each finding** in the `errors` list, create a row in the
   spreadsheet: fill in Application, Screen, Failure Type, and Component;
   mark `Argus Detected? = Yes`.
4. Evaluate the finding: does the flagged problem actually exist? Use the
   criteria in section 5. Fill in `Argus Finding Confirmed?` and the
   classification (TP or FP).
5. After covering all the tool's findings, do **your own sweep** of the
   screen (use the clean print from `default/prints/`): look for failures of
   the same types the tool evaluates that are **not** in `errors.json`. Each
   one becomes an FN row (`Argus Detected? = No`,
   `Argus Finding Confirmed? = Yes`).
6. When genuinely in doubt about any finding, do not guess: mark the row
   with a cell comment and bring it to me. Interpretation disagreements are
   expected and discussing them is part of the method.

## 5. Confirmation criteria per failure type

Quick reference of what to verify for each type. When the criterion involves
a measurement (contrast, size), the finding's own message in `errors.json`
carries the numbers the tool computed; your task is to check that they make
sense for the right element, not to recompute everything.

- **Contrast Failure** (WCAG 1.4.3): is the flagged text hard to read against
  its background? Check that the highlight sits over actual text (not over an
  image or empty area) and that the estimated colors in the message match
  what you see. Light gray text on a white background is the typical real
  failure.
- **Target Size Failure / (Minimum)** (WCAG 2.5.5 / 2.5.8): is the flagged
  element interactive (button, clickable icon) and visibly small? Watch for
  two known false positives: elements **partially cut off** by scrolling (the
  reported size is smaller than the real one) and decorative containers that
  are technically clickable but are not a real touch target.
- **Missing Content Description / Missing Accessible Name**: is the element a
  **functional** image or icon (it does something when tapped) without an
  accessible name? Purely decorative icons are not a failure.
- **Missing Label or Instruction** (WCAG 3.3.2): does the flagged input field
  have any visible label or placeholder saying what to type? If there is
  nothing, it is a real failure.
- **Gesture-Only Navigation** (WCAG 2.1.1): a clickable element that does not
  receive keyboard focus. Hard to confirm from the image alone; confirm the
  element is actually interactive and is not an item of a legacy list
  (ListView), which the tool should already have exempted.
- **Duplicate Text** (WCAG 3.2.4): two elements with the same text doing
  different things? Repeated, merely informative texts are not a failure.
- **Overlapping Elements** (WCAG 1.4.12): do the flagged texts visually
  overlap to the point of hurting readability?
- **Resize Text - insufficient increase** (WCAG 1.4.4): compare the same
  element in the prints from `default/prints/` and `large_text/prints/`. Did
  the flagged text stay **the same size** at both scales? Then the failure is
  real (the app ignores the user's font preference). If it visibly grew, it
  is an FP.
- **Resize Text - insufficient reduction**: same procedure with
  `small_text/prints/`. This type is an **optional** check (WCAG does not
  require reduction); evaluate it normally, the distinction is already
  recorded in the finding.

## 6. Complete example

In the app `SAD_Mobile_18.3_APKPure`, screen `44e38161e554...`, the
`errors.json` contains a finding:

```json
{
  "type": "Contrast Failure",
  "phrase": "Njoftimet",
  "bounds": [42, 712, 1038, 763],
  "Contrast Ratio": "1.81:1",
  ...
}
```

In the `output_images/` image, the highlight sits over the section header
"Njoftimet", light blue on an almost white background. Looking at the screen,
the text is indeed hard to read. The row becomes:

| Application | Screen (screen_id) | Failure Type | Component | Argus Detected? | Argus Finding Confirmed? | Argus Classification |
|---|---|---|---|---|---|---|
| SAD_Mobile_18.3_APKPure | 44e38161e554... | Contrast Failure | Section header "Njoftimet" (android:id/title) | Yes | Yes | TP |

On the same screen, you notice a clickable icon with no accessible name that
does not appear in `errors.json`. That becomes a second row, an FN:

| SAD_Mobile_18.3_APKPure | 44e38161e554... | Missing Content Description | Printer icon at the top of the list | No | Yes | FN |

## 7. Common mistakes to avoid

- Typing the app name or the screen_id instead of copy/pasting. One wrong
  character breaks the automated cross-referencing of the spreadsheet with
  the results later.
- Translating or "improving" the Failure Type. It must be the exact text from
  `errors.json`, otherwise the aggregation by type does not add up.
- Skipping step 5 (the FN sweep). Without it, recall becomes artificially
  perfect and the evaluation loses half its value.
- Classifying as FP something you merely **could not confirm**. FP is when
  you confirm it is **not** a failure; doubt becomes a cell comment, not an
  FP.
- Evaluating repeated screens as if they were new. If two `result_<n>`
  folders are visibly the same screen, evaluate one and note the duplication
  in a comment.
