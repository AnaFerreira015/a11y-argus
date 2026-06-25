import json
import csv
import sys
from pathlib import Path
from collections import Counter, defaultdict

def collect_errors(output_dir: Path):
    errors = []
    error_files = list(output_dir.rglob("errors.json"))

    for error_file in error_files:
        try:
            data = json.loads(error_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Não consegui ler {error_file}: {e}")
            continue

        if isinstance(data, list):
            file_errors = data
        elif isinstance(data, dict):
            file_errors = data.get("errors", [])
        else:
            file_errors = []

        screen_id = error_file.parent.name

        for err in file_errors:
            errors.append({
                "apk": output_dir.name,
                "screen": screen_id,
                "type": err.get("type", ""),
                "element": err.get("element", ""),
                "content": err.get("content", ""),
                "bounds": err.get("bounds", ""),
                "criterion": err.get("Success Criterion", ""),
                "level": err.get("Level", ""),
                "file": str(error_file),
            })

    return errors, error_files

def main():
    if len(sys.argv) < 2:
        print("Uso: python compare_argus_outputs.py <pasta_outputs>")
        sys.exit(1)

    base_dir = Path(sys.argv[1])

    output_dirs = [
        p for p in base_dir.iterdir()
        if p.is_dir() and ("whobird" in p.name.lower() or "output_dir" in p.name.lower())
    ]

    all_rows = []
    summary_rows = []

    for output_dir in sorted(output_dirs):
        errors, error_files = collect_errors(output_dir)
        all_rows.extend(errors)

        by_type = Counter(err["type"] for err in errors)
        by_level = Counter(err["level"] for err in errors)
        screens_with_errors = len(set(err["screen"] for err in errors))

        summary_rows.append({
            "apk": output_dir.name,
            "screens_with_errors": screens_with_errors,
            "errors_json_files": len(error_files),
            "total_errors": len(errors),
            "missing_content_description": by_type.get("Missing Content Description", 0),
            "missing_accessible_name": by_type.get("Missing Accessible Name", 0),
            "resize_text_insufficient_increase": by_type.get("Resize Text - insufficient increase", 0),
            "resize_text_insufficient_reduction": by_type.get("Resize Text - insufficient reduction", 0),
            "touch_target": by_type.get("Touch Target Size", 0),
            "contrast": by_type.get("Contrast Error", 0),
            "duplicate_text": by_type.get("Duplicate Text", 0),
            "overlapping_elements": by_type.get("Overlapping Elements", 0),
            "levels": dict(by_level),
            "types": dict(by_type),
        })

    out_summary = base_dir / "argus_summary.csv"
    out_details = base_dir / "argus_errors_detailed.csv"

    with out_summary.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "apk",
            "screens_with_errors",
            "errors_json_files",
            "total_errors",
            "missing_content_description",
            "missing_accessible_name",
            "resize_text_insufficient_increase",
            "resize_text_insufficient_reduction",
            "touch_target",
            "contrast",
            "duplicate_text",
            "overlapping_elements",
            "levels",
            "types",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    with out_details.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "apk",
            "screen",
            "type",
            "element",
            "content",
            "bounds",
            "criterion",
            "level",
            "file",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"[OK] Resumo salvo em: {out_summary}")
    print(f"[OK] Detalhado salvo em: {out_details}")

    print("\n=== RESUMO ===")
    for row in summary_rows:
        print()
        print(row["apk"])
        print(f"  telas com erros: {row['screens_with_errors']}")
        print(f"  total de erros: {row['total_errors']}")
        print(f"  Missing Content Description: {row['missing_content_description']}")
        print(f"  Missing Accessible Name: {row['missing_accessible_name']}")
        print(f"  Resize Text increase: {row['resize_text_insufficient_increase']}")
        print(f"  Resize Text reduction: {row['resize_text_insufficient_reduction']}")

if __name__ == "__main__":
    main()