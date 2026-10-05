import csv
import sys
from collections import defaultdict

if len(sys.argv) != 2:
    raise SystemExit('usage: python3 sumcsv.py FILE.csv')
totals = defaultdict(int)
with open(sys.argv[1], newline='', encoding='utf-8') as source:
    for row in csv.DictReader(source):
        totals[row['category']] += int(row['amount'])
for category, amount in sorted(totals.items()):
    print(f'{category},{amount}')
