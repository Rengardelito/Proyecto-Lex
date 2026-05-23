import tkinter as tk
from tkinter import messagebox, ttk
import threading
# Importamos tu función principal del archivo donde tenés el bot
# Asegurate que tu archivo del bot se llame 'bot_lexview_pro.py' o cambialo acá:
from bot_lexview import bot_lexview 

class LexViewApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LexView Pro v3.5 - Panel de Control")
        self.root.geometry("450x550")
        self.root.configure(bg="#f0f2f5")

        # Estilos
        style = ttk.Style()
        style.configure("TButton", font=("Segoe UI", 10), padding=10)
        
        # --- ENCABEZADO ---
        header = tk.Frame(root, bg="#2c3e50", height=80)
        header.pack(fill="x")
        tk.Label(header, text="LEXVIEW PRO", fg="white", bg="#2c3e50", 
                 font=("Segoe UI", 18, "bold")).pack(pady=20)

        # --- CONTENEDOR DE DATOS ---
        main_frame = tk.Frame(root, bg="#f0f2f5", padx=30, pady=20)
        main_frame.pack(fill="both", expand=True)

        # Matrícula
        tk.Label(main_frame, text="Matrícula a Auditar:", bg="#f0f2f5", font=("Segoe UI", 10)).pack(anchor="w")
        self.ent_matricula = tk.Entry(main_frame, font=("Segoe UI", 12), bd=2, relief="flat")
        self.ent_matricula.insert(0, "3232") # Valor por defecto
        self.ent_matricula.pack(fill="x", pady=(5, 15))

        # Usuario Forum
        tk.Label(main_frame, text="Usuario Forum:", bg="#f0f2f5", font=("Segoe UI", 10)).pack(anchor="w")
        self.ent_user = tk.Entry(main_frame, font=("Segoe UI", 12), bd=2, relief="flat")
        self.ent_user.insert(0, "RicardoM")
        self.ent_user.pack(fill="x", pady=(5, 15))

        # Clave Forum
        tk.Label(main_frame, text="Contraseña:", bg="#f0f2f5", font=("Segoe UI", 10)).pack(anchor="w")
        self.ent_pass = tk.Entry(main_frame, font=("Segoe UI", 12), bd=2, relief="flat", show="*")
        self.ent_pass.insert(0, "1942")
        self.ent_pass.pack(fill="x", pady=(5, 20))

        # --- BOTONES ---
        # Botón Actualizar (Modo Rápido)
        self.btn_actualizar = tk.Button(main_frame, text="🚀 ACTUALIZAR NOVEDADES", 
                                       bg="#27ae60", fg="white", font=("Segoe UI", 11, "bold"),
                                       bd=0, cursor="hand2", command=lambda: self.lanzar_bot("ACTUALIZAR"))
        self.btn_actualizar.pack(fill="x", pady=5)

        # Botón Descargar Todo (Modo Pesado)
        self.btn_todo = tk.Button(main_frame, text="🏗️ RECONSTRUIR EXPEDIENTES (TODO)", 
                                 bg="#2980b9", fg="white", font=("Segoe UI", 11, "bold"),
                                 bd=0, cursor="hand2", command=lambda: self.lanzar_bot("DESCARGAR_TODO"))
        self.btn_todo.pack(fill="x", pady=5)

        # --- ESTADO ---
        self.lbl_estado = tk.Label(main_frame, text="Estado: Listo", bg="#f0f2f5", 
                                  fg="#7f8c8d", font=("Segoe UI", 9, "italic"))
        self.lbl_estado.pack(pady=20)

    def lanzar_bot(self, modo):
        # Tomamos los datos de la interfaz
        matricula = self.ent_matricula.get()
        user = self.ent_user.get()
        password = self.ent_pass.get()
        
        if not matricula or not user or not password:
            messagebox.showwarning("Faltan datos", "Por favor, completa todos los campos.")
            return

        # Desactivamos botones para que no toquen dos veces
        self.btn_actualizar.config(state="disabled", bg="#95a5a6")
        self.btn_todo.config(state="disabled", bg="#95a5a6")
        self.lbl_estado.config(text=f"Estado: Ejecutando {modo}...", fg="#e67e22")

        # Ejecutamos en un Thread (hilo) separado para que la ventana no se congele
        threading.Thread(target=self.ejecutar_proceso, args=(user, password, matricula, modo), daemon=True).start()

    def ejecutar_proceso(self, user, password, matricula, modo):
        try:
            # Llamamos a tu función orquestadora
            bot_lexview("nico", user, password, matricula, modo=modo)
            messagebox.showinfo("¡Éxito!", f"Proceso de {modo} finalizado correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un fallo: {e}")
        finally:
            # Reestablecemos la interfaz
            self.btn_actualizar.config(state="normal", bg="#27ae60")
            self.btn_todo.config(state="normal", bg="#2980b9")
            self.lbl_estado.config(text="Estado: Listo", fg="#7f8c8d")

if __name__ == "__main__":
    root = tk.Tk()
    app = LexViewApp(root)
    root.mainloop()