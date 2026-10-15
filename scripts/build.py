#!/usr/bin/env python3
"""Build a consolidated, sorted DNS-domain blocklist from public URL sources.

No external Python packages required. Designed for GitHub Actions and Pi-hole.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DOMAIN_RE = re.compile(r"(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
HOSTS_IP_RE = re.compile(r"^(?:[0-9a-fA-F:.]+)\s+(.+)$")
MAX_DOWNLOAD_BYTES = 80 * 1024 * 1024
UA = "Unified-DNS-Blocklist-Builder/1.0 (public-domain-lists)"


def valid_domain(value: str) -> str | None:
    value = value.strip().strip(".").lower()
    if not value or any(x in value for x in ("*", "/", "\\", "@", "?", ":", "[", "]")):
        return None
    try:
        value = value.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    if not DOMAIN_RE.fullmatch(value):
        return None
    try:
        ipaddress.ip_address(value)
        return None
    except ValueError:
        return value


def extract_domains(raw_line: str) -> list[str]:
    """Accept domain-only, hosts and domain-wide ABP rules; reject path rules."""
    line = raw_line.lstrip("\ufeff").strip()
    if not line or line.startswith(("#", "!", "[", "@@", "/", "{")):
        return []
    line = line.partition("#")[0].strip()
    if not line:
        return []

    if line.startswith("||"):
        # Adblock: ||ads.example.com^ or ||ads.example.com^$third-party.
        # Skip path-specific filters to avoid overblocking an entire hostname.
        suffix = line[2:]
        hostname = suffix.split("^", 1)[0]
        if "$" in hostname or "/" in hostname or "*" in hostname:
            return []
        found = valid_domain(hostname)
        return [found] if found else []

    fields = line.split()
    if len(fields) >= 2:
        try:
            ipaddress.ip_address(fields[0])
            result = [valid_domain(field) for field in fields[1:]]
            return [domain for domain in result if domain]
        except ValueError:
            return []

    if len(fields) == 1:
        found = valid_domain(fields[0])
        return [found] if found else []
    return []


def read_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def download_source(url: str, timeout: int = 35, attempts: int = 2) -> tuple[set[str], int]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Only HTTPS source URLs are allowed")
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": UA, "Accept": "text/plain,*/*;q=0.2"})
            with urlopen(request, timeout=timeout) as response:
                data = response.read(MAX_DOWNLOAD_BYTES + 1)
            if len(data) > MAX_DOWNLOAD_BYTES:
                raise ValueError("Source exceeds 80 MiB safety limit")
            text = data.decode("utf-8-sig", errors="replace")
            domains: set[str] = set()
            for line in text.splitlines():
                domains.update(extract_domains(line))
            if not domains:
                raise ValueError("Source did not contain recognizable domains")
            return domains, len(data)
        except (HTTPError, URLError, TimeoutError, OSError, UnicodeError, ValueError) as exc:
            error = exc
            if attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{type(error).__name__}: {error}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources", type=Path, default=ROOT / "sources.txt")
    ap.add_argument("--allowlist", type=Path, default=ROOT / "allowlist.txt")
    ap.add_argument("--output", type=Path, default=ROOT / "master-blocklist.txt")
    ap.add_argument("--report", type=Path, default=ROOT / "build-report.json")
    ap.add_argument("--min-success", type=float, default=0.75, help="Minimum successful source fraction")
    ap.add_argument("--min-retention", type=float, default=0.90, help="Reject output if 10%%+ smaller than previous")
    args = ap.parse_args()

    source_urls = list(dict.fromkeys(read_lines(args.sources)))
    if not source_urls or not 0 < args.min_success <= 1:
        ap.error("Need valid sources and a min-success fraction between 0 and 1")
    if not 0 < args.min_retention <= 1:
        ap.error("min-retention must be between 0 and 1")

    allowed: set[str] = set()
    if args.allowlist.exists():
        for item in read_lines(args.allowlist):
            result = valid_domain(item)
            if result:
                allowed.add(result)

    all_domains: set[str] = set()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(download_source, source): source for source in source_urls}
        for future in as_completed(futures):
            source = futures[future]
            try:
                domains, bytes_read = future.result()
                all_domains.update(domains)
                results.append({"url": source, "status": "ok", "domains": len(domains), "bytes": bytes_read})
                print(f"OK   {len(domains):>8,}  {source}", flush=True)
            except Exception as exc:
                results.append({"url": source, "status": "failed", "error": str(exc)})
                print(f"FAIL {source} -- {exc}", file=sys.stderr, flush=True)

    # An exact allowlist match excludes only that hostname (not subdomains).
    all_domains.difference_update(allowed)
    success = sum(r["status"] == "ok" for r in results)
    sorted_domains = sorted(all_domains)
    report = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_count": len(source_urls),
        "successful_sources": success,
        "failed_sources": len(source_urls) - success,
        "unique_domains": len(sorted_domains),
        "allowlisted_exact_domains": len(allowed),
        "sources": sorted(results, key=lambda entry: source_urls.index(entry["url"])),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if success / len(source_urls) < args.min_success:
        print("REFUSED: Too many upstream download failures. Existing master is preserved.", file=sys.stderr)
        return 1

    prior_count = 0
    if args.output.exists():
        prior_count = sum(1 for _ in args.output.open(encoding="utf-8"))
    if prior_count and len(sorted_domains) < prior_count * args.min_retention:
        print(f"REFUSED: New list shrank from {prior_count:,} to {len(sorted_domains):,}. Existing master preserved.", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as out:
        for domain in sorted_domains:
            out.write(domain + "\n")
    temporary.replace(args.output)
    print(f"DONE: {len(sorted_domains):,} unique domains; {success}/{len(source_urls)} sources OK")
    if success < len(source_urls):
        print("WARNING: Some source URLs failed; inspect build-report.json and repair sources.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
