"""
Multi-layer web scraper.
Primary: Obscura headless browser (anti-detect, JS-capable)
Fallback: httpx HTTP client (fast, minimal)
"""
import json
import random
import subprocess
import asyncio
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
import httpx
from config import (
    OBSCURA_BIN, OBSCURA_PORT, PAGE_FETCH_TIMEOUT,
    USER_AGENTS, CACHE_DIR, INTER_PAGE_DELAY
)


def _cache_key(url):
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _cache_get(url):
    key = _cache_key(url)
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        data = json.loads(cache_file.read_text())
        age = datetime.utcnow() - datetime.fromisoformat(data["cached_at"])
        if age < timedelta(hours=6):
            return data
    return None


def _cache_set(url, content, content_type="text/html"):
    key = _cache_key(url)
    cache_file = CACHE_DIR / f"{key}.json"
    cache_file.write_text(json.dumps({
        "url": url,
        "content": content,
        "content_type": content_type,
        "cached_at": datetime.utcnow().isoformat(),
    }))


class ObscuraScraper:
    def __init__(self, stealth=True):
        self.stealth = stealth
        self.server_proc = None

    def start(self):
        cmd = [OBSCURA_BIN, "serve", "--port", str(OBSCURA_PORT)]
        if self.stealth:
            cmd.append("--stealth")
        self.server_proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    def stop(self):
        if self.server_proc:
            self.server_proc.terminate()
            self.server_proc = None

    def fetch(self, url, timeout=PAGE_FETCH_TIMEOUT):
        cmd = [
            OBSCURA_BIN, "fetch", url,
            "--timeout", str(timeout),
            "--wait-until", "networkidle0",
            "--dump", "text"
        ]
        if self.stealth:
            cmd.append("--stealth")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
        if result.returncode == 0:
            return result.stdout
        raise RuntimeError(f"Obscura fetch failed: {result.stderr[:500]}")

    def fetch_markdown(self, url, timeout=PAGE_FETCH_TIMEOUT):
        cmd = [
            OBSCURA_BIN, "fetch", url,
            "--timeout", str(timeout),
            "--wait-until", "networkidle0",
            "--dump", "markdown"
        ]
        if self.stealth:
            cmd.append("--stealth")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
        if result.returncode == 0:
            return result.stdout
        raise RuntimeError(f"Obscura fetch failed: {result.stderr[:500]}")


class HttpxScraper:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = httpx.Client(
                timeout=PAGE_FETCH_TIMEOUT,
                headers={"User-Agent": random.choice(USER_AGENTS)},
                follow_redirects=True,
            )
        return self._client

    def fetch(self, url):
        cached = _cache_get(url)
        if cached:
            return cached["content"]

        r = self._get_client().get(url)
        r.raise_for_status()
        content = r.text
        _cache_set(url, content, r.headers.get("content-type", "text/html"))
        return content


class Scraper:
    def __init__(self, prefer_obscura=True):
        self.prefer_obscura = prefer_obscura
        self.obscura = None
        self.httpx = HttpxScraper()

        if prefer_obscura:
            try:
                self.obscura = ObscuraScraper(stealth=True)
            except Exception:
                self.obscura = None

    def fetch(self, url, prefer_text=False):
        if self.obscura:
            try:
                if prefer_text:
                    return self.obscura.fetch_markdown(url)
                return self.obscura.fetch(url)
            except Exception:
                pass
        return self.httpx.fetch(url)

    def fetch_multiple(self, urls, prefer_text=False):
        results = {}
        for url in urls:
            try:
                results[url] = self.fetch(url, prefer_text)
            except Exception as e:
                results[url] = f"[ERROR: {e}]"
        return results

    def google_search(self, query, num_results=5):
        search_url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        try:
            html = self.fetch(search_url)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            links = []
            for result in soup.select(".result__a")[:num_results]:
                href = result.get("href", "")
                title = result.get_text(strip=True)
                if href and href.startswith("http"):
                    links.append({"title": title, "url": href})
            return links
        except Exception:
            return []


async def scrape_urls(urls, use_obscura=False):
    scraper = Scraper(prefer_obscura=use_obscura)
    results = {}
    for i, url in enumerate(urls):
        try:
            results[url] = scraper.fetch(url, prefer_text=True)
        except Exception as e:
            results[url] = f"[ERROR: {e}]"
        if i < len(urls) - 1:
            await asyncio.sleep(INTER_PAGE_DELAY)
    return results
