import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from gui.status_bar import StatusBar

LAST_KUBECONFIG_PATH = os.path.expanduser("../.lens_repl_last_kubeconfig")
DEFAULT_SEARCH_NAMES_LIMIT = 9
DEFAULT_SEARCH_NAMES_FALLBACK = ["runtime", "aitunnel", "openai"]


def _normalize_default_search_names(search_names):
    if not isinstance(search_names, list):
        return DEFAULT_SEARCH_NAMES_FALLBACK.copy()

    normalized = []
    for item in search_names:
        value = str(item).strip()
        if not value or value in normalized:
            continue
        normalized.append(value)
        if len(normalized) >= DEFAULT_SEARCH_NAMES_LIMIT:
            break

    if not normalized:
        return DEFAULT_SEARCH_NAMES_FALLBACK.copy()
    return normalized


def _load_config_data():
    if not os.path.exists(LAST_KUBECONFIG_PATH):
        return {
            "kubeconfig_path": None,
            "default_search_names": DEFAULT_SEARCH_NAMES_FALLBACK.copy(),
        }

    with open(LAST_KUBECONFIG_PATH, "r", encoding="utf-8") as f:
        content = f.read().strip()

    if not content:
        return {
            "kubeconfig_path": None,
            "default_search_names": DEFAULT_SEARCH_NAMES_FALLBACK.copy(),
        }

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {
            "kubeconfig_path": content,
            "default_search_names": DEFAULT_SEARCH_NAMES_FALLBACK.copy(),
        }

    return {
        "kubeconfig_path": data.get("kubeconfig_path") or None,
        "default_search_names": _normalize_default_search_names(data.get("default_search_names")),
    }


def _save_config_data(data):
    config = {
        "kubeconfig_path": data.get("kubeconfig_path") or None,
        "default_search_names": _normalize_default_search_names(data.get("default_search_names")),
    }
    with open(LAST_KUBECONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def save_last_kubeconfig(path):
    config = _load_config_data()
    config["kubeconfig_path"] = path
    _save_config_data(config)


def load_last_kubeconfig():
    return _load_config_data()["kubeconfig_path"]


def load_default_search_names():
    return _load_config_data()["default_search_names"]


def save_default_search_names(search_names):
    config = _load_config_data()
    config["default_search_names"] = search_names
    _save_config_data(config)


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

        self.reconnect_btn = ttk.Button(self, text="Reconnect (Refresh)", command=self.on_reconnect)
        self.reconnect_btn.grid(row=0, column=0, sticky="nw", padx=0, pady=0)

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

        self.status_bar.set_status(f"Refresh подключения к kubeconfig: {last_path}...")
        self.update_idletasks()

        if connect_kubeconfig(last_path, self.kube, self.on_success, self.on_error):
            self.status_bar.set_status(f"Refresh подключения завершен: {last_path}")
            self.update_reconnect_button_state()
        else:
            self.status_bar.set_status(f"Ошибка refresh подключения: {last_path}")
