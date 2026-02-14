#!/usr/bin/env python3
import argparse
import hashlib
import os
import subprocess
import shlex

from pathlib import Path
from typing import Generator

BASE_PATH = os.path.dirname(os.path.realpath(__file__))


class ImageBuilder:
    def __init__(self, base_path: str):
        self.base_path = base_path
        self.deps: dict[str, list[str]] = {}
        self.images: dict[str, str] = {}  # name -> path
        self._scan_images()

    def _scan_images(self):
        """Finds all Dockerfiles and builds the dependency graph."""
        for path in Path(self.base_path).rglob("Dockerfile"):
            name = "kelvin/" + os.path.basename(os.path.dirname(path))
            self.images[name] = str(path)

            parents = set()
            with open(path, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if parts and parts[0].upper() == "FROM":
                        # Handle multi-stage builds
                        image_name = parts[1]
                        if image_name.startswith("kelvin/") and image_name.endswith(":latest"):
                            image_name = image_name[:-7]
                        parents.add(image_name)

            if not parents:
                raise ValueError(f"Image {name} has no FROM instruction")

            if name not in self.deps:
                self.deps[name] = []

            for parent in parents:
                self.deps[name].append(parent)

    def _build_deps(self, deps: dict[str, list[str]]) -> list[set[str]]:
        """Dependency resolution algorithm."""
        d = dict((k, set(deps[k])) for k in deps)
        r = []
        while d:
            # values not in keys (items without dep)
            t = set(i for v in d.values() for i in v) - set(d.keys())
            # and keys without value (items without dep)
            t.update(k for k, v in d.items() if not v)
            # can be done right away
            r.append(t)
            # and cleaned up
            d = dict(((k, v - t) for k, v in d.items() if v))
        return r

    def get_build_order(self) -> Generator[list[str], None, None]:
        """Returns batches of images that can be built in parallel, in dependency order."""
        build_groups = self._build_deps(self.deps)
        for group in build_groups:
            # Filter solely for kelvin images as we do not need to build external deps
            kelvin_images = sorted([img for img in group if img.startswith("kelvin/")])
            if kelvin_images:
                yield kelvin_images

    def _build_single_image(self, image: str, dry_run: bool):
        if image.startswith("kelvin/"):
            name = image.split("/")[1]
            print(f"============ {name} ============")

            image_path = self.images[image]
            image_dir = os.path.dirname(image_path)

            with open(image_path, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()

            image_name_hash = f"{image}:{file_hash}"

            cmd = ["docker", "build", "-t", image_name_hash, "-t", f"{image}:latest", "."]

            if dry_run:
                print(f"cd {image_dir} && {shlex.join(cmd)}")
            else:
                subprocess.check_call(cmd, cwd=image_dir)

    def _get_all_parents(self, image: str) -> set[str]:
        """Returns all transitive kelvin/ parents of the given image, including itself."""
        result = {image}
        queue = [image]
        while queue:
            current = queue.pop()
            for parent in self.deps.get(current, []):
                if parent.startswith("kelvin/") and parent not in result:
                    result.add(parent)
                    queue.append(parent)
        return result

    def build(self, dry_run: bool = False, only: str | None = None):
        if only is not None:
            if only not in self.images:
                available = ", ".join(sorted(self.images.keys()))
                raise ValueError(f"Unknown image '{only}'. Available images: {available}")
            needed = self._get_all_parents(only)

        for batch in self.get_build_order():
            if only is not None:
                batch = [img for img in batch if img in needed]
            for image in batch:
                self._build_single_image(image, dry_run)


def main():
    parser = argparse.ArgumentParser(description="Manage Kelvin Docker images")

    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    parser.add_argument(
        "--image",
        default=None,
        help="Build only this image (and its parents). "
        "Use the short name (e.g. 'gcc') or full name (e.g. 'kelvin/gcc').",
    )

    args = parser.parse_args()

    builder = ImageBuilder(BASE_PATH)

    only = args.image
    if only is not None and not only.startswith("kelvin/"):
        only = f"kelvin/{only}"

    builder.build(dry_run=args.dry_run, only=only)


if __name__ == "__main__":
    main()
