# -*- coding: utf-8 -*-
"""
scraper.py
Минимальный, но устойчивый парсер страницы объявления krisha.kz.
Стратегия: robots.txt -> HTML -> JSON-LD -> OpenGraph -> видимые поля -> изображения.

Использование:
    python scraper.py "https://krisha.kz/a/show/XXXXXXX"
"""

import re
import json
import time
import sys
import typing as t
from dataclasses import dataclass, asdict
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
import urllib.robotparser as robotparser

from typing import Dict

def scrape_listing(url: str) -> Dict:
    """
    Точка входа для остального Django-кода.
    Возвращает обычный dict с ключами price, address, images и т.д.
    """
    listing = parse_krisha_listing(url)  # возвращает dataclass Listing
    return listing.to_dict()


# ----------------------------- Настройки -----------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
    "Accept-Language": "ru,en;q=0.9",
}
REQUEST_TIMEOUT = 20  # секунд
RESPECT_DELAY_SEC = 1.0  # пауза между запросами (вежливость)


# ----------------------------- Модель результата -----------------------------

@dataclass
class Listing:
    url: str
    title: t.Optional[str] = None
    price: t.Optional[str] = None
    currency: t.Optional[str] = None
    address: t.Optional[str] = None
    latitude: t.Optional[float] = None
    longitude: t.Optional[float] = None
    rooms: t.Optional[str] = None
    total_area_m2: t.Optional[float] = None
    living_area_m2: t.Optional[float] = None
    kitchen_area_m2: t.Optional[float] = None
    floor: t.Optional[str] = None           # "5 из 9" или "5/9"
    floors_total: t.Optional[str] = None
    year_built: t.Optional[str] = None
    description: t.Optional[str] = None
    images: t.List[str] = None

    def to_dict(self):
        d = asdict(self)
        # очистить пустые поля для красоты
        return {k: v for k, v in d.items() if v not in (None, [], "", {})}


# ----------------------------- Вспомогательные -----------------------------

def can_fetch(url: str) -> bool:
    """Проверка robots.txt: можно ли ходить по этому URL."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = urljoin(base, "/robots.txt")
    rp = robotparser.RobotFileParser()
    try:
        resp = requests.get(robots_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code >= 400:
            # Если robots.txt недоступен — трактуем аккуратно, но даём пройти (обычная практика),
            # либо верните False, если хотите быть максимально строгим.
            return True
        rp.parse(resp.text.splitlines())
        return rp.can_fetch(HEADERS["User-Agent"], url)
    except requests.RequestException:
        # В случае сетевой ошибки — по умолчанию разрешаем (или смените на False).
        return True


def fetch_html(url: str) -> str:
    time.sleep(RESPECT_DELAY_SEC)
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def find_all_json_ld(soup: BeautifulSoup) -> t.List[dict]:
    data = []
    for tag in soup.find_all("script", type=lambda v: v and "ld+json" in v):
        try:
            # могут быть несколько JSON в одном <script>
            txt = tag.string or tag.get_text() or ""
            txt = txt.strip()
            if not txt:
                continue
            obj = json.loads(txt)
            if isinstance(obj, list):
                data.extend(obj)
            else:
                data.append(obj)
        except json.JSONDecodeError:
            continue
    return data


def _first(*vals):
    for v in vals:
        if v is not None and v != "":
            return v
    return None


def _to_float(s: t.Optional[str]) -> t.Optional[float]:
    if not s:
        return None
    # заменить запятую на точку и вытащить число
    m = re.search(r"(\d+[.,]?\d*)", str(s).replace("\u00A0", " ").replace(" ", ""))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


# ----------------------------- Парсеры уровней -----------------------------

def parse_from_jsonld(ld_list: t.List[dict], listing: Listing) -> None:
    """
    Ищем в JSON-LD типы: RealEstateListing, Offer, Product, Place, Apartment и т. п.
    Забираем price, currency, address, geo, images, описание, заголовок.
    """
    images: t.List[str] = []
    for obj in ld_list:
        if not isinstance(obj, dict):
            continue

        typ = obj.get("@type") or obj.get("@graph") and "Graph"
        # Иногда данные лежат внутри @graph
        if "@graph" in obj and isinstance(obj["@graph"], list):
            parse_from_jsonld(obj["@graph"], listing)
            continue

        # Заголовок / описание
        listing.title = _first(listing.title, obj.get("name"), obj.get("headline"))
        listing.description = _first(listing.description, obj.get("description"))

        # Картинки
        if "image" in obj:
            if isinstance(obj["image"], list):
                images.extend([i for i in obj["image"] if isinstance(i, str) and accept_image_url(i)])
            elif isinstance(obj["image"], str) and accept_image_url(obj["image"]):
                images.append(obj["image"])

        # Цена через Offer/priceSpecification
        offer = obj.get("offers") or obj.get("offer") or {}
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        if isinstance(offer, dict):
            price = _first(offer.get("price"),
                           offer.get("priceSpecification", {}).get("price"))
            currency = _first(offer.get("priceCurrency"),
                              offer.get("priceSpecification", {}).get("priceCurrency"))
            listing.price = _first(listing.price, str(price) if price else None)
            listing.currency = _first(listing.currency, currency)

        # Адрес/гео
        addr = obj.get("address")
        if isinstance(addr, dict):
            formatted = _first(
                addr.get("streetAddress"),
                addr.get("addressLocality"),
                addr.get("addressRegion"),
                addr.get("addressCountry"),
                addr.get("address")
            )
            if formatted:
                listing.address = _first(listing.address, _clean_text(formatted))

        geo = obj.get("geo")
        if isinstance(geo, dict):
            lat = _to_float(geo.get("latitude"))
            lon = _to_float(geo.get("longitude"))
            listing.latitude = _first(listing.latitude, lat)
            listing.longitude = _first(listing.longitude, lon)

        # Площадь/комнаты иногда лежат в additionalProperty
        add_props = obj.get("additionalProperty") or obj.get("additionalProperties")
        if isinstance(add_props, list):
            for p in add_props:
                if not isinstance(p, dict):
                    continue
                name = _clean_text(str(p.get("name", ""))).lower()
                val = _clean_text(str(p.get("value", "")))
                if not name or not val:
                    continue
                if "комнат" in name or "rooms" in name:
                    listing.rooms = _first(listing.rooms, val)
                if "площад" in name or "area" in name:
                    # пробуем распознать разные типы площадей
                    if "жила" in name or "living" in name:
                        listing.living_area_m2 = listing.living_area_m2 or _to_float(val)
                    elif "кухн" in name or "kitchen" in name:
                        listing.kitchen_area_m2 = listing.kitchen_area_m2 or _to_float(val)
                    else:
                        listing.total_area_m2 = listing.total_area_m2 or _to_float(val)
                if "этаж" in name and "этажност" not in name:
                    listing.floor = _first(listing.floor, val)
                if "этажност" in name or "floors" in name:
                    listing.floors_total = _first(listing.floors_total, val)
                if "год" in name and "построй" in name:
                    listing.year_built = _first(listing.year_built, val)

    # Дописываем изображения
    if images:
        listing.images = list(dict.fromkeys((listing.images or []) + images))


def parse_from_opengraph(soup: BeautifulSoup, listing: Listing) -> None:
    def og(prop):  # helper
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        return _clean_text(tag["content"]) if tag and tag.get("content") else None

    listing.title = _first(listing.title, og("og:title"), og("twitter:title"))
    listing.description = _first(listing.description, og("og:description"), og("description"))
    img = og("og:image") or og("twitter:image")
    if img and accept_image_url(img):
        listing.images = list(dict.fromkeys((listing.images or []) + [img]))


def parse_from_visible_blocks(soup: BeautifulSoup, listing: Listing) -> None:
    """
    Хейуристики: ищем пары «лейбл : значение» в таблицах и списках,
    подтягиваем комнаты/площади/этажи/год.
    """
    pairs: list[tuple[str, str]] = []

    # 1) Таблицы <table>
    for table in soup.select("table"):
        for row in table.select("tr"):
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]
            if len(cells) == 2:
                pairs.append((cells[0], cells[1]))

    # 2) Списки dt/dd
    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            pairs.append((dt.get_text(" ", strip=True), dd.get_text(" ", strip=True)))

    # 3) Элементы с двоеточием
    for el in soup.find_all(text=re.compile(r".+:\s*")):
        txt = _clean_text(str(el))
        if ":" in txt and len(txt) < 80:
            val = el.parent.get_text(" ", strip=True).replace(txt, "").strip()
            label = txt.replace(":", "").strip()
            if val:
                pairs.append((label, val))

    # нормализация и раскладывание по полям
    for k, v in pairs:
        lk = _clean_text(k).lower()
        v = _clean_text(v)

        if not listing.rooms and ("комнат" in lk or "rooms" in lk):
            listing.rooms = v

        if ("общая площадь" in lk or "площадь" in lk or "area" in lk) and not listing.total_area_m2:
            listing.total_area_m2 = _to_float(v)

        if ("жилая площадь" in lk or "living area" in lk) and not listing.living_area_m2:
            listing.living_area_m2 = _to_float(v)

        if ("площадь кухни" in lk or "kitchen area" in lk) and not listing.kitchen_area_m2:
            listing.kitchen_area_m2 = _to_float(v)

        if ("этаж" in lk) and ("этажност" not in lk):
            listing.floor = _first(listing.floor, v)

        if ("этажност" in lk or "всего этажей" in lk or "floors" in lk):
            listing.floors_total = _first(listing.floors_total, v)

        if ("год постройки" in lk or "year built" in lk) and not listing.year_built:
            listing.year_built = v

        if ("адрес" in lk or "address" in lk) and not listing.address:
            listing.address = v

        if ("цена" in lk or "price" in lk) and not listing.price:
            listing.price = v

    # Заголовок/описание (если совсем пусто)
    if not listing.title:
        h1 = soup.find(["h1", "h2"])
        if h1:
            listing.title = _clean_text(h1.get_text(" ", strip=True))
    if not listing.description:
        # длинный блок описания часто лежит в <div> с большим текстом
        candidates = sorted(
            [div.get_text(" ", strip=True) for div in soup.find_all("div")],
            key=lambda s: len(s),
            reverse=True,
        )
        # берём «очень длинный» текст, но ограничим разумно
        if candidates and len(candidates[0]) > 300:
            listing.description = candidates[0][:1200]


def collect_more_images(soup: BeautifulSoup, listing: Listing) -> None:
    imgs = listing.images or []
    for imgtag in soup.find_all("img"):
        src = imgtag.get("src") or imgtag.get("data-src") or imgtag.get("data-lazy")
        if src and accept_image_url(src):
            imgs.append(src)

    ltag = soup.find("link", rel=lambda v: v and "image_src" in v)
    if ltag and accept_image_url(ltag.get("href", "")):
        imgs.append(ltag["href"])

    listing.images = list(dict.fromkeys(imgs))[:30]

KRISHA_IMG_HOSTS = {
    "krisha-photos.kcdn.online",
    # при желании добавьте другие допустимые хосты
}

KRISHA_ALLOWED_HOST = "krisha-photos.kcdn.online"

def accept_image_url(u: str) -> bool:
    """
    Пропускаем только HTTPS-изображения строго с домена krisha-photos.kcdn.online,
    исключая рекламные/контентные пути (/content/) и non-image ссылки.
    """
    if not u or not u.startswith("http"):
        return False

    pu = urlparse(u)

    # 1) Только https
    if pu.scheme != "https":
        return False

    # 2) Только нужный домен
    if pu.netloc != KRISHA_ALLOWED_HOST:
        return False

    # 3) Отсекаем контентные/рекламные изображения
    if pu.path.startswith("/content/"):
        return False

    # 4) Разрешаем только типичные корни фоток объявлений
    allowed_roots = ("/webp/", "/photos/", "/images/", "/img/")
    if not pu.path.startswith(allowed_roots):
        return False

    # 5) Должно быть изображение по расширению
    allowed_ext = (".jpg", ".jpeg", ".png", ".webp", ".gif")
    if not any(pu.path.lower().endswith(ext) for ext in allowed_ext):
        return False

    return True


# ----------------------------- Главная функция -----------------------------

def parse_krisha_listing(url: str) -> Listing:
    if not can_fetch(url):
        raise PermissionError("robots.txt запрещает доступ к этому URL")

    html = fetch_html(url)
    soup = BeautifulSoup(html, "lxml")

    lst = Listing(url=url)

    # 1) JSON-LD (schema.org)
    parse_from_jsonld(find_all_json_ld(soup), lst)

    # 2) OpenGraph / twitter
    parse_from_opengraph(soup, lst)

    # 3) Видимые блоки и таблицы (дополняем пробелы)
    parse_from_visible_blocks(soup, lst)

    # 4) Собираем больше фото
    collect_more_images(soup, lst)

    # Мини-нормализация «этаж/этажность», если только одно поле
    if lst.floor and not lst.floors_total:
        m = re.search(r"(\d+)\s*[\/|\\]\s*(\d+)", lst.floor)
        if m:
            lst.floor, lst.floors_total = m.group(1), m.group(2)

    return lst


# ----------------------------- CLI -----------------------------

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python scraper.py <URL_объявления>")
        sys.exit(1)
    url = sys.argv[1].strip()
    try:
        data = parse_krisha_listing(url).to_dict()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(2)
