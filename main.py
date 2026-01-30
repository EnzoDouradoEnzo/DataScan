import threading
import webview
from app import app


def iniciar_flask():
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    threading.Thread(target=iniciar_flask, daemon=True).start()

    webview.create_window(
        "DataScan - Sistema Profissional",
        "http://127.0.0.1:5000",
        width=1200,
        height=750,
        resizable=True
    )

    webview.start()