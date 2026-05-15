import re
import os
import time
import shutil
from datetime import datetime

# IMPORTS DE SELENIUM (Críticos para que no tire error)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# IMPORTS DEL PROYECTO
from helpers.bot_base_old import BotBase
from helpers.forum_scraper_old import login_forum, entrar_expediente_correcto
from database.models import db, CausaInfo, Usuario
from config import BASE_DATOS_PDFS, TEMP_DOWNLOAD_PATH

class SincronizadorBot(BotBase):
    def __init__(self, usuario_sistema, socketio=None):
        super().__init__(socketio)
        self.usuario_sistema = usuario_sistema
        # Ruta base donde están las carpetas del abogado (Corrientes)
        self.ruta_usuario = os.path.join("expedientes_clientes", usuario_sistema)

    def emitir_status(self, mensaje, progreso=None):
        """Envía la info al monitor negro del Dashboard"""
        if self.socketio:
            data = {'msg': mensaje}
            if progreso is not None:
                data['progreso'] = progreso
            self.socketio.emit('status_update', data)

    def aspiradora_local(self):
        """Busca qué carpetas tenés físicamente para saber qué sincronizar"""
        from app import app
        self.emitir_status("🔍 Escaneando expedientes locales...", 10)
        
        exptes_encontrados = []
        with app.app_context():
            u = Usuario.query.filter_by(username=self.usuario_sistema).first()
            if not u: return []

            # Recorre tus carpetas buscando el formato NNNNNN-AA
            for root, dirs, files in os.walk(self.ruta_usuario):
                for d in dirs:
                    if re.search(r'\d{5,6}-\d{2}', d):
                        nro_expte = d
                        ruta_completa = os.path.join(root, d)
                        
                        # Si no está en la DB, lo agregamos para que aparezca en el Dashboard
                        existe = CausaInfo.query.filter_by(numero=nro_expte, usuario_id=u.id).first()
                        if not existe:
                            nueva = CausaInfo(
                                numero=nro_expte,
                                demandado="SINCRO LOCAL",
                                juzgado="IMPORTADOS",
                                secretaria="MIGRACIONES",
                                usuario_id=u.id,
                                estado="Sincronizado Local"
                            )
                            db.session.add(nueva)
                        
                        exptes_encontrados.append({"nro": nro_expte, "ruta": ruta_completa})
            db.session.commit()
        return exptes_encontrados

    def descargar_tridente(self, exp_nro, ruta_local):
        """Compara fechas y baja solo lo nuevo"""
        fechas_locales = []
        if os.path.exists(ruta_local):
            for f in os.listdir(ruta_local):
                if " - " in f:
                    fechas_locales.append(f.split(" - ")[0])

        try:
            # Espera a que la tabla de Forum se dibuje
            time.sleep(2)
            # Buscamos las filas de la grilla de actuaciones
            filas = self.driver.find_elements(By.XPATH, "//table[contains(@id, 'Gridactuaciones')]//tr[contains(@class, 'Grid')]")
            
            nuevos = 0
            for fila in filas:
                try:
                    tds = fila.find_elements(By.TAG_NAME, "td")
                    fecha_web = tds[0].text.strip() # Columna Fecha
                    tipo = tds[2].text.strip()      # Columna Tipo
                    
                    if not fecha_web: continue
                    
                    fecha_dt = datetime.strptime(fecha_web, "%d/%m/%Y")
                    fecha_iso = fecha_dt.strftime("%Y-%m-%d")

                    if fecha_iso in fechas_locales:
                        continue # Este ya lo tenés en la Lenovo

                    # Si llegamos acá, es un PDF nuevo
                    link_pdf = fila.find_element(By.XPATH, ".//a[contains(@href, '.pdf')]")
                    link_pdf.click()
                    time.sleep(3) # Tiempo de descarga

                    # Buscamos el archivo en la carpeta temporal para moverlo
                    archivos = sorted([f for f in os.listdir(TEMP_DOWNLOAD_PATH) if f.lower().endswith('.pdf')], 
                                      key=lambda x: os.path.getmtime(os.path.join(TEMP_DOWNLOAD_PATH, x)), 
                                      reverse=True)
                    
                    if archivos:
                        nombre_final = f"{fecha_iso} - {tipo}.pdf".replace("/", "_").replace(":", "")
                        shutil.move(os.path.join(TEMP_DOWNLOAD_PATH, archivos[0]), os.path.join(ruta_local, nombre_final))
                        nuevos += 1
                        self.emitir_status(f"📥 Nuevo PDF: {nombre_final}", None)
                except:
                    continue
            return nuevos
        except Exception as e:
            print(f"Error en tridente: {e}")
            return 0

    def ejecutar(self, user_forum, pass_forum):
        self.iniciar_driver()
        wait = WebDriverWait(self.driver, 30) # Espera de hasta 30 segundos
        
        try:
            self.emitir_status("🔑 Abriendo Forum... Llenando campos", 15)
            self.driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.login")
            
            # --- MISMA LÓGICA DEL CLASIFICADOR ---
            # Llenamos los datos automáticamente
            wait.until(EC.presence_of_element_located((By.ID, "vSECUSERNAME"))).send_keys("RicardoM")
            self.driver.find_element(By.ID, "vSECUSERPASSWORD").send_keys("1942")
            
            self.emitir_status("⚠️ RESOLVÉ EL CAPTCHA Y ENTRÁ", 20)
            
            # El bot se queda esperando a que vos loguees manualmente
            while "login" in self.driver.current_url:
                time.sleep(1)

            self.emitir_status("🚀 Adentro! Iniciando Sincronización...", 25)
            
            expedientes = self.aspiradora_local()
            total = len(expedientes)

            for idx, exp in enumerate(expedientes, 1):
                progreso = int((idx / total) * 70) + 25
                self.emitir_status(f"🔎 Analizando {exp['nro']} ({idx}/{total})", progreso)

                # Entrar al expediente en Forum
                if entrar_expediente_correcto(self.driver, exp['nro']):
                    cant = self.descargar_tridente(exp['nro'], exp['ruta'])
                    if cant > 0:
                        self.emitir_status(f"✅ {exp['nro']}: {cant} archivos bajados.", progreso)
                
            self.emitir_status("🏁 SINCRONIZACIÓN FINALIZADA", 100)
            if self.socketio: self.socketio.emit('bot_finished')


        except Exception as e:
         import traceback
         traceback.print_exc() # esto te muestra la línea exacta
         self.emitir_status(f"❌ Error Crítico: {str(e)}", 0)
        finally:
        # self.cerrar() # comentá esto para debuggear
         input("Presioná Enter para cerrar Chrome...")    
        