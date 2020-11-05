import subprocess
import urllib.request
import concurrent.futures
import logging
import re
import json

logging.basicConfig(level=logging.DEBUG)

def get(url):
    cache_file = f"/tmp/cache_{url.replace('/', '')}"
    try:
        with open(cache_file) as f:
            return f.read()
    except FileNotFoundError as e:
        logging.info("Downloading %s", url)
        try:
            with urllib.request.urlopen(url) as f:
                html = f.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            logging.exception(e)
            html = ""
        with open(cache_file, "w") as f:
            f.write(html)
        return html

def process(check):
    logging.info("Processing %s", check)
    baseurl = 'https://clang.llvm.org/extra/clang-tidy/checks/'
    url = f'{baseurl}{check}.html'
    page = get(url)
    
    if page:
        m = re.search(r'<meta content="\d+;URL=([^"]+)', page)
        if m:
            url = ('' if m.group(1).startswith('http') else baseurl) + m.group(1)
    else:
        url = None

    return check, url

result = {}
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    jobs = []
    checks = subprocess.check_output(['clang-tidy', '--checks=*', '--list-checks'])
    for check in checks.decode('utf-8').strip().split('\n')[1:]:
        check = check.strip()
        jobs.append(executor.submit(process, check))

    for future in concurrent.futures.as_completed(jobs):
        check, url = future.result()
        result[check] = url

with open("urls.json", "w") as f:
    json.dump(result, f, indent=2)
