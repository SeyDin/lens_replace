import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from gui.status_bar import StatusBar

LAST_KUBECONFIG_PATH = os.path.expanduser("../.lens_repl_last_kubeconfig")


def save_last_kubeconfig(path):
    with open(LAST_KUBECONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(path)


def load_last_kubeconfig():
    if os.path.exists(LAST_KUBECONFIG_PATH):
        with open(LAST_KUBECONFIG_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None


def connect_kubeconfig(path, kube, on_success=None, on_error=None, show_error=True):
    try:
        kube.load_config(path)
        save_last_kubeconfig(path)
        if on_success:
            on_success(path)
        return True
    except Exception as e:
        if on_error:
            on_error(e)
        if show_error:
            messagebox.showerror("Ошибка", f"Не удалось подключиться: {e}")
        return False


def select_kubeconfig(kube, on_success=None, on_error=None):
    path = filedialog.askopenfilename(
        title="Выберите kubeconfig",
        filetypes=[("Kubeconfig", "*.yaml *.yml *")],
    )
    if path:
        return connect_kubeconfig(path, kube, on_success, on_error)
    return False


class KubeconfigFrame(tk.Frame):
    def __init__(self, parent, kube, status_bar: StatusBar, on_success=None, on_error=None):
        super().__init__(parent)
        self.kube = kube
        self.on_success = on_success
        self.on_error = on_error

        self.grid_anchor("nw")

        self.kubeconfig_btn = ttk.Button(self, text="Выбрать kubeconfig", command=self.on_select)
        self.kubeconfig_btn.grid(row=0, column=0, sticky="nw", padx=0, pady=0)

        self.reconnect_btn = ttk.Button(self, text="Reconnect", command=self.on_reconnect)
        self.reconnect_btn.grid(row=0, column=1, sticky="nw", padx=(8, 0), pady=0)

        self.status_bar = status_bar
        self.update_reconnect_button_state()

    def update_reconnect_button_state(self):
        last_path = load_last_kubeconfig()
        if last_path:
            self.reconnect_btn.config(state=tk.NORMAL)
        else:
            self.reconnect_btn.config(state=tk.DISABLED)

    def autoload(self):
        last_path = load_last_kubeconfig()
        if not last_path:
            self.update_reconnect_button_state()
            return

        if connect_kubeconfig(last_path, self.kube, self.on_success, self.on_error, show_error=False):
            self.status_bar.set_status(f"Автоматически подключено к kubeconfig: {last_path}")
        self.update_reconnect_button_state()

    def on_select(self):
        if select_kubeconfig(self.kube, self.on_success, self.on_error):
            self.update_reconnect_button_state()

    def on_reconnect(self):
        last_path = load_last_kubeconfig()
        if not last_path:
            self.update_reconnect_button_state()
            messagebox.showwarning("Предупреждение", "Нет сохраненного kubeconfig для переподключения")
            return

        if connect_kubeconfig(last_path, self.kube, self.on_success, self.on_error):
            self.status_bar.set_status(f"Переподключено к kubeconfig: {last_path}")
            self.update_reconnect_button_state()
            messagebox.showinfo("Успех", f"Переподключение выполнено по {last_path}")
