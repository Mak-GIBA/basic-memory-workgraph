"""The workflow is now served by one discoverable Skill: design-research.

Pre-2.3.1 installations may contain five separately discoverable Codex shortcuts.
They are migrated by installer_commands.py only when ownership is verified and the
files are unmodified. All the functionality stays in the core scripts/references.
"""
LEGACY_COMMAND_NAMES = (
    'design-research-reassess', 'design-research-plan',
    'design-research-workstream', 'design-research-resume',
    'design-research-status',
)
COMMANDS = {}  # No newly installed companion Skills; one main user-facing entry.


def assets():
    return {}
