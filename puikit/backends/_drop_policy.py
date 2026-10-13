"""Which operation a file drop asks for, by the platform's drag modifiers.

Both desktop platforms let the user choose copy, move or link while dragging,
by holding a key — different keys on each. A drop target reports what was
asked for, or None when nothing was: the default depends on where the files
land (a move within one volume, a copy across volumes, as Finder and Explorer
both do), and only the app knows that. Pure functions, so the rules are
testable on any platform.
"""

from __future__ import annotations

# grfKeyState bits IDropTarget reports with each call (Windows).
MK_SHIFT = 0x0004
MK_CONTROL = 0x0008
MK_ALT = 0x0020


def drop_operation_macos(mods: frozenset) -> str | None:
    """Finder's: Command moves, Option copies, both together make an alias."""
    if "cmd" in mods and "alt" in mods:
        return "link"
    if "cmd" in mods:
        return "move"
    if "alt" in mods:
        return "copy"
    return None


def drop_operation_windows(key_state: int) -> str | None:
    """Explorer's: Shift moves, Ctrl copies, Ctrl+Shift or Alt makes a
    shortcut."""
    shift, ctrl = bool(key_state & MK_SHIFT), bool(key_state & MK_CONTROL)
    if (shift and ctrl) or key_state & MK_ALT:
        return "link"
    if shift:
        return "move"
    if ctrl:
        return "copy"
    return None


def drop_modifiers_windows(key_state: int) -> frozenset:
    mods = set()
    if key_state & MK_SHIFT:
        mods.add("shift")
    if key_state & MK_CONTROL:
        mods.add("ctrl")
    if key_state & MK_ALT:
        mods.add("alt")
    return frozenset(mods)
