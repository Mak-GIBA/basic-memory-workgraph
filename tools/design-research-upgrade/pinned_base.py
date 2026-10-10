"""Pinned, hash-verified base acquisition; data is decoded before any execution."""
from __future__ import annotations

import argparse

import base64

import hashlib

import io

import json

import os

from pathlib import Path, PurePosixPath

import re

import stat

import subprocess

import sys

import tempfile

import urllib.error

import urllib.parse

import urllib.request

import zipfile

import zlib

VERSION = '2.2.0'

BASE_COMMIT = 'd3f46e0d591b45cb2423317030a489b91566e891'

BASE_BLOB = 'a87ccbcf4ec20e43d8777c70af314f645f6e89e7'

BASE_PROGRAM_BLOB = '6dbae72463cad073e1a25649caf2656f8d8d8db9'

BASE_COMPRESSED_SHA256 = 'a8e2789764a5149873788e38784e9dd487b0da3a8abbd55c24b182211bfed9ee'

BUILDER_BLOB = '37ddcad53e5decf2ea294fa1d2e49a33e17a1a54'

BUNDLE_SHA256 = '3d20f8cfd1634fbb70e66a811e97771dc71413a39e7a97a5a4cbbff4a990bb73'

BUILDER_B64 = 'IyEvdXNyL2Jpbi9lbnYgcHl0aG9uMwoiIiJEZXRlcm1pbmlzdGljYWxseSBlbWJlZCBtYWludGFpbmVkIERlc2lnbiBSZXNlYXJjaCBzb3VyY2VzIGluIG9uZSBCYXNoIGZpbGUuIiIiCmZyb20gX19mdXR1cmVfXyBpbXBvcnQgYW5ub3RhdGlvbnMKCmltcG9ydCBhcmdwYXJzZQppbXBvcnQgYmFzZTY0CmltcG9ydCBoYXNobGliCmltcG9ydCBqc29uCmZyb20gcGF0aGxpYiBpbXBvcnQgUGF0aAppbXBvcnQgemxpYgoKUk9PVCA9IFBhdGgoX19maWxlX18pLnJlc29sdmUoKS5wYXJlbnQKVEFSR0VUID0gUk9PVC5wYXJlbnRzWzFdIC8gImluc3RhbGxfZGVzaWduX3Jlc2VhcmNoLnNoIgoKCmRlZiBidW5kbGUoKToKICAgIGZpbGVzID0ge30KICAgIGZvciBwYXRoIGluIHNvcnRlZCgoUk9PVCAvICJza2lsbCIpLnJnbG9iKCIqIikpOgogICAgICAgIGlmICJfX3B5Y2FjaGVfXyIgaW4gcGF0aC5wYXJ0cyBvciBwYXRoLnN1ZmZpeCA9PSAiLnB5YyI6CiAgICAgICAgICAgIGNvbnRpbnVlCiAgICAgICAgaWYgcGF0aC5pc19zeW1saW5rKCk6CiAgICAgICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoIlBheWxvYWQgc291cmNlIGNhbm5vdCBiZSBhIHN5bWxpbmsiKQogICAgICAgIGlmIG5vdCBwYXRoLmlzX2ZpbGUoKToKICAgICAgICAgICAgY29udGludWUKICAgICAgICBuYW1lID0gcGF0aC5yZWxhdGl2ZV90byhST09UIC8gInNraWxsIikuYXNfcG9zaXgoKQogICAgICAgIGRhdGEgPSBwYXRoLnJlYWRfYnl0ZXMoKQogICAgICAgIGZpbGVzW25hbWVdID0geyJzaGEyNTYiOiBoYXNobGliLnNoYTI1NihkYXRhKS5oZXhkaWdlc3QoKSwKICAgICAgICAgICAgICAgICAgICAgICAiZGF0YV9iNjQiOiBiYXNlNjQuYjY0ZW5jb2RlKGRhdGEpLmRlY29kZSgpLAogICAgICAgICAgICAgICAgICAgICAgICJtb2RlIjogMG83NTUgaWYgbmFtZSBpbgogICAgICAgICAgICAgICAgICAgICAgIHsic2NyaXB0cy9yZXNlYXJjaC5weSIsICJzY3JpcHRzL2hhcm5lc3MucHkiLCAic2NyaXB0cy9nYW4taGFybmVzcy5zaCJ9IGVsc2UgMG82NDR9CiAgICBwYXlsb2FkID0geyJzY2hlbWFfdmVyc2lvbiI6IDEsICJuYW1lIjogImRlc2lnbi1yZXNlYXJjaCIsICJ2ZXJzaW9uIjogIjIuMC4xIiwgImZpbGVzIjogZmlsZXN9CiAgICBkYXRhID0gemxpYi5jb21wcmVzcyhqc29uLmR1bXBzKHBheWxvYWQsIGVuc3VyZV9hc2NpaT1GYWxzZSwgc29ydF9rZXlzPVRydWUsCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgc2VwYXJhdG9ycz0oIiwiLCAiOiIpKS5lbmNvZGUoKSwgbGV2ZWw9OSkKICAgIHJldHVybiBwYXlsb2FkLCBkYXRhCgoKZGVmIHJlbmRlcigpOgogICAgXywgZGF0YSA9IGJ1bmRsZSgpCiAgICBwcm9ncmFtID0gKFJPT1QgLyAiaW5zdGFsbF9kZXNpZ25fcmVzZWFyY2gucHkiKS5yZWFkX3RleHQoInV0Zi04IikucmVwbGFjZSgKICAgICAgICAiX19QQVlMT0FEX1NIQTI1Nl9fIiwgaGFzaGxpYi5zaGEyNTYoZGF0YSkuaGV4ZGlnZXN0KCkpCiAgICBkb2xsYXIgPSBjaHIoMzYpCiAgICBoZWFkZXIgPSBmIiIiIyEvdXNyL2Jpbi9lbnYgYmFzaApzZXQgLWV1byBwaXBlZmFpbAojIEdlbmVyYXRlZCBieSB0b29scy9kZXNpZ24tcmVzZWFyY2gvYnVpbGRfaW5zdGFsbGVyLnB5OyBlZGl0IG1haW50YWluZWQgc291cmNlcy4KIyBObyBhcmd1bWVudHMgaW5zdGFsbHMuIC0tZHJ5LXJ1biBwbGFucyB3aXRob3V0IGNoYW5naW5nIHRoZSBkZXN0aW5hdGlvbi4KUFlUSE9OX0JJTj0ie2RvbGxhcn17e1BZVEhPTl9CSU46LXB5dGhvbjN9fSIKY29tbWFuZCAtdiAiJFBZVEhPTl9CSU4iID4vZGV2L251bGwgMj4mMSB8fCB7ewogIHByaW50ZiAnJXNcXG4nICdQeXRob24gMy4xMCsgaXMgcmVxdWlyZWQuJyA+JjIKICBleGl0IDEKfX0KIiRQWVRIT05fQklOIiAtICIkMCIgIiRAIiA8PCdfX0lOU1RBTExFUl9QWV9fJwoiIiIKICAgIGVuY29kZWQgPSBiYXNlNjQuYjY0ZW5jb2RlKGRhdGEpLmRlY29kZSgpCiAgICByZXR1cm4gKGhlYWRlciArIHByb2dyYW0gKyAiXG5fX0lOU1RBTExFUl9QWV9fXG5leGl0ICQ/XG5cbl9fREVTSUdOX1JFU0VBUkNIX1BBWUxPQURfX1xuIiArCiAgICAgICAgICAgICJcbiIuam9pbihlbmNvZGVkW246biArIDEwMF0gZm9yIG4gaW4gcmFuZ2UoMCwgbGVuKGVuY29kZWQpLCAxMDApKSArICJcbiIpCgoKZGVmIG1haW4oYXJndj1Ob25lKToKICAgIHBhcnNlciA9IGFyZ3BhcnNlLkFyZ3VtZW50UGFyc2VyKGRlc2NyaXB0aW9uPV9fZG9jX18pCiAgICBwYXJzZXIuYWRkX2FyZ3VtZW50KCItLWNoZWNrIiwgYWN0aW9uPSJzdG9yZV90cnVlIiwgaGVscD0iVmVyaWZ5IHRyYWNrZWQgZGlzdHJpYnV0aW9uIG1hdGNoZXMgc291cmNlcyIpCiAgICBwYXJzZXIuYWRkX2FyZ3VtZW50KCItLW91dHB1dCIsIHR5cGU9UGF0aCwgZGVmYXVsdD1UQVJHRVQpCiAgICBhcmdzID0gcGFyc2VyLnBhcnNlX2FyZ3MoYXJndikKICAgIHJlc3VsdCA9IHJlbmRlcigpCiAgICBpZiBhcmdzLmNoZWNrOgogICAgICAgIGlmIG5vdCBhcmdzLm91dHB1dC5pc19maWxlKCkgb3IgYXJncy5vdXRwdXQucmVhZF90ZXh0KCJ1dGYtOCIpICE9IHJlc3VsdDoKICAgICAgICAgICAgcGFyc2VyLmV4aXQoMSwgIkRlc2lnbiBSZXNlYXJjaCBkaXN0cmlidXRpb24gZGlmZmVycyBmcm9tIG1haW50YWluZWQgc291cmNlc1xuIikKICAgICAgICBwcmludCgiRGVzaWduIFJlc2VhcmNoIGRpc3RyaWJ1dGlvbiBtYXRjaGVzIG1haW50YWluZWQgc291cmNlcyIpCiAgICBlbHNlOgogICAgICAgIGFyZ3Mub3V0cHV0LndyaXRlX3RleHQocmVzdWx0LCAidXRmLTgiKQogICAgICAgIGFyZ3Mub3V0cHV0LmNobW9kKDBvNzU1KQogICAgICAgIHByaW50KCJCdWlsdCIsIGFyZ3Mub3V0cHV0Lm5hbWUpCgoKaWYgX19uYW1lX18gPT0gIl9fbWFpbl9fIjoKICAgIG1haW4oKQo='

MARKER = b'\n__DR_UPGRADE_BUNDLE__\n'

RAW_URL = ('https://raw.githubusercontent.com/Mak-GIBA/basic-memory-workgraph/'
           + BASE_COMMIT + '/install_design_research.sh')

API_URL = ('https://api.github.com/repos/Mak-GIBA/basic-memory-workgraph/contents/'
           'install_design_research.sh?ref=' + BASE_COMMIT)

MAX_BASE = 2 * 1024 * 1024

MAX_EXPANDED = 32 * 1024 * 1024

def git_blob(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def safe_relative(name: str) -> str:
    if not isinstance(name, str) or not name or '\\' in name or '\x00' in name:
        raise ValueError('Invalid package path')
    parts = name.rstrip('/').split('/')
    if any(p in ('', '.', '..') for p in parts) or PurePosixPath(name).is_absolute():
        raise ValueError('Unsafe package path: ' + name)
    if any(':' in p for p in parts):
        raise ValueError('Drive or stream path is not allowed')
    return '/'.join(parts)

def safe_output(path: Path) -> Path:
    path = Path(os.path.abspath(path.expanduser()))
    for node in [*reversed(path.parents), path]:
        if node.is_symlink():
            raise ValueError('Refusing output symlink: ' + str(node))
        if node != path and node.exists() and not node.is_dir():
            raise ValueError('Output parent is not a directory')
    return path

class TrustedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if (parsed.scheme != 'https' or parsed.hostname not in
                {'raw.githubusercontent.com', 'api.github.com'} or parsed.username or parsed.password):
            raise ValueError('Refusing redirect outside the pinned public source hosts')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def validate_base(data: bytes) -> bytes:
    if not data or len(data) > MAX_BASE or git_blob(data) != BASE_BLOB:
        raise ValueError('Base installer does not match the pinned Git blob; nothing installed')
    return data

def obtain_base(local: Path | None, offline: bool) -> bytes:
    if local is not None:
        if not local.is_file() or local.stat().st_size > MAX_BASE:
            raise ValueError('--base-installer must be a bounded existing file')
        return validate_base(local.read_bytes())
    if offline:
        raise ValueError('--offline requires --base-installer pointing to the pinned 2.0.1 file')
    opener = urllib.request.build_opener(TrustedRedirect())
    errors = []
    for url in (RAW_URL, API_URL):
        request = urllib.request.Request(url, headers={
            'User-Agent': 'DesignResearchInstaller/2.2.0',
            'Accept': 'application/vnd.github.raw+json',
        })
        try:
            with opener.open(request, timeout=30) as response:
                data = response.read(MAX_BASE + 1)
            # Some GitHub API deployments return JSON instead of the raw media type.
            if len(data) > MAX_BASE:
                raise ValueError('Base response exceeds the size limit')
            if data.lstrip().startswith(b'{'):
                meta = json.loads(data)
                if meta.get('encoding') != 'base64' or meta.get('sha') != BASE_BLOB:
                    raise ValueError('Unexpected GitHub Contents response')
                data = base64.b64decode(''.join(meta['content'].split()), validate=True)
            return validate_base(data)
        except (OSError, ValueError, KeyError, urllib.error.URLError) as exc:
            errors.append(type(exc).__name__ + ': ' + str(exc))
    raise ValueError('Pinned base download failed. Use --base-installer for offline installation. '
                     + ' / '.join(errors))

def unpack_base(raw: bytes, repo: Path) -> None:
    """Decode checked data; do not execute the downloaded Bash entry point."""
    validate_base(raw)
    text = raw.decode('utf-8')
    begin, end = "<<'__INSTALLER_PY__'\n", '\n__INSTALLER_PY__\n'
    if text.count(begin) != 1 or text.count(end) != 1:
        raise ValueError('Base installer program boundary changed')
    program = text.split(begin, 1)[1].split(end, 1)[0]
    expected_line = 'PAYLOAD_SHA256 = "' + BASE_COMPRESSED_SHA256 + '"'
    if program.count(expected_line) != 1:
        raise ValueError('Base payload checksum declaration changed')
    program = program.replace(expected_line, 'PAYLOAD_SHA256 = "__PAYLOAD_SHA256__"', 1)
    if git_blob(program.encode()) != BASE_PROGRAM_BLOB:
        raise ValueError('Base Python installer does not match the inspected source')
    payload_marker = b'\n__DESIGN_RESEARCH_PAYLOAD__\n'
    if raw.count(payload_marker) != 1:
        raise ValueError('Invalid base payload boundary')
    compressed = base64.b64decode(b''.join(raw.split(payload_marker, 1)[1].split()), validate=True)
    if hashlib.sha256(compressed).hexdigest() != BASE_COMPRESSED_SHA256:
        raise ValueError('Base compressed payload checksum mismatch')
    decoder = zlib.decompressobj()
    expanded = decoder.decompress(compressed, MAX_EXPANDED + 1)
    if len(expanded) > MAX_EXPANDED or not decoder.eof or decoder.unused_data:
        raise ValueError('Base expanded payload is invalid or oversized')
    payload = json.loads(expanded)
    if (payload.get('schema_version') != 1 or payload.get('name') != 'design-research'
            or payload.get('version') != '2.0.1' or not isinstance(payload.get('files'), dict)):
        raise ValueError('Unexpected base payload identity')
    decoded = {}
    for name, meta in payload['files'].items():
        name = safe_relative(name)
        content = base64.b64decode(meta['data_b64'], validate=True)
        if hashlib.sha256(content).hexdigest() != meta['sha256'] or meta['mode'] not in (0o644, 0o755):
            raise ValueError('Base file checksum or mode mismatch: ' + name)
        decoded[name] = (content, meta['mode'])
    required = {'SKILL.md', 'scripts/harness.py', 'scripts/report.py', 'scripts/gan-harness.sh',
                'references/protocol.md', 'references/roles.md', 'references/evidence-format.md'}
    if not required.issubset(decoded):
        raise ValueError('Incomplete base skill')
    builder = base64.b64decode(BUILDER_B64, validate=True)
    if git_blob(builder) != BUILDER_BLOB:
        raise ValueError('Embedded upstream builder checksum mismatch')
    root = repo / 'tools/design-research'
    root.mkdir(parents=True, exist_ok=True)
    (root / 'build_installer.py').write_bytes(builder)
    (root / 'install_design_research.py').write_text(program, encoding='utf-8')
    for name, (content, mode) in decoded.items():
        p = root / 'skill' / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
        p.chmod(mode)
    (repo / 'install_design_research.sh').write_bytes(raw)
