#!/usr/bin/env python3
"""Advisory hooks with turn-scoped mode attestation; never write graph notes."""

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent / "basic-memory-workgraph"
SIGNALS = re.compile(
    r"今後|次から|これからは|毎回|好み|覚えて|記憶して|教訓|再利用|再発防止|根本原因|"
    r"原因.{0,40}(?:確認|判明|特定)|"
    r"commit|push|コミット|プッシュ|この形式で|この案で|元に戻|引き続き|あと.{0,20}だけ|修正|調整|フィードバック|改善|解決|うまくいった|期待どおり|成功事例|"
    r"もっと.{0,20}(?:短|長|詳|簡潔)|表にして|ではなく|じゃなく|その意味では|"
    r"\b(?:remember|preference|from now on|next time|lesson|reusable|root cause|"
    r"correction|feedback|instead|improved|resolved|worked|successful|adjust|shorter|"
    r"revise|not what I meant)\b",
    re.IGNORECASE,
)
RECALL = """Before drafting, search directly relevant Corrections, Rules, Workflows,
Validations, and similar Cases in Basic Memory using the current purpose, audience,
output type and constraints. For progressive Cases read the ordered steps and
assessments, checking integrity before reuse. Prefer matching context, then evidence
of actual adoption/reuse; do not equate an implicit signal with satisfaction.
A needs_review Case is not a positive precedent; inspect its sources and affected
Rules/Workflows under AUDIT.md. In Plan/read-only report concerns without writes.
Read promising notes and, when useful, follow their
real graph context at depth 2 or 3. Compare scope and exceptions before applying
an old desired output. A scoped correction is not a standing preference; a graph
path is potential relevance, not automatic applicability. An explicit correction
can show what was requested even if its outcome is unknown. Current instructions
always take precedence. Use applicable context in the initial output. Avoid exposing
irrelevant private memory or persisting a recall diary.
"""


def read_object(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def runtime():
    config = read_object(ROOT / "config.json")
    settings = {
        "mode": config.get("mode", "smart"),
        "caseMode": config.get("caseMode", "off"),
        "skillMode": config.get("skillMode", "review"),
        "correctionMode": config.get("correctionMode", "off"),
    }
    for key, allowed in (("mode", ("smart", "always", "off")),
                         ("caseMode", ("off", "reusable", "progressive")),
                         ("skillMode", ("off", "review", "auto")),
                         ("correctionMode", ("off", "scoped"))):
        if settings[key] not in allowed:
            raise ValueError("Invalid mode")
    policy = (ROOT / "memory-policy.md").read_text(encoding="utf-8").strip()
    if not policy:
        raise ValueError("Missing policy")
    return settings, policy


def state_path(event):
    identity = [event.get("session_id"), event.get("turn_id")]
    # A session-wide flag cannot safely identify the mode of a later turn.
    if not all(isinstance(value, str) and value for value in identity):
        return None
    digest = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
    return ROOT / "state" / f"{digest}.json"


@contextmanager
def state_lock():
    directory = ROOT / "state"
    if directory.is_symlink():
        raise ValueError("Symlinked hook state")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(directory / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def write_state(path, data):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(data, handle)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def take_state(path):
    if path is None:
        return {}
    with state_lock():
        try:
            if path.is_symlink():
                return {}
            return read_object(path)
        except (OSError, ValueError):
            return {}
        finally:
            path.unlink(missing_ok=True)


def candidate(text):
    return isinstance(text, str) and bool(SIGNALS.search(text))


def arm(ticket, token, mode, semantic_candidate=False):
    """Attestation by the agent, not automatic detection of collaboration mode."""
    if mode != "implementation" or not re.fullmatch(r"[a-f0-9]{64}", ticket):
        raise ValueError("Implementation mode and a valid current-turn ticket are required")
    config, _ = runtime()
    if config["mode"] == "off":
        raise ValueError("Automatic persistence is off")
    path = ROOT / "state" / f"{ticket}.json"
    with state_lock():
        if path.is_symlink():
            raise ValueError("Invalid hook state")
        state = read_object(path)
        expected = state.get("token")
        if (not isinstance(expected, str) or not secrets.compare_digest(expected, token)
                or state.get("version") != 1):
            raise ValueError("Invalid or stale token")
        state["armed"] = True
        state["candidate"] = state.get("candidate") is True or semantic_candidate
        write_state(path, state)


def evaluate(event, action):
    state = state_path(event)
    # Consume even on configuration failure, explicit Plan, off, or continuation.
    saved = take_state(state) if action == "save" else {}
    try:
        config, policy = runtime()
    except (OSError, ValueError):
        if action == "recall":
            take_state(state)
            return {"hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "Basic Memory policy is unavailable. Skip automatic memory writes; explicit user save requests remain allowed.",
            }}
        return {}

    mode = config["mode"]
    settings = (
        f"Effective Workgraph settings: auto={mode}, correction={config['correctionMode']}, "
        f"case={config['caseMode']}, skill={config['skillMode']}. "
        "auto=off disables ALL automatic corrections, cases and Skill review/creation. "
        "correction=scoped admits contextual user corrections even with unknown outcomes; "
        "correction=off allows Correction capture only on an explicit save request. "
        "case=off permits concrete case capture only on an explicit save request. "
        "case=progressive allows useful unfinished correction sequences and later adoption/reversal signals in one Case. "
        "skill=review permits review only; skill=auto authorizes reviewed, validated "
        "Workgraph-managed skill creation/registration. "
        f"Read {ROOT / 'templates/CORRECTIONS.md'} for correction capture/recall, "
        f"{ROOT / 'templates/CAPTURE.md'} for a case, "
        f"{ROOT / 'templates/AUDIT.md'} for integrity checking/repair, and "
        f"{ROOT / 'templates/SKILL_REVIEW.md'} for a workflow review. "
        "Use only available conversation evidence; do not read raw transcript logs "
        "or fabricate missing interaction steps."
    )

    # Codex 0.157.1 maps approval policy to default/bypassPermissions; neither
    # proves implementation mode. Explicit plan is an additional deny signal.
    blocked = event.get("permission_mode") == "plan" or event.get("stop_hook_active") is True
    if action == "recall":
        activation = "No current-turn token is available; the Stop hook will not request evaluation."
        if state and mode != "off" and not blocked:
            try:
                with state_lock():
                    token = secrets.token_hex(32)
                    write_state(state, {"version": 1, "token": token, "armed": False,
                                        "candidate": candidate(event.get("prompt"))})
                command = shlex.join([sys.executable, str(Path(__file__).resolve()), "arm",
                                      "--ticket", state.stem, "--token", token,
                                      "--mode", "implementation"])
                activation = (
                    "Before the final answer, confirm the ACTUAL active collaboration mode. "
                    "ONLY in implementation/default mode with writes allowed, run this command "
                    "to enable the current turn's Stop evaluation. NEVER run it in Plan/read-only "
                    "mode or a Stop-hook continuation; permission_mode does not prove the mode. "
                    "Append --candidate if you recognized a correction, adoption/reuse/reversal signal, memory error, or lesson "
                    "semantically, even without a keyword match. Do not print the token to the user.\n"
                    + command
                )
            except (OSError, ValueError):
                pass  # Recall is still available without writable hook state.
        else:
            take_state(state)
        automatic = (
            "Automatic persistence is off. Only explicit user save requests may write."
            if mode == "off" else
            "Automatic persistence follows admission criteria; the Stop hook evaluates at most once after implementation-mode attestation."
        )
        return {"hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": policy + "\n\n" + settings + "\n\n" + automatic + "\n\n" + RECALL + "\n" + activation,
        }}

    if (blocked or mode == "off" or saved.get("version") != 1
            or saved.get("armed") is not True or not isinstance(saved.get("token"), str)):
        return {}
    if mode == "smart" and not (saved.get("candidate") is True or candidate(event.get("last_assistant_message"))):
        return {}
    return {
        "decision": "block",
        "reason": (
            "Evaluate Basic Memory persistence ONCE using the policy below. "
            "This is an evaluation request, not a requirement to write. "
            "If no candidate qualifies or the turn already saved the same knowledge, "
            "finish without writing. Respect the CURRENT mode: if now Plan/read-only, "
            "do not write. Do not arm another token during this continuation.\n\n"
            + policy + "\n\n" + settings
            + "\n\nAfter this one pass, finish normally; do not start another persistence pass."
        ),
    }


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "arm":
        parser = argparse.ArgumentParser(description="Attest implementation mode for this turn only")
        parser.add_argument("--ticket", required=True)
        parser.add_argument("--token", required=True)
        parser.add_argument("--mode", choices=("implementation",), required=True)
        parser.add_argument("--candidate", action="store_true")
        args = parser.parse_args(sys.argv[2:])
        try:
            arm(args.ticket, args.token, args.mode, args.candidate)
        except (OSError, ValueError, TypeError):
            parser.exit(1, "Cannot enable evaluation: missing/invalid current-turn token, policy, or automatic mode.\n")
        print('{"armed": true}')
        return
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict) or len(sys.argv) != 2 or sys.argv[1] not in ("recall", "save"):
            raise ValueError("Invalid hook input")
        result = evaluate(event, sys.argv[1])
    except (OSError, ValueError, TypeError):
        result = {}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
