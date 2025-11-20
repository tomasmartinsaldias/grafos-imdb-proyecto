import sqlite3
import pandas as pd
import csv
import time
import os
import re
import unicodedata

# --- CONFIGURACIÓN ---
DB_NAME = "bacon.db"
RAW_BASICS = "title.basics.tsv"
RAW_PRINCIPALS = "title.principals.tsv"
RAW_RATINGS = "title.ratings.tsv"
RAW_NAMES = "name.basics.tsv"

# 🔥 EL FILTRO MÁGICO: Solo películas con más de X votos
# 500 es un buen balance. Si sigue pesando >100MB, subelo a 1000.
MIN_VOTOS = 450 

def normalizar_texto(texto):
    if not texto: return ""
    texto = texto.lower()
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8')
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    return texto.strip()

def iniciar_db():
    if os.path.exists(DB_NAME): os.remove(DB_NAME)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('CREATE TABLE peliculas (id TEXT PRIMARY KEY, titulo TEXT, anio INTEGER, generos TEXT, rating REAL, votos INTEGER)')
    c.execute('CREATE TABLE actores (id TEXT PRIMARY KEY, nombre TEXT, anio_nac TEXT)')
    c.execute('CREATE TABLE aristas (origen TEXT, destino TEXT)')
    c.execute('CREATE TABLE nombres (nombre_limpio TEXT, id_actor TEXT)')
    conn.commit()
    return conn

def ejecutar_etl_sql():
    print(f"🚀 INICIANDO ETL SQL (MODO VIP > {MIN_VOTOS} VOTOS) -> {DB_NAME}")
    inicio_global = time.time()
    conn = iniciar_db()
    c = conn.cursor()
    
    # --- PASO 1: CARGAR RATINGS Y FILTRAR POR POPULARIDAD ---
    print("1️⃣  Cargando Ratings y aplicando filtro de popularidad...")
    # Guardamos en RAM solo las películas que superan el umbral
    peliculas_populares = set()
    ratings_map = {}
    
    with open(RAW_RATINGS, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        next(reader)
        for row in reader:
            try:
                tconst = row[0]
                votos = int(row[2])
                if votos >= MIN_VOTOS:
                    rating = float(row[1])
                    peliculas_populares.add(tconst)
                    ratings_map[tconst] = (rating, votos)
            except: continue
    print(f"   -> {len(peliculas_populares):,} películas superaron los {MIN_VOTOS} votos.")

    # --- PASO 2: IDENTIFICAR PELÍCULAS VÁLIDAS (CINE/TV + POPULARES) ---
    print("2️⃣  Cruzando con title.basics (Tipo Movie/TVMovie)...")
    validas_finales = set()
    
    chunks = pd.read_csv(RAW_BASICS, sep='\t', usecols=['tconst', 'titleType'], 
                         chunksize=100000, low_memory=False)
    for chunk in chunks:
        # Filtro 1: Tipo correcto
        filtro_tipo = chunk['titleType'].isin(['movie', 'tvMovie'])
        # Filtro 2: Es popular
        filtro_pop = chunk['tconst'].isin(peliculas_populares)
        
        validas = chunk[filtro_tipo & filtro_pop]
        validas_finales.update(validas['tconst'])
        
    # Liberamos memoria
    del peliculas_populares
    print(f"   ✅ Universo Final: {len(validas_finales):,} películas válidas.")
    
    # --- PASO 3: PROCESAR GRAFO (ARISTAS) ---
    print("3️⃣  Procesando Conexiones (Solo universo válido)...")
    nodos_activos = set()
    batch_aristas = []
    
    chunks = pd.read_csv(RAW_PRINCIPALS, sep='\t', 
                         usecols=['tconst', 'nconst', 'category'], 
                         chunksize=500000, low_memory=False)
    
    for i, chunk in enumerate(chunks):
        df = chunk[chunk['category'].isin(['actor', 'actress'])]
        df = df[df['tconst'].isin(validas_finales)] # Solo pelis VIP
        
        if df.empty: continue
        
        for peli, actor in zip(df['tconst'], df['nconst']):
            batch_aristas.append((peli, actor))
            batch_aristas.append((actor, peli))
            nodos_activos.add(peli)
            nodos_activos.add(actor)
        
        if len(batch_aristas) >= 50000:
            c.executemany('INSERT INTO aristas VALUES (?,?)', batch_aristas)
            batch_aristas = []
            
    if batch_aristas: c.executemany('INSERT INTO aristas VALUES (?,?)', batch_aristas)
    conn.commit()
    
    # --- INICIO DEBUG AGREGADO ---
    print("\n📊 --- REPORTE DE DIAGNÓSTICO PRE-SQL ---")
    print(f"   Nodos Totales (con conexiones): {len(nodos_activos):,}")
    
    # Contamos cuántos son películas (empiezan con 'tt') y cuántos actores ('nm')
    solo_pelis = [n for n in nodos_activos if n.startswith('tt')]
    solo_actores = len(nodos_activos) - len(solo_pelis)
    
    print(f"   🎬 Películas sobrevivientes: {len(solo_pelis):,}")
    print(f"   🎭 Actores sobrevivientes:   {solo_actores:,}")
    print("-------------------------------------------\n")
    # --- FIN DEBUG AGREGADO ---

    # --- PASO 4: INSERTAR METADATOS PELÍCULAS ---
    print("4️⃣  Guardando Metadatos de Películas...")
    batch_peliculas = []
    with open(RAW_BASICS, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        next(reader)
        for row in reader:
            tconst = row[0]
            if tconst in nodos_activos: # Solo si tiene conexiones
                titulo = row[2]
                anio = int(row[5]) if row[5].isdigit() else 0
                generos = row[8]
                rat, vot = ratings_map.get(tconst, (0.0, 0))
                
                batch_peliculas.append((tconst, titulo, anio, generos, rat, vot))
                if len(batch_peliculas) >= 10000:
                    c.executemany('INSERT INTO peliculas VALUES (?,?,?,?,?,?)', batch_peliculas)
                    batch_peliculas = []
    if batch_peliculas: c.executemany('INSERT INTO peliculas VALUES (?,?,?,?,?,?)', batch_peliculas)
    conn.commit()

    # --- PASO 5: INSERTAR ACTORES ---
    print("5️⃣  Guardando Actores...")
    batch_actores = []
    batch_nombres = []
    with open(RAW_NAMES, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        next(reader)
        for row in reader:
            nconst = row[0]
            if nconst in nodos_activos: # Solo si tiene conexiones
                nombre = row[1]
                anio_nac = row[2] if len(row) > 2 and row[2].isdigit() else "????"
                
                batch_actores.append((nconst, nombre, anio_nac))
                batch_nombres.append((normalizar_texto(nombre), nconst))
                
                if len(batch_actores) >= 10000:
                    c.executemany('INSERT INTO actores VALUES (?,?,?)', batch_actores)
                    c.executemany('INSERT INTO nombres VALUES (?,?)', batch_nombres)
                    batch_actores = []
                    batch_nombres = []
    if batch_actores:
        c.executemany('INSERT INTO actores VALUES (?,?,?)', batch_actores)
        c.executemany('INSERT INTO nombres VALUES (?,?)', batch_nombres)
    conn.commit()

    # --- FINALIZAR ---
    print("⚡ Indexando y Compactando...")
    c.execute('CREATE INDEX idx_aristas_origen ON aristas(origen)')
    c.execute('CREATE INDEX idx_nombres_limpio ON nombres(nombre_limpio)')
    c.execute('VACUUM') 
    conn.close()
    
    size_mb = os.path.getsize(DB_NAME) / (1024*1024)
    print(f"📦 TAMAÑO FINAL: {size_mb:.2f} MB")

if __name__ == "__main__":
    ejecutar_etl_sql()