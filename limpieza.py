import os
from database.models import db, CausaInfo, Usuario

def limpiar_huerfanos(username):
    """
    Elimina de la DB los registros de CausaInfo que no tienen
    carpeta física correspondiente. Llamar antes de importar datos.
    """
    u = Usuario.query.filter_by(username=username).first()
    if not u:
        print(f"[Limpieza] Usuario '{username}' no encontrado. Se omite limpieza.")
        return 0

    ruta_usuario = os.path.join("expedientes_clientes", username)
    expedientes_en_db = CausaInfo.query.filter_by(usuario_id=u.id).all()

    registros_eliminados = 0

    for registro in expedientes_en_db:
        encontrado_en_disco = False
        for root, dirs, files in os.walk(ruta_usuario):
            if registro.numero in dirs:
                encontrado_en_disco = True
                break

        if not encontrado_en_disco:
            print(f"[Limpieza] Huérfano eliminado: {registro.numero}")
            db.session.delete(registro)
            registros_eliminados += 1

    db.session.commit()
    print(f"[Limpieza] {registros_eliminados} registros eliminados para '{username}'.")
    return registros_eliminados