#!/usr/bin/env python3
"""Advisory recall/save hooks. These hooks never write knowledge-graph notes."""

import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent.parent / "basic-memory-workgraph"
SIGNALS = re.compile(
    r"今後|次から|これからは|毎回|好み|覚えて|記憶して|教訓|再利用|再発防止|根本原因|"
    r"原因.{0,40}(?:確認|判明|特定)|"
    r"\b(?:remember|preference|from now on|next time|lesson|reusable|root cause)\b",
    re.IGNORECASE,
)
RECALL = """Before substantial work, search directly relevant Rules, Workflows,
Validations, and similar Cases in Basic Memory. Read promising notes and, when useful,
follow their graph context at depth 2 or 3. Compare conditions and exceptions before
applying a lesson. A graph path is potential relevance, not automatic applicability.
Current user instructions override older memory. Avoid exposing irrelevant private
memory. Briefly track reused Cases, applicable Rules/Workflows, and conditions that
do not apply; do not persist this tracking as a work diary.
"""


def read_object(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def state_path(event):
    identity = [event.get("session_id"), event.get("turn_id")]
    if not any(isinstance(value, str) and value for value in identity):
        return None
    digest = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
    return ROOT / "state" / f"{digest}.json"


def candidate(text):
    return isinstance(text, str) and bool(SIGNALS.search(text))


def evaluate(event, action):
    try:
        mode = read_object(ROOT / "config.json").get("mode", "smart")
        policy = (ROOT / "memory-policy.md").read_text(encoding="utf-8").strip()
        if mode not in ("smart", "always", "off") or not policy:
            raise ValueError("Missing policy or invalid mode")
    except (OSError, ValueError):
        if action == "recall":
            return {"hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "Basic Memory policy is unavailable. Skip automatic memory writes; explicit user save requests remain allowed.",
            }}
        return {}

    state = state_path(event)
    if action == "recall":
        # Store only a signal flag, never the user's prompt or an unsafe raw ID.
        if state:
            try:
                state.parent.mkdir(parents=True, exist_ok=True)
                state.write_text(json.dumps({"candidate": candidate(event.get("prompt"))}), encoding="utf-8")
            except OSError:
                pass  # Policy injection must still work without writable state.
        automatic = (
            "Automatic persistence is off. Only explicit user save requests may write."
            if mode == "off" else
            "Automatic persistence uses the admission criteria below. A Stop hook may request one evaluation; it never requires a write."
        )
        return {"hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": policy + "\n\n" + automatic + "\n\n" + RECALL,
        }}

    prompt_candidate = False
    if state:
        try:
            prompt_candidate = read_object(state).get("candidate") is True
        except (OSError, ValueError):
            pass
        try:
            state.unlink(missing_ok=True)
        except OSError:
            pass
    if event.get("stop_hook_active") or mode == "off":
        return {}
    if mode == "smart" and not (prompt_candidate or candidate(event.get("last_assistant_message"))):
        return {}
    return {
        "decision": "block",
        "reason": (
            "Evaluate Basic Memory persistence ONCE using the policy below. "
            "This is an evaluation request, not a requirement to write. "
            "If no candidate qualifies or the turn already saved the same knowledge, "
            "finish without writing. Respect plan/read-only modes: do not write there.\n\n"
            + policy
            + "\n\nAfter this one pass, finish normally; do not start another persistence pass."
        ),
    }


def main():
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
