# import os
# import shutil
# import re
# import time
# from datetime import datetime
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.common.keys import Keys
# from webdriver_manager.chrome import ChromeDriverManager

# BASE_PATH = r"C:\Users\nico_\OneDrive\Escritorio\Proyecto Lex"

# def normalizar_nombre_juzgado(nombre):
#     # Quita espacios extra, unifica NRO.1 y NRO. 1
#     nombre = nombre.upper().strip()
#     nombre = re.sub(r'\s+', ' ', nombre) # Espacios múltiples -> 1
#     nombre = re.sub(r'NRO\.?\s*(\d+)', r'NRO.\1', nombre) # NRO. 1 -> NRO.1
#     nombre = re.sub(r'SECRETAR[IÍ]A\s+NRO\.?\s*(\d+)', r'SECRETARIA NRO.\1', nombre)
#     return nombre

# def normalizar_y_mapear_juzgado(nombre_forum, base_path_usuario):
#     """
#     Convierte 'JUZGADO CIVIL Y COMERCIAL NRO.1' en el nombre real que ya existe en disco.
#     Si no existe, devuelve el nombre normalizado.
#     """
#     # 1. Normalizar: quitar JUZGADO, espacios, puntos
#     nombre_limpio = nombre_forum.upper().strip()
#     nombre_limpio = re.sub(r'^JUZGADO\s+', '', nombre_limpio)
#     nombre_limpio = re.sub(r'\s+', ' ', nombre_limpio) # espacios múltiples -> 1
#     nombre_limpio = re.sub(r'NRO\.?\s*(\d+)', r'NRO.\1', nombre_limpio) # NRO. 1 -> NRO.1

#     # 2. Mapeos conocidos - agregá los tuyos acá
#     MAPEOS = {
#         "CIVIL Y COMERCIAL NRO.1": "CIVIL Y COMERCIAL NRO.1",
#         "CIVIL Y COMERCIAL NRO.2": "CIVIL Y COMERCIAL NRO.2",
#         "EJECUCION TRIBUTARIA NRO.1": "DE EJECUCION TRIBUTARIA",
#     }

#     # 3. Buscar si ya existe una carpeta parecida
#     if os.path.exists(base_path_usuario):
#         carpetas_existentes = [d for d in os.listdir(base_path_usuario)
#                               if os.path.isdir(os.path.join(base_path_usuario, d))]

#         for carpeta in carpetas_existentes:
#             # Comparamos sin espacios ni puntos
#             carpeta_norm = re.sub(r'[\s\.]', '', carpeta.upper())
#             limpio_norm = re.sub(r'[\s\.]', '', nombre_limpio.upper())
#             if carpeta_norm == limpio_norm:
#                 print(f"[MAPEO] Forum: '{nombre_forum}' -> Disco: '{carpeta}'")
#                 return carpeta

#     # 4. Si no existe, usar el mapeo o el nombre limpio
#     return MAPEOS.get(nombre_limpio, nombre_limpio)

# def bot_migrador(usuario_forum, clave_forum, progress_callback=None):
#     def emitir(msg, progreso=0):
#         if progress_callback:
#             progress_callback.emit('bot_status', {'msg': msg, 'progreso': progreso})
#             progress_callback.sleep(0.1)
#         print(f"[MIGRADOR] {msg}")

#     emitir("Abriendo Chrome...", 2)
#     driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
#     driver.maximize_window()
#     wait = WebDriverWait(driver, 20)

#     try:
#         # 1. LOGIN A FORUMNA - MISMO QUE bot_lexview.py
#         emitir("Yendo a página de Login...", 5)
#         driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.login")

#         emitir("Escribiendo usuario y clave...", 7)
#         wait.until(EC.presence_of_element_located((By.ID, "vSECUSERNAME"))).send_keys(usuario_forum)
#         driver.find_element(By.ID, "vSECUSERPASSWORD").send_keys(clave_forum)

#         emitir("RESOLVÉ EL CAPTCHA Y DALE INICIAR SESIÓN. Te espero 2 minutos...", 9)
#         # Espera a que desaparezca el login = que entraste
#         WebDriverWait(driver, 120).until_not(
#             EC.url_contains("login")
#         )
#         emitir("✅ Sesión iniciada", 10)
#         time.sleep(2)

#         # 2. IR A CONSULTAR EN LINEA - MISMO QUE bot_lexview.py
#         driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.causass")
#         time.sleep(2)

#         # 3. PROCESAR CARPETAS DE IMPORTADOS
#         ruta_importados = os.path.join(BASE_PATH, "expedientes_clientes", "nico", "IMPORTADOS")
#         if not os.path.exists(ruta_importados):
#             emitir("No existe carpeta IMPORTADOS", 100)
#             return

#         carpetas = [d for d in os.listdir(ruta_importados) if os.path.isdir(os.path.join(ruta_importados, d))]
#         total = len(carpetas)
#         procesados = 0
#         base_path_usuario = os.path.join(BASE_PATH, "expedientes_clientes", "nico")

#         for nombre_carpeta in carpetas:
#             ruta_origen = os.path.join(ruta_importados, nombre_carpeta)
#             procesados += 1
#             emitir(f"Procesando {procesados}/{total}: {nombre_carpeta}", int((procesados/total)*85)+10)

#             # Sacar nro y año: "262437-24 _ BARRERO"
#             match = re.search(r'(\d{5,6})[-_](\d{2})', nombre_carpeta)
#             if not match:
#                 emitir(f"⚠️ No se detectó nro expte en {nombre_carpeta}", 0)
#                 continue

#             nro_exp, anio_corto = match.groups()
#             anio_largo = "20" + anio_corto
#             nro_exp_completo = f"{nro_exp}-{anio_corto}"

#             # 4. CONSULTAR EN FORUMNA PARA SACAR JUZGADO/SECRETARIA REAL
#             try:
#                 # Select Capital
#                 wait.until(EC.element_to_be_clickable((By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop"))).click()
#                 time.sleep(0.5)
#                 wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Capital')]"))).click()

#                 # Cargar número y año
#                 input_nro = wait.until(EC.element_to_be_clickable((By.ID, "vCAUSANRO")))
#                 input_nro.clear()
#                 input_nro.send_keys(nro_exp)

#                 # Buscar
#                 driver.find_element(By.ID, "BTN_SEARCH").click()
#                 time.sleep(4)

#                 # LEER LA TABLA IGUAL QUE EN ASPIRADORA - detectando columnas por header
#                 headers = driver.find_elements(By.XPATH, "//table[contains(@class, 'Grid')]//tr[1]/th")
#                 idx_map = {}
#                 for i, h in enumerate(headers):
#                     texto_header = h.text.strip().upper()
#                     if 'ORGANISMO' in texto_header or 'JUZGADO' in texto_header:
#                         idx_map['juzgado'] = i
#                     elif 'SECRETARÍA' in texto_header or 'SECRETARIA' in texto_header:
#                         idx_map['secretaria'] = i

#                 if 'juzgado' not in idx_map:
#                     raise Exception("No se encontró columna ORGANISMO/JUZGADO")

#                 # Agarrar la primera fila de resultados
#                 fila = wait.until(EC.presence_of_element_located((By.XPATH, "//table[contains(@class, 'Grid')]//tr[td][1]")))
#                 celdas = fila.find_elements(By.TAG_NAME, "td")

#                 texto_organismo = celdas[idx_map['juzgado']].text.strip()
#                 texto_secretaria = celdas[idx_map.get('secretaria', -1)].text.strip() if idx_map.get('secretaria') is not None else ""

#                 # Parsear
#                 juzgado = re.sub(r'^JUZGADO\s+', '', texto_organismo, flags=re.IGNORECASE).strip()
#                 if not texto_organismo.upper().startswith('JUZGADO'):
#                     juzgado = f"JUZGADO {juzgado}"

#                 secretaria = texto_secretaria.strip() if texto_secretaria else "SECRETARIA NRO. 1"

#             except Exception as e:
#                 print(f"[FORUM] Error consultando {nro_exp_completo}: {e}")
#                 juzgado = "CIVIL Y COMERCIAL NRO.1" # Fallback ya normalizado
#                 secretaria = "SECRETARIA NRO. 1"

#             # 5. MAPEAR AL NOMBRE REAL QUE EXISTE EN DISCO - ESTO FALTABA
#             juzgado = normalizar_y_mapear_juzgado(juzgado, base_path_usuario)
#             secretaria = normalizar_y_mapear_juzgado(secretaria, os.path.join(base_path_usuario, juzgado))

#             emitir(f"Forum: {nro_exp_completo} → {juzgado} / {secretaria}", 0)

#             # Limpiar nombres para Windows
#             juzgado_seguro = re.sub(r'[\\/*?:"<>|]', "", juzgado).strip()
#             secretaria_segura = re.sub(r'[\\/*?:"<>|]', "", secretaria).strip()

#             destino_base = os.path.join(base_path_usuario, juzgado_seguro, secretaria_segura, nro_exp_completo)
#             os.makedirs(destino_base, exist_ok=True)

#             # 6. COPIAR PDFs CON FECHA DE MODIFICACIÓN DE WINDOWS - SIN OCR
#             pdfs = [f for f in os.listdir(ruta_origen) if f.lower().endswith('.pdf')]
#             contador = 0

#             for pdf in pdfs:
#                 origen = os.path.join(ruta_origen, pdf)
#                 timestamp = os.path.getmtime(origen)
#                 fecha_str = datetime.fromtimestamp(timestamp).strftime('%d-%m-%Y')

#                 nuevo_nombre = f"FECHA_{fecha_str}_ORDEN_{contador:03d}_{pdf}"
#                 destino = os.path.join(destino_base, nuevo_nombre)

#                 shutil.copy2(origen, destino) # Mantiene fecha original
#                 contador += 1

#             emitir(f"✅ OK: {nro_exp_completo} → {juzgado} / {secretaria}", 0)
#             # 7. BORRAR CARPETA DE IMPORTADOS - SOLO SI SE COPIÓ TODO OK
#             try:
#                 if contador > 0:  # Solo borra si copió al menos 1 PDF
#                     shutil.rmtree(ruta_origen)
#                     emitir(f"🗑️ Eliminada carpeta de IMPORTADOS: {nombre_carpeta}", 0)
#                 else:
#                     emitir(f"⚠️ No se borró IMPORTADOS: no se copió ningún PDF", 0)
#             except Exception as e:
#                 emitir(f"⚠️ Error borrando IMPORTADOS: {e}", 0)
                        
#             time.sleep(1)
            

#         emitir(f"Migración terminada: {procesados} carpetas", 100)

#     finally:
#         driver.quit()

# if __name__ == "__main__":
#     bot_migrador("RicardoM", "1942")
# migrador_lexview.py
# migrador_lexview.py
import os
import re
import shutil
import time
from threading import Event
from helpers.bot_base_old import BotBase
from helpers.expte_parser import extraer_nro_expte_de_emergencia
from helpers.forum_scraper_old import login_forum
from database.models import db, CausaInfo, Usuario
from config import BASE_DATOS_PDFS

class MigradorBot(BotBase):
    def __init__(self, usuario_sistema, socketio=None, stop_event=None):
        """
        Bot especializado en rescatar expedientes de carpetas viejas
        y darlos de alta en el sistema LexView.
        """
        super().__init__(socketio)
        self.usuario_sistema = usuario_sistema
        self.stop_event = stop_event or Event()
        self.ruta_usuario = os.path.join(BASE_DATOS_PDFS, usuario_sistema)

    def ejecutar_migracion(ruta_origen, usuario_actual, socketio):
     try:
        directorio_raiz = os.getcwd()
        ruta_destino_base = os.path.join(directorio_raiz, 'expedientes_clientes', usuario_actual, 'IMPORTADOS')

        print(f"🚀 Iniciando migración...")
        print(f"📂 Destino: {ruta_destino_base}")

        os.makedirs(ruta_destino_base, exist_ok=True)

        carpetas = [d for d in os.listdir(ruta_origen) if os.path.isdir(os.path.join(ruta_origen, d))]
        total = len(carpetas)
        exitosas = 0

        for idx, carpeta_v in enumerate(carpetas):
            ruta_v_completa = os.path.join(ruta_origen, carpeta_v)

            nro = extraer_nro_expte_de_emergencia(ruta_v_completa)
            nombre_final = f"{nro} _ {carpeta_v}" if nro else carpeta_v
            nombre_final = re.sub(r'[\\/*?:"<>|]', "", nombre_final)

            dest_final = os.path.join(ruta_destino_base, nombre_final)

            socketio.emit('bot_status', {
                'msg': f'📦 Migrando: {carpeta_v}',
                'progreso': int(((idx + 1) / total) * 100),
                'contador': f'{idx+1}/{total}'
            })

            if not os.path.exists(dest_final):
                try:
                    shutil.copytree(ruta_v_completa, dest_final)
                    exitosas += 1
                    print(f"✅ {nombre_final}")
                except Exception as e:
                    print(f"❌ Error copiando {carpeta_v}: {e}")
            else:
                print(f"ℹ️ Ya existía: {nombre_final}")

        socketio.emit('bot_finished', {
            'msg': f'✅ Migración finalizada. {exitosas} expedientes importados.'
        })

     except Exception as e:
        print(f"❌ ERROR CRÍTICO: {e}")
        socketio.emit('bot_error', {'msg': str(e)})
    def procesar_expediente_identificado(self, nro_expte, ruta_origen, nombre_carpeta_abogado):
        """
        Registra la causa en DB como PENDIENTE y mueve los archivos físicos.
        """
        try:
            user_id = self.get_user_id()
            if not user_id: return

            # Normalizar el nro para la carpeta
            nro_safe = nro_expte.replace("/", "-").replace(" ", "")

            # 1. Registro en Base de Datos
            causa = CausaInfo.query.filter_by(numero=nro_expte, usuario_id=user_id).first()
            
            if not causa:
                causa = CausaInfo(
                    numero=nro_expte,
                    nombre_carpeta=nro_safe,
                    demandado=nombre_carpeta_abogado.upper(),
                    juzgado="PENDIENTE_MIGRACION",
                    secretaria="EN_ESPERA",
                    usuario_id=user_id,
                    estado="Migrado - Pendiente de Clasificación"
                )
                db.session.add(causa)
                db.session.commit()

            # 2. Movimiento físico a la estructura de LexView
            ruta_destino = os.path.join(self.ruta_usuario, "PENDIENTE_MIGRACION", "EN_ESPERA", nro_safe)
            os.makedirs(ruta_destino, exist_ok=True)

            # Copiar archivos manteniendo metadatos
            for f in os.listdir(ruta_origen):
                origen_f = os.path.join(ruta_origen, f)
                if os.path.isfile(origen_f):
                    shutil.copy2(origen_f, ruta_destino)

            print(f"[OK] Migrado: {nro_expte}")

        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] No se pudo procesar {nro_expte}: {e}")

    def marcar_como_sin_numero(self, ruta_origen, nombre_carpeta):
        """
        Mueve las carpetas donde falló la detección a un lugar visible para el usuario.
        """
        ruta_revisar = os.path.join(self.ruta_usuario, "REVISAR_MANUAL", nombre_carpeta)
        os.makedirs(ruta_revisar, exist_ok=True)
        
        for f in os.listdir(ruta_origen):
            origen_f = os.path.join(ruta_origen, f)
            if os.path.isfile(origen_f):
                shutil.copy2(origen_f, ruta_revisar)
        
        print(f"[AVISO] Sin número detectable en: {nombre_carpeta}")

    def get_user_id(self):
        from app import app # Import local para evitar circular import
        with app.app_context():
            u = Usuario.query.filter_by(username=self.usuario_sistema).first()
            return u.id if u else None

# Para pruebas manuales
if __name__ == "__main__":
    # Esto es solo para testear por consola
    bot = MigradorBot("nico")
    # bot.ejecutar_migracion(r"C:\Ruta\De\Prueba", "user", "pass")