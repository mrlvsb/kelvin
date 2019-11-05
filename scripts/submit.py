#!/usr/bin/env python3
import requests
import sys
import os
import argparse

API_URL = "http://127.0.0.1:8000/api/"

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

par = argparse.ArgumentParser()
cmds = par.add_subparsers(dest='action', required=True)

p = cmds.add_parser('submit', help='submit solution to the task')
p.add_argument('task', help='task name')
p.add_argument('solution', help='location to source file(s)')

args = par.parse_args()

if args.action:
    globals()["command_{}".format(args.action)](args)