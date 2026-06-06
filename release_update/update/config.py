import os
import sys

# ============================================
# RUTA BASE DINÁMICA
# ============================================
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

# ============================================
# RUTAS DERIVADAS
# ============================================
BASE_DATOS_PDFS      = os.path.join(BASE_PATH, 'expedientes_clientes')
TEMP_DOWNLOAD_PATH   = os.path.join(BASE_PATH, 'temp_downloads')
OUTPUT_STATIC        = os.path.join(BASE_PATH, 'static', 'output')
CARPETA_HOTFOLDER    = os.path.join(BASE_PATH, 'IMPORTAR_AQUI')
DB_PATH              = os.path.join(BASE_PATH, 'lexview.db')

# Carpeta para resúmenes PDF diarios (Mejora 1)
RESUMEN_DIARIO_PATH  = os.path.join(BASE_PATH, 'expedientes_clientes', 'RESUMEN_DIARIO')

for path in [BASE_DATOS_PDFS, TEMP_DOWNLOAD_PATH, OUTPUT_STATIC, CARPETA_HOTFOLDER, RESUMEN_DIARIO_PATH]:
    os.makedirs(path, exist_ok=True)

# ============================================
# TESSERACT OCR
# ============================================
_tesseract_local  = os.path.join(BASE_PATH, 'tesseract', 'tesseract.exe')
_tesseract_system = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

if os.path.exists(_tesseract_local):
    TESSERACT_PATH = _tesseract_local
elif os.path.exists(_tesseract_system):
    TESSERACT_PATH = _tesseract_system
else:
    TESSERACT_PATH = None

# ============================================
# FORUM (URLs fijas)
# ============================================
FORUM_URL_LOGIN          = "https://forumna.juscorrientes.gov.ar/com.forumna.login"
FORUM_URL_NOTIFICACIONES = "https://forumna.juscorrientes.gov.ar/com.forumna.notificaciones"
FORUM_URL_CAUSAS         = "https://forumna.juscorrientes.gov.ar/com.forumna.causass"

# ============================================
# SERVIDOR DE LICENCIAS
# ============================================
LICENSE_SERVER_URL = "https://lexviewpro.com.ar/api/verify"

# ============================================
# SELENIUM
# ============================================
SELENIUM_TIMEOUT = 20


# ============================================
# HARDWARE ID — Mejora 2
# Combina UUID de placa madre + serial de disco en un hash SHA256.
# Es prácticamente imposible de trasladar entre máquinas.
# Funciona solo en Windows (donde corre el .exe).
# Si falla cualquier parte, hace fallback a MAC address.
# ============================================
def get_hardware_id() -> str:
    """
    Devuelve un identificador de hardware único y estable para esta PC.
    Combina UUID de placa madre y número de serie del disco C:.
    Resultado: primeros 32 caracteres de SHA256 (ej: 'a3f1b2c4d5e6...')
    """
    import hashlib

    def _wmic(comando: str) -> str:
        """Ejecuta un comando wmic y devuelve la primera línea de datos."""
        import subprocess
        try:
            out = subprocess.check_output(
                comando, shell=True, stderr=subprocess.DEVNULL,
                timeout=5
            ).decode(errors='ignore')
            lineas = [l.strip() for l in out.splitlines() if l.strip()]
            # La primera línea es el encabezado, la segunda es el valor
            return lineas[1] if len(lineas) > 1 else ""
        except Exception:
            return ""

    mb_uuid  = _wmic("wmic csproduct get uuid")
    disk_ser = _wmic("wmic diskdrive get serialnumber")

    if mb_uuid or disk_ser:
        raw = f"{mb_uuid}|{disk_ser}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    # Fallback: MAC address (menos seguro, pero mejor que nada en Linux/Wine)
    import uuid as _uuid
    mac = ':'.join(
        ['{:02X}'.format((_uuid.getnode() >> ele) & 0xff)
         for ele in range(0, 8 * 6, 8)][::-1]
    )
    return hashlib.sha256(mac.encode()).hexdigest()[:32]