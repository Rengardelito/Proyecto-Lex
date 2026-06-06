"""
launcher.py — Punto de entrada del .exe de LexView Pro
Responsabilidades:
  1. Mostrar splash screen
  2. Verificar si hay actualizaciones disponibles en el VPS
  3. Descargar y aplicar la actualización si corresponde
  4. Lanzar app.py (Flask) en un subproceso
  5. Abrir el navegador

Estructura esperada en disco del cliente:
  LexViewPro/
  ├── LexViewPro.exe          ← este launcher compilado
  ├── _internal/              ← archivos extraídos por PyInstaller
  │   ├── app.py
  │   ├── config.py
  │   ├── bots/
  │   ├── helpers/
  │   ├── templates/
  │   ├── static/
  │   └── version.txt         ← "1.0.0"
  └── data/                   ← NUNCA se toca en updates
      ├── lexview.db
      ├── expedientes/
      └── config_local.json
"""

import os
import sys
import json
import time
import shutil
import zipfile
import hashlib
import logging
import tempfile
import threading
import subprocess
import webbrowser
from pathlib import Path

import requests
import tkinter as tk
from tkinter import ttk, messagebox

# ── Configuración ────────────────────────────────────────────
VPS_VERSION_URL  = "https://lexviewpro.com.ar/api/version"
VERSION_FILE     = "version.txt"
FLASK_PORT       = 5000
FLASK_STARTUP_TIMEOUT = 15  # segundos esperando que Flask levante

# Directorios que el updater PUEDE reemplazar
UPDATABLE_DIRS  = ["bots", "helpers", "templates", "static"]
UPDATABLE_FILES = ["app.py", "config.py"]

# Directorios que NUNCA se tocan
PROTECTED_DIRS  = ["data"]
PROTECTED_FILES = ["config_local.json", "version.txt"]  # version.txt se actualiza al final

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    filename="lexview_launcher.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("launcher")


# ════════════════════════════════════════════════════════════
# UTILIDADES
# ════════════════════════════════════════════════════════════

def get_base_dir() -> Path:
    """Directorio raíz de la instalación (donde está el .exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def get_internal_dir() -> Path:
    """Carpeta _internal/ donde viven los archivos de código."""
    base = get_base_dir()
    internal = base / "_internal"
    if internal.exists():
        return internal
    return base  # fallback para desarrollo


def get_local_version() -> str:
    """Lee la versión local desde _internal/version.txt."""
    version_path = get_internal_dir() / VERSION_FILE
    if version_path.exists():
        return version_path.read_text(encoding="utf-8").strip()
    return "0.0.0"


def get_hardware_id() -> str:
    """Lee el hardware ID desde config_local.json."""
    config_path = get_base_dir() / "data" / "config_local.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("hardware_id", "")
    return ""


def version_tuple(v: str):
    """Convierte '1.2.3' en (1, 2, 3) para comparar."""
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except ValueError:
        return (0, 0, 0)


def checksum_ok(filepath: Path, expected_sha256: str) -> bool:
    """Verifica integridad del archivo descargado."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest() == expected_sha256


# ════════════════════════════════════════════════════════════
# SPLASH SCREEN / UI
# ════════════════════════════════════════════════════════════

class SplashScreen:
    """Ventana de splash con barra de progreso durante el arranque/update."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("LexView Pro")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)  # sin bordes

        # Centrar en pantalla
        w, h = 480, 220
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.configure(bg="#1a1a2e")

        # Logo / título
        tk.Label(
            self.root, text="⚖  LexView Pro",
            font=("Segoe UI", 22, "bold"),
            fg="#e0e0ff", bg="#1a1a2e"
        ).pack(pady=(30, 4))

        tk.Label(
            self.root, text="Sistema de Gestión Judicial",
            font=("Segoe UI", 10),
            fg="#8888aa", bg="#1a1a2e"
        ).pack()

        # Mensaje de estado
        self.status_var = tk.StringVar(value="Iniciando...")
        self.status_label = tk.Label(
            self.root, textvariable=self.status_var,
            font=("Segoe UI", 9), fg="#aaaacc", bg="#1a1a2e"
        )
        self.status_label.pack(pady=(20, 6))

        # Barra de progreso
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Lex.Horizontal.TProgressbar",
            troughcolor="#0f0f23",
            background="#6c63ff",
            thickness=6,
        )
        self.progress = ttk.Progressbar(
            self.root, style="Lex.Horizontal.TProgressbar",
            length=380, mode="determinate"
        )
        self.progress.pack(pady=4)

        # Versión
        self.version_var = tk.StringVar(value=f"v{get_local_version()}")
        tk.Label(
            self.root, textvariable=self.version_var,
            font=("Segoe UI", 8), fg="#555577", bg="#1a1a2e"
        ).pack(pady=(8, 0))

        self.root.update()

    def set_status(self, msg: str, progress: int = None):
        self.status_var.set(msg)
        if progress is not None:
            self.progress["value"] = progress
        self.root.update()

    def set_version(self, v: str):
        self.version_var.set(f"v{v}")
        self.root.update()

    def close(self):
        self.root.destroy()

    def pump(self):
        """Procesar eventos Tk sin bloquear."""
        self.root.update()


# ════════════════════════════════════════════════════════════
# AUTO-UPDATER
# ════════════════════════════════════════════════════════════

class AutoUpdater:
    def __init__(self, splash: SplashScreen):
        self.splash = splash
        self.base_dir = get_base_dir()
        self.internal_dir = get_internal_dir()
        self.local_version = get_local_version()
        self.hw_id = get_hardware_id()

    # ── 1. Verificar versión ──────────────────────────────────
    def check_for_update(self) -> dict | None:
        """
        Consulta el VPS. Devuelve el dict de respuesta si hay update,
        None si está actualizado o no se puede contactar el servidor.
        """
        if not self.hw_id:
            log.warning("No se encontró hardware_id, saltando check de versión.")
            return None

        try:
            self.splash.set_status("Verificando actualizaciones...", 5)
            resp = requests.get(
                VPS_VERSION_URL,
                params={"hw_id": self.hw_id},
                timeout=8,
            )
            if resp.status_code != 200:
                log.warning(f"VPS respondió {resp.status_code} al chequear versión.")
                return None

            data = resp.json()
            remote_version = data.get("version", "0.0.0")

            log.info(f"Versión local: {self.local_version} | Remota: {remote_version}")

            if version_tuple(remote_version) > version_tuple(self.local_version):
                log.info("Actualización disponible.")
                return data
            else:
                log.info("El sistema está actualizado.")
                return None

        except requests.exceptions.ConnectionError:
            log.warning("Sin conexión al VPS. Continuando sin verificar updates.")
            return None
        except Exception as e:
            log.error(f"Error inesperado al chequear versión: {e}")
            return None

    # ── 2. Descargar zip ─────────────────────────────────────
    def download_update(self, url: str, expected_sha256: str = None) -> Path | None:
        """Descarga el zip de GitHub Releases a un directorio temporal."""
        try:
            self.splash.set_status("Descargando actualización...", 20)
            tmp_dir = Path(tempfile.mkdtemp(prefix="lexview_update_"))
            zip_path = tmp_dir / "update.zip"

            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                downloaded = 0

                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = 20 + int((downloaded / total) * 40)
                            self.splash.set_status(
                                f"Descargando... {downloaded // 1024} KB / {total // 1024} KB",
                                pct
                            )
                        self.splash.pump()

            log.info(f"Zip descargado en: {zip_path}")

            # Verificar checksum si el servidor lo provee
            if expected_sha256:
                if not checksum_ok(zip_path, expected_sha256):
                    log.error("Checksum inválido. Abortando update.")
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    return None
                log.info("Checksum OK.")

            return zip_path

        except Exception as e:
            log.error(f"Error descargando update: {e}")
            return None

    # ── 3. Aplicar update ────────────────────────────────────
    def apply_update(self, zip_path: Path, new_version: str) -> bool:
        """
        Extrae el zip sobre _internal/, reemplazando solo los archivos
        de código. Nunca toca data/ ni config_local.json.

        Estructura esperada dentro del zip:
          update/
          ├── app.py
          ├── config.py
          ├── bots/
          ├── helpers/
          ├── templates/
          └── static/
        """
        self.splash.set_status("Creando backup...", 62)

        # Backup de seguridad de los archivos actuales
        backup_dir = self.base_dir / f"_backup_{self.local_version}"
        try:
            self._backup_current(backup_dir)
        except Exception as e:
            log.warning(f"No se pudo crear backup completo: {e}")

        self.splash.set_status("Aplicando actualización...", 70)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                members = zf.namelist()

                for member in members:
                    # Normalizar ruta: quitar prefijo "update/" si existe
                    rel_path = Path(member)
                    parts = rel_path.parts
                    if parts and parts[0] in ("update", "update/"):
                        rel_path = Path(*parts[1:]) if len(parts) > 1 else None

                    if rel_path is None or str(rel_path) == ".":
                        continue

                    # Verificar que no pisa archivos protegidos
                    top_level = rel_path.parts[0] if rel_path.parts else ""
                    if top_level in PROTECTED_DIRS or str(rel_path) in PROTECTED_FILES:
                        log.info(f"Saltando archivo protegido: {rel_path}")
                        continue

                    # Verificar que el archivo está en la lista de actualizables
                    is_updatable = (
                        str(rel_path) in UPDATABLE_FILES
                        or top_level in UPDATABLE_DIRS
                    )
                    if not is_updatable:
                        log.info(f"Saltando archivo no autorizado: {rel_path}")
                        continue

                    # Extraer
                    dest = self.internal_dir / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)

                    if not member.endswith("/"):  # no es directorio
                        with zf.open(member) as src, open(dest, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        log.info(f"Actualizado: {rel_path}")

                    self.splash.pump()

            # Actualizar version.txt SOLO si todo salió bien
            version_path = self.internal_dir / VERSION_FILE
            version_path.write_text(new_version, encoding="utf-8")
            log.info(f"Versión actualizada a {new_version}")

            # Limpiar backup si el update fue exitoso
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)

            return True

        except Exception as e:
            log.error(f"Error aplicando update: {e}")
            self._restore_backup(backup_dir)
            return False

    def _backup_current(self, backup_dir: Path):
        """Copia los archivos actualizables al directorio de backup."""
        backup_dir.mkdir(parents=True, exist_ok=True)
        for name in UPDATABLE_FILES:
            src = self.internal_dir / name
            if src.exists():
                shutil.copy2(src, backup_dir / name)
        for name in UPDATABLE_DIRS:
            src = self.internal_dir / name
            if src.exists():
                shutil.copytree(src, backup_dir / name, dirs_exist_ok=True)
        log.info(f"Backup creado en: {backup_dir}")

    def _restore_backup(self, backup_dir: Path):
        """Restaura el backup si el update falló."""
        if not backup_dir.exists():
            return
        log.warning("Restaurando backup...")
        for name in UPDATABLE_FILES:
            src = backup_dir / name
            if src.exists():
                shutil.copy2(src, self.internal_dir / name)
        for name in UPDATABLE_DIRS:
            src = backup_dir / name
            if src.exists():
                dest = self.internal_dir / name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
        log.info("Backup restaurado.")

    # ── Flujo completo ───────────────────────────────────────
    def run(self) -> bool:
        """
        Ejecuta el ciclo completo de update.
        Retorna True si se aplicó una actualización.
        """
        update_info = self.check_for_update()
        if not update_info:
            return False

        new_version   = update_info["version"]
        download_url  = update_info["download_url"]
        sha256        = update_info.get("sha256")
        changelog     = update_info.get("changelog", "")

        msg = f"Hay una nueva versión disponible: v{new_version}\n"
        if changelog:
            msg += f"\nNovedades:\n{changelog}\n"
        msg += "\n¿Desea actualizar ahora?"

        if not messagebox.askyesno("Actualización disponible", msg):
            log.info("Usuario rechazó la actualización.")
            return False

        zip_path = self.download_update(download_url, sha256)
        if not zip_path:
            messagebox.showerror(
                "Error",
                "No se pudo descargar la actualización.\nSe iniciará la versión actual."
            )
            return False

        success = self.apply_update(zip_path, new_version)

        if success:
            self.splash.set_status(f"✓ Actualizado a v{new_version}", 100)
            time.sleep(1)

            try:
                shutil.rmtree(zip_path.parent, ignore_errors=True)
            except Exception:
                pass

            messagebox.showinfo(
                "Actualización completada",
                f"LexView Pro se actualizó a v{new_version}.\nEl sistema se reiniciará ahora."
            )

            self.splash.close()

            os.execv(sys.executable, [sys.executable] + sys.argv)

            return True

        else:
            try:
                shutil.rmtree(zip_path.parent, ignore_errors=True)
            except Exception:
                pass

            messagebox.showerror(
                "Error en la actualización",
                "No se pudo aplicar la actualización.\nSe restauró la versión anterior."
            )
            return False


# ════════════════════════════════════════════════════════════
# LANZADOR DE FLASK
# ════════════════════════════════════════════════════════════

def launch_flask(internal_dir: Path):
    """Lanza Flask en un thread dentro del mismo proceso."""
    import sys
    sys.path.insert(0, str(internal_dir))
    
    def _run():
        try:
            import app as flask_app
            flask_app.run_app()
        except Exception as e:
            log.error(f"Flask thread error: {e}")
            import traceback
            log.error(traceback.format_exc())
    
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    log.info("Flask lanzado en thread interno")
    return t


def wait_for_flask(port: int, timeout: int, splash: SplashScreen) -> bool:
    """Espera hasta que Flask responda en el puerto dado."""
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            splash.pump()
            time.sleep(0.5)
    return False

# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════

def main():
   
    base = get_base_dir()
    log.info(f"BASE_DIR: {base}")
    log.info(f"DATA_DIR: {base / 'data'}")
    # ── Crear carpeta data y config_local.json PRIMERO ───────
    
    data_dir = base / "data"
    data_dir.mkdir(exist_ok=True)
    config_path = data_dir / "config_local.json"
    if not config_path.exists():
        import json
        import hashlib
        import subprocess as _sp
        def _wmic(cmd):
            try:
                out = _sp.check_output(cmd, shell=True, stderr=_sp.DEVNULL, timeout=5).decode(errors='ignore')
                lines = [l.strip() for l in out.splitlines() if l.strip()]
                return lines[1] if len(lines) > 1 else ""
            except:
                return ""
        mb = _wmic("wmic csproduct get uuid")
        dk = _wmic("wmic diskdrive get serialnumber")
        raw = f"{mb}|{dk}"
        hw_id = hashlib.sha256(raw.encode()).hexdigest()[:32]
        config_path.write_text(
            json.dumps({"hardware_id": hw_id, "forum_user": "", "forum_pass": ""}),
            encoding="utf-8"
        )
        log.info(f"config_local.json creado: {hw_id}")
    splash = SplashScreen()
    splash.set_status("Iniciando LexView Pro...", 0)

    internal_dir = get_internal_dir()

    # ── Crear carpeta data y config_local.json si no existen ─
    data_dir = get_base_dir() / "data"
    data_dir.mkdir(exist_ok=True)
    config_path = data_dir / "config_local.json"
    if not config_path.exists():
        import json
        hw_id = get_hardware_id()
        config_path.write_text(
            json.dumps({"hardware_id": hw_id, "forum_user": "", "forum_pass": ""}),
            encoding="utf-8"
        )
        log.info(f"config_local.json creado con hardware_id: {hw_id}")

    # ── Auto-updater ─────────────────────────────────────────
    updater = AutoUpdater(splash)
    updated = updater.run()

    if updated:
        # Relanzar el exe para que tome los nuevos archivos
        # splash.close()
        # os.execv(sys.executable, [sys.executable] + sys.argv)
        return  # nunca llega acá

    # ── Lanzar Flask ─────────────────────────────────────────
    splash.set_status("Iniciando servidor...", 85)
    flask_proc = launch_flask(internal_dir)

    splash.set_status("Esperando servidor...", 90)
    if not wait_for_flask(FLASK_PORT, FLASK_STARTUP_TIMEOUT, splash):
        splash.close()
        stderr = "Flask no respondió. Revisá flask_stderr.log"
        log.error(f"Flask no respondió a tiempo.\nSTDERR:\n{stderr}")
        messagebox.showerror(
            "Error de inicio",
            f"LexView Pro no pudo iniciar correctamente.\n\nDetalle:\n{stderr[:500]}"
        )
        pass  # thread no necesita terminate
        sys.exit(1)

    # ── Abrir navegador ──────────────────────────────────────
    splash.set_status("Abriendo LexView Pro...", 98)
    time.sleep(0.3)
    webbrowser.open(f"http://127.0.0.1:{FLASK_PORT}")

    splash.close()
    log.info("Launcher completado. Flask corriendo.")

    # Mantener vivo hasta que el usuario cierre
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()