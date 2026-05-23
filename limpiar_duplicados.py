# ════════════════════════════════════════════════════════════
# 1. GUARDAR COMO: limpiar_duplicados.py en la raíz del proyecto
#    EJECUTAR CON: python limpiar_duplicados.py
# ════════════════════════════════════════════════════════════

import os
import shutil
import sys

# Agregar el path del proyecto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.path.join(os.getcwd(), "expedientes_clientes", "Nicolas_Navarro")

def limpiar_sin_secretaria():
    for juzgado in os.listdir(BASE):
        ruta_juzgado = os.path.join(BASE, juzgado)
        if not os.path.isdir(ruta_juzgado):
            continue

        ruta_sin_sec = os.path.join(ruta_juzgado, "SIN SECRETARIA")
        if not os.path.isdir(ruta_sin_sec):
            continue

        # Buscar secretarías correctas (las que no son SIN SECRETARIA)
        secretarias = [
            d for d in os.listdir(ruta_juzgado)
            if os.path.isdir(os.path.join(ruta_juzgado, d))
            and d != "SIN SECRETARIA"
        ]

        if not secretarias:
            print(f"⚠️ Sin secretaría correcta en {juzgado}, saltando")
            continue

        # Para cada expediente en SIN SECRETARIA
        for expte in os.listdir(ruta_sin_sec):
            origen = os.path.join(ruta_sin_sec, expte)
            if not os.path.isdir(origen):
                continue

            # Buscar en qué secretaría correcta está este expediente
            destino = None
            for sec in secretarias:
                posible = os.path.join(ruta_juzgado, sec, expte)
                if os.path.exists(posible):
                    destino = posible
                    break

            if destino:
                # Existe en la secretaría correcta → mover archivos que falten
                archivos_origen = set(os.listdir(origen))
                archivos_destino = set(os.listdir(destino))
                faltantes = archivos_origen - archivos_destino

                for archivo in faltantes:
                    src = os.path.join(origen, archivo)
                    dst = os.path.join(destino, archivo)
                    shutil.move(src, dst)
                    print(f"  📄 Movido: {archivo} → {sec}/{expte}")

                # Borrar carpeta origen si quedó vacía
                if not os.listdir(origen):
                    os.rmdir(origen)
                    print(f"  🗑️ Eliminado: SIN SECRETARIA/{expte}")
                else:
                    print(f"  ⚠️ Quedan archivos en SIN SECRETARIA/{expte}")
            else:
                # No existe en ninguna secretaría correcta → mover a la primera
                sec_correcta = secretarias[0]
                dest_dir = os.path.join(ruta_juzgado, sec_correcta, expte)
                shutil.move(origen, dest_dir)
                print(f"  📦 Movido completo: {expte} → {sec_correcta}")

        # Borrar SIN SECRETARIA si quedó vacía
        if os.path.exists(ruta_sin_sec) and not os.listdir(ruta_sin_sec):
            os.rmdir(ruta_sin_sec)
            print(f"✅ Eliminada carpeta SIN SECRETARIA de {juzgado}")

def limpiar_db_duplicados():
    from app import app
    from database.models import db, CausaInfo
    from sqlalchemy import func

    with app.app_context():
        duplicados = db.session.query(CausaInfo.numero, func.count(CausaInfo.id))\
            .filter_by(usuario_id=1)\
            .group_by(CausaInfo.numero)\
            .having(func.count(CausaInfo.id) > 1).all()

        print(f"\n📊 Duplicados en DB: {len(duplicados)}")

        for nro, cant in duplicados:
            registros = CausaInfo.query.filter_by(numero=nro, usuario_id=1)\
                .order_by(CausaInfo.id).all()

            # Mantener el que tiene secretaría válida y más datos
            mejor = None
            for r in registros:
                if r.secretaria and 'SIN' not in r.secretaria.upper():
                    if mejor is None or (r.demandado and r.demandado != 'SIN CARATULAR'):
                        mejor = r

            if mejor is None:
                mejor = registros[0]

            for r in registros:
                if r.id != mejor.id:
                    db.session.delete(r)
                    print(f"  🗑️ Eliminado duplicado DB: {nro} - {r.secretaria}")

        db.session.commit()
        print("✅ DB limpiada")

if __name__ == "__main__":
    print("🧹 Limpiando carpetas SIN SECRETARIA...")
    limpiar_sin_secretaria()
    print("\n🧹 Limpiando duplicados en DB...")
    limpiar_db_duplicados()
    print("\n✅ Todo listo")
