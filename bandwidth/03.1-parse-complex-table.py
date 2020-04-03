#!/usr/bin/env python3
import sys
from bs4 import BeautifulSoup
soup = BeautifulSoup(sys.stdin.read(), 'html.parser')

def keep_tag(tag):
    if 'col-city' in tag['class']:
        return True
    if 'col-download' in tag['class']:
        return True
    if 'col-upload' in tag['class']:
        return True
    return False


for tag in soup.find_all("td"):
    if not keep_tag(tag): continue
    print(tag.get_text())
