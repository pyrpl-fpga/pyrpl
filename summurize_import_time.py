# summarize_importtime_clean.py
# python -X importtime -m pyrpl 2> import.log
# needs to be run in a console before
import re
from collections import defaultdict

times = defaultdict(float)

with open("import.log") as f:
    for line in f:
        # Match lines like: "import time:      1246 |       1942 | encodings.idna"
        m = re.search(r'import time:\s*(\d+)\s*\|\s*\d+\s*\|\s*(\S+)', line)
        if m:
            t_total = float(m.group(1))  # total import time in ms
            mod = m.group(2).split('.')[0]  # top-level module
            times[mod] += t_total

# Print top 20 slowest modules
for mod, t in sorted(times.items(), key=lambda x: x[1], reverse=True)[:20]:
    print(f"{mod:15s} {t:8.1f} ms")
