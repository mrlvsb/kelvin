import logging
import shutil
from pathlib import Path
from typing import Set
from urllib.parse import urlparse

import bs4
import requests
from bs4 import Comment


logger = logging.getLogger("moss.local.result")


def download_moss_result(root_url: str, directory: Path):
    """
    Downloads a MOSS result from the MOSS website and stores all its HTML files
    locally, under the given `directory`.
    """
    logger.info(f"Downloading {root_url} from MOSS")

    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True, exist_ok=True)

    downloaded = set()
    download_recursively(root_url, root_url, directory, downloaded, name="index.html")


def load_url(url: str) -> bytes:
    return requests.get(url).content


def save_data(data: bytes, path: Path):
    with open(path, "wb") as f:
        f.write(data)


def get_link_and_name(url: str, root_url: str) -> (str, str):
    name = Path(urlparse(url).path).name
    is_absolute = url.startswith("/") or url.startswith("http")
    if is_absolute:
        return (url, name)
    url_dir = root_url[: root_url.rfind("/")]
    return (f"{url_dir}/{name}", name)


def normalize_document(page: bs4.BeautifulSoup):
    # Remove comments
    for element in page.find_all(lambda tag: isinstance(tag, Comment)):
        element.extract()

    def normalize_link(link: str) -> str:
        if "moss" in link:
            return link[link.rfind("/") + 1 :]
        return link

    # Remove MOSS links
    for element in page.find_all("a"):
        if element.has_attr("href"):
            element["href"] = normalize_link(element["href"])
    for element in page.find_all("img"):
        if element.has_attr("src"):
            element["src"] = normalize_link(element["src"])


def download_recursively(
    url: str,
    root_url: str,
    directory: Path,
    downloaded: Set[str],
    name: str,
):
    if url in downloaded:
        return

    data = load_url(url)
    downloaded.add(url)

    if name.endswith(".html"):
        page = bs4.BeautifulSoup(data, "html.parser")

        logger.info(f"Examining HTML page {root_url}/{name}")

        links = [
            t["src"] for t in page.find_all(lambda tag: "src" in tag.attrs or "SRC" in tag.attrs)
        ]
        for link in links:
            (link_url, link_name) = get_link_and_name(link, root_url)
            download_recursively(link_url, root_url, directory, downloaded, name=link_name)

        normalize_document(page)
        data = str(page).encode()
    logger.info(f"Saving {directory}/{name}")
    save_data(data, directory / name)
