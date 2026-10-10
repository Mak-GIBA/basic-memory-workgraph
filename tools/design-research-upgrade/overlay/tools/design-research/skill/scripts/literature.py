"""Bounded, read-only academic API clients. Python standard library only.

Metadata is discovery evidence, not proof of a paper's findings or review status.
No arbitrary URL fetch, PDF download, shell execution, or credential persistence.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import email.utils
import hashlib
import functools
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASES = {"arxiv": "https://export.arxiv.org/api/query",
         "semantic-scholar": "https://api.semanticscholar.org/graph/v1",
         "crossref": "https://api.crossref.org/works"}
HOSTS = {urllib.parse.urlsplit(url).hostname for url in BASES.values()}
FIELDS = "title,abstract,url,year,publicationDate,publicationTypes,venue,citationCount,externalIds,openAccessPdf,authors"
INTERVALS = {"export.arxiv.org": 3.1, "api.semanticscholar.org": 1.1, "api.crossref.org": 1.0}
MAX_BYTES = 5_000_000
ARXIV_RE = re.compile(r"(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?\Z", re.I)


class ResearchError(Exception):
    pass


def schema_guard(func):
    @functools.wraps(func)
    def guarded(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (TypeError, KeyError, AttributeError, IndexError, ValueError) as exc:
            raise ResearchError("Unexpected provider response schema; do not treat this as a successful empty search.") from exc
    return guarded


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def checked_dir(path: Path, create=False) -> Path:
    path = Path(os.path.abspath(path.expanduser()))
    for part in [*reversed(path.parents), path]:
        if part.is_symlink():
            raise ResearchError("Refusing a symlink in the cache/output path.")
        if part.exists() and not part.is_dir():
            raise ResearchError("Cache/output parent is not a directory.")
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def check_file(path: Path) -> None:
    checked_dir(path.parent)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ResearchError("Refusing a non-regular file.")


def atomic_json(path: Path, data: dict) -> None:
    checked_dir(path.parent, create=True)
    check_file(path)
    fd, name = tempfile.mkstemp(prefix=".dr-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def clean_query(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 2000 or any(ord(c) < 32 for c in value):
        raise ResearchError("Query must contain 1-2000 characters without control characters.")
    return value


def doi_id(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", value, flags=re.I)
    # Preserve DOI punctuation; quote it safely when used in an API path.
    if not re.fullmatch(r"10\.\d{4,9}/[^\s]+", value) or any(ord(c) < 32 for c in value):
        raise ResearchError("Invalid DOI identifier.")
    return value.lower()


def arxiv_id(value: str) -> str:
    value = re.sub(r"^(?:https?://arxiv\.org/(?:abs|pdf)/|arxiv:)", "", value.strip(), flags=re.I)
    if value.endswith(".pdf"):
        value = value[:-4]
    if not ARXIV_RE.fullmatch(value):
        raise ResearchError("Invalid arXiv identifier.")
    return value


def semantic_id(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[a-fA-F0-9]{40}|CorpusId:\d+", value):
        return value
    if value.upper().startswith("DOI:"):
        return "DOI:" + doi_id(value[4:])
    if value.upper().startswith("ARXIV:"):
        return "ARXIV:" + arxiv_id(value[6:])
    raise ResearchError("Use a Semantic Scholar paper hash, CorpusId:number, DOI:..., or ARXIV:... identifier.")


class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
        if (new.scheme != "https" or new.hostname != old.hostname or new.port not in (None, 443)
                or new.username or new.password):
            raise ResearchError("Blocked a cross-origin or non-HTTPS API redirect.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def retry_delay(value: str | None, fallback: float) -> float:
    if value:
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                date = email.utils.parsedate_to_datetime(value)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=dt.timezone.utc)
                return max(0.0, (date - dt.datetime.now(dt.timezone.utc)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                pass
    return fallback


class Client:
    def __init__(self, cache_dir: Path, *, offline=False, allow_network=False,
                 ttl=86400, timeout=15, opener=None, sleep=time.sleep):
        self.cache_dir = checked_dir(cache_dir)
        self.offline, self.allow_network = offline, allow_network
        self.ttl, self.timeout = ttl, timeout
        self.opener = opener or urllib.request.build_opener(RestrictedRedirect())
        self.sleep = sleep

    @contextlib.contextmanager
    def rate_guard(self, host: str):
        # Shared across local processes using this cache; not a distributed limiter.
        try:
            import fcntl
        except ImportError as exc:
            raise ResearchError("Use Linux/macOS/WSL for the scholarly CLI (fcntl required).") from exc
        root = checked_dir(self.cache_dir / "rate", create=True)
        path = root / (host + ".lock")
        check_file(path)
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "r+", encoding="ascii") as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                raise ResearchError("Rate lock is not a regular file.")
            deadline = time.monotonic() + 30
            while True:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise ResearchError("Provider is busy in another local process; retry later.")
                    self.sleep(0.1)
            try:
                try:
                    last = float(f.read(128) or "0")
                except ValueError:
                    last = 0
                wait = min(INTERVALS[host], max(0, last + INTERVALS[host] - time.time()))
                if wait:
                    self.sleep(wait)
                yield
            finally:
                f.seek(0)
                f.truncate()
                f.write(str(time.time()))
                f.flush()
                fcntl.flock(f, fcntl.LOCK_UN)

    def get(self, url: str, *, provider: str) -> tuple[bytes, dict]:
        parts = urllib.parse.urlsplit(url)
        if (parts.scheme != "https" or parts.hostname not in HOSTS or parts.port not in (None, 443)
                or parts.username or parts.password):
            raise ResearchError("Only the fixed scholarly API HTTPS hosts are permitted.")
        if provider not in BASES or urllib.parse.urlsplit(BASES[provider]).hostname != parts.hostname:
            raise ResearchError("Provider and endpoint do not match.")
        cache = self.cache_dir / "responses" / (hashlib.sha256(url.encode()).hexdigest() + ".json")
        check_file(cache)
        try:
            if cache.exists() and cache.stat().st_size <= MAX_BYTES * 2:
                data = json.loads(cache.read_text("utf-8"))
                age = time.time() - data["fetched_epoch"]
                cached_body = data["body"].encode("utf-8")
                if len(cached_body) > MAX_BYTES or not isinstance(data["retrieved_at"], str):
                    raise ValueError("Invalid cached response")
                if self.offline or (0 <= age <= self.ttl):
                    return cached_body, {"from_cache": True, "stale": not (0 <= age <= self.ttl),
                                         "retrieved_at": data["retrieved_at"]}
        except (ValueError, KeyError, TypeError, OSError, AttributeError):
            pass
        if self.offline:
            raise ResearchError("offline_cache_miss: no usable cached response for this exact request")
        if not self.allow_network:
            raise ResearchError("Network is disabled. Use --allow-network for non-sensitive research queries, or --offline.")
        headers = {"User-Agent": "basic-memory-workgraph-design-research/1.0 (read-only academic discovery)",
                   "Accept": "application/atom+xml" if provider == "arxiv" else "application/json"}
        key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "") if provider == "semantic-scholar" else ""
        mail = os.environ.get("CROSSREF_MAILTO", "") if provider == "crossref" else ""
        if any(c in key + mail for c in "\r\n"):
            raise ResearchError("Credential/contact environment variable contains invalid control characters.")
        if key:
            headers["x-api-key"] = key
        if mail:
            if not re.fullmatch(r"[^\s@()]+@[^\s@()]+\.[^\s@()]+", mail):
                raise ResearchError("CROSSREF_MAILTO is not a valid contact email.")
            headers["User-Agent"] += f" (mailto:{mail})"
        for attempt in range(2):
            try:
                with self.rate_guard(parts.hostname):
                    request = urllib.request.Request(url, headers=headers, method="GET")
                    with self.opener.open(request, timeout=self.timeout) as response:
                        body = response.read(MAX_BYTES + 1)
                        if len(body) > MAX_BYTES:
                            raise ResearchError("API response exceeds the 5 MB safety limit.")
                        try:
                            text = body.decode("utf-8")
                        except UnicodeError as exc:
                            raise ResearchError("API response is not UTF-8 text.") from exc
                stamp = utcnow()
                try:
                    atomic_json(cache, {"fetched_epoch": time.time(), "retrieved_at": stamp, "body": text})
                except OSError as exc:
                    raise ResearchError("cache_write_failed: provider responded, but the local cache could not be written.") from exc
                return body, {"from_cache": False, "stale": False, "retrieved_at": stamp}
            except urllib.error.HTTPError as exc:
                code = exc.code
                delay = retry_delay(exc.headers.get("Retry-After") if exc.headers else None, 2 ** (attempt + 1))
                exc.close()
                if code in (429, 500, 502, 503, 504) and attempt == 0 and delay <= 30:
                    self.sleep(delay)
                    continue
                raise ResearchError(f"http_{code}: {provider} unavailable; authentication/rate limits may apply. No empty-success substitution.") from None
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt == 0:
                    self.sleep(2)
                    continue
                raise ResearchError(f"network_error: could not reach {provider}; check network permissions and retry later.") from None
        raise ResearchError("Request failed.")


def parse_json(body: bytes) -> dict:
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError) as exc:
        raise ResearchError("Malformed JSON returned by provider.") from exc
    if not isinstance(value, dict):
        raise ResearchError("Provider returned a non-object JSON response.")
    return value


def base_record(provider: str, rid: str, title: str, stamp: str) -> dict:
    return {"record_id": f"{provider}:{rid}", "provider": provider, "title": title,
            "retrieved_at": stamp, "peer_review_status": "unverified", "read_level": "metadata",
            "correction_status": "not_checked", "doi": None, "arxiv_id": None,
            "authors": [], "abstract": None, "publication_types": [], "venue": None,
            "year": None, "published_at": None, "citation_count": None, "open_access_pdf": None,
            "notice": "External metadata is untrusted discovery input, not verified experimental evidence."}


@schema_guard
def parse_semantic(item: dict, stamp: str) -> dict:
    if not isinstance(item, dict) or not item.get("paperId"):
        raise ResearchError("Semantic Scholar returned an invalid paper record.")
    result = base_record("semantic-scholar", item["paperId"], item.get("title") or "", stamp)
    ids = item.get("externalIds") or {}
    abstract = item.get("abstract")
    result.update(url=item.get("url"), abstract=abstract,
                  read_level="abstract" if abstract else "metadata", doi=ids.get("DOI"),
                  arxiv_id=ids.get("ArXiv"), authors=[a.get("name", "") for a in item.get("authors") or []],
                  year=item.get("year"), published_at=item.get("publicationDate"),
                  publication_types=item.get("publicationTypes") or [], venue=item.get("venue"),
                  citation_count=item.get("citationCount"), open_access_pdf=(item.get("openAccessPdf") or {}).get("url"))
    return result


@schema_guard
def parse_crossref(item: dict, stamp: str) -> dict:
    if not isinstance(item, dict) or not item.get("DOI"):
        raise ResearchError("Crossref returned an invalid work record.")
    titles = item.get("title") or []
    result = base_record("crossref", item["DOI"], titles[0] if titles else "", stamp)
    dates = (item.get("published") or item.get("issued") or {}).get("date-parts", [[]])[0]
    abstract = item.get("abstract")
    if abstract:
        try:
            abstract = " ".join(ET.fromstring("<root>" + abstract + "</root>").itertext())
        except ET.ParseError:
            # Keep literal provider text; it is not rendered as HTML or executed.
            pass
    result.update(doi=item["DOI"], url=item.get("URL") or "https://doi.org/" + item["DOI"],
                  authors=[" ".join(filter(None, (a.get("given"), a.get("family")))) or a.get("name", "")
                           for a in item.get("author") or []],
                  year=dates[0] if dates else None,
                  published_at="-".join(str(n).zfill(4 if i == 0 else 2) for i, n in enumerate(dates)) or None,
                  abstract=abstract, read_level="abstract" if abstract else "metadata",
                  publication_types=[item.get("type")] if item.get("type") else [],
                  venue=(item.get("container-title") or [None])[0], citation_count=item.get("is-referenced-by-count"),
                  relations=item.get("relation") or {}, updates=item.get("update-to") or [],
                  correction_status="metadata_only_not_exhaustive")
    return result


@schema_guard
def parse_arxiv(body: bytes, stamp: str) -> tuple[list[dict], int | None]:
    if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
        raise ResearchError("Unsafe XML declaration in arXiv response.")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ResearchError("Malformed Atom XML returned by arXiv.") from exc
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom",
          "o": "http://a9.com/-/spec/opensearch/1.1/"}
    if root.tag != "{http://www.w3.org/2005/Atom}feed":
        raise ResearchError("Expected an Atom feed from arXiv.")
    result = []
    for entry in root.findall("a:entry", ns):
        rawid = entry.findtext("a:id", "", ns)
        if "api/errors" in rawid:
            raise ResearchError("arXiv rejected the query; check advanced query syntax.")
        rid = arxiv_id(rawid.replace("http://arxiv.org/abs/", ""))
        paper = base_record("arxiv", rid, " ".join(entry.findtext("a:title", "", ns).split()), stamp)
        abstract = " ".join(entry.findtext("a:summary", "", ns).split())
        published = entry.findtext("a:published", "", ns)
        paper.update(arxiv_id=rid, url="https://arxiv.org/abs/" + rid,
                     abstract=abstract or None, read_level="abstract" if abstract else "metadata",
                     doi=entry.findtext("x:doi", None, ns), venue=entry.findtext("x:journal_ref", None, ns),
                     year=int(published[:4]) if published[:4].isdigit() else None,
                     published_at=published, updated_at=entry.findtext("a:updated", None, ns),
                     publication_types=["preprint"],
                     authors=[a.findtext("a:name", "", ns) for a in entry.findall("a:author", ns)])
        for link in entry.findall("a:link", ns):
            if link.attrib.get("type") == "application/pdf":
                paper["open_access_pdf"] = link.attrib.get("href")
        result.append(paper)
    total = root.findtext("o:totalResults", None, ns)
    return result, int(total) if total and total.isdigit() else None


def build_search(provider: str, query: str, limit: int, offset: int, year_from=None, year_to=None) -> str:
    clean_query(query)
    if provider not in BASES or not (1 <= limit <= 50) or not (0 <= offset <= 9950):
        raise ResearchError("Invalid provider, limit (1-50), or offset (0-9950).")
    for year in (year_from, year_to):
        if year is not None and not 1900 <= year <= 2100:
            raise ResearchError("Year filters must be between 1900 and 2100.")
    if year_from and year_to and year_from > year_to:
        raise ResearchError("year-from must not exceed year-to.")
    if provider == "arxiv":
        # Accept advanced arXiv syntax when the caller supplied a field qualifier.
        # Otherwise perform a literal all-fields phrase search instead of sending
        # unsupported generic web-search syntax to the arXiv API.
        if not re.search(r"(?:^|[ (])(?:ti|au|abs|co|jr|cat|rn|id|all):", query, re.I):
            literal = query.replace('\\', ' ').replace('\"', ' ').replace('"', ' ')
            literal = " ".join(literal.split())
            query = f'all:"{literal}"'
        if year_from or year_to:
            query = f"({query}) AND submittedDate:[{year_from or 1900}01010000 TO {year_to or 2100}12312359]"
        params = {"search_query": query, "start": offset, "max_results": limit,
                  "sortBy": "relevance", "sortOrder": "descending"}
        base = BASES[provider]
    elif provider == "semantic-scholar":
        params = {"query": query, "limit": limit, "offset": offset, "fields": FIELDS}
        if year_from or year_to:
            params["publicationDateOrYear"] = f"{year_from or ''}:{year_to or ''}"
        base = BASES[provider] + "/paper/search"
    else:
        params = {"query.bibliographic": query, "rows": limit, "offset": offset}
        filters = []
        if year_from:
            filters.append(f"from-pub-date:{year_from}-01-01")
        if year_to:
            filters.append(f"until-pub-date:{year_to}-12-31")
        if filters:
            params["filter"] = ",".join(filters)
        base = BASES[provider]
    return base + "?" + urllib.parse.urlencode(params)


@schema_guard
def search(client: Client, provider: str, query: str, limit=10, offset=0, year_from=None, year_to=None) -> dict:
    url = build_search(provider, query, limit, offset, year_from, year_to)
    body, meta = client.get(url, provider=provider)
    stamp = meta["retrieved_at"]
    if provider == "arxiv":
        papers, total = parse_arxiv(body, stamp)
        next_offset = offset + len(papers) if papers and total is not None and offset + len(papers) < total else None
    else:
        data = parse_json(body)
        if provider == "semantic-scholar":
            if not isinstance(data.get("data"), list):
                raise ResearchError("Semantic Scholar response is missing its data array.")
            papers = [parse_semantic(p, stamp) for p in data["data"]]
            total, next_offset = data.get("total"), data.get("next")
        else:
            message = data.get("message") or {}
            if not isinstance(message, dict) or not isinstance(message.get("items"), list):
                raise ResearchError("Crossref response is missing its items array.")
            papers = [parse_crossref(p, stamp) for p in message["items"]]
            total = message.get("total-results")
            next_offset = offset + len(papers) if papers and isinstance(total, int) and offset + len(papers) < total else None
    return {"provider": provider, "status": "ok", **meta, "total_reported": total,
            "next_offset": next_offset, "papers": papers[:limit]}


@schema_guard
def lookup(client: Client, provider: str, identifier: str) -> dict:
    if provider == "arxiv":
        url = BASES[provider] + "?" + urllib.parse.urlencode({"id_list": arxiv_id(identifier), "max_results": 1})
    elif provider == "crossref":
        url = BASES[provider] + "/" + urllib.parse.quote(doi_id(identifier), safe="")
    elif provider == "semantic-scholar":
        url = BASES[provider] + "/paper/" + urllib.parse.quote(semantic_id(identifier), safe="") + "?" + urllib.parse.urlencode({"fields": FIELDS})
    else:
        raise ResearchError("Unknown provider.")
    body, meta = client.get(url, provider=provider)
    if provider == "arxiv":
        papers, _ = parse_arxiv(body, meta["retrieved_at"])
    elif provider == "crossref":
        papers = [parse_crossref(parse_json(body).get("message"), meta["retrieved_at"])]
    else:
        papers = [parse_semantic(parse_json(body), meta["retrieved_at"])]
    return {"provider": provider, "status": "ok", **meta, "papers": papers}


@schema_guard
def links(client: Client, identifier: str, direction: str, limit=10, offset=0) -> dict:
    if direction not in ("references", "citations") or not 1 <= limit <= 50 or not 0 <= offset <= 9950:
        raise ResearchError("Invalid citation traversal parameters.")
    url = BASES["semantic-scholar"] + "/paper/" + urllib.parse.quote(semantic_id(identifier), safe="")
    url += "/" + direction + "?" + urllib.parse.urlencode({"fields": FIELDS, "limit": limit, "offset": offset})
    body, meta = client.get(url, provider="semantic-scholar")
    data = parse_json(body)
    if not isinstance(data.get("data"), list):
        raise ResearchError("Citation response is missing its data array.")
    key = "citedPaper" if direction == "references" else "citingPaper"
    papers = [parse_semantic(row[key], meta["retrieved_at"]) for row in data["data"]
              if isinstance(row, dict) and isinstance(row.get(key), dict) and row[key].get("paperId")]
    return {"provider": "semantic-scholar", "status": "ok", **meta, "direction": direction,
            "next_offset": data.get("next"), "papers": papers[:limit],
            "note": "One bounded page only. A citation is not an endorsement or independent replication."}


def mark_families(papers: list[dict]) -> list[dict]:
    """Tag overlapping identities, retain all versions and conflicting metadata."""
    parents = list(range(len(papers)))
    seen = {}

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    for i, paper in enumerate(papers):
        keys = []
        if paper.get("doi"):
            keys.append("doi:" + str(paper["doi"]).lower())
        if paper.get("arxiv_id"):
            keys.append("arxiv:" + re.sub(r"v\d+$", "", str(paper["arxiv_id"])))
        for key in keys:
            if key in seen:
                parents[root(i)] = root(seen[key])
            else:
                seen[key] = i
    for i, paper in enumerate(papers):
        paper["family_id"] = "F" + str(root(i) + 1)
    return papers
