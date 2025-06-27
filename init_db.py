import sqlite3
import pandas as pd
import os

# Ruta simple y robusta para la base de datos
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')


def inicializar_bd():
    excel_path = 'Libro1.xlsx'
    if not os.path.exists(excel_path):
        print(f"Error: No se encontró el archivo '{excel_path}'.")
        return

    # Conectar a la base de datos usando la ruta definida
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- Tabla Principal de Préstamos ---
    cursor.execute("DROP TABLE IF EXISTS prestamos")
    cursor.execute("""
    CREATE TABLE prestamos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha DATE NOT NULL,
        identificacion TEXT NOT NULL,
        nombre TEXT NOT NULL,
        area TEXT,
        pc BOOLEAN,
        pc_numero INTEGER,
        pc_pertenece TEXT,
        kit BOOLEAN,
        aire BOOLEAN,
        cabinas BOOLEAN,
        consola BOOLEAN,
        vbeam BOOLEAN,
        ubicacion TEXT NOT NULL,
        edificio TEXT,
        hora_inicio TIME NOT NULL,
        prestado_por TEXT NOT NULL,
        hora_entrega TIME,
        recibido_por TEXT,
        horas_utilizacion REAL,
        observaciones TEXT
    );
    """)

    # --- Tablas auxiliares ---

    # 1. Usuarios
    cursor.execute("DROP TABLE IF EXISTS usuarios")
    cursor.execute("CREATE TABLE usuarios (id TEXT PRIMARY KEY, nombre TEXT NOT NULL, area TEXT);")
    df_users = pd.read_excel(excel_path, usecols=['ID', 'NOMBRE', 'AREA']).dropna(subset=['ID'])
    df_users['ID'] = df_users['ID'].apply(lambda x: str(x).split('.')[0] if pd.notna(x) else x)
    df_users.drop_duplicates(subset=['ID'], keep='first', inplace=True)
    df_users.to_sql('usuarios', conn, if_exists='append', index=False)

    # 2. Ubicaciones
    cursor.execute("DROP TABLE IF EXISTS ubicaciones")
    cursor.execute(
        "CREATE TABLE ubicaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, edificio TEXT);")
    df_loc = pd.read_excel(excel_path, usecols=['SALONES Y OFICINA', 'EDIFICIO']).dropna()
    df_loc.rename(columns={'SALONES Y OFICINA': 'nombre', 'EDIFICIO': 'edificio'}, inplace=True)
    df_loc.to_sql('ubicaciones', conn, if_exists='append', index=False)

    # 3. Auxiliares
    cursor.execute("DROP TABLE IF EXISTS auxiliares")
    cursor.execute("CREATE TABLE auxiliares (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL);")
    df_aux = pd.read_excel(excel_path, usecols=['AUXILIAR']).dropna().drop_duplicates()
    df_aux.rename(columns={'AUXILIAR': 'nombre'}, inplace=True)
    df_aux.to_sql('auxiliares', conn, if_exists='append', index=False)

    # 4. Equipos
    cursor.execute("DROP TABLE IF EXISTS equipos")
    cursor.execute("CREATE TABLE equipos (id INTEGER PRIMARY KEY, pertenece TEXT NOT NULL);")
    df_equipos = pd.read_excel(excel_path, usecols=['EQUIPOS', 'PERTENECE']).dropna()
    df_equipos.rename(columns={'EQUIPOS': 'id', 'PERTENECE': 'pertenece'}, inplace=True)
    df_equipos['id'] = pd.to_numeric(df_equipos['id'], errors='coerce').dropna().astype(int)
    df_equipos.drop_duplicates(subset=['id'], keep='first', inplace=True)
    df_equipos.to_sql('equipos', conn, if_exists='append', index=False)

    print("Base de datos inicializada correctamente.")
    conn.commit()
    conn.close()


if __name__ == '__main__':
    inicializar_bd()