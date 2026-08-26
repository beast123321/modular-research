"""Safe media asset acquisition.

The default downloader rejects local/private destinations before network I/O
and validates redirect targets before following them.
"""
from __future__ import annotations

import hashlib
import ipaddress
from pathlib import Path
import socket
from typing import Iterable, Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler


def _reject_ip(ip_text: str) -> None:
    ip = ipaddress.ip_address(ip_text)
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        raise ValueError(f"media URL resolves to non-public address: {ip}")


def validate_public_media_url(url: str, *, resolve_dns: bool = True) -> None:
    parsed = urlparse(str(url))
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("media URL must use http or https")
    if not parsed.hostname:
        raise ValueError("media URL must include a hostname")
    host = parsed.hostname
    try:
        _reject_ip(host)
        is_literal = True
    except ValueError as exc:
        try:
            ipaddress.ip_address(host)
        except ValueError:
            is_literal = False
        else:
            raise exc
    if resolve_dns and not is_literal:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        if not infos:
            raise ValueError("media hostname did not resolve")
        for info in infos:
            _reject_ip(info[4][0])


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urljoin(req.full_url, newurl)
        validate_public_media_url(target)
        return super().redirect_request(req, fp, code, msg, headers, target)


def _default_fetcher(url: str):
    opener = build_opener(_SafeRedirectHandler())
    request = Request(url, headers={"User-Agent": "modular-research/2"})
    response = opener.open(request, timeout=30)
    return response


def _iter_chunks(source: Any, chunk_size: int = 1024 * 1024) -> Iterable[bytes]:
    if isinstance(source, (bytes, bytearray)):
        yield bytes(source)
        return
    if hasattr(source, "read"):
        try:
            while True:
                chunk = source.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            close = getattr(source, "close", None)
            if callable(close):
                close()
        return
    for chunk in source:
        if chunk:
            yield bytes(chunk)


def download_media(url: str, dest: str | Path, *, max_bytes: int = 100 * 1024 * 1024, fetcher=None, validate_url: bool = True) -> dict[str, Any]:
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if validate_url:
        validate_public_media_url(url)
    destination = Path(dest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".part")
    tmp.unlink(missing_ok=True)
    total = 0
    digest = hashlib.sha256()
    try:
        source = (fetcher or _default_fetcher)(url)
        with tmp.open("wb") as fh:
            for chunk in _iter_chunks(source):
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"media exceeds max_bytes={max_bytes}")
                digest.update(chunk)
                fh.write(chunk)
        tmp.replace(destination)
        return {"source_url": url, "local_path": str(destination), "byte_size": total, "sha256": digest.hexdigest(), "status": "downloaded"}
    except Exception:
        tmp.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise
