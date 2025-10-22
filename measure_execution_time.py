import os
import time
import csv

def get_first_and_last_timestamps(dir_path):
    json_files = [
        f for f in os.listdir(dir_path)
        if f.endswith(".json")
    ]
    if not json_files:
        return None, None

    json_paths = [os.path.join(dir_path, f) for f in json_files]
    creation_times = [os.path.getmtime(p) for p in json_paths]

    start_time = min(creation_times)
    end_time = max(creation_times)

    return start_time, end_time

def measure_execution_times(base_dir="."):
    results = []

    for folder in os.listdir(base_dir):
        if folder.startswith("output_dir_"):
            app_name = folder.replace("output_dir_", "")
            states_dir = os.path.join(base_dir, folder, "default", "states")
            if not os.path.exists(states_dir):
                continue
            start_ts, end_ts = get_first_and_last_timestamps(states_dir)
            if not start_ts or not end_ts:
                continue
            total_seconds = end_ts - start_ts
            total_minutes = round(total_seconds / 60, 2)
            results.append((app_name, round(total_seconds, 2), total_minutes))

    return results

def save_to_csv(results, filename="execution_times.csv"):
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["apk_name", "execution_time_seconds", "execution_time_minutes"])
        for row in results:
            writer.writerow(row)

execution_times = measure_execution_times()
save_to_csv(execution_times)
print(f"[INFO] Results saved in 'execution_times.csv' with {len(execution_times)} applications.")
