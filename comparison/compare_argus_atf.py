#!/usr/bin/env python3
"""Compara achados do a11y-argus com os do atf-harness (motor do
Accessibility Scanner) para os mesmos estados de UI.

Uso:
    python compare_argus_atf.py --atf-dir atf/ --argus-dir argus/ \
        --map state_map.json --out comparacao_out/

O state_map.json mapeia o stateId do ATF para a pasta de resultado do argus:
    {"teste_001": "result_1", "teste_002": "result_2", "teste_003": "result_4"}
No pipeline com replay do DroidBot esse mapa e 1:1 pelo state_str e pode ser
gerado automaticamente.

Saida: um CSV por par de estado + summary.csv agregado, com veredito por
achado: MATCHED, ARGUS_ONLY ou ATF_ONLY, dentro de cada categoria do
crosswalk. Achados de categorias sem contraparte na outra ferramenta recebem
veredito NO_COUNTERPART (diferenca de escopo, nao de deteccao).
"""

import argparse
import csv
import json
from pathlib import Path

# Crosswalk: categoria comum -> (checks do ATF, tipos do argus).
# Categorias com um dos lados vazio marcam diferenca de escopo entre as
# ferramentas (NO_COUNTERPART), nao falha de deteccao.
CROSSWALK = {
    "contrast_text": (
        ["TextContrastCheck"],
        ["Contrast Failure"],
    ),
    "target_size": (
        ["TouchTargetSizeCheck"],
        ["Target Size Failure", "Target Size Failure (Minimum)"],
    ),
    "missing_speakable_text": (
        ["SpeakableTextPresentCheck"],
        ["Missing Content Description", "Missing Accessible Name"],
    ),
    "duplicate_text": (
        ["DuplicateSpeakableTextCheck"],
        ["Duplicate Text"],
    ),
    # Mesma causa raiz vista por angulos diferentes: o ATF aponta texto sem
    # unidade sp (estatico), o argus observa o texto nao escalar (dinamico).
    "text_scaling": (
        ["TextSizeCheck"],
        ["Resize Text - insufficient increase",
         "Resize Text - insufficient reduction"],
    ),
    # Ambas checam rotulos de link/acao ambiguos.
    "link_purpose": (
        ["LinkPurposeUnclearCheck"],
        ["Link Purpose Failure"],
    ),
    # Sem contraparte no argus (v. atual):
    "contrast_image": (["ImageContrastCheck"], []),
    "class_name": (["ClassNameCheck"], []),
    "duplicate_clickable_bounds": (["DuplicateClickableBoundsCheck"], []),
    # ATF: campo editavel COM contentDescription (anti-pattern); distinto do
    # Non-essential CD do argus (decorativo com descricao). Mantidos separados.
    "editable_content_desc": (["EditableContentDescCheck"], []),
    # ATF: ordem de travessia de acessibilidade; distinto da ordem de foco de
    # entrada medida pelo argus. Mantidos separados (v. discussao no texto).
    "traversal_order": (["TraversalOrderCheck"], []),
    # Sem contraparte no ATF:
    "labels_instructions": ([], ["Missing Label or Instruction"]),
    "gesture_navigation": ([], ["Gesture-Only Navigation"]),
    "focus_order": ([], ["Focus Order Failure"]),
    "overlapping_elements": ([], ["Overlapping Elements"]),
    "non_essential_content_desc":
        ([], ["Non-essential Content Description Should Be Empty"]),
    "error_identification": ([], ["Missing Error Description"]),
}

IOMIN_THRESHOLD = 0.5


def build_category_index():
    atf_idx, argus_idx = {}, {}
    for cat, (atf_checks, argus_types) in CROSSWALK.items():
        for c in atf_checks:
            atf_idx[c] = cat
        for t in argus_types:
            argus_idx[t] = cat
    return atf_idx, argus_idx


def iomin(b1, b2):
    """Intersection over minimum area de dois bounds [l, t, r, b]."""
    l = max(b1[0], b2[0])
    t = max(b1[1], b2[1])
    r = min(b1[2], b2[2])
    b = min(b1[3], b2[3])
    if r <= l or b <= t:
        return 0.0
    inter = (r - l) * (b - t)
    a1 = max(1, (b1[2] - b1[0]) * (b1[3] - b1[1]))
    a2 = max(1, (b2[2] - b2[0]) * (b2[3] - b2[1]))
    return inter / min(a1, a2)


def load_atf(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    density = (data.get("screen") or {}).get("density")
    findings = []
    for r in data.get("results", []):
        el = r.get("element") or {}
        if not el or not el.get("bounds"):
            continue
        findings.append({
            "tool": "atf",
            "check": r["check"],
            "severity": r["type"],
            "bounds": el["bounds"],
            "label": el.get("text") or el.get("resource_id") or "",
            "detail": r.get("message", "")[:120],
        })
    return findings, density


def load_argus(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    findings = []
    for e in data.get("errors", []):
        if not e.get("bounds"):
            continue
        findings.append({
            "tool": "argus",
            "check": e["type"],
            "severity": e.get("Level", ""),
            "bounds": e["bounds"],
            "label": e.get("phrase") or e.get("element")
                     or e.get("resource_id") or e.get("content") or "",
            "detail": (e.get("Details") or e.get("description") or "")[:120],
        })
    return findings


def aggregate_by_element(findings):
    """Colapsa achados da mesma ferramenta com bounds identicos dentro da
    mesma categoria num unico achado logico (ex.: increase/reduction do
    argus, ou Name/Description no mesmo elemento). Os tipos originais sao
    preservados concatenados."""
    groups = {}
    for f in findings:
        key = (f["category"], tuple(f["bounds"]))
        if key not in groups:
            groups[key] = dict(f)
            groups[key]["n_reports"] = 1
        else:
            g = groups[key]
            if f["check"] not in g["check"]:
                g["check"] += " + " + f["check"]
            g["n_reports"] += 1
            if not g["label"] and f["label"]:
                g["label"] = f["label"]
    return list(groups.values())


ATF_TARGET_DP = 48
ARGUS_ENHANCED_DP = 44


def match_state(atf_findings, argus_findings, density=None):
    """Matching guloso por categoria: melhor IoMin primeiro."""
    atf_idx, argus_idx = build_category_index()
    for f in atf_findings:
        f["category"] = atf_idx.get(f["check"], "uncategorized_atf")
    for f in argus_findings:
        f["category"] = argus_idx.get(f["check"], "uncategorized_argus")

    atf_findings = aggregate_by_element(atf_findings)
    argus_findings = aggregate_by_element(argus_findings)

    rows = []
    categories = {f["category"] for f in atf_findings + argus_findings}
    for cat in sorted(categories):
        atf_cat = [f for f in atf_findings if f["category"] == cat]
        argus_cat = [f for f in argus_findings if f["category"] == cat]
        has_counterpart = bool(CROSSWALK.get(cat, ([], []))[0]) and \
                          bool(CROSSWALK.get(cat, ([], []))[1])

        pairs = sorted(
            ((iomin(a["bounds"], g["bounds"]), i, j)
             for i, a in enumerate(atf_cat)
             for j, g in enumerate(argus_cat)),
            reverse=True)
        used_a, used_g = set(), set()
        for score, i, j in pairs:
            if score < IOMIN_THRESHOLD or i in used_a or j in used_g:
                continue
            used_a.add(i)
            used_g.add(j)
            rows.append(_row(cat, "MATCHED", atf_cat[i], argus_cat[j], score))
        for i, f in enumerate(atf_cat):
            if i not in used_a:
                verdict = "ATF_ONLY" if has_counterpart else "NO_COUNTERPART"
                note = ""
                if cat == "target_size" and density:
                    l, t, r, b = f["bounds"]
                    min_dim_px = min(r - l, b - t)
                    if (ARGUS_ENHANCED_DP * density <= min_dim_px
                            < ATF_TARGET_DP * density):
                        verdict = "THRESHOLD_GAP"
                        note = (f"menor dimensao = "
                                f"{min_dim_px / density:.1f}dp: passa nos "
                                f"{ARGUS_ENHANCED_DP}dp do argus (2.5.5), "
                                f"falha nos {ATF_TARGET_DP}dp do ATF")
                rows.append(_row(cat, verdict, f, None, "", note))
        for j, f in enumerate(argus_cat):
            if j not in used_g:
                verdict = "ARGUS_ONLY" if has_counterpart else "NO_COUNTERPART"
                rows.append(_row(cat, verdict, None, f, ""))
    return rows


def _row(cat, verdict, atf_f, argus_f, score, note=""):
    return {
        "category": cat,
        "verdict": verdict,
        "iomin": f"{score:.2f}" if score != "" else "",
        "atf_check": atf_f["check"] if atf_f else "",
        "atf_severity": atf_f["severity"] if atf_f else "",
        "atf_bounds": str(atf_f["bounds"]) if atf_f else "",
        "atf_label": atf_f["label"] if atf_f else "",
        "argus_type": argus_f["check"] if argus_f else "",
        "argus_level": argus_f["severity"] if argus_f else "",
        "argus_bounds": str(argus_f["bounds"]) if argus_f else "",
        "argus_label": argus_f["label"] if argus_f else "",
        "argus_reports": argus_f.get("n_reports", "") if argus_f else "",
        "note": note,
    }


FIELDS = ["state", "category", "verdict", "iomin",
          "atf_check", "atf_severity", "atf_bounds", "atf_label",
          "argus_type", "argus_level", "argus_bounds", "argus_label",
          "argus_reports", "note"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atf-dir", required=True)
    ap.add_argument("--argus-dir", required=True)
    ap.add_argument("--map", required=True,
                    help="JSON {stateId_atf: pasta_result_argus}")
    ap.add_argument("--out", default="comparacao_out")
    ap.add_argument("--density", type=float, default=None,
                    help="densidade do device (fallback se o JSON do ATF nao tiver)")
    args = ap.parse_args()

    state_map = json.loads(Path(args.map).read_text(encoding="utf-8"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows = []
    for state_id, result_dir in state_map.items():
        atf_path = Path(args.atf_dir) / f"{state_id}.json"
        argus_path = Path(args.argus_dir) / result_dir / "errors.json"
        if not atf_path.exists() or not argus_path.exists():
            print(f"[WARN] par incompleto: {state_id} <-> {result_dir}, pulando")
            continue
        atf_findings, density = load_atf(atf_path)
        rows = match_state(atf_findings, load_argus(argus_path),
                           density=density or args.density)
        for r in rows:
            r["state"] = state_id
        all_rows.extend(rows)

        with open(out_dir / f"{state_id}.csv", "w", newline="",
                  encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)

    with open(out_dir / "comparacao_completa.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(all_rows)

    # Sumario agregado por categoria e veredito
    summary = {}
    for r in all_rows:
        key = (r["category"], r["verdict"])
        summary[key] = summary.get(key, 0) + 1
    with open(out_dir / "summary.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["category", "verdict", "count"])
        for (cat, verdict), count in sorted(summary.items()):
            w.writerow([cat, verdict, count])

    print(f"\n{'categoria':32s} {'veredito':16s} qtd")
    for (cat, verdict), count in sorted(summary.items()):
        print(f"{cat:32s} {verdict:16s} {count}")
    print(f"\nSaida em: {out_dir}/")


if __name__ == "__main__":
    main()
