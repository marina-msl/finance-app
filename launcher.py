"""Ponto de entrada para o executável empacotado (PyInstaller).

Sobe o servidor e abre o navegador em http://127.0.0.1:8000 automaticamente.
Fechar esta janela encerra o servidor.
"""
import os
import threading
import webbrowser

import uvicorn

from main import app

PORT = int(os.environ.get("FINANCE_APP_PORT", "8000"))


def _open_browser():
    webbrowser.open(f"http://127.0.0.1:{PORT}")


if __name__ == "__main__":
    threading.Timer(1.5, _open_browser).start()
    uvicorn.run(app, host="127.0.0.1", port=PORT)
