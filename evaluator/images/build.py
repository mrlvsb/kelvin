#!/usr/bin/env python3
import os
import hashlib
import subprocess
from pathlib import Path

def build_deps(arg):
    d=dict((k, set(arg[k])) for k in arg)
    r=[]
    while d:
        # values not in keys (items without dep)
        t=set(i for v in d.values() for i in v)-set(d.keys())
        # and keys without value (items without dep)
        t.update(k for k, v in d.items() if not v)
        # can be done right away
        r.append(t)
        # and cleaned up
        d=dict(((k, v-t) for k, v in d.items() if v))
    return r


deps = {}
base_path = os.path.dirname(os.path.realpath(__file__))
for path in Path(base_path).rglob('Dockerfile'):
    name = 'kelvin/' + os.path.basename(os.path.dirname(path))

    parent = None
    with open(path) as f:
        for line in f:
            parts = line.strip().split(' ')
            if parts[0].upper() == 'FROM':
                parent = parts[1]
    if not parent:
        print(f"Image {name} has no FROM")
        exit(1)

    if name not in deps:
        deps[name] = []

    deps[name].append(parent)

for group in build_deps(deps):
	for image in group:
		if image.startswith('kelvin/'):
			name = image.split('/')[1]
			print(f"============ {name} ============")

			with open(os.path.join(base_path, name, "Dockerfile"), 'rb') as f:
				hash = hashlib.md5(f.read()).hexdigest()
			image_name = f"{image}:{hash}"
			cmd = ["docker", "build", "-t", image_name,  "-t", image, "."]
			p = subprocess.check_call(cmd, cwd=os.path.join(os.path.dirname(os.path.realpath(__file__)), name))
