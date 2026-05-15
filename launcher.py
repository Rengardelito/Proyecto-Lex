"""
launcher.py
===========
Punto de entrada del .exe
Arranca Flask en background y abre el browser en localhost:5000
"""
import sys
import os
import time
import threading
import webbrowser

if getattr(sys, 'frozen', False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE)
os.chdir(BASE)

def abrir_browser():
    time.sleep(2.5)
    webbrowser.open("http://127.0.0.1:5000")

def main():
    t = threading.Thread(target=abrir_browser, daemon=True)
    t.start()

    from app import app, socketio, db
    with app.app_context():
        db.create_all()

    socketio.run(app, host='127.0.0.1', port=5000, debug=False, allow_unsafe_werkzeug=True)
if __name__ == '__main__':
    main()