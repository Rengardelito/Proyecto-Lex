import sqlite3

def parchear_a_piloto():
    try:
        # Conectamos al archivo de tu base de datos
        conn = sqlite3.connect('lexview.db')
        cursor = conn.cursor()
        
        print("Conectado a lexview.db...")

        # 1. Intentamos agregar la columna 'plan' (por si no existe)
        try:
            cursor.execute("ALTER TABLE usuario ADD COLUMN plan TEXT DEFAULT 'piloto'")
            print("✅ Columna 'plan' creada con valor por defecto 'piloto'.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("ℹ️ La columna 'plan' ya existía.")
            else:
                raise e

        # 2. Forzamos a que todos los usuarios existentes sean 'piloto'
        # Esto es lo que necesitas para probar las funcionalidades full
        cursor.execute("UPDATE usuario SET plan = 'piloto'")
        
        conn.commit()
        print("✅ ¡Éxito! Todos los usuarios han sido actualizados al plan 'piloto'.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    parchear_a_piloto()