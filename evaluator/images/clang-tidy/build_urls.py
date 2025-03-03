#!/usr/bin/env python3
import subprocess
import urllib.request
import urllib.error
import urllib.parse
import concurrent.futures
import logging
import re
import json
from typing import Tuple, Optional

logging.basicConfig(level=logging.DEBUG)


def get(url: str) -> str:
    logging.info("Downloading %s", url)
    try:
        with urllib.request.urlopen(url) as f:
            html = f.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        logging.exception(e)
        html = ""
    return html


def process(check: str) -> Tuple[str, Optional[str]]:
    logging.info("Processing %s", check)
    baseurl = "https://clang.llvm.org/extra/clang-tidy/checks/"
    prefixes = ["clang-analyzer"]
    matched = [prefix for prefix in prefixes if check.startswith(prefix)]
    if len(matched):
        matched.append(check.split(f"{matched[0]}-", 1)[1])
    else:
        matched = check.split("-", 1)
    baseurl += f"{matched.pop(0)}/"
    short_check = matched.pop(0)
    url = f"{baseurl}{short_check}.html"
    page = get(url)

    if page:
        m = re.search(r'<meta content="\d+;URL=([^"]+)', page)
        if m:
            url = urllib.parse.urljoin(
                ("" if m.group(1).startswith("http") else baseurl), m.group(1)
            )
    else:
        url = None

    return check, url


result = {}
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    jobs = []
    checks = subprocess.check_output(["clang-tidy", "--checks=*", "--list-checks"])
    for check in checks.decode("utf-8").strip().split("\n")[1:]:
        check = check.strip()
        jobs.append(executor.submit(process, check))

    for future in concurrent.futures.as_completed(jobs):
        check, url = future.result()
        result[check] = url

with open("urls.json", "w") as f:
    json.dump(result, f, indent=2)
