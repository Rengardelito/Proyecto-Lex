"""
crear_usuario.py
================
Ejecutar UNA SOLA VEZ para crear el primer usuario en la DB.
Uso:
    python crear_usuario.py

Después de esto, el login de LexView funciona con usuario+contraseña real.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from database.models import db, Usuario

def crear_usuario():
    with app.app_context():
        db.create_all()

        print("=== CREAR USUARIO LEXVIEW ===")
        username  = input("Nombre de usuario: ").strip()
        password  = input("Contraseña: ").strip()
        matricula = input("Matrícula (opcional, Enter para saltar): ").strip()
        forum_u   = input("Usuario Forum (opcional): ").strip()
        forum_p   = input("Contraseña Forum (opcional): ").strip()

        if Usuario.query.filter_by(username=username).first():
            print(f"❌ El usuario '{username}' ya existe.")
            return

        u = Usuario(
            username  = username,
            matricula = matricula or None,
            forum_user= forum_u or None,
            forum_pass= forum_p or None,
            licencia_activa = True   # activo por defecto para el piloto
        )
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        print(f"✅ Usuario '{username}' creado correctamente.")

if __name__ == '__main__':
    crear_usuario()