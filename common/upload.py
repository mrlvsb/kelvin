import os
import re
import stat
import zipfile
import tarfile
import py7zr
from os.path import basename, dirname
from typing import List, Tuple

import magic
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
    def __init__(self, file: UploadedFile):
        super().__init__()
        self.archive = zipfile.ZipFile(file, "r")

    def get_files(self) -> List[Tuple[str, zipfile.ZipInfo]]:
        return [(f.filename, f) for f in self.archive.filelist if not f.is_dir()]

    def upload_file(self, path: str, file, submit: Submit) -> str:
        self.check_file_type(file, zipfile.ZipInfo)

        target_path = submit.source_path(path)
        os.makedirs(dirname(target_path), exist_ok=True)
        self.archive.extract(path, path=submit.dir())
        self.count += 1
        return target_path

    def close(self) -> None:
        self.archive.close()


class TarUploader(Uploader):
    def __init__(self, file: UploadedFile):
        super().__init__()
        self.archive = tarfile.open(fileobj=file, mode="r")

    def get_files(self) -> List[Tuple[str, tarfile.TarInfo]]:
        return [(f.name, f) for f in self.archive.getmembers() if not f.isdir()]

    def upload_file(self, path: str, file, submit: Submit) -> str:
        self.check_file_type(file, tarfile.TarInfo)

        target_path = submit.source_path(path)
        os.makedirs(dirname(target_path), exist_ok=True)
        self.archive.extract(path, path=submit.dir(), filter="data")
        self.count += 1
        return target_path

    def close(self) -> None:
        self.archive.close()


class SevenZipUploader(Uploader):
    def __init__(self, file: UploadedFile):
        super().__init__()
        self.archive = py7zr.SevenZipFile(
            file.file,
            "r",
        )

    def __is_file(self, file: py7zr.py7zr.ArchiveFile):
        """
        Checks if an ArchiveFile is a regular file and not a link, directory or socket.
        py7zr library doesn't have this method available in stable versions at the moment.
        Source: https://github.com/miurahr/py7zr/blob/master/py7zr/py7zr.py
        """
        e = file._get_unix_extension()
        if e is not None:
            return stat.S_ISREG(e)
        return not (file.is_directory or file.is_symlink or file.is_junction or file.is_socket)

    def get_files(self) -> List[Tuple[str, py7zr.py7zr.ArchiveFile]]:
        return [(f.filename, f) for f in self.archive.files if self.__is_file(f)]

    def upload_file(self, path: str, file, submit: Submit) -> str:
        self.check_file_type(file, py7zr.py7zr.ArchiveFile)

        target_path = submit.source_path(path)
        os.makedirs(dirname(target_path), exist_ok=True)
        # https://py7zr.readthedocs.io/en/latest/api.html#py7zr.SevenZipFile.extract
        self.archive.reset()
        self.archive.extract(targets=[path], path=submit.dir())
        self.count += 1
        return target_path

    def close(self) -> None:
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
    uploader = None
    if len(paths) == 1:

        def reset_file() -> UploadedFile:
            """
            Returns first file, seeked to zero.
            This is required since checkers of file headers do not seek back.
            """
            files[0].seek(0)
            return files[0]

        if zipfile.is_zipfile(reset_file()):
            uploader = ZipUploader(reset_file())
        elif tarfile.is_tarfile(reset_file()):
            uploader = TarUploader(reset_file())
        elif py7zr.is_7zfile(reset_file().file):
            uploader = SevenZipUploader(reset_file())

    if uploader is None:
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
