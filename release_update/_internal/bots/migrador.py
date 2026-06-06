# bots/migrador.py
import re
import os
import shutil
from helpers.expte_parser import extraer_nro_expte_de_emergencia

def ejecutar_importar_backup(ruta_backup, usuario_nombre, usuario_id, socketio, app):
    
    from database.models import db, CausaInfo
    import config

    patron_expte = re.compile(r'^\d{4,6}-\d{1,4}$')

    socketio.emit('bot_status', {'msg': f'📂 Escaneando backup...'})

    encontrados = 0
    importados  = 0
    ya_existian = 0
    errores     = 0
    procesados  = set()

    def recorrer(ruta_actual, nivel=0):
        nonlocal encontrados, importados, ya_existian, errores

        try:
            contenido = [d for d in os.listdir(ruta_actual)
                        if os.path.isdir(os.path.join(ruta_actual, d))]
        except Exception:
            return

        for carpeta in contenido:
            ruta_carpeta = os.path.join(ruta_actual, carpeta)

            if patron_expte.match(carpeta):
                nro_expte = carpeta

                # Evitar duplicados
                if nro_expte in procesados:
                    continue
                procesados.add(nro_expte)

                encontrados += 1

                partes = os.path.relpath(ruta_carpeta, ruta_backup).split(os.sep)

                if len(partes) >= 3:
                    juzgado    = partes[-3]
                    secretaria = partes[-2]
                elif len(partes) == 2:
                    juzgado    = partes[-2]
                    secretaria = 'SECRETARIA UNICA'
                else:
                    juzgado    = 'SIN JUZGADO'
                    secretaria = 'SECRETARIA UNICA'

                socketio.emit('bot_status', {
                    'msg': f'📋 {nro_expte} — {juzgado}'
                })

                try:
                    with app.app_context():
                        ya_existe = CausaInfo.query.filter(
                            CausaInfo.numero == nro_expte,
                            CausaInfo.usuario_id == usuario_id
                        ).first()

                        if ya_existe:
                            ya_existian += 1
                            socketio.emit('bot_status', {
                                'msg': f'⏩ Ya existe: {nro_expte}'
                            })
                        else:
                            nueva = CausaInfo(
                                numero=nro_expte,
                                juzgado=juzgado,
                                secretaria=secretaria,
                                demandado='SIN CARATULAR',
                                estado='En Trámite',
                                usuario_id=usuario_id
                            )
                            db.session.add(nueva)
                            db.session.commit()

                    ruta_dest = os.path.join(
                        config.BASE_DATOS_PDFS,
                        usuario_nombre,
                        juzgado,
                        secretaria,
                        nro_expte
                    )
                    os.makedirs(ruta_dest, exist_ok=True)

                    pdfs_copiados = 0
                    for archivo in os.listdir(ruta_carpeta):
                        if archivo.lower().endswith('.pdf'):
                            origen  = os.path.join(ruta_carpeta, archivo)
                            destino = os.path.join(ruta_dest, archivo)
                            if not os.path.exists(destino):
                                shutil.copy2(origen, destino)
                                pdfs_copiados += 1

                    importados += 1
                    socketio.emit('bot_status', {
                        'msg': f'✅ {nro_expte}: {pdfs_copiados} PDFs'
                    })

                except Exception as e:
                    errores += 1
                    socketio.emit('bot_status', {
                        'msg': f'❌ Error en {nro_expte}: {str(e)}'
                    })

            else:
                if nivel < 5:
                    recorrer(ruta_carpeta, nivel + 1)

    recorrer(ruta_backup)

    socketio.emit('bot_status', {'msg': '━' * 40})
    socketio.emit('bot_status', {'msg': '📊 RESUMEN IMPORTACIÓN BACKUP'})
    socketio.emit('bot_status', {'msg': f'🔍 Encontrados: {encontrados}'})
    socketio.emit('bot_status', {'msg': f'✅ Importados: {importados}'})
    socketio.emit('bot_status', {'msg': f'⏩ Ya existían: {ya_existian}'})
    if errores:
        socketio.emit('bot_status', {'msg': f'❌ Errores: {errores}'})
    socketio.emit('bot_status', {'msg': '━' * 40})
    socketio.emit('bot_finished', {})

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