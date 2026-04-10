import logging
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from functools import partial
from tkinter import ttk, messagebox, filedialog

from gui.kubeconfig_tab import load_default_search_names
from gui.status_bar import StatusBar
from gui.utils import format_pod_name, delete_color_marks
from kube.k8s_client import KubeClient
from app_logger import logger


# noinspection PyAttributeOutsideInit
class PodsTab(tk.Frame):
    def __init__(self, parent, kube_client: KubeClient | None, status_bar: StatusBar):
        super().__init__(parent)
        self.kube = kube_client if kube_client else KubeClient()
        self.kubeconfig = None
        self.pods = []
        self.filtered_pods = []
        self.default_searches_buttons: list[ttk.Button] = []
        self._default_search_text: dict[ttk.Button, str] = {}
        self.selected_pod = None
        self.namespace_nodes = {}
        self.right_click_pod_name = None
        self.status_bar = status_bar
        self.indicator_images = {}
        self.executor = ThreadPoolExecutor(max_workers=2)

        self._last_find_query = ""
        self._last_find_index = "1.0"
        self._log_chunk_size = 1000
        self._loaded_log_lines = 0
        self._loading_more_logs = False
        self._has_more_logs = False
        self._log_request_token = 0

        self._init_paned()
        self.create_widgets()
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _init_paned(self):
        self.paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=8)
        self.paned.pack(fill="both", expand=True)

    def _create_indicator_image(self, color: str) -> tk.PhotoImage:
        image = tk.PhotoImage(width=12, height=12)
        image.put(color, to=(0, 0, 12, 12))
        return image

    def _init_indicator_images(self):
        self.indicator_images = {
            "green": self._create_indicator_image("#2ecc71"),
            "yellow": self._create_indicator_image("#f1c40f"),
            "red": self._create_indicator_image("#e74c3c"),
        }

    def _on_destroy(self, event):
        if event.widget is self:
            self.executor.shutdown(wait=False, cancel_futures=True)

    def create_widgets(self):
        self._init_indicator_images()

        self.search_frame = tk.Frame(self)
        self.search_frame.pack(fill="x", padx=5, pady=5)

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(self.search_frame, textvariable=self.search_var)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.search_entry.bind('<Return>', lambda event: self.search_pods())

        self.search_btn = ttk.Button(self.search_frame, text="Поиск", command=self.search_pods)
        self.search_btn.pack(side="left", padx=(0, 5))

        self.default_searches_frame = tk.Frame(self.search_frame)
        self.default_searches_frame.pack(side="left", padx=(0, 5))
        self.apply_default_search_names(load_default_search_names())

        self.reset_btn = ttk.Button(self.search_frame, text="Сбросить", command=self.reset_pods)
        self.reset_btn.pack(side="left")

        self.left_panel = tk.Frame(self.paned)
        self.right_panel = tk.Frame(self.paned)
        self.paned.add(self.left_panel, minsize=120)
        self.paned.add(self.right_panel, minsize=200)

        self.pods_tree = ttk.Treeview(self.left_panel)
        self.pods_tree.pack(side="left", fill="both", expand=True)
        self.pods_tree["columns"] = ("ready", "status", "restarts")
        self.pods_tree.heading("#0", text="Namespace / Pod")
        self.pods_tree.heading("ready", text="Ready")
        self.pods_tree.heading("status", text="Status")
        self.pods_tree.heading("restarts", text="Restarts")
        self.pods_tree.column("#0", width=260)
        self.pods_tree.column("ready", width=60, anchor="center", stretch=False)
        self.pods_tree.column("status", width=70, anchor="center")
        self.pods_tree.column("restarts", width=50, anchor="center", stretch=False)
        self.pods_tree.bind("<<TreeviewSelect>>", self.on_pod_select)
        self.pods_tree.bind("<Button-3>", self.on_right_click)

        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Скопировать имя", command=self.copy_pod_name)

        self.pod_log_frame = tk.Frame(self.right_panel)
        self.pod_log_frame.pack(fill="both", expand=True)

        self.find_frame = tk.Frame(self.pod_log_frame)

        self.find_var = tk.StringVar()
        self.find_entry = ttk.Entry(self.find_frame, textvariable=self.find_var)
        self.find_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.find_entry.bind("<Return>", lambda event: self.find_next())
        self.find_entry.bind("<Shift-Return>", lambda event: self.find_prev())
        self.find_entry.bind("<Escape>", lambda event: self.hide_find_bar())
        self.find_entry.bind("<KeyRelease>", lambda event: self.highlight_find_matches())

        self.find_prev_btn = ttk.Button(self.find_frame, text="Prev", command=self.find_prev)
        self.find_prev_btn.pack(side="left", padx=(0, 5))

        self.find_next_btn = ttk.Button(self.find_frame, text="Next", command=self.find_next)
        self.find_next_btn.pack(side="left", padx=(0, 5))

        self.find_close_btn = ttk.Button(self.find_frame, text="X", width=3, command=self.hide_find_bar)
        self.find_close_btn.pack(side="left")

        self.logs_container = tk.Frame(self.pod_log_frame)
        self.logs_container.pack(fill="both", expand=True)

        self.pod_logs = tk.Text(self.logs_container, width=80, wrap="none", bg="#181818", fg="#e0e0e0")
        self.pod_logs.pack(side="left", fill="both", expand=True)
        self.pod_logs.bind("<Control-KeyPress>", self.copy_selected_logs)
        self.pod_logs.bind("<Button-3>", self.on_logs_right_click)
        self.pod_logs.bind("<MouseWheel>", self._on_log_mousewheel, add="+")
        self.pod_logs.bind("<Button-4>", self._on_log_mousewheel_linux_up, add="+")
        self.pod_logs.bind("<Button-5>", self._on_log_mousewheel_linux_down, add="+")
        self.pod_logs.bind("<Prior>", self._on_log_navigation, add="+")
        self.pod_logs.bind("<Up>", self._on_log_navigation, add="+")
        self.pod_logs.bind("<Home>", self._on_log_navigation, add="+")
        self.pod_logs.tag_configure("find_match", background="#3a3a3a", foreground="#ffffff")
        self.pod_logs.tag_configure("find_current", background="#5c3b00", foreground="#ffffff")

        self.logs_context_menu = tk.Menu(self, tearoff=0)
        self.logs_context_menu.add_command(label="Скопировать", command=self.copy_selected_logs)

        self.log_scrollbar = ttk.Scrollbar(self.logs_container, orient="vertical", command=self._on_log_scrollbar)
        self.log_scrollbar.pack(side="right", fill="y")
        self.log_horizontal_scrollbar = ttk.Scrollbar(self.pod_log_frame, orient="horizontal", command=self.pod_logs.xview)
        self.log_horizontal_scrollbar.pack(fill="x")
        self.pod_logs.config(yscrollcommand=self.log_scrollbar.set, xscrollcommand=self.log_horizontal_scrollbar.set)

        self.refresh_btn = ttk.Button(self.pod_log_frame, text="Обновить", command=self.refresh_logs)
        self.refresh_btn.pack(side="left")
        self.refresh_btn["state"] = "disabled"

        self.download_btn = ttk.Button(self.pod_log_frame, text="Скачать логи", command=self.download_logs)
        self.download_btn.pack(side="left")
        self.download_btn["state"] = "disabled"

    def apply_default_search_names(self, search_names: list[str]):
        for button in self.default_searches_buttons:
            button.destroy()
        self.default_searches_buttons.clear()
        self._default_search_text.clear()

        for name in search_names:
            button = ttk.Button(self.default_searches_frame, text=name)
            button.config(command=partial(self.search_default, button))
            button.pack(side="left", padx=(0, 5))
            self.default_searches_buttons.append(button)
            self._default_search_text[button] = name

    def on_ctrl_f(self, event=None):
        if not self.winfo_ismapped():
            return
        self.show_find_bar()
        return "break"

    def show_find_bar(self):
        if not self.find_frame.winfo_ismapped():
            self.find_frame.pack(side="top", fill="x", padx=5, pady=(5, 0))
        self.find_entry.focus_set()
        self.find_entry.selection_range(0, tk.END)
        self.highlight_find_matches()

    def hide_find_bar(self):
        if self.find_frame.winfo_ismapped():
            self.find_frame.pack_forget()
        self.clear_find_tags()
        self.pod_logs.focus_set()

    def clear_find_tags(self):
        self.pod_logs.tag_remove("find_match", "1.0", tk.END)
        self.pod_logs.tag_remove("find_current", "1.0", tk.END)

    def highlight_find_matches(self):
        query = self.find_var.get()
        self.clear_find_tags()
        if not query:
            self._last_find_query = ""
            self._last_find_index = "1.0"
            return

        idx = "1.0"
        while True:
            pos = self.pod_logs.search(query, idx, stopindex=tk.END, nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(query)}c"
            self.pod_logs.tag_add("find_match", pos, end)
            idx = end

        if query != self._last_find_query:
            self._last_find_query = query
            self._last_find_index = "1.0"

    def find_next(self):
        query = self.find_var.get()
        if not query:
            return

        if query != self._last_find_query:
            self._last_find_query = query
            self._last_find_index = "1.0"
            self.highlight_find_matches()

        start = self.pod_logs.index(tk.INSERT)
        pos = self.pod_logs.search(query, start, stopindex=tk.END, nocase=True)
        if not pos:
            pos = self.pod_logs.search(query, "1.0", stopindex=start, nocase=True)
        if not pos:
            return

        end = f"{pos}+{len(query)}c"
        self.pod_logs.tag_remove("find_current", "1.0", tk.END)
        self.pod_logs.tag_add("find_current", pos, end)
        self.pod_logs.mark_set(tk.INSERT, end)
        self.pod_logs.see(pos)
        self._last_find_index = end

    def find_prev(self):
        query = self.find_var.get()
        if not query:
            return

        if query != self._last_find_query:
            self._last_find_query = query
            self._last_find_index = "1.0"
            self.highlight_find_matches()

        start = self.pod_logs.index(tk.INSERT)
        pos = self.pod_logs.search(query, start, stopindex="1.0", nocase=True, backwards=True)
        if not pos:
            pos = self.pod_logs.search(query, tk.END, stopindex=start, nocase=True, backwards=True)
        if not pos:
            return

        end = f"{pos}+{len(query)}c"
        self.pod_logs.tag_remove("find_current", "1.0", tk.END)
        self.pod_logs.tag_add("find_current", pos, end)
        self.pod_logs.mark_set(tk.INSERT, pos)
        self.pod_logs.see(pos)
        self._last_find_index = pos

    def _get_pod_status_info(self, pod):
        container_statuses = getattr(pod.status, "container_statuses", None) or []
        spec_containers = getattr(pod.spec, "containers", []) or []
        total_containers = len(container_statuses) or len(spec_containers)
        ready_containers = sum(1 for status in container_statuses if getattr(status, "ready", False))
        restarts = sum(getattr(status, "restart_count", 0) or 0 for status in container_statuses)

        phase = getattr(pod.status, "phase", "Unknown") or "Unknown"
        reasons = []

        for status in container_statuses:
            state = getattr(status, "state", None)
            waiting = getattr(state, "waiting", None) if state else None
            terminated = getattr(state, "terminated", None) if state else None
            running = getattr(state, "running", None) if state else None

            if waiting and getattr(waiting, "reason", None):
                reasons.append(waiting.reason)
            elif terminated and getattr(terminated, "reason", None):
                reasons.append(terminated.reason)
            elif terminated and getattr(terminated, "exit_code", 0):
                reasons.append(f"ExitCode:{terminated.exit_code}")
            elif running and not getattr(status, "ready", False):
                reasons.append("Running")

        if not reasons and getattr(pod.status, "reason", None):
            reasons.append(pod.status.reason)

        status_text = reasons[0] if reasons else phase
        ready_text = f"{ready_containers}/{total_containers}"
        restarts_text = str(restarts)

        red_reasons = {
            "CrashLoopBackOff",
            "ErrImagePull",
            "ImagePullBackOff",
            "RunContainerError",
            "CreateContainerError",
            "CreateContainerConfigError",
            "InvalidImageName",
            "OOMKilled",
            "Error",
            "Failed",
        }
        yellow_phases = {"Pending", "Unknown"}

        if any(reason in red_reasons or str(reason).startswith("ExitCode:") for reason in reasons) or phase == "Failed":
            return "red", ready_text, status_text, restarts_text
        if total_containers > 0 and ready_containers == total_containers and phase == "Running":
            return "green", ready_text, status_text, restarts_text
        if phase == "Succeeded":
            return "green", ready_text, status_text, restarts_text
        if reasons or phase in yellow_phases or ready_containers < total_containers:
            return "yellow", ready_text, status_text, restarts_text
        return "yellow", ready_text, status_text, restarts_text

    def on_logs_right_click(self, event):
        try:
            self.pod_logs.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            return "break"
        self.logs_context_menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def copy_selected_logs(self, event=None):
        if event is not None and getattr(event, 'keycode', None) == 67:
            try:
                text = self.pod_logs.get(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                return "break"
            self.clipboard_clear()
            self.clipboard_append(text)
            return "break"
        return

    def _reset_log_paging(self):
        self._loading_more_logs = False
        self._has_more_logs = False
        self._loaded_log_lines = 0
        self._log_request_token += 1

    def _count_log_lines(self, logs: str) -> int:
        if not logs:
            return 0
        return logs.count("\n") + (0 if logs.endswith("\n") else 1)

    def _on_log_scrollbar(self, *args):
        self.pod_logs.yview(*args)
        self.after_idle(self._maybe_load_more_logs)

    def _on_log_mousewheel(self, event):
        if getattr(event, "delta", 0) > 0:
            self.after_idle(self._maybe_load_more_logs)

    def _on_log_mousewheel_linux_up(self, event):
        self.after_idle(self._maybe_load_more_logs)

    def _on_log_mousewheel_linux_down(self, event):
        return

    def _on_log_navigation(self, event):
        self.after_idle(self._maybe_load_more_logs)

    def _maybe_load_more_logs(self):
        if not self.selected_pod or self._loading_more_logs or not self._has_more_logs:
            return
        first, _ = self.pod_logs.yview()
        if first > 0:
            return
        current_logs = self.pod_logs.get("1.0", "end-1c")
        if not current_logs.strip() or current_logs == "Loading logs...":
            return
        self._loading_more_logs = True
        next_tail_lines = self._loaded_log_lines + self._log_chunk_size
        pod_name = self.selected_pod.metadata.name
        namespace = self.selected_pod.metadata.namespace
        request_token = self._log_request_token
        future = self.executor.submit(self._fetch_pod_logs_page, pod_name, namespace, next_tail_lines)
        future.add_done_callback(lambda f: self.after(0, self._handle_more_pod_logs_future, pod_name, namespace, request_token, next_tail_lines, f))

    def _fetch_pod_logs_page(self, pod_name: str, namespace: str, tail_lines: int) -> str:
        logs = self.kube.get_pod_logs_page(
            name=pod_name,
            namespace=namespace,
            tail_lines=tail_lines
        )
        return delete_color_marks(logs)

    def _prepend_logs(self, older_logs: str):
        if not older_logs:
            self._has_more_logs = False
            return
        current_top_index = self.pod_logs.index("@0,0")
        current_logs = self.pod_logs.get("1.0", "end-1c")
        combined_logs = f"{older_logs}{current_logs}"
        self.pod_logs.delete("1.0", tk.END)
        self.pod_logs.insert("1.0", combined_logs)
        self.pod_logs.see(current_top_index)
        if self.find_frame.winfo_ismapped():
            self.highlight_find_matches()

    def _handle_more_pod_logs_future(self, pod_name: str, namespace: str, request_token: int, tail_lines: int, future):
        self._loading_more_logs = False
        if request_token != self._log_request_token:
            return
        if not self.selected_pod:
            return
        if self.selected_pod.metadata.name != pod_name or self.selected_pod.metadata.namespace != namespace:
            return
        try:
            logs = future.result()
        except Exception as e:
            logger.exception("Ошибка при подгрузке логов: %s", e)
            self.status_bar.reset_status()
            return

        current_logs = self.pod_logs.get("1.0", "end-1c")
        if logs == current_logs:
            self._has_more_logs = False
            return

        older_logs = ""
        if current_logs and logs.endswith(current_logs):
            older_logs = logs[:-len(current_logs)]
        else:
            older_logs = logs

        if not older_logs:
            self._has_more_logs = False
            return

        self._loaded_log_lines = self._count_log_lines(logs)
        self._has_more_logs = self._count_log_lines(logs) >= tail_lines
        self._prepend_logs(older_logs)

    def search_default(self, button: ttk.Button):
        text = self._default_search_text.get(button) or button.cget("text")
        self.search_var.set(text)
        self.search_pods()

    def fill_default_search_buttons(self, search_name: str) -> None:
        search_name = search_name.strip()
        if not search_name:
            return
        existed_searchs = [self._default_search_text.get(x) or x.cget("text") for x in self.default_searches_buttons]
        if search_name in existed_searchs:
            return
        else:
            existed_searchs.pop(0)
            existed_searchs.append(search_name)
            for i, button in enumerate(self.default_searches_buttons):
                self._default_search_text[button] = existed_searchs[i]
                button.configure(text=existed_searchs[i])

    def load_pods(self):
        self.status_bar.set_status("Loading pods ...")
        self.pods_tree.delete(*self.pods_tree.get_children())
        self.namespace_nodes.clear()
        self.selected_pod = None
        self.pod_logs.delete(1.0, tk.END)
        self.clear_find_tags()
        self._reset_log_paging()
        self.refresh_btn["state"] = "disabled"
        self.download_btn["state"] = "disabled"
        future = self.executor.submit(self.kube.list_pods)
        future.add_done_callback(lambda f: self.after(0, self._handle_pods_future, f))

    def _handle_pods_future(self, future):
        try:
            pods = future.result()
        except Exception as e:
            logger.exception("Ошибка при получении подов: %s", e)
            messagebox.showerror("Ошибка", f"Ошибка при получении подов: {e}")
            self.status_bar.reset_status()
            return
        self.pods = pods
        self.filtered_pods = pods
        self._fill_treeview(self.filtered_pods)
        self.status_bar.reset_status()

    def _fill_treeview(self, pods, open_: bool = False):
        self.pods_tree.delete(*self.pods_tree.get_children())
        self.namespace_nodes.clear()
        ns_map = {}
        for pod in pods:
            ns = pod.metadata.namespace
            ns_map.setdefault(ns, []).append(pod)
        for ns, pods_in_ns in ns_map.items():
            ns_id = self.pods_tree.insert("", "end", text=ns, open=open_)
            self.namespace_nodes[ns] = ns_id
            for pod in pods_in_ns:
                indicator_color, ready_text, status_text, restarts_text = self._get_pod_status_info(pod)
                self.pods_tree.insert(
                    ns_id,
                    "end",
                    text=f"  {pod.metadata.name}",
                    image=self.indicator_images[indicator_color],
                    values=(ready_text, status_text, restarts_text)
                )
        self.pod_logs.delete(1.0, tk.END)
        self.clear_find_tags()
        self._reset_log_paging()
        self.refresh_btn["state"] = "disabled"
        self.download_btn["state"] = "disabled"

    def search_pods(self):
        query = self.search_var.get().strip().lower()
        if not query:
            self.filtered_pods = self.pods
        else:
            self.filtered_pods = [
                pod for pod in self.pods
                if query in pod.metadata.name.lower()
            ]
        self._fill_treeview(self.filtered_pods, open_=True)
        self.fill_default_search_buttons(self.search_var.get().strip())

    def reset_pods(self):
        self.search_var.set("")
        self.filtered_pods = self.pods
        self._fill_treeview(self.pods)

    def on_pod_select(self, event):
        selected = self.pods_tree.selection()
        if not selected:
            self.selected_pod = None
            self.refresh_btn["state"] = "disabled"
            self.download_btn["state"] = "disabled"
            self.pod_logs.delete(1.0, tk.END)
            self.clear_find_tags()
            self._reset_log_paging()
            return
        item_id = selected[0]
        parent_id = self.pods_tree.parent(item_id)
        if not parent_id:
            self.selected_pod = None
            self.refresh_btn["state"] = "disabled"
            self.download_btn["state"] = "disabled"
            self.pod_logs.delete(1.0, tk.END)
            self.clear_find_tags()
            self._reset_log_paging()
            return
        ns = self.pods_tree.item(parent_id, "text")
        pod_name = self.pods_tree.item(item_id, "text").strip()
        pod = next((p for p in self.filtered_pods if p.metadata.namespace == ns and p.metadata.name == pod_name), None)
        self.selected_pod = pod
        self.refresh_btn["state"] = "normal"
        self.download_btn["state"] = "normal"
        self.show_pod_logs(pod)

    def on_right_click(self, event):
        item_id = self.pods_tree.identify_row(event.y)
        parent_id = self.pods_tree.parent(item_id)
        if item_id and parent_id:
            pod_name = format_pod_name(self.pods_tree.item(item_id, "text").strip())
            self.right_click_pod_name = pod_name
            self.context_menu.tk_popup(event.x_root, event.y_root)
        else:
            self.right_click_pod_name = None

    def copy_pod_name(self):
        if self.right_click_pod_name:
            self.clipboard_clear()
            self.clipboard_append(self.right_click_pod_name)

    def show_pod_logs(self, pod):
        if pod is None:
            return
        self._reset_log_paging()
        self.pod_logs.delete(1.0, tk.END)
        self.clear_find_tags()
        self.pod_logs.insert(tk.END, "Loading logs...")
        self.status_bar.set_status(f"Loading logs for {pod.metadata.name} ...")
        pod_name = pod.metadata.name
        namespace = pod.metadata.namespace
        request_token = self._log_request_token
        future = self.executor.submit(self._fetch_pod_logs, pod_name, namespace)
        future.add_done_callback(lambda f: self.after(0, self._handle_pod_logs_future, pod_name, namespace, request_token, f))

    def _fetch_pod_logs(self, pod_name: str, namespace: str) -> str:
        logs = self.kube.get_pod_logs(
            name=pod_name,
            namespace=namespace,
            tail_lines=self._log_chunk_size
        )
        return delete_color_marks(logs)

    def _handle_pod_logs_future(self, pod_name: str, namespace: str, request_token: int, future):
        if request_token != self._log_request_token:
            return
        if not self.selected_pod:
            return
        if self.selected_pod.metadata.name != pod_name or self.selected_pod.metadata.namespace != namespace:
            return
        try:
            logs = future.result()
        except Exception as e:
            logger.exception("Ошибка при получении логов: %s", e)
            self.pod_logs.delete(1.0, tk.END)
            self.pod_logs.insert(tk.END, f"Ошибка при получении логов: {e}")
            self.pod_logs.see(tk.END)
            self.status_bar.reset_status()
            return
        self._loaded_log_lines = self._count_log_lines(logs)
        self._has_more_logs = self._loaded_log_lines >= self._log_chunk_size
        self.pod_logs.delete(1.0, tk.END)
        self.pod_logs.insert(tk.END, logs)
        self.pod_logs.see(tk.END)
        if self.find_frame.winfo_ismapped():
            self.highlight_find_matches()
        self.status_bar.reset_status()

    def refresh_logs(self):
        if self.selected_pod:
            self.show_pod_logs(self.selected_pod)
        else:
            self.status_bar.reset_status()

    def download_logs(self):
        if not self.selected_pod:
            return
        pod = self.selected_pod
        file_path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("All files", "*.*")],
            title="Сохранить логи пода как..."
        )
        if not file_path:
            return
        try:
            logs = self.kube.download_pod_logs(
                name=pod.metadata.name,
                namespace=pod.metadata.namespace
            )
            logs = delete_color_marks(logs)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(logs)
            messagebox.showinfo("Успех", f"Логи успешно сохранены в файл: {file_path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при скачивании логов: {e}")

    def filter_pods_by_labels(self, namespace, match_labels: dict):
        def pod_matches(pod):
            if pod.metadata.namespace != namespace:
                return False
            pod_labels = getattr(pod.metadata, 'labels', {}) or {}
            for k, v in match_labels.items():
                if pod_labels.get(k) != v:
                    return False
            return True
        self.filtered_pods = [pod for pod in self.pods if pod_matches(pod)]
        self._fill_treeview(self.filtered_pods)
