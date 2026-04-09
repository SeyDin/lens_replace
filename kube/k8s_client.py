from kubernetes import client, config
from kubernetes.client.rest import ApiException


class KubeClient:
    def __init__(self):
        self.api = None
        self.apps_api = None

    def load_config(self, path):
        config.load_kube_config(config_file=path)
        self.api = client.CoreV1Api()
        self.apps_api = client.AppsV1Api()

    def list_pods(self):
        if not self.api:
            raise Exception("Kubernetes API не инициализирован. Сначала вызовите load_config().")
        return self.api.list_pod_for_all_namespaces().items

    def list_deployments(self):
        if not self.apps_api:
            raise Exception("Kubernetes Apps API не инициализирован. Сначала вызовите load_config().")
        return self.apps_api.list_deployment_for_all_namespaces().items

    def _read_pod_logs(self, name, namespace, tail_lines=None):
        if not self.api:
            raise Exception("Kubernetes API не инициализирован. Сначала вызовите load_config().")

        request_kwargs = {
            "name": name,
            "namespace": namespace,
            "_preload_content": False
        }
        if tail_lines is not None:
            request_kwargs["tail_lines"] = tail_lines

        response = self.api.read_namespaced_pod_log(**request_kwargs)
        raw_logs = response.data if hasattr(response, "data") else response

        if isinstance(raw_logs, bytes):
            return raw_logs.decode("utf-8", errors="replace")
        return str(raw_logs)

    def get_pod_logs(self, name, namespace, tail_lines=1000):
        return self._read_pod_logs(name=name, namespace=namespace, tail_lines=tail_lines)

    def get_pod_logs_page(self, name, namespace, tail_lines):
        return self._read_pod_logs(name=name, namespace=namespace, tail_lines=tail_lines)

    def download_pod_logs(self, name, namespace):
        if not self.api:
            raise Exception("Kubernetes API не инициализирован. Сначала вызовите load_config().")
        return self._read_pod_logs(name=name, namespace=namespace, tail_lines=30000)

    def scale_deployment(self, name, namespace, replicas):
        """\n        Масштабировать deployment до указанного количества реплик.\n        """
        if not self.apps_api:
            raise Exception("Kubernetes Apps API не инициализирован. Сначала вызовите load_config().")
        body = {'spec': {'replicas': replicas}}
        try:
            return self.apps_api.patch_namespaced_deployment(
                name=name,
                namespace=namespace,
                body=body
            )
        except ApiException as e:
            raise Exception(f"Ошибка при масштабировании deployment: {e}")
