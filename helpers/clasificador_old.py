# helpers/clasificador.py
import os
import time
import shutil
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from database.models import db, CausaInfo
from helpers.expte_parser import extraer_nro_expte_de_emergencia

# def ejecutar_clasificacion_inteligente(usuario_id, usuario_nombre, socketio, app_context):
#     options = webdriver.ChromeOptions()
#     # Ventana visible para el Captcha
#     driver = webdriver.Chrome(options=options)
#     wait = WebDriverWait(driver, 30)

#     try:
#         # 1. LOGIN AUTOMÁTICO EN FORUM
#         socketio.emit('bot_status', {'msg': '🔑 Abriendo Forum para Login...', 'progreso': 5})
#         driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.login")
        
#         # Esperamos a que carguen los campos de login (usando IDs de tu versión estable)
#         wait.until(EC.presence_of_element_located((By.ID, "vSECUSERNAME"))).send_keys("RicardoM")
#         driver.find_element(By.ID, "vSECUSERPASSWORD").send_keys("1942")
        
#         socketio.emit('bot_status', {'msg': '⚠️ Resolvé el Captcha e iniciá sesión', 'progreso': 10})
        
#         # Esperar a que el usuario loguee manualmente
#         while "login" in driver.current_url:
#             time.sleep(1)

#         # 2. PROCESO DE CLASIFICACIÓN
#         ruta_base = os.path.join(os.getcwd(), 'expedientes_clientes', usuario_nombre)
#         ruta_importados = os.path.join(ruta_base, 'IMPORTADOS')
        
#         if not os.path.exists(ruta_importados):
#             socketio.emit('bot_error', {'msg': 'No se encontró la carpeta IMPORTADOS'})
#             return

#         carpetas = [d for d in os.listdir(ruta_importados) if os.path.isdir(os.path.join(ruta_importados, d))]
#         total = len(carpetas)

#         for idx, nombre_folder in enumerate(carpetas):
#             # 🛡️ INICIALIZACIÓN DE VARIABLES (Esto evita el error de 'not associated with a value')
#             nro_completo = nombre_folder.split(' _ ')[0] if ' _ ' in nombre_folder else ""
#             juz_final = "POR CLASIFICAR"
#             sec_final = "REVISAR"
#             demandado_final = "CARATULA NO ENCONTRADA"
            
#             # Validación de formato
#             if "-" not in nro_completo:
#                 socketio.emit('bot_log', {'log': [f'⚠️ Saltado: {nombre_folder} (Sin número válido)']})
#                 continue

#             nro_solo = nro_completo.split('-')[0]
            
#             # Emitimos estado (ahora juz_final siempre tiene valor)
#             socketio.emit('bot_status', {
#                 'msg': f'⚖️ Clasificando: {nro_completo}',
#                 'progreso': int(((idx + 1) / total) * 100),
#                 'contador': f'{idx+1}/{total}',
#                 'detalle': f'📍 Ubicado en: {juz_final}',
#                 'estatus': 'TRABAJANDO'
#             })

#             # Navegar a búsqueda en Forum
#             driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.causass")
            
#             try:
#                 # Seleccionar Capital
#                 wait.until(EC.element_to_be_clickable((By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop"))).click()
#                 wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Capital')]"))).click()
                
#                 # Cargar Nro y Buscar
#                 input_nro = wait.until(EC.element_to_be_clickable((By.ID, "vCAUSANRO")))
#                 input_nro.clear()
#                 input_nro.send_keys(nro_solo)
#                 driver.find_element(By.ID, "BTN_SEARCH").click()
                
#                 time.sleep(4) # Espera para que cargue la grilla

#                 # 3. EXTRACCIÓN DE DATOS
#                 fila_xpath = f"//tr[td[3][contains(., '{nro_solo}')]]"
#                 wait.until(EC.presence_of_element_located((By.XPATH, fila_xpath)))
                
#                 juzgado_web = driver.find_element(By.XPATH, f"{fila_xpath}/td[1]").text.strip()
#                 caratula_web = driver.find_element(By.XPATH, f"{fila_xpath}/td[5]").text.strip()
                
#                 # Asignamos los valores finales reales
#                 juz_final = juzgado_web.replace("/", "-").upper()
#                 demandado_final = caratula_web.upper()
#                 sec_final = "SECRETARIA UNICA"

#             except Exception as e:
#                 print(f"⚠️ Error en Forum para {nro_completo}: {e}")
#                 # Los valores por defecto ya están seteados arriba

#             # 4. MUDANZA FÍSICA Y BASE DE DATOS
#             ruta_final = os.path.join(ruta_base, juz_final, sec_final, nro_completo)
#             os.makedirs(os.path.dirname(ruta_final), exist_ok=True)

#             try:
#                 # Mover carpeta física
#                 if not os.path.exists(ruta_final):
#                     shutil.move(os.path.join(ruta_importados, nombre_folder), ruta_final)
                
#                 # Registrar en DB
#                 with app_context:
#                     existe = CausaInfo.query.filter_by(numero=nro_completo, usuario_id=usuario_id).first()
#                     if not existe:
#                         nueva_causa = CausaInfo(
#                             numero=nro_completo,
#                             juzgado=juz_final,
#                             secretaria=sec_final,
#                             demandado=demandado_final,
#                             estado="En Trámite",
#                             usuario_id=usuario_id
#                         )
#                         db.session.add(nueva_causa)
#                         db.session.commit()
                
#                 # Log de éxito
#                 socketio.emit('bot_log', {
#                     'log': [
#                         f'✅ {nro_completo} -> {juz_final}', 
#                         f'📋 {demandado_final[:35]}...'
#                     ]
#                 })

#             except Exception as e:
#                 print(f"❌ Error al mover o guardar {nro_completo}: {e}")

#     except Exception as e:
#         print(f"❌ ERROR CRÍTICO: {e}")
#         socketio.emit('bot_error', {'msg': str(e)})
#     finally:
#         driver.quit()
def ejecutar_clasificacion_inteligente(usuario_id, usuario_nombre, socketio, app_context):
    options = webdriver.ChromeOptions()
    # Mantenemos la ventana visible para que resuelvas el Captcha si es necesario
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 30)

    try:
        # 1. LOGIN EN FORUM
        socketio.emit('bot_status', {'msg': '🔑 Abriendo Forum para Login...', 'progreso': 5})
        driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.login")
        
        # Carga automática de credenciales según tus IDs estables
        wait.until(EC.presence_of_element_located((By.ID, "vSECUSERNAME"))).send_keys("RicardoM")
        driver.find_element(By.ID, "vSECUSERPASSWORD").send_keys("1942")
        
        socketio.emit('bot_status', {'msg': '⚠️ Resolvé el Captcha e iniciá sesión', 'progreso': 10})
        socketio.emit('bot_log', {'log': ['📢 Esperando inicio de sesión manual...']})
        
        # Esperar a que el usuario pase el login
        while "login" in driver.current_url:
            time.sleep(1)

        # 2. PREPARACIÓN DE RUTAS
        ruta_base = os.path.join(os.getcwd(), 'expedientes_clientes', usuario_nombre)
        ruta_importados = os.path.join(ruta_base, 'IMPORTADOS')
        
        if not os.path.exists(ruta_importados):
            socketio.emit('bot_error', {'msg': 'No se encontró la carpeta IMPORTADOS'})
            return

        carpetas = [d for d in os.listdir(ruta_importados) if os.path.isdir(os.path.join(ruta_importados, d))]
        total = len(carpetas)
        socketio.emit('bot_log', {'log': [f'📁 Se encontraron {total} carpetas para clasificar.']})

        for idx, nombre_folder in enumerate(carpetas):
            # --- INICIALIZACIÓN DE VARIABLES POR CADA EXPEDIENTE ---
            nro_completo = nombre_folder.split(' _ ')[0] if ' _ ' in nombre_folder else ""
            juz_final = "POR CLASIFICAR"
            sec_final = "REVISAR"
            demandado_final = "CARATULA NO ENCONTRADA"
            
            if "-" not in nro_completo:
                socketio.emit('bot_log', {'log': [f'⚠️ Saltado: {nombre_folder} (Formato inválido)']})
                continue

            nro_solo = nro_completo.split('-')[0]
            
            # MONITOR: Actualización de estado principal
            socketio.emit('bot_status', {
                'msg': f'⚖️ Clasificando: {nro_completo}',
                'progreso': int(((idx + 1) / total) * 100),
                'contador': f'{idx+1}/{total}',
                'detalle': f'📍 Buscando en Forum...',
                'estatus': 'TRABAJANDO'
            })

            # MONITOR: Log detallado
            socketio.emit('bot_log', {'log': [f'🔍 Buscando expediente {nro_solo} en Capital...']})

            # Navegar a búsqueda
            driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.causass")
            
            try:
                # Selección de Localidad (Capital)
                wait.until(EC.element_to_be_clickable((By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop"))).click()
                wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Capital')]"))).click()
                
                # Cargar número y buscar
                input_nro = wait.until(EC.element_to_be_clickable((By.ID, "vCAUSANRO")))
                input_nro.clear()
                input_nro.send_keys(nro_solo)
                driver.find_element(By.ID, "BTN_SEARCH").click()
                
                time.sleep(3) # Espera técnica para carga de grilla

                # 3. EXTRACCIÓN
                fila_xpath = f"//tr[td[3][contains(., '{nro_solo}')]]"
                wait.until(EC.presence_of_element_located((By.XPATH, fila_xpath)))
                
                juzgado_web = driver.find_element(By.XPATH, f"{fila_xpath}/td[1]").text.strip()
                caratula_web = driver.find_element(By.XPATH, f"{fila_xpath}/td[5]").text.strip()
                
                juz_final = juzgado_web.replace("/", "-").upper()
                demandado_final = caratula_web.upper()
                sec_final = "SECRETARIA UNICA"

            except Exception as e:
                socketio.emit('bot_log', {'log': [f'❌ No se hallaron datos para {nro_completo} en la web.']})

            # 4. MOVIMIENTO FÍSICO Y BASE DE DATOS
            ruta_final = os.path.join(ruta_base, juz_final, sec_final, nro_completo)
            os.makedirs(os.path.dirname(ruta_final), exist_ok=True)

            try:
                if not os.path.exists(ruta_final):
                    shutil.move(os.path.join(ruta_importados, nombre_folder), ruta_final)
                
                with app_context:
                    existe = CausaInfo.query.filter_by(numero=nro_completo, usuario_id=usuario_id).first()
                    if not existe:
                        nueva_causa = CausaInfo(
                            numero=nro_completo,
                            juzgado=juz_final,
                            secretaria=sec_final,
                            demandado=demandado_final,
                            estado="En Trámite",
                            usuario_id=usuario_id
                        )
                        db.session.add(nueva_causa)
                        db.session.commit()
                
                # MONITOR: Log de éxito final por expediente
                socketio.emit('bot_log', {
                    'log': [
                        f'✅ Clasificado: {nro_completo}',
                        f'🏛️ Destino: {juz_final}',
                        f'👤 Carátula: {demandado_final[:40]}...'
                    ]
                })

            except Exception as e:
                socketio.emit('bot_log', {'log': [f'💥 Error al mover archivos de {nro_completo}']})

        socketio.emit('bot_status', {'msg': '✅ Proceso de Clasificación Finalizado', 'progreso': 100})

    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {e}")
        socketio.emit('bot_error', {'msg': str(e)})
    finally:
        driver.quit()