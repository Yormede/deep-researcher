"""
Content extractor - strips HTML boilerplate, extracts readable text.
Implements a Readability-like algorithm in pure Python.
"""
import re
from html.parser import HTMLParser


class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []

    def handle_data(self, d):
        self.text.append(d)

    def get_data(self):
        return "".join(self.text)


def html_to_text(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()


def strip_html_tags(html):
    return re.sub(r"<[^>]+>", " ", html)


def clean_text(text):
    text = re.sub(r"\s*<style[^>]*>.*?</style>\s*", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\s*<script[^>]*>.*?</script>\s*", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = strip_html_tags(text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n\n".join(lines)
    return text


def extract_main_content(html, max_chars=15000):
    text = clean_text(html)
    paragraphs = [p for p in text.split("\n\n") if len(p) > 40]
    important = []
    for p in paragraphs:
        score = 0
        if re.search(r"\d{4}", p):
            score += 1
        if len(p) > 200:
            score += 1
        if re.search(r"(study|research|found|according|published|report)", p, re.IGNORECASE):
            score += 2
        if len(p.split()) > 30:
            score += 1
        important.append((score, p))

    important.sort(key=lambda x: -x[0])
    result = []
    total = 0
    for _, para in important[:30]:
        if total + len(para) > max_chars:
            result.append(para[:max_chars - total])
            break
        result.append(para)
        total += len(para)

    return "\n\n".join(result)


def extract_metadata(html):
    title = ""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = clean_text(title_match.group(1))

    description = ""
    desc_match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE
    )
    if not desc_match:
        desc_match = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
            html, re.IGNORECASE
        )
    if desc_match:
        description = desc_match.group(1)

    publish_date = ""
    date_match = re.search(
        r'<meta[^>]+(?:property|name)=["\'](?:article:published_time|date)["\']\s+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE
    )
    if date_match:
        publish_date = date_match.group(1)

    return {
        "title": title[:300] if title else "Untitled",
        "description": description[:500] if description else "",
        "publish_date": publish_date[:30] if publish_date else "",
    }
