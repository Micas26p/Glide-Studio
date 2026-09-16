"""Offline web launcher. Never terminates a process to claim its port."""
import json
import socket
import threading
import urllib.request
import webbrowser

import uvicorn
from desktop_app import default_data_root, wait_for_health


def main():
    host, port = '127.0.0.1', 8787
    url = f'http://{host}:{port}'
    with socket.socket() as probe:
        occupied = probe.connect_ex((host, port)) == 0
    if occupied:
        try:
            with urllib.request.urlopen(url + '/api/health', timeout=2) as response:
                health = json.load(response)
            if health.get('ok') and health.get('data_root') == str(default_data_root()):
                webbrowser.open(url)
                return 0
        except (OSError, ValueError):
            pass
        print(f'A porta {port} esta em uso por outro processo. Feche-o ou use iniciar.bat.')
        return 1

    def open_when_ready():
        try:
            wait_for_health(url)
            webbrowser.open(url)
        except RuntimeError as exc:
            print(exc)

    threading.Thread(target=open_when_ready, daemon=True).start()
    uvicorn.run('app:app', host=host, port=port)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
