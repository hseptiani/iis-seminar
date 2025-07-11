
# IIS Seminar – Warehouse operations with Eurotrade (Munich Airport) – Internet of Things and Industrial Services

This repository contains the code and resources developed for the IIS Seminar project **"Internet of Things and Industrial Services"** in cooperation with Eurotrade (Munich Airport).

The project focuses on converting unstructured event logs from Automated Small-Parts Storage Systems (AKL – Automatisches Kleinteilelager) into structured data formats, enabling pattern discovery and supporting root cause analysis in warehouse operations.

---

## 📦 Project Overview

In modern logistics environments, AKL systems generate large volumes of unstructured event logs. This project addresses key challenges:

✅ Transforming raw AKL logs into structured datasets using regex-based parsing.  
✅ Identifying recurring event sequences, failure loops, and irregular routing (e.g., to NIO lanes).  
✅ Supporting exploratory analysis to detect potential root causes behind missing boxes and process inefficiencies.

The study was conducted using one week of real-world log data from **Eurotrade Munich Airport GmbH**.

---

## 🗂 Repository Structure

```
├── rawdata/                # Week-long raw log data (compressed)
├── result/                 # Output directory for parsed and transformed data
├── AKL_complete.csv        # Combined and cleaned dataset after transformation
├── alert_extract.py        # Script to extract and analyze alert messages
├── alert_patterns.txt      # Regex patterns for alert extraction
├── analysis.ipynb          # Jupyter Notebook with event count, NIO, and error analyses
├── combined_logs.py        # Script to combine multiple log files
├── extraction.py           # Core extraction and parsing script
```

---

## ⚙️ How to Use

1️⃣ **Clone the repository**
```bash
git clone https://github.com/hseptiani/iis-seminar.git
```

2️⃣ **Run the extraction and combination scripts**
```bash
python extraction.py
python combined_logs.py
python alert_extract.py
```

3️⃣ **Open the analysis notebook**
Launch Jupyter Notebook and open:
```
analysis.ipynb
```

Inside, you can explore:
- Event count distributions
- Unique event type analysis
- High-frequency failure loops (e.g., repeated `Execute RBG`)
- NIO case analysis (e.g., missing `mfs_id` warnings)
- System error patterns (e.g., Java `NullPointerException`)

---

## 📊 Key Findings (from Final Research Paper)

- **11,280 unique LEs (Ladeeinheiten / box IDs)** were processed.
- Most LEs had under 1,000 events; some outliers exceeded 30,000 events due to repeated failure attempts.
- The majority of LEs (61.85%) included seven distinct event types, indicating comprehensive process coverage.
- **462 LEs routed to NIO lanes** were linked to missing `mfs_id` warnings; others showed alternative failure paths.
- System-level Java errors (e.g., `NullPointerException`) were found in some Handle Request and Process Alert events.

---

## 🙌 Acknowledgments

We thank **Eurotrade Munich Airport GmbH** for providing real-world AKL data and supporting this exploratory research.

This project was developed as part of the IIS Seminar at **Friedrich-Alexander-Universität Erlangen-Nürnberg**, under the supervision of Prof. Dr. Martin Matzner, Annina Ließmann and Weixin Wang.

---

Authors: Evelina Ignatova, Hanna Septiani, Siddhant Chindhe
