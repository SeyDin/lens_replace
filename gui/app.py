import tkinter as tk
from tkinter import ttk
from gui.pods_tab import PodsTab
from gui.deployments_tab import DeploymentsTab
from gui.kubeconfig_tab import KubeconfigFrame
from kube.k8s_client import KubeClient
from gui.status_bar import StatusBar


class KubeGUI(tk.Tk):
    def __init__(self, kube_client: KubeClient):
        super().__init__()
        self.title("Kubernetes VIBE GUI")
        self.geometry("1300x800")

        self.kube = kube_client
        self.kubeconfig = None

        self.status_bar = StatusBar(self)

        self.kubeconfig_frame = KubeconfigFrame(self, self.kube, on_success=self.on_kubeconfig_selected, status_bar=self.status_bar)
        self.kubeconfig_frame.pack(anchor="nw", fill="x", padx=10, pady=10)

        self.tabs = ttk.Notebook(self)
        self.pods_tab = PodsTab(self.tabs, self.kube, self.status_bar)
        self.deployments_tab = DeploymentsTab(self.tabs, self.kube, pods_tab=self.pods_tab, notebook=self.tabs, status_bar=self.status_bar)
        self.tabs.add(self.pods_tab, text="Pods")
        self.tabs.add(self.deployments_tab, text="Deployments")
        self.tabs.pack(expand=1, fill="both")

        self._bind_global_shortcuts()
        self.kubeconfig_frame.autoload()

    def _bind_global_shortcuts(self):
        self.bind_all("<Control-KeyPress>", self._on_ctrl_f, add="+")

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

    def on_kubeconfig_selected(self, path):
        self.kubeconfig = path
        self.status_bar.set_status(f"Kubeconfig выбран: {path}")
        if hasattr(self.pods_tab, "load_pods"):
            self.pods_tab.load_pods()
        if hasattr(self.deployments_tab, "load_deployments"):
            self.deployments_tab.load_deployments()
