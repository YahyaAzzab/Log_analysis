import re


def extract(row: str):
    pattern = re.compile(
        r'(?P<month>\w{3})\s(?P<day>\d{1,2})\s(?P<time>\d{2}:\d{2}:\d{2})\s.+:\s(?P<message>Invalid|Failed)')
    match = re.search(pattern, row)
    if match:
        print(match.groupdict())
# (?P<month>\w{3})\s(?P<day>\d{1,2})\s(?P<time>\d{2}:\d{2}:\d{2})\s.+:\s(?P<message>\w+)
# (?P<month>\w{3})\s(?P<day>\d{1,2})\s(?P<time>\d{2}:\d{2}:\d{2})\s.+:\s(?P<message>Invalid|Failed)