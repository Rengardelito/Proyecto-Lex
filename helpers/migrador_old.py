# helpers/migrador.py
import re
import os
import shutil
from .expte_parser import extraer_nro_expte_de_emergencia

def ejecutar_migracion_legado(ruta_origen, usuario_actual, socketio):
    try:
        # 1. DETECCIÓN AUTOMÁTICA DE RUTA:
        # Esto busca la carpeta donde está corriendo tu app.py
        directorio_raiz = os.getcwd() 
        
        # 2. CONSTRUCCIÓN DE RUTA DINÁMICA:
        # Así, si el usuario es 'nico', va a /nico/. Si es 'juan', va a /juan/.
        ruta_destino_base = os.path.join(directorio_raiz, 'expedientes_clientes', usuario_actual, 'IMPORTADOS')
        
        print(f"🚀 Iniciando migración...")
        print(f"📂 Destino detectado: {ruta_destino_base}")
        
        if not os.path.exists(ruta_destino_base):
            os.makedirs(ruta_destino_base, exist_ok=True)
        
        # Listamos las carpetas de la tanda que elegiste
        carpetas = [d for d in os.listdir(ruta_origen) if os.path.isdir(os.path.join(ruta_origen, d))]
        total = len(carpetas)
        exitosas = 0
        
        for idx, carpeta_v in enumerate(carpetas):
            ruta_v_completa = os.path.join(ruta_origen, carpeta_v)
            
            # Usamos tu parser veloz para sacar el número de expediente
            nro = extraer_nro_expte_de_emergencia(ruta_v_completa)
            
            # Nombre de la carpeta: "NRO _ NOMBRE ORIGINAL"
            nombre_final = f"{nro} _ {carpeta_v}" if nro else carpeta_v
            # Limpiamos caracteres prohibidos por Windows
            nombre_final = re.sub(r'[\\/*?:"<>|]', "", nombre_final)
            
            dest_final = os.path.join(ruta_destino_base, nombre_final)
            
            # Avisamos al Dashboard
            socketio.emit('bot_status', {
                'msg': f'Migrando: {carpeta_v}',
                'progreso': int(((idx + 1) / total) * 100),
                'contador': f'{idx+1}/{total}'
            })

            if not os.path.exists(dest_final):
                try:
                    shutil.copytree(ruta_v_completa, dest_final)
                    exitosas += 1
                    print(f"✅ OK: {nombre_final}")
                except Exception as e:
                    print(f"❌ Error al copiar {carpeta_v}: {e}")
            else:
                print(f"ℹ️ Ya existía: {nombre_final}")

        print(f">>> MIGRACIÓN FINALIZADA. TOTAL NUEVOS: {exitosas}")
        socketio.emit('bot_finished', {
            'exptes': exitosas,
            'msg': f'Se vincularon {exitosas} expedientes a tu legajo.'
        })

    except Exception as e:
        print(f"❌ ERROR CRÍTICO EN MIGRACIÓN: {e}")
        socketio.emit('bot_error', {'msg': str(e)})