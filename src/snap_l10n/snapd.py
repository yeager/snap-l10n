#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Daniel Nylander <daniel@danielnylander.se>

"""Interface to snapd REST API via unix socket and snap filesystem inspection."""

import http.client
import json
import os
import glob
import socket
import configparser


SNAPD_SOCKET = "/run/snapd.socket"


class SnapdConnection(http.client.HTTPConnection):
    """HTTP connection over the snapd unix socket."""

    def __init__(self):
        super().__init__("localhost")

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(SNAPD_SOCKET)


def _snapd_get(path: str) -> dict:
    """Perform a GET request to the snapd API."""
    conn = SnapdConnection()
    conn.request("GET", path)
    resp = conn.getresponse()
    data = json.loads(resp.read().decode())
    conn.close()
    if data.get("type") == "error":
        raise RuntimeError(data.get("result", {}).get("message", "snapd error"))
    return data.get("result", data)


def get_installed_snaps() -> list[dict]:
    """Return list of installed snaps from snapd API."""
    return _snapd_get("/v2/snaps")


def _find_locale_files(snap_name: str) -> list[str]:
    """Find locale/language codes available in a snap's mount point."""
    languages = set()
    snap_mount = f"/snap/{snap_name}/current"
    if not os.path.isdir(snap_mount):
        return []

    # Check common locale paths
    locale_dirs = [
        os.path.join(snap_mount, "usr", "share", "locale"),
        os.path.join(snap_mount, "share", "locale"),
        os.path.join(snap_mount, "usr", "local", "share", "locale"),
    ]
    for locale_dir in locale_dirs:
        if os.path.isdir(locale_dir):
            for entry in os.listdir(locale_dir):
                lc_path = os.path.join(locale_dir, entry, "LC_MESSAGES")
                if os.path.isdir(lc_path) and os.listdir(lc_path):
                    languages.add(entry)

    return sorted(languages)


def _check_desktop_l10n(snap_name: str) -> dict | None:
    """Check .desktop files in the snap for translated Name/Comment fields.

    Returns None if no .desktop files, or a set of language codes found.
    """
    snap_mount = f"/snap/{snap_name}/current"
    patterns = [
        os.path.join(snap_mount, "**", "*.desktop"),
    ]
    desktop_files = []
    for pat in patterns:
        desktop_files.extend(glob.glob(pat, recursive=True))

    if not desktop_files:
        return None

    languages = set()
    for df in desktop_files:
        try:
            cp = configparser.RawConfigParser()
            cp.read(df, encoding="utf-8")
            if not cp.has_section("Desktop Entry"):
                continue
            for key in cp.options("Desktop Entry"):
                # Keys like Name[sv], Comment[de]
                if "[" in key and "]" in key:
                    lang = key.split("[")[1].rstrip("]")
                    if lang:
                        languages.add(lang.split(".")[0].split("@")[0])
        except Exception:
            continue

    return sorted(languages) if desktop_files else None


def get_snap_l10n_info(snap: dict) -> dict:
    """Build l10n info dict for a single snap."""
    name = snap.get("name", "")
    languages = _find_locale_files(name)
    desktop_l10n = _check_desktop_l10n(name)

    has_locale = len(languages) > 0
    has_desktop = desktop_l10n is not None and len(desktop_l10n) > 0

    if has_locale and has_desktop:
        status = "full"
    elif has_locale or has_desktop:
        status = "partial"
    else:
        status = "none"

    publisher = snap.get("publisher", {})
    if isinstance(publisher, dict):
        publisher_name = publisher.get("display-name") or publisher.get("username") or ""
    else:
        publisher_name = str(publisher) if publisher else ""

    return {
        "name": name,
        "version": snap.get("version", ""),
        "publisher": publisher_name,
        "languages": languages,
        "desktop_l10n": desktop_l10n,
        "status": status,
    }
