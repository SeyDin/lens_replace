from gui.app import KubeGUI
from kube.k8s_client import KubeClient

if __name__ == "__main__":
    kube_client = KubeClient()
    app = KubeGUI(kube_client)
    app.mainloop()
