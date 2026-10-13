"""File clipboard contents — what ``Panel.get_clipboard_files`` returns."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClipboardFiles:
    """Files on the OS clipboard, as another application put them there (or
    this one).

    ``paths`` are local filesystem paths, in clipboard order. ``cut`` is True
    when the writer asked for the files to be *moved* on paste — Windows
    Explorer's Cut ("Preferred DropEffect" = move). macOS has no cut for
    files, so it is always False there; the app decides what a paste does."""

    paths: tuple[str, ...]
    cut: bool = False
