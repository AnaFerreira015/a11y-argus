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
   Se a saida do batch_compare for informada (--compare-dir), cada linha
   ganha o veredito da comparacao (MATCHED/ATF_ONLY/THRESHOLD_GAP) e, nos
   MATCHED, a referencia do achado do argus correspondente, permitindo
   herdar a validacao ja feita na aba do argus.
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
          "AS Detected?", "AS Finding Confirmed?", "AS Classification",
          "Compare Verdict", "Matched Argus Finding", "Auto Note"]


def load_argus_sheet(path):
    """{(app, screen, failure_type): set(classificacoes)}. Tolera linhas de
    titulo/banner acima do cabecalho real."""
    import csv as _csv
    from collections import defaultdict
    with open(path, encoding="utf-8-sig", newline="") as f:
        raw = list(_csv.reader(f))
    header_idx = None
    for i, line in enumerate(raw):
        if "Application" in line and "Failure Type" in line:
            header_idx = i
            break
    if header_idx is None:
        raise SystemExit("[CATALOG] Cabecalho nao encontrado na planilha "
                         "(esperava colunas 'Application' e 'Failure Type').")
    header = raw[header_idx]
    idx = defaultdict(set)
    for line in raw[header_idx + 1:]:
        row = dict(zip(header, line))
        key = (row.get("Application", "").strip(),
               row.get("Screen (screen_id)", "").strip(),
               row.get("Failure Type", "").strip())
        cls = (row.get("Argus Classification", "") or "").strip().upper()
        if cls:
            idx[key].add(cls)
    return idx


def autofill(verdict, argus_ref, app, screen, sheet):
    """Retorna (confirmed, classification, note) para a linha."""
    if verdict == "THRESHOLD_GAP":
        return "Yes", "TP", "auto: threshold AS 48dp (gap 44-48dp)"
    if verdict == "MATCHED" and sheet is not None and argus_ref:
        argus_types = argus_ref.split(" @ ")[0]
        classes = set()
        for t in [t.strip() for t in argus_types.split("+")]:
            classes |= sheet.get((app, screen, t), set())
        if classes == {"TP"}:
            return "Yes", "TP", "auto: via match argus (TP)"
        if classes == {"FP"}:
            return "No", "FP", "auto: via match argus (FP)"
        if classes:
            return "", "", "match argus: misto na planilha, conferir"
        return "", "", "match argus: linha argus ainda nao avaliada"
    return "", "", ""


def load_compare_index(compare_dir, app_name):
    """{(state, atf_bounds_str): [(atf_check, verdict, argus_ref), ...]}
    a partir do comparacao_completa.csv do app no batch_compare. A lista
    existe porque dois achados do ATF podem compartilhar o mesmo elemento
    (ex.: TouchTargetSize e SpeakableText no mesmo botao); o lookup
    desambigua pelo nome do check."""
    idx = {}
    path = Path(compare_dir) / app_name / "comparacao_completa.csv"
    if not path.is_file():
        return idx
    import csv as _csv
    with open(path, encoding="utf-8-sig") as f:
        for row in _csv.DictReader(f):
            bounds = row.get("atf_bounds", "")
            if not bounds:
                continue
            argus_ref = ""
            if row.get("verdict") == "MATCHED":
                argus_ref = (f"{row.get('argus_type', '')} @ "
                             f"{row.get('argus_bounds', '')}")
            idx.setdefault((row.get("state", ""), bounds), []).append(
                (row.get("atf_check", ""), row.get("verdict", ""), argus_ref))
    return idx


def lookup_verdict(cmp_idx, state, bounds_str, check_name):
    """Encontra o veredito do achado certo quando varios checks do ATF
    compartilham os mesmos bounds. O atf_check da comparacao pode vir
    agregado ("A + B"), por isso a busca e por pertencimento."""
    for atf_check, verdict, argus_ref in cmp_idx.get((state, bounds_str), []):
        if check_name and check_name in atf_check:
            return verdict, argus_ref
    return "", ""


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


def catalog_app(app_dir: Path, rows: list, compare_dir=None, sheet=None):
    app_name = app_dir.name.replace("output_dir_", "", 1)
    map_path = app_dir / "state_map_atf.json"
    if not map_path.is_file():
        return None, "sem state_map_atf.json (replay nao rodou)"
    state_map = load_json(map_path)
    if not state_map:
        return None, "state_map vazio"

    cmp_idx = load_compare_index(compare_dir, app_name) if compare_dir else {}

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
            bounds_str = str(el.get("bounds", ""))
            verdict, argus_ref = lookup_verdict(
                cmp_idx, atf_state, bounds_str, f.get("check", ""))
            confirmed, classification, note = autofill(
                verdict, argus_ref, app_name, argus_screen_id, sheet)
            rows.append({
                "Application": app_name,
                "Screen (screen_id)": argus_screen_id,
                "AS Rule": f.get("check", ""),
                "AS Severity": f.get("type", ""),
                "Component": component_of(el),
                "Bounds": str(el.get("bounds", "")),
                "Message": (f.get("message", "") or "")[:200],
                "AS Detected?": "Yes",
                "AS Finding Confirmed?": confirmed,
                "AS Classification": classification,
                "Compare Verdict": verdict,
                "Matched Argus Finding": argus_ref,
                "Auto Note": note,
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
    ap.add_argument("--compare-dir", default=None,
                    help="pasta de saida do batch_compare (ex.: comparacao_batch) "
                         "para anexar o veredito da comparacao a cada linha")
    ap.add_argument("--argus-sheet", default=None,
                    help="planilha do argus exportada em CSV: preenche "
                         "automaticamente Confirmed/Classification das linhas "
                         "MATCHED herdando a validacao do argus")
    args = ap.parse_args()

    root = Path(args.root)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    app_dirs = sorted(p for p in root.glob("output_dir_*") if p.is_dir())
    if args.app:
        app_dirs = [p for p in app_dirs
                    if p.name == f"output_dir_{args.app}"]

    sheet = load_argus_sheet(args.argus_sheet) if args.argus_sheet else None

    rows, skipped = [], []
    for app_dir in app_dirs:
        stats, reason = catalog_app(app_dir, rows,
                                    compare_dir=args.compare_dir, sheet=sheet)
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

    auto = sum(1 for r in rows if r["AS Classification"])
    print(f"\n[CATALOG] {len(rows)} linhas -> {csv_path} "
          f"({auto} preenchidas automaticamente, "
          f"{len(rows) - auto} para validacao manual)")
    if skipped:
        print(f"[CATALOG] {len(skipped)} apps pulados")


if __name__ == "__main__":
    main()
