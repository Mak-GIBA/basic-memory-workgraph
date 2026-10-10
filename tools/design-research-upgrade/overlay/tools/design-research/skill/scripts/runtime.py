"""Owned processes, isolated checks and source integrity for Design Research."""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import tempfile
import time
import urllib.parse
import uuid


class Blocked(Exception):
    pass


class Cancelled(Exception):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def log(message):
    print("[DR-GAN] " + message, flush=True)


def regular_path(path):
    path = Path(os.path.abspath(Path(path).expanduser()))
    for node in [*reversed(path.parents), path]:
        if node.is_symlink():
            raise Blocked(f"Refusing symlink path: {node}")
    return path


def relative(value):
    p = Path(value)
    if not value or p.is_absolute() or ".." in p.parts or "\\" in value or "\0" in value:
        raise Blocked(f"Unsafe relative path: {value!r}")
    return p


def atomic_json(path, value):
    path = regular_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex[:8])
    try:
        with temp.open("w", encoding="utf-8") as f:
            os.chmod(temp, 0o600)
            json.dump(sanitize_tree(value), f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def atomic_bytes(path, data):
    path = regular_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name+'.tmp-'+uuid.uuid4().hex[:8])
    try:
        with temp.open('xb') as stream:
            os.chmod(temp,0o600)
            stream.write(data)
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_command(argv, *, cwd=None, timeout=20):
    try:
        return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Blocked(f"Cannot execute {argv[0]}: {exc}") from exc


def codex_capabilities(project=None, *, smoke=True):
    checks = {"python": True, "codex": bool(shutil.which("codex"))}
    errors = []
    if checks["codex"]:
        result = checked_command(["codex", "exec", "--help"])
        checks["structured_exec"] = result.returncode == 0 and all(
            flag in result.stdout for flag in
            ("--json", "--output-schema", "--output-last-message", "--sandbox", "--ephemeral"))
        if smoke and checks["structured_exec"]:
            try:
                command = sandbox_command("read-only", False, ["/bin/true"])
                result = checked_command(command, cwd=project, timeout=15)
                checks["sandbox"] = result.returncode == 0
                if result.returncode:
                    errors.append(scrub(result.stderr[-800:]))
            except Blocked as exc:
                checks["sandbox"] = False
                errors.append(str(exc))
    return {"ready": all(checks.values()), "checks": checks, "errors": errors}


def sandbox_command(mode, network, argv):
    result = checked_command(["codex", "sandbox", "--help"])
    suffix = ["linux"] if "Commands:" in result.stdout and "linux" in result.stdout else []
    return ["codex", "-c", f'sandbox_mode="{mode}"', "-c",
            "sandbox_workspace_write.network_access=" + ("true" if network else "false"),
            "sandbox", *suffix, "--", *argv]


SKIP_DIRS = {".git", "node_modules", "__pycache__", ".next", ".cache", ".venv",
             "venv", "dist", "build", "test-results", "playwright-report", ".pytest_cache"}


def fingerprint(project, output):
    project, output = Path(project), Path(output)
    head = ""
    names = None
    if shutil.which("git"):
        result = checked_command(["git", "-C", str(project), "rev-parse", "HEAD"])
        head = result.stdout.strip() if result.returncode == 0 else ""
        if head:
            result = checked_command(["git", "-C", str(project), "ls-files", "-z",
                                      "--cached", "--others", "--exclude-standard"])
            if result.returncode:
                raise Blocked("Cannot inspect source files")
            names = sorted(set(result.stdout.split("\0")) - {""})
    if names is None:
        names = []
        for root, dirs, files in os.walk(project):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            names.extend((Path(root) / name).relative_to(project).as_posix() for name in files)
    excluded = output.relative_to(project).as_posix() + "/"
    files = {}
    for name in names:
        if name.startswith(excluded) or name == "docs/design-research/.gan.lock":
            continue
        path = project / relative(name)
        if path.is_symlink():
            files[name] = "symlink:" + os.readlink(path)
        elif path.is_file():
            files[name] = sha256(path) + ":" + str(path.stat().st_mode & 0o777)
        else:
            files[name] = "missing"
    return {"head": head, "files": files}


def changed_files(before, after):
    return sorted(k for k in before["files"].keys() | after["files"].keys()
                  if before["files"].get(k) != after["files"].get(k))


def assert_source(expected, project, output):
    actual = fingerprint(project, output)
    if actual != expected:
        raise Blocked("Source changed outside a declared fix; start a fresh audit/run. " +
                      ", ".join(changed_files(expected, actual)[:8]))


def sensitive_path(name):
    path = Path(name)
    return (any(part in {".codex", ".agents", ".ssh", ".aws", ".gnupg"} for part in path.parts)
            or any(part == ".env" or part.startswith(".env.") for part in path.parts)
            or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
            or path.name in {"auth.json", "credentials", ".npmrc", ".pypirc", ".netrc"})


def copy_source(project, destination, snapshot):
    destination.mkdir(parents=True, exist_ok=False)
    for name, value in snapshot["files"].items():
        if sensitive_path(name) or value == "missing":
            continue
        source = Path(project) / relative(name)
        if source.is_symlink():
            # Copies never follow source links into personal directories.
            continue
        dest = destination / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    # Existing dependencies remain outside the sandbox's writable root.
    for name in ("node_modules", ".venv", "venv"):
        source = Path(project) / name
        if source.is_dir() and not source.is_symlink():
            (destination / name).symlink_to(source, target_is_directory=True)


def preflight_commands(project, commands):
    """Preparation errors are discovered before expensive model roles/checks."""
    import shlex
    project = Path(project)
    for name in ("node_modules", ".venv", "venv"):
        if commands and (project / name).is_symlink():
            raise Blocked("Preparation: dependency symlink is not supported in isolated copies: " + name +
                          "; use a real local dependency directory or a system runtime, then start a new run")
    with tempfile.TemporaryDirectory(prefix="design-research-preflight-") as temp:
        env = test_environment(temp)
        for row in commands:
            if not isinstance(row.get("command"), str) or not row["command"].strip():
                raise Blocked("Preparation: empty check command")
            syntax = subprocess.run(["/bin/bash", "-n", "-c", row["command"]], env=env,
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
            if syntax.returncode:
                raise Blocked("Preparation: invalid check command syntax: " + scrub(syntax.stderr[-500:]))
            try:
                parts = shlex.split(row["command"].lstrip().splitlines()[0], comments=True)
            except (ValueError, IndexError):
                # Multiline quoted commands need the real sandbox check; never execute them here.
                continue
            if not parts:
                raise Blocked("Preparation: empty check command")
            executable = parts[0]
            # Shell constructs/assignments need the existing runtime sandbox checks.
            if "=" in executable or executable in {"if", "for", "while", "cd", "export", "test", "["}:
                continue
            if "/" in executable:
                if Path(executable).is_absolute():
                    candidate = Path(executable)
                else:
                    candidate = project / executable
                if not candidate.is_file() or not os.access(candidate, os.X_OK):
                    raise Blocked("Preparation: check executable is missing or not executable: " + executable)
            elif not shutil.which(executable, path=env.get("PATH")):
                lookup = subprocess.run(["/bin/bash", "-c", 'type -t -- "$1"', "preflight", executable],
                                        env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
                if lookup.returncode or lookup.stdout.strip() != "builtin":
                    raise Blocked("Preparation: runtime is not available in the test environment: " + executable)
    return {"status": "ready", "scope": "Executable/dependency layout only; commands are not executed"}


def load_test_env(path):
    if not path:
        return {}
    path = regular_path(path)
    if not path.is_file():
        raise Blocked("Test environment file does not exist")
    result = {}
    for number, line in enumerate(path.read_text("utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, sep, value = line.partition("=")
        if not sep or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise Blocked(f"Invalid test environment assignment on line {number}")
        if key in {"HOME", "PATH", "CODEX_HOME", "PYTHONPATH", "LD_PRELOAD", "LD_LIBRARY_PATH"}:
            raise Blocked(f"Reserved test environment key: {key}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        # This format is literal. No shell interpolation, sourcing or eval.
        if "\0" in value:
            raise Blocked("Invalid test environment value")
        if key in {"NODE_ENV", "APP_ENV", "ENVIRONMENT"} and value.lower() in {"prod", "production"}:
            raise Blocked("Production environment is outside this harness")
        result[key] = value
    return result


def test_environment(root, explicit=None):
    root = Path(root)
    home = root / ".test-home"
    home.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k in
           {"PATH", "LANG", "LC_ALL", "TZ", "SYSTEMROOT", "TMPDIR"}}
    env.update({"HOME": str(home), "XDG_CACHE_HOME": str(home / ".cache"),
                "XDG_CONFIG_HOME": str(home / ".config"), "PYTHONDONTWRITEBYTECODE": "1",
                "NODE_ENV": "test", "CI": "1", "DR_GAN_CHILD": "1"})
    env.update(explicit or {})
    return env


def scrub(value, extra=None):
    value = str(value)
    secrets = []
    for key, item in {**os.environ, **(extra or {})}.items():
        if (re.search(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|DATABASE|DSN", key, re.I)
                and item and len(item) >= 4):
            secrets.append(item)
    for secret in sorted(set(secrets), key=len, reverse=True):
        value = value.replace(secret, "[REDACTED]")
    value = re.sub(r"(?i)(authorization[\"']?\s*[:=]\s*[\"']?(?:bearer\s+)?)[^\s,\"'}]+",
                   r"\1[REDACTED]", value)
    value = re.sub(r"(?i)((?:api[_-]?key|access[_-]?token|password|secret)[\"']?\s*[:=]\s*[\"']?)"
                   r"[^\s,\"'}]+", r"\1[REDACTED]", value)
    value = re.sub(r"(https?://|postgres(?:ql)?://|mysql://)([^/\s@]+)@",
                   r"\1[REDACTED]@", value)
    return value


def sanitize_tree(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key == "dossier_json" and isinstance(item, str) and item:
                try:
                    result[key] = json.dumps(sanitize_tree(json.loads(item)), ensure_ascii=False)
                    continue
                except ValueError:
                    pass
            result[key] = sanitize_tree(item)
        return result
    if isinstance(value, list):
        return [sanitize_tree(item) for item in value]
    return scrub(value) if isinstance(value, str) else value


def terminate_owned(process):
    # start_new_session gives this process its own group, including orphan children.
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=3)


def capture(argv, *, cwd, env, directory, timeout, label, heartbeat=20, input_text=None):
    directory = regular_path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {name: directory / f"{name}.log" for name in ("stdout", "stderr")}
    started = time.monotonic()
    result = {"started_at": now(), "timed_out": False, "truncated": False}
    # A file-backed stdin avoids both argv size limits and pipe write deadlocks.
    # Close the parent's anonymous file after spawn; the child owns its descriptor.
    prompt_input = None
    try:
        if input_text is not None:
            prompt_input = tempfile.TemporaryFile()
            prompt_input.write(input_text.encode("utf-8"))
            prompt_input.seek(0)
        process = subprocess.Popen(argv, cwd=cwd, env=env,
                                   stdin=prompt_input if prompt_input is not None else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
    finally:
        if prompt_input is not None:
            prompt_input.close()
    streams = {process.stdout: "stdout", process.stderr: "stderr"}
    selector = selectors.DefaultSelector()
    chunks = {name: bytearray() for name in paths}
    next_update = started + heartbeat
    try:
        for stream in streams:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)
        while selector.get_map() or process.poll() is None:
            stamp = time.monotonic()
            if stamp - started > timeout:
                result["timed_out"] = True
                terminate_owned(process)
                break
            if stamp >= next_update:
                log(f"{label}: running ({int(stamp - started)}s)")
                next_update = stamp + heartbeat
            for key, _ in selector.select(timeout=0.2):
                data = os.read(key.fileobj.fileno(), 65536)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                name = streams[key.fileobj]
                available = 4 * 1024 * 1024 - len(chunks[name])
                chunks[name].extend(data[:max(available, 0)])
                if len(data) > available:
                    result["truncated"] = True
        if process.poll() is None:
            process.wait(timeout=3)
        result["exit_code"] = process.returncode
    except BaseException:
        terminate_owned(process)
        raise
    finally:
        # A successful shell can leave a background process. It is still owned here.
        terminate_owned(process)
        selector.close()
        for stream in streams:
            stream.close()
        for name, data in chunks.items():
            paths[name].write_text(scrub(data.decode("utf-8", "replace"), env), "utf-8")
    result["finished_at"] = now()
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    result["paths"] = {name: str(path) for name, path in paths.items()}
    return result


def local_url(value):
    if not value:
        return ""
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise Blocked("--url must be a credential-free local HTTP(S) URL")
    host = parsed.hostname
    try:
        local = ipaddress.ip_address(host).is_loopback
    except ValueError:
        local = host == "localhost"
    if not local:
        raise Blocked("Use a local isolated test service with --url")
    return value
