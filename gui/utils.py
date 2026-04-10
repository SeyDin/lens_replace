import re
import tkinter as tk


def format_pod_name(pod_name: str) -> str:
    res_list = []
    for sym in pod_name:
        if pod_name not in ("\n", " "):
            res_list.append(sym)
    return "".join(res_list)


def delete_color_marks(log: str) -> str:
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    return ansi_escape.sub('', log)


def handle_text_shortcuts(event=None, on_change=None):
    if event is None:
        return

    widget = getattr(event, "widget", None)
    if widget is None:
        return

    keycode = getattr(event, "keycode", None)
    keysym = str(getattr(event, "keysym", "")).lower()

    is_ctrl_a = keysym in {"ф", "cyrillic_ef"} or (keycode == 65 and keysym != "a")
    is_ctrl_c = keysym in {"с", "cyrillic_es"} or (keycode == 67 and keysym != "c")
    is_ctrl_x = keysym in {"ч", "cyrillic_che"} or (keycode == 88 and keysym != "x")
    is_ctrl_v = keysym in {"м", "cyrillic_em"} or (keycode == 86 and keysym != "v")

    if is_ctrl_a:
        if isinstance(widget, tk.Text):
            widget.tag_add(tk.SEL, "1.0", "end-1c")
            widget.mark_set(tk.INSERT, "end-1c")
            widget.see(tk.INSERT)
        else:
            widget.selection_range(0, tk.END)
            widget.icursor(tk.END)
        return "break"

    if is_ctrl_c:
        try:
            if isinstance(widget, tk.Text):
                selected_text = widget.get(tk.SEL_FIRST, tk.SEL_LAST)
            else:
                selected_text = widget.selection_get()
        except tk.TclError:
            return "break"
        widget.clipboard_clear()
        widget.clipboard_append(selected_text)
        return "break"

    if is_ctrl_x:
        try:
            if isinstance(widget, tk.Text):
                selection_start = widget.index(tk.SEL_FIRST)
                selection_end = widget.index(tk.SEL_LAST)
                selected_text = widget.get(selection_start, selection_end)
            else:
                selection_start = widget.index(tk.SEL_FIRST)
                selection_end = widget.index(tk.SEL_LAST)
                selected_text = widget.selection_get()
        except tk.TclError:
            return "break"

        widget.clipboard_clear()
        widget.clipboard_append(selected_text)
        widget.delete(selection_start, selection_end)

        if isinstance(widget, tk.Text):
            widget.mark_set(tk.INSERT, selection_start)
            widget.see(tk.INSERT)
        else:
            widget.icursor(selection_start)

        if callable(on_change):
            on_change()

        return "break"

    if not is_ctrl_v:
        return

    try:
        clipboard_text = widget.clipboard_get()
    except tk.TclError:
        return "break"

    if isinstance(widget, tk.Text):
        try:
            selection_start = widget.index(tk.SEL_FIRST)
            selection_end = widget.index(tk.SEL_LAST)
            widget.delete(selection_start, selection_end)
            insert_index = selection_start
        except tk.TclError:
            insert_index = widget.index(tk.INSERT)
        widget.insert(insert_index, clipboard_text)
        widget.mark_set(tk.INSERT, f"{insert_index}+{len(clipboard_text)}c")
        widget.see(tk.INSERT)
    else:
        try:
            selection_start = widget.index(tk.SEL_FIRST)
            selection_end = widget.index(tk.SEL_LAST)
            widget.delete(selection_start, selection_end)
            insert_index = selection_start
        except tk.TclError:
            insert_index = widget.index(tk.INSERT)
        widget.insert(insert_index, clipboard_text)
        widget.icursor(insert_index + len(clipboard_text))

    if callable(on_change):
        on_change()

    return "break"