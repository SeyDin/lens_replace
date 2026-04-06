import tkinter as tk
from tkinter import ttk


class RefreshSettingsWindow(tk.Toplevel):
    def __init__(self, parent, interval_seconds: int, enabled: bool, on_save):
        super().__init__(parent)
        self.title("Настройки автообновления")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._on_save = on_save

        self.enabled_var = tk.BooleanVar(value=enabled)
        self.interval_var = tk.StringVar(value=str(interval_seconds))

        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        self.enabled_check = ttk.Checkbutton(
            container,
            text="Включить периодическое обновление",
            variable=self.enabled_var,
            command=self._toggle_interval_state,
        )
        self.enabled_check.pack(anchor="w")

        interval_frame = ttk.Frame(container)
        interval_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(interval_frame, text="Интервал обновления, сек:").pack(side="left")
        self.interval_entry = ttk.Entry(interval_frame, textvariable=self.interval_var, width=10)
        self.interval_entry.pack(side="left", padx=(8, 0))

        self.error_label = ttk.Label(container, text="", foreground="#c0392b")
        self.error_label.pack(anchor="w", pady=(8, 0))

        buttons_frame = ttk.Frame(container)
        buttons_frame.pack(fill="x", pady=(12, 0))

        ttk.Button(buttons_frame, text="Сохранить", command=self._save).pack(side="right")
        ttk.Button(buttons_frame, text="Отмена", command=self.destroy).pack(side="right", padx=(0, 8))

        self._toggle_interval_state()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _toggle_interval_state(self):
        state = "normal" if self.enabled_var.get() else "disabled"
        self.interval_entry.configure(state=state)

    def _save(self):
        enabled = self.enabled_var.get()
        interval_text = self.interval_var.get().strip()

        if enabled:
            try:
                interval_seconds = int(interval_text)
            except ValueError:
                self.error_label.configure(text="Введите целое число секунд")
                return
            if interval_seconds <= 0:
                self.error_label.configure(text="Интервал должен быть больше нуля")
                return
        else:
            interval_seconds = int(interval_text) if interval_text.isdigit() and int(interval_text) > 0 else 30

        self.error_label.configure(text="")
        self._on_save(interval_seconds, enabled)
        self.destroy()
