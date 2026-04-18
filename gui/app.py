import os
import sys
import time
import tkinter as tk
from tkinter import ttk

from app_logger import logger
from gui.default_search_names_window import DefaultSearchNamesWindow
from gui.pods_tab import PodsTab
from gui.deployments_tab import DeploymentsTab
from gui.kubeconfig_tab import KubeconfigFrame, load_default_search_names, save_default_search_names
from gui.refresh_settings_window import RefreshSettingsWindow
from gui.refresh_timer_formatter import RefreshTimerFormatter
from kube.k8s_client import KubeClient
from gui.status_bar import StatusBar
from gui.utils import handle_text_shortcuts


class KubeGUI(tk.Tk):
    def __init__(self, kube_client: KubeClient):
        super().__init__()
        self.title("Kubernetes VIBE GUI")
        self.geometry("1300x800")
        self._icon_image = None
        self._set_app_icon()

        self.kube = kube_client
        self.kubeconfig = None
        self.auto_refresh_enabled = False
        self.auto_refresh_interval_seconds = 30
        self.refresh_settings_window = None
        self.default_search_names_window = None
        self.last_refresh_timestamp = None
        self.auto_refresh_after_id = None
        self.refresh_age_after_id = None
        self.refresh_timer_formatter = RefreshTimerFormatter()

        self._create_menu()

        self.toolbar_frame = tk.Frame(self)
        self.toolbar_frame.pack(anchor="nw", fill="x", padx=10, pady=(10, 0))

        self.status_bar = StatusBar(self)

        self.kubeconfig_frame = KubeconfigFrame(self.toolbar_frame, self.kube, on_success=self.on_kubeconfig_selected, status_bar=self.status_bar)
        self.kubeconfig_frame.pack(side="right", anchor="center")

        self.last_refresh_var = tk.StringVar(value="Последнее обновление: ещё не выполнялось")
        self.last_refresh_label = ttk.Label(
            self.toolbar_frame,
            textvariable=self.last_refresh_var,
            font=("TkDefaultFont", 8),
        )
        self.last_refresh_label.pack(side="right", anchor="center", padx=(0, 10))

        self.tabs = ttk.Notebook(self)
        self.pods_tab = PodsTab(self.tabs, self.kube, self.status_bar)
        self.deployments_tab = DeploymentsTab(self.tabs, self.kube, pods_tab=self.pods_tab, notebook=self.tabs, status_bar=self.status_bar)
        self.tabs.add(self.pods_tab, text="Pods")
        self.tabs.add(self.deployments_tab, text="Deployments")
        self.tabs.pack(expand=1, fill="both")

        self._bind_global_shortcuts()
        self._start_refresh_age_updater()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.kubeconfig_frame.autoload()

    def _create_menu(self):
        self.menu_bar = tk.Menu(self)

        self.settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.settings_menu.add_command(
            label="Выбрать kubeconfig",
            command=self.select_kubeconfig_from_menu,
        )
        self.settings_menu.add_separator()
        self.settings_menu.add_command(
            label="Настройки автообновления",
            command=self.open_refresh_settings,
        )
        self.settings_menu.add_command(
            label="Настройки строк поиска",
            command=self.open_default_search_names_settings,
        )
        self.menu_bar.add_cascade(label="Настройки", menu=self.settings_menu)

        self.config(menu=self.menu_bar)

    def _set_app_icon(self):
        base_dir = os.path.dirname(__file__)
        ico_path = os.path.join(base_dir, "assets", "app_icon.ico")
        png_path = os.path.join(base_dir, "assets", "app_icon.png")

        try:
            if sys.platform.startswith("win") and os.path.exists(ico_path):
                self.iconbitmap(ico_path)
                return

            else:
                self._icon_image = tk.PhotoImage(file=png_path)
                self.iconphoto(True, self._icon_image)
                return
        except Exception as e:
            logger.exception(str(e))
            pass

    def _bind_global_shortcuts(self):
        self.bind_all("<Control-KeyPress>", self._on_global_ctrl_key, add="+")

    def _on_global_ctrl_key(self, event=None):
        shortcut_result = handle_text_shortcuts(event)
        if shortcut_result == "break":
            return shortcut_result
        return self._on_ctrl_f(event)

    def _on_ctrl_f(self, event=None):
        if event.keycode == 70:
            try:
                tab_id = self.tabs.select()
                if not tab_id:
                    return
                tab_widget = self.tabs.nametowidget(tab_id)
            except Exception:
                return

            handler = getattr(tab_widget, "on_ctrl_f", None)
            if callable(handler):
                return handler(event)

    def _on_close(self):
        if self.auto_refresh_after_id is not None:
            self.after_cancel(self.auto_refresh_after_id)
            self.auto_refresh_after_id = None
        if self.refresh_age_after_id is not None:
            self.after_cancel(self.refresh_age_after_id)
            self.refresh_age_after_id = None
        self.destroy()

    def select_kubeconfig_from_menu(self):
        self.kubeconfig_frame.on_select()

    def open_refresh_settings(self):
        if self.refresh_settings_window and self.refresh_settings_window.winfo_exists():
            self.refresh_settings_window.focus_set()
            return

        self.refresh_settings_window = RefreshSettingsWindow(
            self,
            interval_seconds=self.auto_refresh_interval_seconds,
            enabled=self.auto_refresh_enabled,
            on_save=self.save_refresh_settings,
        )

    def open_default_search_names_settings(self):
        if self.default_search_names_window and self.default_search_names_window.winfo_exists():
            self.default_search_names_window.focus_set()
            return

        self.default_search_names_window = DefaultSearchNamesWindow(
            self,
            search_names=load_default_search_names(),
            on_save=self.save_default_search_names_settings,
        )

    def save_refresh_settings(self, interval_seconds: int, enabled: bool):
        self.auto_refresh_interval_seconds = interval_seconds
        self.auto_refresh_enabled = enabled
        self._schedule_auto_refresh()
        state_text = "включено" if enabled else "выключено"
        self.status_bar.set_status(
            f"Автообновление {state_text}, интервал: {self.auto_refresh_interval_seconds} сек"
        )

    def save_default_search_names_settings(self, search_names: list[str]):
        save_default_search_names(search_names)
        actual_search_names = load_default_search_names()
        self.pods_tab.apply_default_search_names(actual_search_names)
        self.deployments_tab.apply_default_search_names(actual_search_names)
        self.status_bar.set_status("Предопределенные строки поиска сохранены")

    def _start_refresh_age_updater(self):
        self._update_last_refresh_label()
        self.refresh_age_after_id = self.after(1000, self._start_refresh_age_updater)

    def _update_last_refresh_label(self):
        self.last_refresh_var.set(
            self.refresh_timer_formatter.format_last_refresh_message(self.last_refresh_timestamp)
        )

    def _schedule_auto_refresh(self):
        if self.auto_refresh_after_id is not None:
            self.after_cancel(self.auto_refresh_after_id)
            self.auto_refresh_after_id = None

        if not self.auto_refresh_enabled or not self.kubeconfig:
            return

        self.auto_refresh_after_id = self.after(
            self.auto_refresh_interval_seconds * 1000,
            self._run_auto_refresh,
        )

    def _run_auto_refresh(self):
        self.auto_refresh_after_id = None
        if not self.auto_refresh_enabled or not self.kubeconfig:
            return
        self.refresh_cluster_data()
        self._schedule_auto_refresh()

    def refresh_cluster_data(self):
        if not self.kubeconfig:
            return
        self.last_refresh_timestamp = time.time()
        self._update_last_refresh_label()
        if hasattr(self.pods_tab, "load_pods"):
            self.pods_tab.load_pods()
        if hasattr(self.deployments_tab, "load_deployments"):
            self.deployments_tab.load_deployments()

    def on_kubeconfig_selected(self, path):
        self.kubeconfig = path
        self.status_bar.set_status(f"Kubeconfig выбран: {path}")
        self.refresh_cluster_data()
        self._schedule_auto_refresh()
