#!/usr/bin/env python3
"""Gera o catalogo de achados do ATF (Accessibility Scanner) para a planilha
de avaliacao manual, com imagens anotadas para conferencia visual.

Para cada app com replay concluido (pastas atf/ e state_map_atf.json), o
script:
1. Cruza cada scan do ATF com o result_N do argus via state_map, usando o
   screen_id do argus como identificador de tela (mesma coluna Screen da
   planilha, permitindo cruzar as linhas do argus e do AS).
2. Emite um CSV pronto para colar na planilha, uma linha por achado, com
   AS Detected? ja preenchido como Yes e as colunas de validacao vazias.
3. Desenha os bounds de cada achado sobre o print da tela, salvando em
   results/result_N/as_images/, no mesmo estilo das output_images do argus.

Uso:
    python catalog_atf.py --root C:\\Projects\\a11y-argus --out catalogo_as
    python catalog_atf.py --root . --app SAD_Mobile_18.3_APKPure

Requer Pillow (pip install pillow).
"""

import argparse
import csv
import json
from pathlib import Path

SEVERITIES_TO_CATALOG = {"ERROR", "WARNING"}

COLORS = {"ERROR": (220, 38, 38), "WARNING": (245, 158, 11)}

FIELDS = ["Application", "Screen (screen_id)", "AS Rule", "AS Severity",
          "Component", "Bounds", "Message",
          "AS Detected?", "AS Finding Confirmed?", "AS Classification"]


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def component_of(element):
    if not element:
        return ""
    return (element.get("resource_id")
            or element.get("text")
            or element.get("content_description")
            or element.get("class")
            or "")


def annotate(print_path, findings, out_path):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False
    if not Path(print_path).exists():
        return False
    img = Image.open(print_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = None
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            font = ImageFont.truetype(name, 34)
            break
        except OSError:
            continue
    if font is None:
        try:
            font = ImageFont.load_default(size=34)
        except TypeError:
            font = ImageFont.load_default()

    for i, f in enumerate(findings):
        el = f.get("element") or {}
        bounds = el.get("bounds")
        if not bounds:
            continue
        left, top, right, bottom = bounds
        color = COLORS.get(f.get("type"), (59, 130, 246))
        draw.rectangle([left, top, right, bottom], outline=color, width=4)
        label = f"{i}: {f.get('check', '?')}"
        bbox = draw.textbbox((0, 0), label, font=font)
        lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        ly = top - lh - 12 if top - lh - 12 >= 0 else top + 4
        lx = max(0, min(left, img.width - lw - 8))
        draw.rectangle([lx, ly, lx + lw + 8, ly + lh + 8], fill=color)
        draw.text((lx + 4, ly + 2), label, fill=(255, 255, 255), font=font)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return True


def catalog_app(app_dir: Path, rows: list):
    app_name = app_dir.name.replace("output_dir_", "", 1)
    map_path = app_dir / "state_map_atf.json"
    if not map_path.is_file():
        return None, "sem state_map_atf.json (replay nao rodou)"
    state_map = load_json(map_path)
    if not state_map:
        return None, "state_map vazio"

    n_findings, n_images = 0, 0
    for atf_state, result_dir in sorted(state_map.items()):
        atf_json = app_dir / "atf" / f"{atf_state}.json"
        errors_json = app_dir / "results" / result_dir / "errors.json"
        if not atf_json.is_file() or not errors_json.is_file():
            continue

        argus_screen_id = load_json(errors_json).get("screen_id", atf_state)
        scan = load_json(atf_json)
        findings = [r for r in scan.get("results", [])
                    if r.get("type") in SEVERITIES_TO_CATALOG]

        for i, f in enumerate(findings):
            el = f.get("element") or {}
            rows.append({
                "Application": app_name,
                "Screen (screen_id)": argus_screen_id,
                "AS Rule": f.get("check", ""),
                "AS Severity": f.get("type", ""),
                "Component": component_of(el),
                "Bounds": str(el.get("bounds", "")),
                "Message": (f.get("message", "") or "")[:200],
                "AS Detected?": "Yes",
                "AS Finding Confirmed?": "",
                "AS Classification": "",
            })
        n_findings += len(findings)

        # Imagem anotada sobre o print da captura original do argus
        print_path = (app_dir / "default" / "prints" /
                      f"screen_default_{argus_screen_id}.png")
        out_img = (app_dir / "results" / result_dir / "as_images" /
                   f"as_{argus_screen_id}.png")
        if findings and annotate(print_path, findings, out_img):
            n_images += 1

    return (n_findings, n_images), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--app", default=None,
                    help="processa so um app (nome sem 'output_dir_')")
    ap.add_argument("--out", default="catalogo_as")
    args = ap.parse_args()

    root = Path(args.root)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    app_dirs = sorted(p for p in root.glob("output_dir_*") if p.is_dir())
    if args.app:
        app_dirs = [p for p in app_dirs
                    if p.name == f"output_dir_{args.app}"]

    rows, skipped = [], []
    for app_dir in app_dirs:
        stats, reason = catalog_app(app_dir, rows)
        name = app_dir.name.replace("output_dir_", "", 1)
        if reason:
            skipped.append((name, reason))
            print(f"[CATALOG] PULADO {name}: {reason}")
        else:
            print(f"[CATALOG] {name}: {stats[0]} achados, "
                  f"{stats[1]} imagens anotadas")

    csv_path = out_dir / "catalogo_as.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"\n[CATALOG] {len(rows)} linhas -> {csv_path}")
    if skipped:
        print(f"[CATALOG] {len(skipped)} apps pulados")


if __name__ == "__main__":
    main()
