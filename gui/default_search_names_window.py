import tkinter as tk
from tkinter import ttk

from gui.kubeconfig_tab import DEFAULT_SEARCH_NAMES_LIMIT


class DefaultSearchNamesWindow(tk.Toplevel):
    def __init__(self, parent, search_names: list[str], on_save):
        super().__init__(parent)
        self.title("Настройка строк поиска")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._on_save = on_save
        self.search_name_vars: list[tk.StringVar] = []

        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text=f"Укажите до {DEFAULT_SEARCH_NAMES_LIMIT} предопределенных строк поиска:",
        ).pack(anchor="w")

        fields_frame = ttk.Frame(container)
        fields_frame.pack(fill="both", expand=True, pady=(10, 0))

        initial_values = list(search_names[:DEFAULT_SEARCH_NAMES_LIMIT])
        while len(initial_values) < DEFAULT_SEARCH_NAMES_LIMIT:
            initial_values.append("")

        for i, value in enumerate(initial_values, start=1):
            row = ttk.Frame(fields_frame)
            row.pack(fill="x", pady=2)

            ttk.Label(row, text=f"{i}.", width=3).pack(side="left")
            var = tk.StringVar(value=value)
            self.search_name_vars.append(var)
            entry = ttk.Entry(row, textvariable=var, width=40)
            entry.pack(side="left", fill="x", expand=True)

        self.error_label = ttk.Label(container, text="", foreground="#c0392b")
        self.error_label.pack(anchor="w", pady=(8, 0))

        buttons_frame = ttk.Frame(container)
        buttons_frame.pack(fill="x", pady=(12, 0))

        ttk.Button(buttons_frame, text="Сохранить", command=self._save).pack(side="right")
        ttk.Button(buttons_frame, text="Отмена", command=self.destroy).pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _save(self):
        search_names = []
        duplicates = set()

        for var in self.search_name_vars:
            value = var.get().strip()
            if not value:
                continue
            if value in search_names:
                duplicates.add(value)
                continue
            search_names.append(value)

        if duplicates:
            duplicate_text = ", ".join(sorted(duplicates))
            self.error_label.configure(text=f"Повторяющиеся значения: {duplicate_text}")
            return

        self.error_label.configure(text="")
        self._on_save(search_names)
        self.destroy()
