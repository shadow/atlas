#!/usr/bin/env python3
import sys
import csv

unique = set()

# Get all the unique (country_name, country_code) pairs from the GeoLite2 City
# CSV file
csv_in = csv.DictReader(sys.stdin)
for row in csv_in:
    code, name = row['country_iso_code'], row['country_name']
    code = code.lower()
    name = name.lower().replace(' ', '-')
    if not name or not code: continue
    unique.add((name, code))
# Convert to a list and sort it since humans might be looking at the output
unique = list(unique)
unique.sort()

# Then output
for item in unique:
    print(*item)
