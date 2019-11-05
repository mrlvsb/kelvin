import requests
import sys
import os
import argparse

API_URL = "http://127.0.0.1:8000/api/"

par = argparse.ArgumentParser()
par.add_argument('task', help='task name')
par.add_argument('solution', help='location to source file(s)')

args = par.parse_args()

token = None
try:
    with open(os.path.expanduser("~/.upr-token")) as f:
        token = f.read().strip()
except FileNotFoundError as e:
    print("Add your submit token to ~/.upr-token")
    exit(1)


files = {
    'solution': ('solution', open(args.solution), 'application/octet-stream'),
}

headers = {
    'Authorization': 'Bearer:  {}'.format(token)
}

res = requests.post("{}submit/{}".format(API_URL, args.task), files=files, headers=headers)
if res.status_code != 200:
    print("Error while submitting solution")
    print(res)
    print(res.text)
else:
    print(res.text)
