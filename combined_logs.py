import os
import re
import gzip
import csv
import pickle
import pandas as pd

# Set to your relative or absolute folder path
folder = "rawdata/weeklong"
max_files = None  # Optional: limit for debugging

# Regex pattern
timestamp_pattern = re.compile(
    r'^\[(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) (\w) ([^\s\]]+) (\w+) ([^\]]+)\]\s*(.*)$'
)

# Collect files
files = []
for root, _, fs in os.walk(folder):
    for file in fs:
        if file.endswith(".log.gz"):
            files.append(os.path.join(root, file))

if max_files:
    files = sorted(files)[:max_files]

print(f"🗂 Found {len(files)} files.")

# Parsing setup
entries = []
current_entry = ""
current_match = None
match_count = 0
line_count = 0

def flush_entry():
    if current_match and current_entry:
        timestamp, level, lane, group_id, code = current_match.groups()[:5]
        description = current_entry.strip()
        entries.append([timestamp, level, lane, group_id, code, description])

# Process files
for file_path in files:
    print(f"📖 Processing: {file_path}")
    open_func = gzip.open if file_path.endswith(".gz") else open
    with open_func(file_path, 'rt', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line_count += 1
            match = timestamp_pattern.match(line)
            if match:
                flush_entry()
                current_match = match
                current_entry = match.group(6) + "\n"
                match_count += 1
            else:
                current_entry += line

# Final flush
flush_entry()

print(f"✅ Total lines read: {line_count}")
print(f"✅ Log entries matched: {match_count}")
print(f"✅ Log entries parsed: {len(entries)}")

# Save CSV
if entries:
    csv_path = "parsed_log_output.csv"
    with open(csv_path, "w", encoding="utf-8", newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Timestamp", "Level", "Lane", "GroupID", "Code", "Message"])
        writer.writerows(entries)
    print(f"💾 Saved {csv_path}")

    # Save pickle version
    pkl_path = "parsed_log_output.pkl.gz"
    with gzip.open(pkl_path, "wb") as pkl_file:
        pickle.dump(entries, pkl_file)
    print(f"💾 Saved {pkl_path}")

    # ✅ Display first 20 rows as DataFrame
    df = pd.DataFrame(entries, columns=["Timestamp", "Level", "Lane", "GroupID", "Code", "Message"])
    print("\n🧾 First 20 log entries:")
    print(df.head(20))

else:
    print("⚠️ No log entries were parsed. Check your regex or log format.")
