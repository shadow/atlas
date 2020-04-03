#!/usr/bin/env python3
import sys
from bs4 import BeautifulSoup
soup = BeautifulSoup(sys.stdin.read(), 'html.parser')

for tag in soup.find_all("td"):
    print(tag.get_text())
