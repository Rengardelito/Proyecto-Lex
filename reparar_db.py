import sqlite3

def agregar_columna_plan():
    try:
        # Conectamos directamente al archivo de la base de datos
        conn = sqlite3.connect('lexview.db')
        cursor = conn.cursor()
        
        print("Intentando agregar la columna 'plan' a la tabla 'usuario'...")
        
        # Ejecutamos el comando SQL para agregar la columna
        # Le ponemos 'trial' por defecto para que no falle con los usuarios existentes
        cursor.execute("ALTER TABLE usuario ADD COLUMN plan TEXT DEFAULT 'piloto'")
        
        conn.commit()
        print("✅ Columna 'plan' agregada con éxito.")
        
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ La columna 'plan' ya existe.")
        else:
            print(f"❌ Error operativo: {e}")
    except Exception as e:
        print(f"❌ Ocurrió un error inesperado: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    agregar_columna_plan()