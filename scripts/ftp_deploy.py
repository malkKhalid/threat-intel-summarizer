"""Robust FTP/FTPS deploy for cPanel/Namecheap.

Tries explicit FTPS (ignoring self-signed certs), then falls back to plain FTP.
Prints clear diagnostics so failures are easy to debug in CI logs.

Environment variables:
    FTP_SERVER, FTP_USERNAME, FTP_PASSWORD, FTP_PORT (default 21),
    FTP_SERVER_DIR (default "/"), LOCAL_DIR (default ./data/reports)
"""

from __future__ import annotations

import ftplib
import os
import ssl
import sys
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name, default)
    return value.strip()


def connect(host: str, port: int, user: str, password: str) -> tuple[ftplib.FTP, str]:
    """Return (ftp, method). Try FTPS first, then plain FTP."""
    errors: list[str] = []

    # 1) Explicit FTPS with relaxed certificate verification.
    try:
        ctx = ssl._create_unverified_context()
        ftp = ftplib.FTP_TLS(context=ctx, timeout=60)
        ftp.connect(host, port)
        ftp.login(user, password)
        ftp.prot_p()
        return ftp, "FTPS (explicit, TLS data channel)"
    except Exception as exc:  # noqa: BLE001
        errors.append(f"FTPS failed: {type(exc).__name__}: {exc}")

    # 2) Plain FTP.
    try:
        ftp = ftplib.FTP(timeout=60)
        ftp.connect(host, port)
        ftp.login(user, password)
        return ftp, "FTP (plain)"
    except Exception as exc:  # noqa: BLE001
        errors.append(f"FTP failed: {type(exc).__name__}: {exc}")

    raise SystemExit("Could not connect to FTP:\n  - " + "\n  - ".join(errors))


def ensure_dir(ftp: ftplib.FTP, remote_dir: str) -> None:
    """Recursively create and enter remote_dir (relative to the FTP root)."""
    ftp.cwd("/")
    for part in [p for p in remote_dir.split("/") if p not in ("", ".")]:
        try:
            ftp.cwd(part)
        except ftplib.error_perm:
            ftp.mkd(part)
            ftp.cwd(part)


def upload_dir(ftp: ftplib.FTP, server_dir: str, local_dir: Path) -> int:
    root = server_dir.rstrip("/") or ""
    count = 0
    for path in sorted(local_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(local_dir).as_posix()
        remote = f"{root}/{rel}"
        parent = "/".join(remote.split("/")[:-1]) or "/"
        ensure_dir(ftp, parent)
        with path.open("rb") as handle:
            ftp.storbinary(f"STOR {path.name}", handle)
        print(f"  uploaded {rel} -> {remote}")
        count += 1
    return count


def main() -> int:
    host = _env("FTP_SERVER")
    user = _env("FTP_USERNAME")
    password = _env("FTP_PASSWORD")
    port = int(_env("FTP_PORT", "21") or "21")
    server_dir = _env("FTP_SERVER_DIR", "/") or "/"
    local_dir = Path(_env("LOCAL_DIR", "./data/reports"))

    if not host or not user or not password:
        print("ERROR: FTP_SERVER, FTP_USERNAME and FTP_PASSWORD are required.", file=sys.stderr)
        return 2
    if not local_dir.exists():
        print(f"ERROR: local dir not found: {local_dir}", file=sys.stderr)
        return 3

    print(f"Connecting to {host}:{port} as {user} ...")
    ftp, method = connect(host, port, user, password)
    print(f"Connected via {method}")
    try:
        print(f"Entering server dir: {server_dir!r}")
        ensure_dir(ftp, server_dir)
        print("Current remote directory:", ftp.pwd())
        count = upload_dir(ftp, server_dir, local_dir)
        print(f"Uploaded {count} file(s) successfully.")
    finally:
        try:
            ftp.quit()
        except Exception:  # noqa: BLE001
            ftp.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
