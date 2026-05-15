# bots/migrador.py
import re
import os
import shutil
from helpers.expte_parser import extraer_nro_expte_de_emergencia

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