from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import ttk, messagebox

from gui.status_bar import StatusBar
from kube.k8s_client import KubeClient

# noinspection PyAttributeOutsideInit
class DeploymentsTab(tk.Frame):
    def __init__(self, parent, kube_client: KubeClient | None, status_bar: StatusBar, pods_tab=None, notebook=None):
        super().__init__(parent)
        self.kube = kube_client if kube_client else KubeClient()
        self.deployments = []
        self.filtered_deployments = []
        self.deployment_by_ns = {}
        self.selected_deployment = None
        self.search_var = tk.StringVar()
        self.default_searches_buttons: list[ttk.Button] = []
        self.pods_tab = pods_tab
        self.notebook = notebook
        self.status_bar = status_bar
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.create_widgets()
        self.bind("<Destroy>", self._on_destroy, add="+")

    def create_widgets(self):
        self.content_frame = tk.Frame(self)
        self.content_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(self.content_frame)
        self.tree.pack(side="left", fill="y")
        self.tree["columns"] = ("replicas",)
        self.tree.heading("#0", text="Namespace / Deployment")
        self.tree.heading("replicas", text="Replicas")
        self.tree.column("replicas", width=80, anchor="center")
        self.tree.bind("<<TreeviewSelect>>", self.on_deployment_select)

        right_frame = tk.Frame(self.content_frame)
        right_frame.pack(side="left", fill="both", expand=True)

        self.deployment_info = tk.Text(right_frame, width=80, bg="#181818", fg="#e0e0e0")
        self.deployment_info.pack(fill="both", expand=True)

        self.scale_frame = tk.Frame(right_frame)
        self.scale_frame.pack(fill="x", pady=5)
        tk.Label(self.scale_frame, text="Изменить количество реплик:").pack(side="left")
        self.replicas_entry = tk.Entry(self.scale_frame, width=5)
        self.replicas_entry.pack(side="left", padx=5)
        self.scale_btn = tk.Button(self.scale_frame, text="Изменить", command=self.on_scale_click)
        self.scale_btn.pack(side="left")

        self.goto_pods_btn = tk.Button(self.scale_frame, text="Перейти к подам deployment", command=self.goto_deployment_pods)
        self.goto_pods_btn.pack(side="left", padx=(10, 0))

        self.search_frame = tk.Frame(self)
        self.search_frame.pack(side="bottom", fill="x", padx=5, pady=5)

        self.search_entry = ttk.Entry(self.search_frame, textvariable=self.search_var)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.search_entry.bind('<Return>', lambda event: self.search_deployments())

        self.search_btn = ttk.Button(self.search_frame, text="Поиск", command=self.search_deployments)
        self.search_btn.pack(side="left", padx=(0, 5))

        default_search_names = ["runtime", "aitunnel", "openai"]
        for i in range(3):
            button = ttk.Button(self.search_frame, text=default_search_names[i])
            button.config(command=lambda b=button: self.search_default(b))
            button.pack(side="bottom", padx=(0, 5))
            button.search_text = default_search_names[i]
            self.default_searches_buttons.append(button)

        self.reset_btn = ttk.Button(self.search_frame, text="Сбросить", command=self.reset_deployments)
        self.reset_btn.pack(side="left")

        self.refresh_btn = ttk.Button(self.scale_frame, text="Обновить информацию о deployment", command=self.load_deployments)
        self.refresh_btn.pack(side="left", padx=(10, 0))

    def _on_destroy(self, event):
        if event.widget is self:
            self.executor.shutdown(wait=False, cancel_futures=True)

    def on_ctrl_f(self, event=None):
        if not self.winfo_ismapped():
            return
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, tk.END)
        return "break"

    def load_deployments(self):
        self.status_bar.set_status("Load deployments ...")
        self.tree.delete(*self.tree.get_children())
        self.deployment_info.delete(1.0, tk.END)
        self.replicas_entry.delete(0, tk.END)
        self.selected_deployment = None
        future = self.executor.submit(self.kube.list_deployments)
        future.add_done_callback(lambda f: self.after(0, self._handle_deployments_future, f))

    def _handle_deployments_future(self, future):
        try:
            deployments = future.result()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при получении деплойментов: {e}")
            self.status_bar.reset_status()
            return
        self.deployments = deployments
        self.filtered_deployments = deployments
        self._fill_treeview(self.filtered_deployments)
        self.deployment_info.delete(1.0, tk.END)
        self.replicas_entry.delete(0, tk.END)
        self.selected_deployment = None
        self.status_bar.reset_status()

    def _fill_treeview(self, deployments):
        self.tree.delete(*self.tree.get_children())
        self.deployment_by_ns = {}
        for dep in deployments:
            ns = dep.metadata.namespace
            if ns not in self.deployment_by_ns:
                self.deployment_by_ns[ns] = []
            self.deployment_by_ns[ns].append(dep)
        for ns, deps in self.deployment_by_ns.items():
            ns_id = self.tree.insert("", "end", text=ns)
            for dep in deps:
                dep_id = self.tree.insert(ns_id, "end", text=dep.metadata.name, values=(dep.spec.replicas,))
                self.tree.set(dep_id, "replicas", dep.spec.replicas)
                self.tree.item(dep_id, tags=(f"{ns}/{dep.metadata.name}",))

    def search_deployments(self):
        self.status_bar.set_status("Search deployments ...")
        query = self.search_var.get().strip().lower()
        self.status_bar.set_status(f"Search deployments like '{query}' ...")
        if not query:
            self.filtered_deployments = self.deployments
        else:
            self.filtered_deployments = [
                dep for dep in self.deployments
                if query in dep.metadata.name.lower()
            ]
        self._fill_treeview(self.filtered_deployments)
        self.fill_default_search_buttons(self.search_var.get().strip())
        self.status_bar.reset_status()

    def reset_deployments(self):
        self.search_var.set("")
        self.filtered_deployments = self.deployments
        self._fill_treeview(self.deployments)

    def search_default(self, button: ttk.Button):
        self.search_var.set(button.search_text)
        self.search_deployments()

    def fill_default_search_buttons(self, search_name: str) -> None:
        existed_searches = [x.search_text for x in self.default_searches_buttons]
        if search_name in existed_searches:
            return
        else:
            existed_searches.pop(0)
            existed_searches.append(search_name)
            for i, button in enumerate(self.default_searches_buttons):
                button.search_text = existed_searches[i]
                button.configure(text=existed_searches[i])

    def on_deployment_select(self, event):
        self.status_bar.set_status("Loading deployment info ...")
        selected = self.tree.selection()
        if not selected:
            self.status_bar.reset_status()
            return
        item_id = selected[0]
        parent_id = self.tree.parent(item_id)
        if not parent_id:
            self.selected_deployment = None
            self.deployment_info.delete(1.0, tk.END)
            self.replicas_entry.delete(0, tk.END)
            self.status_bar.reset_status()
            return
        ns = self.tree.item(parent_id, "text")
        dep_name = self.tree.item(item_id, "text")
        dep = next((d for d in self.deployment_by_ns[ns] if d.metadata.name == dep_name), None)
        if dep:
            self.selected_deployment = dep
            info = f"Name: {dep.metadata.name}\nNamespace: {dep.metadata.namespace}\nReplicas: {dep.spec.replicas}"
            info += f"Selector: {dep.spec.selector.match_labels}"
            self.deployment_info.delete(1.0, tk.END)
            self.deployment_info.insert(tk.END, info)
            self.replicas_entry.delete(0, tk.END)
            self.replicas_entry.insert(0, str(dep.spec.replicas))
        self.status_bar.reset_status()

    def on_scale_click(self):
        self.status_bar.set_status("Scale pods ...")
        dep = self.selected_deployment
        if dep is None:
            messagebox.showwarning("Внимание", "Сначала выберите deployment.")
            self.status_bar.reset_status()
            return
        try:
            replicas = int(self.replicas_entry.get())
            if replicas < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное неотрицательное число реплик.")
            return
        finally:
            self.status_bar.reset_status()
        try:
            self.kube.scale_deployment(dep.metadata.name, dep.metadata.namespace, replicas)
            messagebox.showinfo("Успех", f"Количество реплик изменено на {replicas}.")
            self.load_deployments()
        except Exception as e:
            self.status_bar.reset_status()
            messagebox.showerror("Ошибка", f"Ошибка при изменении количества реплик: {e}")
        finally:
            self.status_bar.reset_status()

    def goto_deployment_pods(self):
        self.status_bar.set_status("Moving to deployment pods ...")
        dep = self.selected_deployment
        if dep is None:
            messagebox.showwarning("Внимание", "Сначала выберите deployment.")
            self.status_bar.reset_status()
            return
        ns = dep.metadata.namespace
        selector = dep.spec.selector.match_labels
        if not selector:
            self.status_bar.reset_status()
            messagebox.showwarning("Внимание", "У deployment нет selector.match_labels.")
            return
        if self.pods_tab and self.notebook:
            for tab_id in self.notebook.tabs():
                if self.notebook.nametowidget(tab_id) is self.pods_tab:
                    self.notebook.select(tab_id)
                    break
            self.pods_tab.filter_pods_by_labels(ns, selector)
        self.status_bar.reset_status()
