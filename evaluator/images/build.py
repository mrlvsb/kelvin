#!/usr/bin/env python3
import argparse
import hashlib
import os
import subprocess
import logging
import shlex

from pathlib import Path
from typing import Dict, List, Set, Generator

logging.basicConfig(level=logging.INFO, format="%(message)s")

BASE_PATH = os.path.dirname(os.path.realpath(__file__))


class ImageBuilder:
    def __init__(self, base_path: str):
        self.base_path = base_path
        self.deps: Dict[str, List[str]] = {}
        self.images: Dict[str, str] = {}  # name -> path
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
                        parents.add(image_name)

            if not parents:
                logging.warning(f"Image {name} has no FROM instruction")
                continue

            if name not in self.deps:
                self.deps[name] = []

            for parent in parents:
                self.deps[name].append(parent)

    def _build_deps(self, deps: Dict[str, List[str]]) -> List[Set[str]]:
        """Original dependency resolution algorithm."""
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

    def get_build_order(self) -> Generator[List[str], None, None]:
        """Returns batches of images that can be built in parallel, in dependency order."""
        build_groups = self._build_deps(self.deps)
        for group in build_groups:
            # Filter solely for kelvin images as we do not need to build external deps
            kelvin_images = sorted([img for img in group if img.startswith("kelvin/")])
            if kelvin_images:
                yield kelvin_images

    def list_order(self):
        for batch in self.get_build_order():
            print(batch)

    def _inject_params(self, cache_arg: str, token: str, repo: str) -> str:
        if cache_arg and "type=gha" in cache_arg:
            parts = [cache_arg]
            if token and "ghtoken=" not in cache_arg:
                parts.append(f"ghtoken={token}")
            if repo and "scope=" not in cache_arg:
                parts.append(f"scope={repo}")
            return ",".join(parts)
        return cache_arg

    def _build_single_image(
        self, image: str, dry_run: bool, cache_from: str, cache_to: str, gh_token: str, gh_repo: str
    ):
        if image.startswith("kelvin/"):
            name = image.split("/")[1]
            logging.info(f"============ {name} ============")

            image_path = self.images[image]
            image_dir = os.path.dirname(image_path)

            with open(image_path, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()

            image_name_hash = f"{image}:{file_hash}"

            cmd = ["docker", "buildx", "build", "--load"]

            if cache_from:
                cmd.extend(["--cache-from", self._inject_params(cache_from, gh_token, gh_repo)])
            if cache_to:
                cmd.extend(["--cache-to", self._inject_params(cache_to, gh_token, gh_repo)])

            if image in self.deps:
                for parent in self.deps[image]:
                    if parent.startswith("kelvin/"):
                        # Inject build contexts for local dependencies (GitHub Actions)
                        # We map:
                        # 1. The exact string from FROM (e.g. kelvin/base)
                        # 2. The canonical latest tag (e.g. docker.io/kelvin/base:latest) to handle BuildKit normalization
                        cmd.extend(["--build-context", f"{parent}=docker-image://{parent}"])
                        if ":" not in parent:
                            cmd.extend(
                                [
                                    "--build-context",
                                    f"docker.io/{parent}:latest=docker-image://{parent}",
                                ]
                            )
                        else:
                            cmd.extend(
                                ["--build-context", f"docker.io/{parent}=docker-image://{parent}"]
                            )

            cmd.extend(["-t", image_name_hash, "-t", image, "."])

            if dry_run:
                logging.info(f"cd {image_dir} && {shlex.join(cmd)}")
            else:
                subprocess.check_call(cmd, cwd=image_dir)

    def build(
        self,
        dry_run: bool = False,
        cache_from: str = None,
        cache_to: str = None,
        gh_token: str = None,
        gh_repo: str = None,
    ):
        for batch in self.get_build_order():
            for image in batch:
                self._build_single_image(image, dry_run, cache_from, cache_to, gh_token, gh_repo)


def main():
    parser = argparse.ArgumentParser(description="Manage Kelvin Docker images")

    parser.add_argument("--list-order", action="store_true", help="Show the build dependency order")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    parser.add_argument("--cache-from", help="Cache source (e.g. type=gha)")
    parser.add_argument("--cache-to", help="Cache destination (e.g. type=gha,mode=max)")
    parser.add_argument("--gh-token", help="GitHub token for type=gha cache")
    parser.add_argument("--gh-repo", help="GitHub repository scope for type=gha cache")

    args = parser.parse_args()

    builder = ImageBuilder(BASE_PATH)

    if args.list_order:
        builder.list_order()
    else:
        builder.build(
            dry_run=args.dry_run,
            cache_from=args.cache_from,
            cache_to=args.cache_to,
            gh_token=args.gh_token,
            gh_repo=args.gh_repo,
        )


if __name__ == "__main__":
    main()
