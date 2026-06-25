import os
import json
import pandas as pd
from collections import defaultdict

BASE_DIR = "."

failures_per_screen = []
app_failure_frequency = defaultdict(lambda: defaultdict(int))
ranking_failures = defaultdict(lambda: {"application": set(), "total": 0})
wcag_distribution = defaultdict(int)

def process_errors(app_name, screen_id, error_list):
    for error in error_list:
        type = error["type"]
        criterion = error.get("Success Criterion", "")
        level = error.get("Level", "")

        failures_per_screen.append({
            "Application": app_name,
            "Screen (screen_id)": screen_id,
            "Failure Type": type,
            "WCAG criteria": criterion,
            "Level": level,
            "Count": 1
        })

        key = (type, criterion, level)
        app_failure_frequency[app_name][key] += 1
        ranking_failures[type]["application"].add(app_name)
        ranking_failures[type]["total"] += 1
        wcag_distribution[level] += 1

for app_folder in os.listdir(BASE_DIR):
    if not app_folder.startswith("output_dir_"):
        continue

    app_path = os.path.join(BASE_DIR, app_folder)
    app_name = app_folder.replace("output_dir_", "")
    results_path = os.path.join(app_path, "results")

    if not os.path.isdir(results_path):
        continue

    for app_folder in os.listdir(results_path):
        result_path = os.path.join(results_path, app_folder)
        if not os.path.isdir(result_path):
            continue

        for file_name in ["errors.json", "overlapping_errors.json"]:
            path = os.path.join(result_path, file_name)
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                    screen_id = data.get("screen_id")
                    errors = data.get("errors", [])
                    process_errors(app_name, screen_id, errors)

df_failures_per_screen = pd.DataFrame(failures_per_screen)
df_failures_per_screen.to_csv("failures_per_screen.csv", index=False)

rq1_rows = []
for applications, errors in app_failure_frequency.items():
    total = sum(errors.values())
    for (type, criterion, level), qty in errors.items():
        rq1_rows.append({
            "Application": applications,
            "Failure Type": type,
            "WCAG criteria": criterion,
            "Level": level,
            "Number of Occurrences": qty,
            "Percentage (%)": round((qty / total) * 100, 2) if total > 0 else 0.0
        })
df_rq1 = pd.DataFrame(rq1_rows)
df_rq1.to_csv("failure_frequency.csv", index=False)

df_rq2 = pd.DataFrame([
    {
        "Failure Type": type,
        "Total Occurrences": data["total"],
        "Affected Applications": len(data["application"])
    }
    for type, data in ranking_failures.items()
]).sort_values(by="Total Occurrences", ascending=False)
df_rq2.insert(0, "Rank", range(1, len(df_rq2) + 1))
df_rq2.to_csv("ranking_failures.csv", index=False)

wcag_adjusted = defaultdict(int, wcag_distribution)

if "Advisory" in wcag_adjusted:
    wcag_adjusted["AA"] += wcag_adjusted["Advisory"]
    del wcag_adjusted["Advisory"]

total_failures = sum(wcag_adjusted.values())

df_rq3 = pd.DataFrame([
    {
        "WCAG Level": level,
        "Total Failures": total,
        "Percentage (%)": round((total / total_failures) * 100, 2)
    }
    for level, total in wcag_adjusted.items()
])

df_rq3.to_csv("wcag_distribution.csv", index=False)

pivot_dict = defaultdict(dict)
total_per_app = {app: sum(errors.values()) for app, errors in app_failure_frequency.items()}

for applications, errors in app_failure_frequency.items():
    for (type, criterion, level), qty in errors.items():
        key = (type, criterion, level)
        pivot_dict[key][f"{applications} - Number of Occurrences"] = int(qty)
        percentage = (qty / total_per_app[applications]) * 100 if total_per_app[applications] > 0 else 0.0
        pivot_dict[key][f"{applications} - %"] = round(percentage, 2)

pivot_rows = []
for (type, criterion, level), values in pivot_dict.items():
    base = {
        "Failure Type": type,
        "WCAG criteria": criterion,
        "Level": level
    }
    base.update(values)
    pivot_rows.append(base)

df_rq1_pivot = pd.DataFrame(pivot_rows)
df_rq1_pivot.to_csv("pivoted_fault_frequency.csv", index=False)

print("Spreadsheets generated successfully!")
