import os
import re
import zipfile
import py7zr
from os.path import basename, dirname
from typing import List

import magic
import tempfile
from pathlib import Path
from django.core.exceptions import SuspiciousOperation
from django.core.files.uploadedfile import UploadedFile

from common.models import Submit

mimedetector = magic.Magic(mime=True)

SUBMIT_DROPPED_MIMES = [
    "application/x-object",
    "application/x-pie-executable",
    "application/x-sharedlib",
]


class Uploader:
    def __init__(self):
        self.count = 0

    def get_files(self):
        raise NotImplementedError()

    def upload_file(self, path: str, file, submit: Submit):
        raise NotImplementedError()

    def close(self):
        pass

    def check_file_type(self, file, type):
        if not isinstance(file, type):
            raise Exception(f"Invalid file type {type(file)}")

class ZipUploader(Uploader):
    def __init__(self, file):
        super().__init__()
        self.archive = zipfile.ZipFile(file, "r")

    def get_files(self):
        return [(f.filename, f) for f in self.archive.filelist if not f.is_dir()]

    def upload_file(self, path: str, file, submit: Submit):
        self.check_file_type(file, zipfile.ZipInfo)

        target_path = submit.source_path(path)
        os.makedirs(dirname(target_path), exist_ok=True)

        self.archive.extract(path, path=submit.dir())
        self.count += 1
        return target_path

    def close(self):
        self.archive.close()


class SevenZUploader(Uploader):
    def __init__(self, file):
        super().__init__()
        self.archive = py7zr.sevenzipfile(file, mode="r")

    def get_files(self):
        return [(name, name) for name in self.archive.getnames()]

    def upload_file(self, path: str, file, submit: Submit):
        target_path = submit.source_path(path)
        os.makedirs(dirname(target_path), exist_ok=True)

        extracted = self.archive.read([path])
        with open(target_path, "wb") as f:
            f.write(extracted[path].read())

        self.count += 1
        return target_path

    def close(self):
        self.archive.close()


class FileUploader(Uploader):
    def __init__(self, paths, files):
        super().__init__()
        self.paths = paths
        self.files = files

    def get_files(self):
        return list(zip(self.paths, self.files))

    def upload_file(self, path: str, file, submit: Submit) -> str:
        self.check_file_type(file, UploadedFile)

        target_path = submit.source_path(path)
        os.makedirs(dirname(target_path), exist_ok=True)
        with open(target_path, "wb") as storage_file:
            for chunk in file.chunks():
                storage_file.write(chunk)
        self.count += 1
        return target_path


def store_uploaded_file(submit: Submit, uploader: Uploader, path: str, file):
    if path[0] == "/" or ".." in path.split("/"):
        raise SuspiciousOperation()

    target_path = uploader.upload_file(path, file, submit)

    mime = mimedetector.from_file(target_path)
    if mime in SUBMIT_DROPPED_MIMES:
        os.unlink(target_path)


IGNORED_FILEPATH_REGEX = re.compile(
    r"(__pycache__/)|(CMakeFiles/)|(\.git/)|(\.vscode/)|(\.cmake/)|(\.pyc$)|(bin/)|(obj/)"
)
MAX_UPLOAD_FILECOUNT = 200


def filter_files_by_filename(files):
    ignored_prefixes = set()

    # All files have to be traversed first, the correct order cannot be determined easily
    for path, _ in files:
        # This directory looks like a virtualenv, ignore it
        if basename(path) == "pyvenv.cfg":
            ignored_prefixes.add(dirname(path))

    def is_valid_path(path: str):
        if any(path.startswith(prefix) for prefix in ignored_prefixes):
            return False
        if IGNORED_FILEPATH_REGEX.search(path) is not None:
            return False
        return True

    return [(path, f) for (path, f) in files if is_valid_path(path)]


class TooManyFilesError(BaseException):
    pass


def upload_submit_files(submit: Submit, paths: List[str], files: List[UploadedFile]):
    if len(paths) == 1 and (get_extension(paths[0]) == ".zip" or get_extension(paths[0]) == ".7z"):
        if get_extension(paths[0]) == ".7z":
            uploader = SevenZUploader(files[0])
        else:
            uploader = ZipUploader(files[0])
    else:
        uploader = FileUploader(paths, files)

    try:
        files = uploader.get_files()
        files = [(os.path.normpath(path), f) for (path, f) in files]
        files = filter_files_by_filename(files)

        for path, file in files:
            if uploader.count >= MAX_UPLOAD_FILECOUNT:
                raise TooManyFilesError()
            store_uploaded_file(submit, uploader, path, file)
    finally:
        uploader.close()


def get_extension(path: str) -> str:
    return os.path.splitext(path)[1].lower()
