# import shutil
# import glob
# import requests
# import urllib3
# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.common.action_chains import ActionChains
# from selenium.webdriver.common.keys import Keys
# from webdriver_manager.chrome import ChromeDriverManager
# import time
# import os
# import re
# from datetime import datetime, date
# import fitz # PyMuPDF

# # ============================================
# # CONFIGURACIÓN GLOBAL
# # ============================================
# BASE_PATH = r"C:\Users\nico_\OneDrive\Escritorio\Proyecto Lex"
# TEMP_DOWNLOAD_PATH = os.path.join(BASE_PATH, "temp_downloads")

# # ============================================
# # FUNCIÓN AUXILIAR: Validar PDF
# # ============================================
# def es_pdf_valido(ruta_archivo):
#     """Chequea que el archivo empiece con %PDF- y tenga más de 100 bytes"""
#     try:
#         if not os.path.exists(ruta_archivo):
#             return False
#         if os.path.getsize(ruta_archivo) < 100:
#             return False
#         with open(ruta_archivo, 'rb') as f:
#             header = f.read(5)
#             return header == b'%PDF-'
#     except Exception as e:
#         print(f"[VALIDADOR ERROR] {e}")
#         return False

# # ============================================
# # FUNCIÓN: Crear estructura de carpetas
# # ============================================
# def crear_estructura_expediente(usuario_sistema, juzgado, secretaria, expte_numero):
#     """Crea la estructura de carpetas y devuelve la ruta final"""
#     ruta = os.path.join(
#         BASE_PATH,
#         "expedientes_clientes",
#         usuario_sistema,
#         juzgado,
#         f"{secretaria}",
#         expte_numero
#     )
#     os.makedirs(ruta, exist_ok=True)
#     print(f"Ruta asegurada: {ruta}")
#     return ruta

# # ============================================
# # FUNCIÓN NUEVA: Actualizar estado desde tabla
# # ============================================
# def actualizar_estado_desde_tabla(usuario_sistema, juzgado, secretaria, expte, filas_tabla):
#     """
#     Lee la tabla de actuaciones y actualiza el estado procesal.
#     Regla: Si Numero tiene 8+ dígitos, es proveído del juzgado.
#     """
#     try:
#         from app import app, db, CausaInfo

#         proveidos = []

#         for fila in filas_tabla:
#             numero = str(fila.get('Numero', '')).strip()
#             extracto = str(fila.get('Extracto', '')).strip()
#             fecha_str = str(fila.get('Fecha', '')).strip()

#             # Regla clave: 8 dígitos = proveído del juzgado
#             if len(numero) >= 8 and numero.isdigit():
#                 # Limpiamos basura del extracto
#                 extracto_limpio = re.sub(r'^\d{1,2}/\d{1,2}/\d{2,4}.*?-', '', extracto).strip()
#                 extracto_limpio = extracto_limpio.split(' - ')[0].strip()
#                 extracto_limpio = extracto_limpio.replace('Ã‘', 'Ñ').replace('Ã©', 'é').replace('Ã³', 'ó').replace('Ã¡', 'á').replace('Ã­', 'í').replace('Ãº', 'ú')

#                 if extracto_limpio:
#                     try:
#                         fecha_dt = datetime.strptime(fecha_str, '%d/%m/%Y').date()
#                         proveidos.append({
#                             'fecha_dt': fecha_dt,
#                             'estado': extracto_limpio[:100]
#                         })
#                     except:
#                         continue

#         if not proveidos:
#             print(f"[{expte}] No se encontraron proveídos en la tabla")
#             return None

#         # Ordenamos por fecha descendente y tomamos el primero
#         ultimo_proveido = sorted(proveidos, key=lambda x: x['fecha_dt'], reverse=True)[0]
#         nuevo_estado = ultimo_proveido['estado']

#         # Actualizamos CausaInfo usando el contexto de la app
#         with app.app_context():
#             info = db.session.query(CausaInfo).filter_by(nombre_carpeta=expte).first()
#             if not info:
#                 info = CausaInfo(nombre_carpeta=expte)
#                 db.session.add(info)

#             info.estado = nuevo_estado
#             db.session.commit()

#         print(f"[{expte}] Estado actualizado: {nuevo_estado}")
#         return nuevo_estado # Devolvemos el string, no el objeto

#     except Exception as e:
#         print(f"Error actualizando estado de {expte}: {e}")
#         try:
#             with app.app_context():
#                 db.session.rollback()
#         except:
#             pass
#         return None

# # ============================================
# # 1. ASPIRADORA - Detecta Secretaría y crea carpetas
# # ============================================
# def aspiradora_notificaciones(driver, wait, matricula, usuario_sistema, emit_event):
#     """
#     Parsea la tabla de notificaciones detectando columnas por header.
#     Devuelve: [{"nro": "262118/24", "tipo": "EXP", "juzgado": "CIVIL Y COMERCIAL NRO.1", "secretaria": "SECRETARIA NRO.1"},...]
#     Además crea las carpetas Juzgado/Secretaría/Expte automáticamente.
#     """
#     emit_event('bot_status', {'msg': '🔍 Entrando a Notificaciones...', 'progreso': 12, 'contador': '0/0'})
#     driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.notificaciones")
#     time.sleep(5)

#     # Filtros
#     emit_event('bot_status', {'msg': '📍 Seleccionando Localidad: Capital', 'progreso': 14, 'contador': '0/0'})
#     btn_combo_loc = wait.until(EC.element_to_be_clickable((By.ID, "COMBO_ID_LOCALIDADContainer_btnGroupDrop")))
#     btn_combo_loc.click()
#     time.sleep(1)
#     wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Capital')]"))).click()

#     # Matrícula
#     emit_event('bot_status', {'msg': f'✍️ Cargando matrícula: {matricula}', 'progreso': 16, 'contador': '0/0'})
#     input_mat = wait.until(EC.element_to_be_clickable((By.ID, "vMATRICULA")))
#     driver.execute_script("arguments[0].scrollIntoView(true);", input_mat)
#     time.sleep(0.5)
#     driver.execute_script("arguments[0].value = arguments[1];", input_mat, str(matricula))
#     driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", input_mat)
#     driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", input_mat)
#     time.sleep(1)

#     valor_final = input_mat.get_attribute('value')
#     if valor_final!= str(matricula):
#         emit_event('bot_error', {'msg': f'❌ No se pudo cargar la matrícula. Quedó: {valor_final}'})
#         return []

#     emit_event('bot_status', {'msg': f'✅ Matrícula {valor_final} cargada OK', 'progreso': 18, 'contador': '0/0'})

#     emit_event('bot_status', {'msg': '🔎 Buscando notificaciones...', 'progreso': 20, 'contador': '0/0'})
#     driver.find_element(By.XPATH, "//input[@value='Buscar']").click()
#     time.sleep(7)

#     expedientes = []
#     vistos = set()

#     try:
#         # Detectar columnas por header
#         headers = driver.find_elements(By.XPATH, "//table[contains(@class, 'Grid')]//tr[1]/th")
#         idx_map = {}
#         for i, h in enumerate(headers):
#             texto_header = h.text.strip().upper()
#             if 'EXPEDIENTES' in texto_header:
#                 idx_map['exptes'] = i
#             elif 'ORGANISMO' in texto_header:
#                 idx_map['juzgado'] = i
#             elif 'SECRETARÍA' in texto_header or 'SECRETARIA' in texto_header:
#                 idx_map['secretaria'] = i

#         print(f"[DEBUG] Mapa de columnas: {idx_map}")

#         if 'exptes' not in idx_map or 'juzgado' not in idx_map:
#             emit_event('bot_error', {'msg': '❌ No se encontraron las columnas Expedientes u Organismo'})
#             return []

#         filas = driver.find_elements(By.XPATH, "//table[contains(@class, 'Grid')]//tr[td]")
#         emit_event('bot_status', {'msg': f'📄 {len(filas)} filas encontradas en la tabla', 'progreso': 22, 'contador': '0/0'})
#         print(f"Encontradas {len(filas)} filas en la tabla\n")

#         for fila in filas:
#             celdas = fila.find_elements(By.TAG_NAME, "td")

#             try:
#                 texto_exptes = celdas[idx_map['exptes']].text.strip()
#                 texto_juzgado = celdas[idx_map['juzgado']].text.strip()
#                 texto_secretaria = celdas[idx_map.get('secretaria', -1)].text.strip() if idx_map.get('secretaria') is not None else "ÚNICA"
#             except IndexError:
#                 print(f"[SKIP] Fila con columnas insuficientes: {len(celdas)} celdas")
#                 continue

#             if not texto_exptes or not texto_juzgado:
#                 continue

#             juzgado_limpio = re.sub(r'^JUZGADO\s+', '', texto_juzgado, flags=re.IGNORECASE).strip()
#             secretaria_limpia = texto_secretaria.strip()
#             partes = texto_exptes.split(" - ")

#             for parte in partes:
#                 parte = parte.strip()
#                 if not parte:
#                     continue

#                 match = re.match(r'^([A-Z]+\d*)\s*(\d{4,6})(?:\s*/\s*(\d+))?$', parte)

#                 if match:
#                     tipo = match.group(1)
#                     nro = match.group(2)
#                     año = match.group(3)

#                     numero_completo = f"{nro}-{año}" if año else nro
#                     key = f"{tipo}{numero_completo}"

#                     if key not in vistos:
#                         exp_dict = {
#                             "nro": numero_completo,
#                             "tipo": tipo,
#                             "juzgado": juzgado_limpio,
#                             "secretaria": secretaria_limpia,
#                             "completo": f"{tipo} {numero_completo}"
#                         }
#                         expedientes.append(exp_dict)
#                         vistos.add(key)

#                         crear_estructura_expediente(
#                             usuario_sistema=usuario_sistema,
#                             juzgado=juzgado_limpio,
#                             secretaria=secretaria_limpia,
#                             expte_numero=numero_completo
#                         )

#                         print(f" ✅ {exp_dict['completo']} - {juzgado_limpio} - {secretaria_limpia}")
#                 else:
#                     print(f"[WARN] No matcheó regex: '{parte}'")

#         emit_event('bot_status', {'msg': f'🎯 Aspiradora: {len(expedientes)} expedientes únicos', 'progreso': 25, 'contador': f'0/{len(expedientes)}'})
#         print(f"\n🎯 ASPIRADORA: {len(expedientes)} expedientes únicos detectados")
#         return expedientes

#     except Exception as e:
#         emit_event('bot_error', {'msg': f'❌ Error en ASPIRADORA: {e}'})
#         print(f"❌ Error en ASPIRADORA: {e}")
#         return []

# # ============================================
# # 2. SELECTOR - Entrar al expediente
# # ============================================
# def entrar_expediente_correcto(driver, wait, expte_dict):
#     nro_completo = expte_dict["nro"]
#     tipo = expte_dict["tipo"]

#     if "-" in nro_completo:
#         nro, año = nro_completo.split("-")
#     else:
#         nro, año = nro_completo, ""

#     driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.causass")
#     time.sleep(2)

#     wait.until(EC.element_to_be_clickable((By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop"))).click()
#     wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Capital')]"))).click()

#     input_nro = wait.until(EC.element_to_be_clickable((By.ID, "vCAUSANRO")))
#     input_nro.clear()
#     input_nro.send_keys(nro)
#     driver.find_element(By.ID, "BTN_SEARCH").click()
#     time.sleep(3)

#     if año:
#         xpath_fila = f"""
#         //tr[
#             td[2][contains(normalize-space(.), '{tipo}')] and
#             td[3][contains(normalize-space(.), '{nro}')] and
#             td[4][contains(normalize-space(.), '{año}')]
#         ]//span[contains(text(), '{nro}')]
#         """
#     else:
#         xpath_fila = f"""
#         //tr[
#             td[2][contains(normalize-space(.), '{tipo}')] and
#             td[3][contains(normalize-space(.), '{nro}')]
#         ]//span[contains(text(), '{nro}')]
#         """

#     try:
#         celda_link = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_fila)))
#         ActionChains(driver).double_click(celda_link).perform()
#         print(f"✅ Entrando a: {expte_dict['completo']}")
#         time.sleep(4)
#         iframes = driver.find_elements(By.TAG_NAME, "iframe")
#         if iframes:
#             driver.switch_to.frame(iframes[0])
#             time.sleep(2)
#         return True
#     except Exception as e:
#         print(f"⚠️ No se pudo entrar a {expte_dict['completo']}: {e}")
#         return False

# # ============================================
# # 3A. DESCARGADOR - Solo fecha más reciente + Devuelve tabla
# # ============================================
# def descargar_solo_fecha_reciente(expte, destino_expte, descargas_dir, driver, wait):
#     descargas = 0
#     filas_tabla = []

#     try:
#         wait.until(EC.presence_of_element_located((By.XPATH, "//table//tbody")))
#         time.sleep(1)
#         print("📋 Tabla detectada")
#     except:
#         print("❌ No se detectó tabla de actuaciones")
#         return 0, []

#     # DETECTAR COLUMNAS POR HEADER - VERSIÓN MEJORADA
#     idx_map = {}
#     try:
#         headers = driver.find_elements(By.XPATH, "//table[contains(@class, 'Grid')]//tr[1]/th")
#         header_texts = []
#         for i, h in enumerate(headers):
#             texto_header = h.text.strip().upper()
#             header_texts.append(f"[{i}] {texto_header}")

#             if 'FECHA' in texto_header:
#                 idx_map['fecha'] = i
#             # AMPLIADO: más variantes de "Numero"
#             elif any(x in texto_header for x in ['NUMERO', 'NÚMERO', 'NRO', 'N°', 'Nº', 'NUM', 'NRO.', 'N°.', 'Nº.']):
#                 idx_map['numero'] = i
#             elif any(x in texto_header for x in ['EXTRACTO', 'DETALLE', 'DESCRIPCION', 'CARATULA']):
#                 idx_map['extracto'] = i
#             elif any(x in texto_header for x in ['DOCUMENTO', 'DOC']):
#                 idx_map['documento'] = i
#             elif any(x in texto_header for x in ['FIRMADA', 'FIRMA', 'FIRMANTE']):
#                 idx_map['firmada'] = i

#         print(f"[DEBUG] Headers encontrados: {' | '.join(header_texts)}")
#         print(f"[DEBUG] Mapa columnas expte: {idx_map}")

#         if 'fecha' not in idx_map or 'extracto' not in idx_map:
#             print("⚠️ No se encontraron columnas Fecha/Extracto")
#             return 0, []
#     except Exception as e:
#         print(f"Error detectando headers: {e}")
#         return 0, []

#     filas = driver.find_elements(By.XPATH, "//table//tbody/tr")
#     print(f"🔍 Filas encontradas: {len(filas)}")

#     if not filas:
#         print("No se encontraron actuaciones.")
#         return 0, []

#     # Ahora parseamos con fallback
#     for fila in filas:
#         try:
#             celdas = fila.find_elements(By.TAG_NAME, "td")
#             if len(celdas) < 3:
#                 continue

#             fecha_str = celdas[idx_map['fecha']].text.strip()

            
           
#             numero_str = celdas[idx_map['numero']].text.strip()

#             extracto_str = celdas[idx_map['extracto']].text.strip()
#             documento_str = celdas[idx_map['documento']].text.strip() if 'documento' in idx_map else ''
#             firmada_str = celdas[idx_map['firmada']].text.strip() if 'firmada' in idx_map else ''

#             filas_tabla.append({
#                 'Documento': documento_str,
#                 'Fecha': fecha_str,
#                 'Numero': numero_str,
#                 'Extracto': extracto_str,
#                 'Firmada': firmada_str
#             })
#         except Exception as e:
#             print(f"[DEBUG] Error parseando fila: {e}")
#             continue

#     if not filas_tabla:
#         print("⚠️ No se pudo parsear ninguna fila de la tabla")
#         return 0, []

#     # Resto igual que antes...
#     primera_fecha = ""
#     for fila_data in filas_tabla:
#         if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', fila_data['Fecha']):
#             primera_fecha = fila_data['Fecha']
#             print(f"✅ Fecha válida encontrada: {primera_fecha}")
#             break

#     if not primera_fecha:
#         print("⚠️ No se encontró ninguna fila con fecha válida")
#         return 0, filas_tabla

#     print(f"📅 Última fecha: {primera_fecha}")

#     main_window = driver.current_window_handle
#     fila_idx = 0
#     filas_elementos = driver.find_elements(By.XPATH, "//table//tbody/tr")

#     while fila_idx < len(filas_elementos):
#         fila = filas_elementos[fila_idx]

#         try:
#             celdas = fila.find_elements(By.TAG_NAME, "td")
#             fecha_fila = celdas[idx_map['fecha']].text.strip() if idx_map['fecha'] < len(celdas) else ""
#         except:
#             fila_idx += 1
#             continue

#         if not re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', fecha_fila):
#             fila_idx += 1
#             continue

#         if fecha_fila!= primera_fecha:
#             print("⏭️ Cambió la fecha. Fin de descarga.")
#             break

#         nombre_base = f"FECHA_{fecha_fila.replace('/', '-').replace(' ', '')}_ID_fila_{fila_idx:04d}"
#         dest_final_pdf = os.path.join(destino_expte, f"{nombre_base}.pdf")

#         if os.path.exists(dest_final_pdf):
#             print(f"⏩ Ya existe: {nombre_base}")
#             fila_idx += 1
#             continue

#         print(f"📥 Bajando actuación fila_{fila_idx:04d}...")

#         archivos_antes = set(os.listdir(descargas_dir))
#         try:
#             boton_ver = None
#             try:
#                 boton_ver = fila.find_element(By.XPATH, ".//td[1]//a")
#             except:
#                 try:
#                     boton_ver = fila.find_element(By.XPATH, ".//a[.//i]")
#                 except:
#                     boton_ver = fila.find_element(By.XPATH, ".//a")

#             if not boton_ver:
#                 raise Exception("No se encontró el link de la actuación")

#             driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", boton_ver)
#             time.sleep(0.5)
#             driver.execute_script("arguments[0].click();", boton_ver)

#             pdf_movido = False
#             for _ in range(15):
#                 time.sleep(1)
#                 archivos_despues = set(os.listdir(descargas_dir))
#                 nuevos = archivos_despues - archivos_antes
#                 pdfs_nuevos = [f for f in nuevos if f.endswith('.pdf') and not f.endswith('.crdownload')]
#                 if pdfs_nuevos:
#                     archivo_origen = os.path.join(descargas_dir, pdfs_nuevos[0])
#                     shutil.move(archivo_origen, dest_final_pdf)
#                     print(f"✅ PDF movido: {nombre_base}.pdf")
#                     descargas += 1
#                     pdf_movido = True
#                     break

#             if not pdf_movido:
#                 print(f"⚠️ No se detectó descarga automática en fila_{fila_idx}")

#         except Exception as e:
#             print(f"⚠️ Error al abrir fila_{fila_idx}: {e}")
#             fila_idx += 1
#             continue

#         fila_idx += 1

#     return descargas, filas_tabla
# # ============================================
# # 3B. DESCARGADOR - Ciclo cronológico
# # ============================================
# def descargar_ciclo_cronologico(expte, destino_expte, descargas_dir, driver, wait):
#     descargas = 0
#     main_window = driver.current_window_handle

#     try:
#         wait.until(EC.presence_of_element_located((By.XPATH, "//table//tbody")))
#         time.sleep(1)
#         print("📋 Tabla detectada")
#     except:
#         print("❌ No se detectó tabla de actuaciones")
#         return 0

#     filas = driver.find_elements(By.XPATH, "//table//tbody/tr")
#     print(f"🔍 Filas encontradas: {len(filas)}")

#     if not filas:
#         print("No se encontraron actuaciones.")
#         return 0

#     filas_filtradas = []
#     for idx, fila in enumerate(filas):
#         try:
#             celdas = fila.find_elements(By.TAG_NAME, "td")
#             if len(celdas) < 3:
#                 continue
#             fecha_texto = celdas[2].get_attribute('textContent').strip()
#             if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', fecha_texto):
#                 filas_filtradas.append(fila)
#         except:
#             continue

#     if not filas_filtradas:
#         print("No se encontraron actuaciones con fecha válida.")
#         return 0

#     fecha_minima = filas_filtradas[0].find_elements(By.TAG_NAME, "td")[2].get_attribute('textContent').strip()
#     print(f"📅 Fecha más antigua: {fecha_minima}")

#     fila_idx = 0
#     while fila_idx < len(filas_filtradas):
#         fila = filas_filtradas[fila_idx]

#         try:
#             fecha_actuacion_texto = fila.find_elements(By.TAG_NAME, "td")[2].get_attribute('textContent').strip()
#         except:
#             fila_idx += 1
#             continue

#         if not re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', fecha_actuacion_texto):
#             fila_idx += 1
#             continue

#         fecha_actuacion = fecha_actuacion_texto.replace('/', '-').replace(' ', '')
#         nombre_base = f"FECHA_{fecha_actuacion}_ID_fila_{fila_idx:04d}"
#         dest_final_pdf = os.path.join(destino_expte, f"{nombre_base}.pdf")

#         if os.path.exists(dest_final_pdf):
#             print(f"⏩ Ya existe: {nombre_base}")
#             fila_idx += 1
#             continue

#         print(f"📥 Bajando actuación fila_{fila_idx:04d}...")

#         try:
#             boton_ver = None
#             try:
#                 boton_ver = fila.find_element(By.XPATH, ".//td[1]//a")
#             except:
#                 try:
#                     boton_ver = fila.find_element(By.XPATH, ".//a[.//i]")
#                 except:
#                     boton_ver = fila.find_element(By.XPATH, ".//a")

#             if not boton_ver:
#                 raise Exception("No se encontró el link de la actuación")

#             driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", boton_ver)
#             time.sleep(0.5)

#             ActionChains(driver).key_down(Keys.CONTROL).click(boton_ver).key_up(Keys.CONTROL).perform()

#             WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > 1)
#             driver.switch_to.window(driver.window_handles[-1])

#             wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
#             time.sleep(2)

#             pdf_data = driver.execute_cdp_cmd("Page.printToPDF", {
#                 "printBackground": True,
#                 "paperWidth": 8.27,
#                 "paperHeight": 11.69,
#                 "marginTop": 0.4,
#                 "marginBottom": 0.4,
#                 "marginLeft": 0.4,
#                 "marginRight": 0.4
#             })

#             import base64
#             with open(dest_final_pdf, 'wb') as f:
#                 f.write(base64.b64decode(pdf_data['data']))

#             print(f"✅ PDF generado: {nombre_base}.pdf")
#             descargas += 1

#             driver.close()
#             driver.switch_to.window(main_window)
#             time.sleep(0.5)

#         except Exception as e:
#             print(f"⚠️ Error al procesar fila_{fila_idx}: {e}")
#             if len(driver.window_handles) > 1:
#                 driver.switch_to.window(driver.window_handles[-1])
#                 driver.close()
#             driver.switch_to.window(main_window)
#             fila_idx += 1
#             continue

#         fila_idx += 1

#     return descargas

# # ============================================
# # ORQUESTADOR PRINCIPAL - LEXVIEW PRO 2026
# # ============================================
# def bot_lexview(usuario_sistema, usuario_forum, clave_forum, matricula, modo="ACTUALIZAR", progress_callback=None):
#     def emit_event(event, data):
#         if progress_callback:
#             progress_callback.emit(event, data)
#             progress_callback.sleep(0.1)
#         print(data.get('msg', ''))

#     os.makedirs(TEMP_DOWNLOAD_PATH, exist_ok=True)

#     emit_event('bot_status', {'msg': '🚀 Iniciando Chrome...', 'progreso': 2, 'contador': '0/0'})

#     options = webdriver.ChromeOptions()
#     prefs = {
#         "download.default_directory": TEMP_DOWNLOAD_PATH,
#         "download.prompt_for_download": False,
#         "plugins.always_open_pdf_externally": True
#     }
#     options.add_experimental_option("prefs", prefs)

#     try:
#         driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
#         emit_event('bot_status', {'msg': '✅ Chrome abierto', 'progreso': 5, 'contador': '0/0'})
#     except Exception as e:
#         emit_event('bot_error', {'msg': f'No se pudo abrir Chrome: {str(e)}'})
#         return

#     wait = WebDriverWait(driver, 20)

#     try:
#         start_time = time.time()
#         emit_event('bot_status', {'msg': '🔑 Yendo a página de Login...', 'progreso': 7, 'contador': '0/0'})
#         driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.login")

#         emit_event('bot_status', {'msg': '✍️ Escribiendo usuario y clave...', 'progreso': 9, 'contador': '0/0'})
#         wait.until(EC.presence_of_element_located((By.ID, "vSECUSERNAME"))).send_keys(usuario_forum)
#         driver.find_element(By.ID, "vSECUSERPASSWORD").send_keys(clave_forum)

#         emit_event('bot_status', {'msg': '⏳ Esperando que resuelvas el Captcha e Iniciar Sesión...', 'progreso': 10, 'contador': 'Login'})
#         while "login" in driver.current_url:
#             time.sleep(2)

#         emit_event('bot_status', {'msg': '✅ Sesión iniciada correctamente', 'progreso': 11, 'contador': '0/0'})
#         print("✅ Sesión iniciada.")

#         expedientes = aspiradora_notificaciones(
#             driver=driver,
#             wait=wait,
#             matricula=matricula,
#             usuario_sistema=usuario_sistema,
#             emit_event=emit_event
#         )

#         if not expedientes:
#             emit_event('bot_status', {'msg': '❌ No hay expedientes para esa matrícula', 'progreso': 100, 'contador': '0/0'})
#             emit_event('bot_finished', {'exptes': 0, 'pdfs': 0, 'tiempo': '0s'})
#             return

#         total_exptes = len(expedientes)
#         total_pdfs = 0
#         log_items = []

#         for index, exp in enumerate(expedientes):
#             actual = index + 1
#             porc = int((actual / total_exptes) * 70) + 25

#             emit_event('bot_status', {
#                 'msg': f"Buscando expte: {exp['completo']}",
#                 'progreso': porc,
#                 'contador': f"{actual}/{total_exptes}",
#                 'current_exp': exp['completo'],
#                 'current_juzgado': exp['juzgado']
#             })

#             print(f"\n🚀 PROCESANDO: {exp['completo']}")

#             ruta_destino = os.path.join(
#                 BASE_PATH,
#                 "expedientes_clientes",
#                 usuario_sistema,
#                 exp['juzgado'],
#                 exp['secretaria'],
#                 exp['nro']
#             )
#             os.makedirs(ruta_destino, exist_ok=True)

#             try:
#                 if entrar_expediente_correcto(driver, wait, exp):
#                     emit_event('bot_status', {
#                         'msg': f'📥 Descargando actuaciones de {exp["nro"]}...',
#                         'progreso': porc,
#                         'contador': f"{actual}/{total_exptes}"
#                     })

#                     pdfs_nuevos = 0
#                     filas_tabla = []

#                     if modo == "ACTUALIZAR":
#                         pdfs_nuevos, filas_tabla = descargar_solo_fecha_reciente(exp['completo'], ruta_destino, TEMP_DOWNLOAD_PATH, driver, wait)
#                     else:
#                         pdfs_nuevos = descargar_ciclo_cronologico(exp['completo'], ruta_destino, TEMP_DOWNLOAD_PATH, driver, wait)

#                     # NUEVO: Actualizar estado procesal desde la tabla
#                     if filas_tabla:
#                         nuevo_estado = actualizar_estado_desde_tabla(
#                             usuario_sistema,
#                             exp['juzgado'],
#                             exp['secretaria'],
#                             exp['nro'],
#                             filas_tabla
#                         )
#                         if nuevo_estado:
#                             emit_event('bot_status', {
#                                 'msg': f'📋 Estado: {nuevo_estado}',
#                                 'progreso': porc,
#                                 'contador': f"{actual}/{total_exptes}"
#                             })

#                     total_pdfs += pdfs_nuevos
#                     log_items.insert(0, f"✅ {exp['completo']} - {pdfs_nuevos} PDFs")
#                     log_items = log_items[:3]
#                     emit_event('bot_log', {'log': log_items})

#                     driver.switch_to.default_content()
#                     time.sleep(1)
#                 else:
#                     print(f"⚠️ No se pudo entrar a {exp['completo']}, salteo")
#                     log_items.insert(0, f"⚠️ {exp['completo']} - No se pudo entrar")
#                     log_items = log_items[:3]
#                     emit_event('bot_log', {'log': log_items})

#             except Exception as e:
#                 print(f"❌ Error en {exp['completo']}: {e}")
#                 log_items.insert(0, f"❌ {exp['completo']} - Error")
#                 log_items = log_items[:3]
#                 emit_event('bot_log', {'log': log_items})
#                 try:
#                     driver.switch_to.default_content()
#                     while len(driver.window_handles) > 1:
#                         driver.switch_to.window(driver.window_handles[-1])
#                         driver.close()
#                     driver.switch_to.window(driver.window_handles[0])
#                 except:
#                     print("⚠️ No se pudo recuperar la sesión")
#                     pass
#                 continue

#         duracion_seg = int(time.time() - start_time)
#         duracion_formateada = f"{duracion_seg // 60}m {duracion_seg % 60}s"

#         emit_event('bot_finished', {
#             'exptes': total_exptes,
#             'pdfs': total_pdfs,
#             'tiempo': duracion_formateada
#         })

#     except Exception as e:
#         emit_event('bot_error', {'msg': f'Error crítico: {str(e)}'})
#     finally:
#         emit_event('bot_status', {'msg': '👋 Cerrando Chrome...', 'progreso': 100, 'contador': 'Listo'})
#         try:
#             if 'driver' in locals():
#                 driver.quit()
#         except:
#             pass
#         print("\n🎉 PROCESO COMPLETO FINALIZADO")

# if __name__ == "__main__":
#     bot_lexview("nico", "RicardoM", "1942", "11221", modo="ACTUALIZAR")

# bot_lexview.py - Versión Refactorizada 2026
import os
import time
import re
import shutil
from datetime import datetime
from selenium.webdriver.common.by import By
from helpers.bot_base_old import BotBase
from helpers.forum_scraper_old import login_forum, entrar_expediente_correcto
from config import BASE_PATH, TEMP_DOWNLOAD_PATH

class BotLexview(BotBase):
    def __init__(self, user_forum, pass_forum, matricula, socketio=None):
        super().__init__(socketio)
        self.user_forum = user_forum
        self.pass_forum = pass_forum
        self.matricula = matricula

    import shutil # Asegurate de tener esto arriba de todo en el archivo

def descargar_solo_fecha_reciente(self, expte_nro, destino_expte, descargas_dir):
    """Descarga solo las actuaciones que no existen localmente basándose en la fecha"""
    self.emit_event('bot_status', f"📂 Escaneando carpeta local de {expte_nro}...", 40)
    
    # 1. Escaneamos qué fechas (ISO) ya tenemos bajadas
    fechas_existentes = []
    if os.path.exists(destino_expte):
        for f in os.listdir(destino_expte):
            if f.endswith('.pdf') and " - " in f:
                fechas_existentes.append(f.split(" - ")[0])

    try:
        # 2. Localizamos la tabla de actuaciones en Forum
        filas = self.driver.find_elements(By.XPATH, "//table[@id='tablaActuaciones']/tbody/tr")
        pdfs_nuevos = 0

        for fila in filas:
            try:
                # Sacamos datos de la tabla
                fecha_web = fila.find_element(By.XPATH, "./td[1]").text.strip()
                tipo_actuacion = fila.find_element(By.XPATH, "./td[3]").text.strip()
                
                fecha_dt = datetime.strptime(fecha_web, "%d/%m/%Y")
                fecha_iso = fecha_dt.strftime("%Y-%m-%d")

                # 🚀 FILTRO: Si ya existe la fecha, saltamos
                if fecha_iso in fechas_existentes:
                    continue

                # ⬇️ DESCARGA
                link_descarga = fila.find_element(By.XPATH, ".//a[contains(@href, '.pdf')]")
                link_descarga.click()
                
                # --- ESPERA INTELIGENTE POR EL ARCHIVO ---
                # Esperamos que el archivo aparezca en la carpeta de descargas temporales
                time.sleep(4) # Tiempo prudencial para que Chrome termine
                
                # Buscamos el archivo más reciente en la carpeta de descargas
                # (Asumimos que Chrome baja el PDF con un nombre genérico o el de Forum)
                archivos_temp = sorted(
                    [f for f in os.listdir(descargas_dir) if f.lower().endswith('.pdf')],
                    key=lambda x: os.path.getmtime(os.path.join(descargas_dir, x)),
                    reverse=True
                )

                if archivos_temp:
                    ultimo_pdf = archivos_temp[0]
                    ruta_origen = os.path.join(descargas_dir, ultimo_pdf)
                    
                    # Renombrado Pro
                    nombre_limpio = f"{fecha_iso} - {tipo_actuacion}.pdf".replace("/", "_").replace(":", "_")
                    ruta_destino = os.path.join(destino_expte, nombre_limpio)

                    # MOVER AL DESTINO FINAL
                    os.makedirs(destino_expte, exist_ok=True)
                    shutil.move(ruta_origen, ruta_destino)
                    
                    pdfs_nuevos += 1
                    self.emit_event('bot_status', f"✅ Guardado: {nombre_limpio}", 60)

            except Exception as e:
                print(f"Error en fila de actuación: {e}")
                continue
        
        return pdfs_nuevos

    except Exception as e:
        self.emit_event('bot_error', f"No se pudo leer la tabla de actuaciones: {str(e)}")
        return 0

    def ejecutar_actualizacion(self, usuario_sistema):
        self.iniciar_driver()
        try:
            # 1. Login
            if not login_forum(self.driver, self.user_forum, self.pass_forum):
                return

            # 2. Aspiradora (Movería esta lógica a helpers/forum_scraper si la vas a reusar)
            # Por ahora la dejamos acá para procesar las Notificaciones Automáticas
            # ... (Aquí va tu código de leer la tabla de notificaciones) ...

            # 3. Match y Movimiento (Tu función de reclasificación)
            # mover_expte_si_existe_en_default(...)
            
            self.emit_event('bot_status', "✅ Actualización finalizada", 100)
        finally:
            self.cerrar()

# El puente para Flask
def bot_lexview(usuario_sistema, usuario_forum, clave_forum, matricula, modo="ACTUALIZAR", progress_callback=None):
    bot = BotLexview(usuario_forum, clave_forum, matricula, progress_callback)
    bot.ejecutar_actualizacion(usuario_sistema)

    