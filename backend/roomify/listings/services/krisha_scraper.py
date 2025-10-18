# -*- coding: utf-8 -*-
from __future__ import annotations
import json, re, time
from typing import Dict, List, Optional
from urllib.parse import urlparse, urljoin
import urllib.robotparser as robotparser

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
    "Accept-Language": "ru,en;q=0.9",
}
REQUEST_TIMEOUT = 20
RESPECT_DELAY_SEC = 1.0

KRISHA_BASE = "https://krisha.kz/a/show/"
KRISHA_ALLOWED_HOST = "krisha-photos.kcdn.online"
ALLOWED_IMAGE_ROOTS = ("/webp/", "/photos/", "/images/", "/img/")
ALLOWED_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")

def build_krisha_url(ad_id: int | str) -> str:
    return f"{KRISHA_BASE}{int(ad_id)}"

def accept_image_url(u: str) -> bool:
    if not u or not u.startswith("http"):
        return False
    pu = urlparse(u)
    if pu.scheme != "https":
        return False
    if pu.netloc != KRISHA_ALLOWED_HOST:
        return False
    if pu.path.startswith("/content/"):
        return False
    if not pu.path.startswith(ALLOWED_IMAGE_ROOTS):
        return False
    if not any(pu.path.lower().endswith(ext) for ext in ALLOWED_IMAGE_EXT):
        return False
    return True

def can_fetch(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")
    rp = robotparser.RobotFileParser()
    try:
        r = requests.get(robots_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if r.status_code >= 400:
            return True
        rp.parse(r.text.splitlines())
        return rp.can_fetch(HEADERS["User-Agent"], url)
    except requests.RequestException:
        return True

def fetch_html(url: str) -> str:
    time.sleep(RESPECT_DELAY_SEC)
    r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.text

def _clean(s: Optional[str]) -> Optional[str]:
    if not s:
        return s
    return re.sub(r"\s+", " ", s).strip()

def _jsonlds(soup: BeautifulSoup) -> List[dict]:
    out = []
    for tag in soup.find_all("script", type=lambda v: v and "ld+json" in v):
        raw = (tag.string or tag.get_text() or "").strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
            if isinstance(obj, list):
                out.extend(obj)
            else:
                out.append(obj)
        except json.JSONDecodeError:
            continue
    return out

def _og(soup: BeautifulSoup, key: str) -> Optional[str]:
    tag = soup.find("meta", property=key) or soup.find("meta", attrs={"name": key})
    return _clean(tag["content"]) if tag and tag.get("content") else None

def scrape_listing_by_id(ad_id: int | str) -> Dict:
    # 1) валидация и URL
    try:
        ad_id = int(str(ad_id).strip())
    except ValueError:
        raise ValueError("ad_id must be integer-like")
    url = build_krisha_url(ad_id)

    # 2) robots
    if not can_fetch(url):
        raise PermissionError("robots.txt forbids this URL")

    # 3) HTML
    html = fetch_html(url)
    soup = BeautifulSoup(html, "lxml")

    title = None
    desc = None
    images: List[str] = []

    # 4) JSON-LD (главный источник)
    for obj in _jsonlds(soup):
        if not isinstance(obj, dict):
            continue
        # графы
        if "@graph" in obj and isinstance(obj["@graph"], list):
            for sub in obj["@graph"]:
                if not isinstance(sub, dict):
                    continue
                title = title or _clean(sub.get("name") or sub.get("headline"))
                desc = desc or _clean(sub.get("description"))
                img = sub.get("image")
                if isinstance(img, list):
                    for i in img:
                        if isinstance(i, str) and accept_image_url(i):
                            images.append(i)
                elif isinstance(img, str) and accept_image_url(img):
                    images.append(img)
        # корневой объект
        title = title or _clean(obj.get("name") or obj.get("headline"))
        desc = desc or _clean(obj.get("description"))
        img = obj.get("image")
        if isinstance(img, list):
            for i in img:
                if isinstance(i, str) and accept_image_url(i):
                    images.append(i)
        elif isinstance(img, str) and accept_image_url(img):
            images.append(img)

    # 5) Open Graph / Twitter (fallback)
    ogimg = _og(soup, "og:image") or _og(soup, "twitter:image")
    if ogimg and accept_image_url(ogimg):
        images.append(ogimg)
    title = title or _og(soup, "og:title") or _og(soup, "twitter:title")
    desc = desc or _og(soup, "og:description") or _og(soup, "description")

    # 6) добираем <img>
    for imgtag in soup.find_all("img"):
        src = imgtag.get("src") or imgtag.get("data-src") or imgtag.get("data-lazy")
        if src and accept_image_url(src):
            images.append(src)

    # 7) итог
    images = list(dict.fromkeys(images))  # уникализируем, сохраняем порядок

    return {
        "title": title or f"Объявление №{ad_id} — Крыша",
        "description": desc or "",
        "images": images,
        "url": url,
    }
