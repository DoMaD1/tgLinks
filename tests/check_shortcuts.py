"""Run manually on Windows with Tcl/Tk; preserves the existing clipboard."""
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from tkinter import ttk
from app import App, LoginDialog, add_input, windows_shortcut

root = App()
root.withdraw()
try:
    previous = root.clipboard_get()
except tk.TclError:
    previous = None
try:
    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)

    buttons = [w for w in descendants(root) if isinstance(w, ttk.Button) and w.cget('text') == 'Вставить']
    assert len(buttons) == 5
    for button in buttons:
        field = next(w for w in button.master.winfo_children() if isinstance(w, ttk.Entry))
        root.clipboard_clear()
        root.clipboard_append('https://t.me/пример')
        field.delete(0, 'end')
        field.insert(0, 'replace me')
        field.selection_range(0, 'end')
        button.invoke()
        assert field.get() == 'https://t.me/пример', field.get()
        field.selection_range(0, 'end')
        event = SimpleNamespace(widget=field, keycode=86, keysym='Cyrillic_em', state=4)
        assert windows_shortcut(event) == 'break'
        assert field.get() == 'https://t.me/пример', field.get()
        event.keycode = 65
        assert windows_shortcut(event) == 'break'
        assert field.selection_present()
        event.keycode = 86
        event.state = 4 | 0x20000
        assert windows_shortcut(event) is None
        assert field.bind('<KeyPress>')

    # Exercise the actual modal login dialogs and their paste buttons.
    def fill_dialog():
        for child in root.winfo_children():
            if isinstance(child, LoginDialog):
                child.paste_button.invoke()
                child.ok()
                return
        root.after(50, fill_dialog)

    for secret in (False, True):
        root.after(100, fill_dialog)
        dialog = LoginDialog(root, 'Test', secret)
        assert dialog.result == 'https://t.me/пример'
    print('PASS: all 5 paste buttons, code/password dialogs, selection replacement, Ctrl+A, AltGr exclusion, widget bindings')
finally:
    root.clipboard_clear()
    if previous is not None:
        root.clipboard_append(previous)
    root.update()
    root.destroy()
