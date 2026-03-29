import re

def format_pod_name(pod_name: str) -> str:
    res_list = []
    for sym in pod_name:
        if pod_name not in ("\n", " "):
            res_list.append(sym)
    return "".join(res_list)


def delete_color_marks(log: str) -> str:
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    return ansi_escape.sub('', log)