"""The file clipboard (capability ``clipboard_files``): the Panel's three
calls, the base backend's harmless defaults, and the memory backend's
process-local store that app tests drive. The macOS and Windows
implementations touch the real OS clipboard; Windows' is covered in
test_windows_backend.py, macOS's by hand (a test must not overwrite the
user's clipboard)."""

from puikit import PROFILE_GUI_DESKTOP, PROFILE_TUI, ClipboardFiles, Panel
from puikit.backend import Backend
from puikit.backends.memory_backend import MemoryBackend


def test_profiles():
    assert PROFILE_GUI_DESKTOP.supports("clipboard_files")
    assert not PROFILE_TUI.supports("clipboard_files")


def test_base_backend_has_no_file_clipboard():
    class Bare(MemoryBackend):
        pass

    b = Bare()
    # The base implementation, not the memory backend's store.
    assert Backend.set_clipboard_files(b, ["/tmp/a"]) is False
    assert Backend.get_clipboard_files(b) is None
    assert Backend.clipboard_change_count(b) is None


def test_panel_round_trip_on_the_memory_backend():
    panel = Panel(MemoryBackend())
    before = panel.clipboard_change_count()
    assert panel.set_clipboard_files(["/tmp/a.txt", "/tmp/b.txt"], cut=True) is True
    assert panel.get_clipboard_files() == ClipboardFiles(("/tmp/a.txt", "/tmp/b.txt"), cut=True)
    assert panel.clipboard_change_count() != before


def test_writing_text_replaces_the_files():
    panel = Panel(MemoryBackend())
    panel.set_clipboard_files(["/tmp/a.txt"])
    count = panel.clipboard_change_count()
    panel.set_clipboard("hello")
    assert panel.get_clipboard_files() is None
    assert panel.get_clipboard() == "hello"
    assert panel.clipboard_change_count() != count


def test_paths_are_strings():
    from pathlib import Path
    panel = Panel(MemoryBackend())
    panel.set_clipboard_files([Path("/tmp/a.txt")])
    assert panel.get_clipboard_files().paths == ("/tmp/a.txt",)
