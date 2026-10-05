import csv
import json
import sys

seen = set()
counts = {'ok': 0, 'failed': 0}
total = 0
with open(sys.argv[1], encoding='utf-8', newline='') as source:
    reader = csv.DictReader(source)
    if reader.fieldnames != ['packet_id', 'status', 'bytes']:
        raise SystemExit('invalid header')
    for row in reader:
        ident = row['packet_id']
        status = row['status']
        amount = row['bytes']
        if not ident or ident in seen or status not in counts or not amount.isdigit():
            raise SystemExit('invalid row')
        seen.add(ident)
        counts[status] += 1
        total += int(amount)
print(json.dumps({**counts, 'bytes': total}, sort_keys=True))
