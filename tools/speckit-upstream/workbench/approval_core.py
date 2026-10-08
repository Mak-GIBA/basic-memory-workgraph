"""Approval hashing and dependency-aware validity for upstream items.

This is a local workflow record, not cryptographic identity proof or access control.
"""
from __future__ import annotations
import json
from pathlib import Path
from .common import WorkbenchError, inside, sha

LEDGER_PATH = '.specify/workbench/approvals.jsonl'
DEPENDENCY_LINKS = {
    'derives_from','addresses','belongs_to','satisfies','verifies',
    'changes','depends_on','supports'
}
NON_APPROVAL_TYPES = {'evidence','issue','risk'}
EXCLUDED_HASH_FIELDS = {'status','approval','result','result_evidence'}
HASH_VERSION = 2

# All five workflows share a minimum upstream structure. An approved goal may
# explicitly justify omitting need/story; core requirement/design/verification
# coverage cannot be waived by an empty list or a configuration-only change.
READINESS_CATEGORIES = {
    'goal': {'goal'},
    'need': {'need'},
    'story': {'story'},
    'requirements': {'requirement','quality','interface','data','operation','constraint'},
    'design': {'design','decision'},
    'verification': {'verification'},
}
EXEMPTIBLE_CATEGORIES = {'need','story'}


def coverage_status(byid: dict[str, dict], states: dict[str, dict]) -> dict:
    active = [r for r in byid.values() if r.get('status') != 'retired']
    goals = [r for r in active if r.get('type') == 'goal']
    out = {}
    for category, types in READINESS_CATEGORIES.items():
        present = sorted(r['id'] for r in active if r.get('type') in types)
        exemptions = []
        if not present and category in EXEMPTIBLE_CATEGORIES and goals:
            for goal in goals:
                mapping = goal.get('readiness_exemptions', {})
                reason = mapping.get(category) if isinstance(mapping, dict) else None
                if (states.get(goal['id'], {}).get('state') == 'valid'
                        and goal.get('basis') == 'agreed'
                        and isinstance(reason, str) and reason.strip()):
                    exemptions.append({'id': goal['id'], 'reason': reason})
            # Do not let an unrelated goal silently waive coverage for the system.
            if len(exemptions) != len(goals):
                exemptions = []
        out[category] = {'ids': present, 'exemptions': exemptions,
                         'satisfied': bool(present or exemptions)}
    return out


def semantic_payload(row: dict) -> dict:
    """Fields whose meaning is covered by user approval.

    Approval metadata, lifecycle status, and verification execution results are excluded
    so recording an approval/result does not invalidate the approved plan itself.
    """
    return {
        k: v for k, v in row.items()
        if not k.startswith('_') and k not in EXCLUDED_HASH_FIELDS
    }


def hash_version(row: dict) -> int:
    return 3 if row.get('_section') is not None else HASH_VERSION


def item_hash(row: dict) -> str:
    payload = {
        'hash_version': hash_version(row),
        'item': semantic_payload(row),
        'document': {'file': row.get('_file'),
                     'prose_sha256': row.get('_prose_sha256')},
    }
    if hash_version(row) == 3:
        payload['document'].update(section=row['_section'], shared_prose_sha256=row['_shared_prose_sha256'])
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')
    return sha(body)


def dependency_hashes(row: dict, byid: dict[str, dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    links = row.get('links', {})
    if not isinstance(links, dict):
        return out
    for rel, targets in links.items():
        if rel not in DEPENDENCY_LINKS or not isinstance(targets, list):
            continue
        for target in targets:
            if isinstance(target, str) and target in byid:
                out[target] = item_hash(byid[target])
    return dict(sorted(out.items()))


def load_events(root: Path) -> list[dict]:
    path = inside(root, LEDGER_PATH)
    if not path.exists():
        return []
    if path.is_symlink() or not path.is_file():
        raise WorkbenchError('approval ledgerが通常ファイルではありません')
    events=[]
    for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            event=json.loads(line)
        except ValueError as exc:
            raise WorkbenchError(f'approval ledger {n}行目がJSONではありません') from exc
        if not isinstance(event, dict) or event.get('schema_version') != 1:
            raise WorkbenchError(f'approval ledger {n}行目が未対応形式です')
        if event.get('event') not in {'approve','revoke'} or not isinstance(event.get('id'), str):
            raise WorkbenchError(f'approval ledger {n}行目が不正です')
        events.append(event)
    return events


def latest_events(root: Path) -> dict[str, dict]:
    latest={}
    for event in load_events(root):
        latest[event['id']] = event
    return latest


def approval_states(root: Path, byid: dict[str, dict]) -> dict[str, dict]:
    """Return current approval validity for each item.

    Downstream approval becomes stale if an approved dependency changed or itself
    became stale through another dependency. Cycles are handled conservatively.
    """
    events=latest_events(root)
    memo: dict[str, dict] = {}

    def state(key: str, stack: tuple[str, ...]=()) -> dict:
        if key in memo:
            return memo[key]
        row=byid.get(key)
        if row is None:
            return {'state':'missing_item','reason':'item not found'}
        if row.get('status') == 'retired':
            out={'state':'retired','reason':'retired item'};memo[key]=out;return out
        event=events.get(key)
        if event is None:
            if row.get('status') == 'approved':
                out={'state':'legacy_unbound','reason':'approved status has no hash-bound ledger record'}
            else:
                out={'state':'missing','reason':'no approval event'}
            memo[key]=out;return out
        if event.get('event') == 'revoke':
            out={'state':'revoked','reason':'latest approval event is revoke','event':event};memo[key]=out;return out
        if row.get('status') != 'approved':
            out={'state':'status_mismatch','reason':'ledger says approve but document status is not approved','event':event};memo[key]=out;return out
        current=item_hash(row)
        if event.get('hash_version') != hash_version(row):
            out={'state':'legacy_unbound','reason':'approval predates Markdown prose binding; review and explicitly approve again','event':event};memo[key]=out;return out
        if event.get('item_hash') != current:
            out={'state':'stale_content','reason':'approved content changed','event':event,'current_hash':current};memo[key]=out;return out
        inline=row.get('approval',{})
        required=['by','reference','date','review_id','content_hash']
        if (not isinstance(inline,dict) or any(not isinstance(inline.get(k),str) or not inline[k].strip() for k in required)
                or inline.get('content_hash') != current or inline.get('review_id') != event.get('review_id')
                or inline.get('hash_version') != hash_version(row)
                or any(inline.get(k) != event.get(k) for k in ('by','reference','date'))):
            out={'state':'metadata_mismatch','reason':'document approval metadata does not match ledger','event':event};memo[key]=out;return out
        saved_deps=event.get('dependency_hashes',{})
        if not isinstance(saved_deps,dict):
            out={'state':'metadata_mismatch','reason':'invalid dependency hashes','event':event};memo[key]=out;return out
        current_deps=dependency_hashes(row,byid)
        if saved_deps != current_deps:
            out={'state':'stale_dependency','reason':'linked upstream/dependency content changed','event':event,
                 'saved_dependencies':saved_deps,'current_dependencies':current_deps};memo[key]=out;return out
        # Propagate staleness through the dependency graph even when the direct target text did not change.
        if key not in stack:
            for dep in current_deps:
                target=byid.get(dep,{})
                if target.get('type') in NON_APPROVAL_TYPES or target.get('status') == 'retired':
                    continue
                if dep in stack:
                    continue
                dep_state=state(dep,stack+(key,))
                if dep_state.get('state') != 'valid':
                    out={'state':'stale_dependency','reason':f'dependency {dep} approval is {dep_state.get("state")}',
                         'event':event,'dependency':dep,'dependency_state':dep_state.get('state')}
                    memo[key]=out;return out
        out={'state':'valid','reason':'hash-bound approval is current','event':event,
             'content_hash':current,'dependency_hashes':current_deps}
        memo[key]=out;return out

    for key in byid:
        state(key)
    return memo
