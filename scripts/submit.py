#!/usr/bin/env python3
import requests
import sys
import os
import argparse

URL = os.getenv("UPR_URL", "https://upr.cs.vsb.cz")
API_URL = URL + "/api/"

def command_submit(args):
    token = None
    try:
        with open(os.path.expanduser("~/.upr-token")) as f:
            token = f.read().strip()
    except FileNotFoundError:
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

def command_upgrade(args):
    res = requests.get("{}/upr.py".format(URL))
    if res.status_code == 200:
        path = os.path.realpath(__file__)
        with open(path, "w") as f:
            f.write(res.text)

par = argparse.ArgumentParser()
cmds = par.add_subparsers(dest='action', required=True)

p = cmds.add_parser('submit', help='submit solution to the task')
p.add_argument('task', help='task name')
p.add_argument('solution', help='location to source file(s)')

cmds.add_parser('upgrade', help='upgrade this tool')

args = par.parse_args()

if args.action:
    globals()["command_{}".format(args.action)](args)
