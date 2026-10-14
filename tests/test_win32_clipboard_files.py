"""The Windows file clipboard (_win32_native's CF_HDROP calls) against the real
clipboard: a 64-bit HGLOBAL must reach DragQueryFileW through its declared
argtypes. The module once rebound ``shell32`` to a fresh WinDLL further down,
which dropped those declarations, so any handle above 2**31 raised
OverflowError -- and a GUI app that reads the clipboard on its first draw died
at startup whenever files were on it."""

import sys

import pytest

# Skip at collection time: _win32_native's module body calls ctypes.WinDLL.
if sys.platform != "win32":
    pytest.skip("Windows-only backend", allow_module_level=True)

import ctypes  # noqa: E402

from puikit.backends import _win32_native as native  # noqa: E402


@pytest.fixture
def clipboard():
    """Leave the clipboard holding text, not files, whatever the test did."""
    yield
    native.set_clipboard_text(0, "")


def test_every_call_declared_on_shell32_keeps_its_argtypes():
    assert native.shell32.DragQueryFileW.argtypes is not None
    assert native.shell32.ShellExecuteW.restype is ctypes.c_void_p
    assert native.shell32.Shell_NotifyIconW.argtypes is not None


def test_files_round_trip_through_the_clipboard(clipboard, tmp_path):
    paths = [str(tmp_path / "a.txt"), str(tmp_path / "b ü.txt")]
    assert native.set_clipboard_files(0, paths, cut=False)
    assert native.get_clipboard_files(0) == (paths, False)


def test_a_cut_reads_back_as_a_cut(clipboard, tmp_path):
    paths = [str(tmp_path / "a.txt")]
    assert native.set_clipboard_files(0, paths, cut=True)
    assert native.get_clipboard_files(0) == (paths, True)


def test_text_on_the_clipboard_is_not_files(clipboard):
    native.set_clipboard_text(0, "plain text")
    assert native.get_clipboard_files(0) is None
