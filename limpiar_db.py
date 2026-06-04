import os
from app import app
from database.models import db, CausaInfo, Usuario

def probar_limpieza_fuera_del_bot(username_prueba):
    print(f"🚀 Iniciando simulacro de limpieza para el usuario: {username_prueba}")
    
    with app.app_context():
        # 1. Buscamos al usuario
        u = Usuario.query.filter_by(username=username_prueba).first()
        if not u:
            print("❌ Error: Usuario no encontrado en la base de datos.")
            return

        # 2. Definimos la ruta donde deberían estar las carpetas
        ruta_usuario = os.path.join("expedientes_clientes", username_prueba)
        
        # 3. Traemos los expedientes que la DB dice que existen
        expedientes_en_db = CausaInfo.query.filter_by(usuario_id=u.id).all()
        print(f"📊 La DB tiene {len(expedientes_en_db)} expedientes registrados.")

        registros_eliminados = 0
        
        for registro in expedientes_en_db:
            # Lógica de búsqueda: ¿Está el número de este registro en alguna subcarpeta?
            encontrado_en_disco = False
            
            # Caminamos por la carpeta del usuario buscando el número
            for root, dirs, files in os.walk(ruta_usuario):
                if registro.numero in dirs:
                    encontrado_en_disco = True
                    break
            
            if not encontrado_en_disco:
                print(f"🗑️  Huerfano detectado: {registro.numero}. No existe carpeta. Borrando...")
                db.session.delete(registro)
                registros_eliminados += 1
        
        # 4. Guardamos los cambios
        db.session.commit()
        print(f"✅ Limpieza completada. Se eliminaron {registros_eliminados} registros.")
        print(f"✨ Ahora la DB y tus carpetas están sincronizadas.")

if __name__ == "__main__":
    # Cambiá 'Nico' (o tu nombre de usuario en la DB) para probar
    NOMBRE_USUARIO = "Nicolas_Navarro" 
    probar_limpieza_fuera_del_bot(NOMBRE_USUARIO)