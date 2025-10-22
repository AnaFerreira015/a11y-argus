import os
import cereja as cj
import pandas as pd

apks = cj.FileIO.load(r'C:\Users\dasil\PycharmProjects\ocr-test\apks.csv', cols=('apk_path',)).data

total_apks = len(apks)

BASE_DIR = r"C:\Users\dasil\PycharmProjects\ocr-test"

total_analyzed = 0

for folder in os.listdir(BASE_DIR):
    if folder.startswith("output_dir_"):
        results_path = os.path.join(BASE_DIR, folder, "results")

        if os.path.exists(results_path) and os.path.isdir(results_path):
            subfolders = [p for p in os.listdir(results_path) if os.path.isdir(os.path.join(results_path, p))]

            if subfolders:
                total_analyzed += 1
                print(f"{folder} → {len(subfolders)} screen(s)")

print(f"\nTotal apps evaluated (with non-empty 'results' folder): {total_analyzed}")

total_not_analyzed = total_apks - total_analyzed
percentage_coverage = round((total_analyzed / total_apks) * 100, 2)

coverage_table = pd.DataFrame({
    'Metric': [
        'Total APKs collected',
        'Total APKs analyzed by the tool',
        'Total unanalyzed APKs',
        'Percentage of coverage (%)'
    ],
    'Value': [
        total_apks,
        total_analyzed,
        total_not_analyzed,
        percentage_coverage
    ]
})

coverage_table.loc[0:2, 'Value'] = coverage_table.loc[0:2, 'Value'].astype(int)

print("\nCoverage Table:")
print(f'{"Metric":<40} | {"Value":>10}')
print("-" * 55)
for _, row in coverage_table.iterrows():
    metric = row['Metric']
    value = row['Value']
    if isinstance(value, float) and not 'Percentage' in metric:
        value = int(value)
    print(f'{metric:<40} | {value:>10}')

coverage_table.to_csv('coverage_table.csv', index=False)
