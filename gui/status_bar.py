import tkinter as tk
from tkinter import ttk

class StatusBar:
    def __init__(self, parent):
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = ttk.Label(parent, textvariable=self.status_var, relief=tk.SUNKEN, anchor="e")
        self.status_bar.pack(side="bottom", fill="x")

    def set_status(self, text: str):
        self.status_var.set(text)

    def reset_status(self):
        self.status_var.set("Ready")
