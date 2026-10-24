"""Local UTF-8 RSS 2.0 only. No fetching links, DTDs or external entities."""
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
import re
from xml.etree import ElementTree

from pydantic import ValidationError

from .models import NewsPayload

MAX_XML_BYTES = 1_048_576
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"


class TextOnly(HTMLParser):
    BLOCKED = {"script", "style", "iframe", "object", "template", "head", "svg", "noscript"}
    BREAKS = {"p", "div", "br", "li", "ul", "ol", "blockquote", "h1", "h2", "h3", "tr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.blocked = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCKED:
            self.blocked.append(tag)
        if not self.blocked and tag in self.BREAKS:
            self.parts.append(" ")

    def handle_startendtag(self, tag, attrs):
        if not self.blocked and tag in self.BREAKS:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if self.blocked:
            if tag == self.blocked[-1]:
                self.blocked.pop()
        elif tag in self.BREAKS:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.blocked:
            self.parts.append(data)


def clean_html(value):
    parser = TextOnly()
    parser.feed(value or "")
    parser.close()
    return " ".join("".join(parser.parts).split())


def parse_date(raw):
    if raw is None:
        return None, []
    try:
        try:
            date = parsedate_to_datetime(raw)
        except (ValueError, TypeError):
            date = datetime.fromisoformat(raw)
        if date.tzinfo is None or date.utcoffset() is None:
            raise ValueError("unknown timezone")
        return date.astimezone(timezone.utc), []
    except (ValueError, TypeError, OverflowError):
        return None, ["INVALID_PUBDATE"]


@dataclass
class Item:
    index: int
    payload: NewsPayload | None
    issues: list[str]


def read_rss(path: Path, source_name: str) -> list[Item]:
    with path.open("rb") as file:
        data = file.read(MAX_XML_BYTES + 1)
    if len(data) > MAX_XML_BYTES:
        raise ValueError("RSS exceeds 1 MiB")
    xml = data.decode("utf-8-sig")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)\b", xml, re.IGNORECASE):
        raise ValueError("DTD and entities are forbidden")
    root = ElementTree.fromstring(xml)
    channel = root.find("channel")
    if root.tag != "rss" or root.get("version") != "2.0" or channel is None:
        raise ValueError("Expected RSS 2.0 with a channel")
    language = channel.findtext("language")
    language = language.strip() if language is not None else None
    items = []
    for index, element in enumerate(channel.findall("item"), 1):
        title = clean_html(element.findtext("title"))
        content = clean_html(element.findtext(CONTENT)) or clean_html(element.findtext("description"))
        guid = element.findtext("guid") or None
        link = element.findtext("link")
        link = link.strip() or None if link is not None else None
        published_at, issues = parse_date(element.findtext("pubDate"))
        if not title or not content:
            items.append(Item(index, None, issues + ["MISSING_TITLE" if not title else "MISSING_CONTENT"]))
            continue
        if link is None and guid is None:
            items.append(Item(index, None, issues + ["NO_RELIABLE_IDENTITY"]))
            continue
        try:
            payload = NewsPayload(title=title, content=content, url=link, source_name=source_name,
                                  source_id=guid, published_at=published_at, language=language)
        except ValidationError as error:
            # Record field names only, not full texts, XML, URLs or server secrets.
            fields = sorted({str(e["loc"][0]) for e in error.errors()})
            items.append(Item(index, None, issues + ["INVALID_FIELDS:" + ",".join(fields)]))
        else:
            items.append(Item(index, payload, issues))
    return items
