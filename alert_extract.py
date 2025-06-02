import os
import re

def extract_alert_patterns(rawdata_dir):
    alert_patterns = set()
    for filename in os.listdir(rawdata_dir):
        if filename.endswith('.log'):
            filepath = os.path.join(rawdata_dir, filename)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if re.search(r'alert', line, re.IGNORECASE):
                        alert_patterns.add(line.strip())
    return alert_patterns

if __name__ == "__main__":
    rawdata_dir = "rawdata"
    patterns = extract_alert_patterns(rawdata_dir)
    with open("alert_patterns.txt", "w", encoding="utf-8") as out:
        for pattern in sorted(patterns):
            out.write(pattern + "\n")