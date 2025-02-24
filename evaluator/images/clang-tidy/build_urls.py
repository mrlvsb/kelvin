import subprocess
import urllib.request
import urllib.error
import urllib.parse
import concurrent.futures
import logging
import re
import json
from pathlib import Path
from typing import Dict, Tuple

logging.basicConfig(level=logging.DEBUG)


def get(url: str) -> str:
    cache_file = f"/tmp/cache_{url.replace('/', '')}"
    try:
        with open(cache_file) as f:
            return f.read()
    except FileNotFoundError:
        logging.info("Downloading %s", url)
        try:
            with urllib.request.urlopen(url) as f:
                html = f.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            logging.exception(e)
            html = ""
        with open(cache_file, "w") as f:
            f.write(html)
        return html


def process(check: str) -> Tuple[str, str]:
    logging.info("Processing %s", check)
    baseurl = "https://clang.llvm.org/extra/clang-tidy/checks/"
    checks = list_checks()
    if check in checks and checks[check]:
        url = checks[check]
    else:
        url = f"{baseurl}{check}.html"
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


def list_checks() -> Dict[str, str]:
    f = Path("/tmp/cache_clangtidy_parsed_checks")
    if f.exists():
        with open(f, "r") as file:
            return json.load(file)

    logging.info("Downloading Clang-Tidy checks")
    baseurl = "https://clang.llvm.org/extra/clang-tidy/checks/"
    list_url = f"{baseurl}list.html"
    page = get(list_url)
    dct = {}

    if page:
        table = re.findall(r'<table class="docutils align-default">(.*?)</table>', page, re.DOTALL)
        if len(table) > 0:
            # Checks table
            tab = table[0]
            dct = {
                m.group(2): urllib.parse.urljoin(baseurl, m.group(1))
                for m in re.finditer(
                    r'<a class="reference internal" href="(.*?)"><span class="doc">(.*?)</span></a>',
                    tab,
                    re.DOTALL,
                )
            }
            if len(table) > 1:
                # Check aliases table
                tab = table[1]
                dct |= {
                    m.group(2): urllib.parse.urljoin(baseurl, m.group(1))
                    for m in re.finditer(
                        r'<tr class="row-.*?"><td><p><a class="reference internal" href="(.*?)"><span class="doc">(.*?)</span></a></p></td>',
                        tab,
                        re.DOTALL,
                    )
                }
    with open(f, "w") as file:
        json.dump(dct, file)
    return dct


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
