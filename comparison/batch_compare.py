#!/usr/bin/env python3
"""Roda a comparacao argus x ATF em lote sobre todos os output_dir_* e
agrega um sumario global.

Uso:
    python batch_compare.py --root C:\\Projects\\a11y-argus --out comparacao_batch

Requisitos por app (gerados pelo pipeline + replay_atf.py):
    output_dir_<app>/results/result_N/errors.json   (analise do argus)
    output_dir_<app>/atf/<state>.json               (scans do ATF)
    output_dir_<app>/state_map_atf.json             (mapeamento estado->result)

Deve ficar na mesma pasta do compare_argus_atf.py (importa dele).

Saida:
    <out>/<app>/comparacao_completa.csv   por app
    <out>/comparacao_global.csv           todas as linhas, com coluna app
    <out>/summary_global.csv              contagens por categoria x veredito
    <out>/summary_por_app.csv             contagens por app x categoria x veredito
    <out>/apps_pulados.csv                apps sem os artefatos necessarios
"""

import argparse
import csv
import json
from pathlib import Path

from compare_argus_atf import load_atf, load_argus, match_state, FIELDS

GLOBAL_FIELDS = ["app"] + FIELDS


def compare_app(output_dir: Path, out_dir: Path):
    """Retorna (linhas, motivo_pulo). Se motivo_pulo nao for None, o app
    foi pulado."""
    map_path = output_dir / "state_map_atf.json"
    atf_dir = output_dir / "atf"
    results_dir = output_dir / "results"

    if not map_path.is_file():
        return [], "sem state_map_atf.json (replay nao rodou?)"
    if not atf_dir.is_dir():
        return [], "sem pasta atf"
    if not results_dir.is_dir():
        return [], "sem pasta results"

    state_map = json.loads(map_path.read_text(encoding="utf-8"))
    if not state_map:
        return [], "state_map vazio (nenhum estado casado no replay)"

    rows = []
    for state_id, result_dir in state_map.items():
        atf_path = atf_dir / f"{state_id}.json"
        argus_path = results_dir / result_dir / "errors.json"
        if not atf_path.is_file() or not argus_path.is_file():
            continue
        atf_findings, density = load_atf(atf_path)
        state_rows = match_state(atf_findings, load_argus(argus_path),
                                 density=density)
        for r in state_rows:
            r["state"] = state_id
        rows.extend(state_rows)

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "comparacao_completa.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    return rows, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True,
                    help="pasta que contem os output_dir_*")
    ap.add_argument("--out", default="comparacao_batch")
    args = ap.parse_args()

    root = Path(args.root)
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    app_dirs = sorted(p for p in root.glob("output_dir_*") if p.is_dir())
    print(f"[BATCH] {len(app_dirs)} output_dir_* encontrados em {root}")

    all_rows, skipped = [], []
    for app_dir in app_dirs:
        app_name = app_dir.name.replace("output_dir_", "", 1)
        rows, skip_reason = compare_app(app_dir, out_root / app_name)
        if skip_reason:
            skipped.append((app_name, skip_reason))
            print(f"[BATCH] PULADO {app_name}: {skip_reason}")
            continue
        for r in rows:
            r["app"] = app_name
        all_rows.extend(rows)
        n_states = len({r["state"] for r in rows})
        print(f"[BATCH] {app_name}: {len(rows)} linhas, {n_states} estados")

    with open(out_root / "comparacao_global.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=GLOBAL_FIELDS)
        w.writeheader()
        w.writerows(all_rows)

    summary_global, summary_app = {}, {}
    for r in all_rows:
        summary_global[(r["category"], r["verdict"])] = \
            summary_global.get((r["category"], r["verdict"]), 0) + 1
        key = (r["app"], r["category"], r["verdict"])
        summary_app[key] = summary_app.get(key, 0) + 1

    with open(out_root / "summary_global.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["category", "verdict", "count"])
        for (cat, verdict), count in sorted(summary_global.items()):
            w.writerow([cat, verdict, count])

    with open(out_root / "summary_por_app.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["app", "category", "verdict", "count"])
        for (app, cat, verdict), count in sorted(summary_app.items()):
            w.writerow([app, cat, verdict, count])

    with open(out_root / "apps_pulados.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["app", "motivo"])
        w.writerows(skipped)

    print(f"\n[BATCH] {len(app_dirs) - len(skipped)} apps comparados, "
          f"{len(skipped)} pulados, {len(all_rows)} linhas no total")
    print(f"\n{'categoria':32s} {'veredito':16s} qtd")
    for (cat, verdict), count in sorted(summary_global.items()):
        print(f"{cat:32s} {verdict:16s} {count}")
    print(f"\nSaida em: {out_root}/")


if __name__ == "__main__":
    main()
