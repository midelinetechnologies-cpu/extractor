import requests
import time
import re
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class URLResult:
    url: str
    is_working: bool
    status_code: Optional[int]
    response_time: Optional[float]
    error_message: Optional[str]
    content_type: Optional[str]
    server: Optional[str]
    redirect_url: Optional[str]

    @property
    def status_text(self) -> str:
        return "UP" if self.is_working else "DOWN"

    @property
    def response_time_str(self) -> str:
        if self.response_time is not None:
            return f"{self.response_time:.3f}s"
        return "N/A"


_URL_RE = re.compile(
    r"^https?://"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,}"
    r"(?::\d{1,5})?"
    r"(?:/[^\s]*)?$"
)

_TYPO_SCHEME_RE = re.compile(
    r"^(h[htps]{1,6}):/+", re.IGNORECASE
)


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return url

    # Fix common scheme typos (htps://, htp://, htpps://, etc.)
    m = _TYPO_SCHEME_RE.match(url)
    if m:
        rest = url[m.end():]
        typo = m.group(1).lower()
        scheme = "https" if "s" in typo else "http"
        url = f"{scheme}://{rest}"
    elif url.startswith("://"):
        url = "https" + url
    elif not url.startswith(("http://", "https://")):
        # Bare domain: www.example.com or example.com
        if url.startswith("www."):
            url = "https://" + url
        else:
            url = "https://" + url

    return url


def validate_url(url: str) -> bool:
    return bool(_URL_RE.match(url))


def check_single_url(
    url: str, timeout: int = 10, verify_ssl: bool = True
) -> URLResult:
    normalized_url = normalize_url(url)

    if not normalized_url or not validate_url(normalized_url):
        return URLResult(
            url=url,
            is_working=False,
            status_code=None,
            response_time=None,
            error_message="Invalid URL format",
            content_type=None,
            server=None,
            redirect_url=None,
        )

    try:
        start_time = time.time()
        response = requests.get(
            normalized_url,
            timeout=timeout,
            verify=verify_ssl,
            allow_redirects=True,
            headers={"User-Agent": "URL-Status-Checker/1.0 (Streamlit App)"},
        )
        response_time = time.time() - start_time

        content_type = response.headers.get("Content-Type", "Unknown")
        server = response.headers.get("Server", "Unknown")
        redirect_url = response.url if response.history else None
        is_working = response.status_code < 400

        return URLResult(
            url=normalized_url,
            is_working=is_working,
            status_code=response.status_code,
            response_time=response_time,
            error_message=None if is_working else f"HTTP {response.status_code}",
            content_type=content_type,
            server=server,
            redirect_url=redirect_url,
        )
    except requests.exceptions.Timeout:
        return URLResult(
            url=normalized_url, is_working=False, status_code=None,
            response_time=None, error_message=f"Timeout after {timeout}s",
            content_type=None, server=None, redirect_url=None,
        )
    except requests.exceptions.ConnectionError:
        return URLResult(
            url=normalized_url, is_working=False, status_code=None,
            response_time=None, error_message="Connection Error - Host unreachable",
            content_type=None, server=None, redirect_url=None,
        )
    except requests.exceptions.SSLError:
        return URLResult(
            url=normalized_url, is_working=False, status_code=None,
            response_time=None, error_message="SSL Certificate Error",
            content_type=None, server=None, redirect_url=None,
        )
    except requests.exceptions.TooManyRedirects:
        return URLResult(
            url=normalized_url, is_working=False, status_code=None,
            response_time=None, error_message="Too many redirects",
            content_type=None, server=None, redirect_url=None,
        )
    except requests.exceptions.RequestException as e:
        return URLResult(
            url=normalized_url, is_working=False, status_code=None,
            response_time=None, error_message=str(e)[:100],
            content_type=None, server=None, redirect_url=None,
        )


def check_multiple_urls(
    urls: List[str],
    timeout: int = 10,
    max_workers: int = 10,
    verify_ssl: bool = True,
    progress_callback=None,
) -> List[URLResult]:
    results = []
    total = len(urls)
    normalized_urls = [normalize_url(u) for u in urls]

    with ThreadPoolExecutor(max_workers=min(max_workers, total)) as executor:
        future_to_idx = {
            executor.submit(check_single_url, url, timeout, verify_ssl): i
            for i, url in enumerate(urls)
        }
        completed = 0
        for future in as_completed(future_to_idx):
            results.append((future_to_idx[future], future.result()))
            completed += 1
            if progress_callback:
                progress_callback(completed, total)

    results.sort(key=lambda pair: pair[0])
    return [r for _, r in results]


def parse_url_input(input_text: str) -> List[str]:
    if not input_text or not input_text.strip():
        return []

    parts = re.split(r"[,;\n\r]+", input_text)
    return [p.strip() for p in parts if p.strip()]
