import pandas as pd
import csv
import time
import pickle
import re
import unicodedata

# --- CONFIGURACIÓN ---
RAW_BASICS = "raw/title.basics.tsv"
RAW_PRINCIPALS = "raw/title.principals.tsv"
RAW_RATINGS = "raw/title.ratings.tsv"
RAW_NAMES = "raw/name.basics.tsv"

OUTPUT_GRAFO = "grafo_bacon.pkl"
OUTPUT_METADATA = "metadata_bacon.pkl"

# 🔥 FILTRO DE CALIDAD
MIN_VOTOS = 100 

def normalizar_texto(texto):
    if not texto: return ""
    texto = texto.lower()
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8')
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    return texto.strip()

def obtener_peliculas_validas_con_ratings():
    """
    Paso 1: Identificar películas que sean CINE/TV y tengan > MIN_VOTOS.
    Devuelve: Un SET de IDs válidos y un Diccionario de Ratings.
    """
    print(f"1️⃣  Cargando Ratings y Filtrando por {MIN_VOTOS} votos...")
    
    ratings_map = {}
    peliculas_populares = set()
    
    try:
        with open(RAW_RATINGS, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            next(reader)
            for row in reader:
                try:
                    tconst = row[0]
                    votos = int(row[2])
                    if votos >= MIN_VOTOS:
                        ratings_map[tconst] = (float(row[1]), votos)
                        peliculas_populares.add(tconst)
                except: continue
    except FileNotFoundError:
        print("❌ Error: No encuentro title.ratings.tsv")
        return set(), {}

    print(f"   -> {len(peliculas_populares):,} películas pasaron el filtro de votos.")

    print("2️⃣  Cruzando con Tipos (Movie/TV)...")
    validas_finales = set()
    
    try:
        chunks = pd.read_csv(RAW_BASICS, sep='\t', usecols=['tconst', 'titleType'], 
                             chunksize=100000, low_memory=False)
        for chunk in chunks:
            # 1. Tipo correcto
            filtro_tipo = chunk['titleType'].isin(['movie', 'tvMovie'])
            # 2. Es popular
            filtro_pop = chunk['tconst'].isin(peliculas_populares)
            
            # Intersección de filtros
            ids_ok = chunk[filtro_tipo & filtro_pop]['tconst']
            validas_finales.update(ids_ok)
            
    except FileNotFoundError:
        print("❌ Error: No encuentro title.basics.tsv")
        return set(), {}
        
    print(f"   ✅ Universo Final: {len(validas_finales):,} películas para el Grafo.")
    return validas_finales, ratings_map

def construir_grafo_y_metadata(ids_validos, ratings_map):
    print(f"3️⃣  Construyendo Grafo en RAM (Esto tardará)...")
    inicio = time.time()
    
    grafo = {}
    mapa_peliculas = {}
    mapa_actores = {}
    mapa_nombres = {}
    lista_generos = set()
    candidatos = []
    
    # --- A. CONSTRUIR GRAFO (ARISTAS) ---
    try:
        chunks = pd.read_csv(RAW_PRINCIPALS, sep='\t', 
                             usecols=['tconst', 'nconst', 'category'], 
                             chunksize=500000, low_memory=False)
        
        for chunk in chunks:
            # Filtramos: Solo actores Y solo en películas válidas
            df = chunk[chunk['category'].isin(['actor', 'actress'])]
            df = df[df['tconst'].isin(ids_validos)]
            
            if df.empty: continue
            
            for peli, actor in zip(df['tconst'], df['nconst']):
                # Grafo Bidireccional
                if peli not in grafo: grafo[peli] = []
                grafo[peli].append(actor)
                
                if actor not in grafo: grafo[actor] = []
                grafo[actor].append(peli)
                
    except FileNotFoundError: return {}, {}
    
    print(f"   ✅ Grafo listo: {len(grafo):,} nodos conectados.")

    # --- B. METADATOS PELÍCULAS ---
    print("4️⃣  Procesando Metadatos Películas...")
    with open(RAW_BASICS, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        next(reader)
        for row in reader:
            tconst = row[0]
            if tconst in grafo:
                titulo = row[3]
                anio = int(row[5]) if row[5].isdigit() else 0
                generos = row[8].split(',')
                rat, vot = ratings_map.get(tconst, (0.0, 0))
                dur = int(row[7]) if row[7].isdigit() else 0
                
                mapa_peliculas[tconst] = (titulo, anio, generos, dur, rat, vot)
                
                for g in generos:
                    if g != '\\N': lista_generos.add(g)

    # --- C. METADATOS ACTORES ---
    print("5️⃣  Procesando Metadatos Actores y Generando Candidatos...")
    with open(RAW_NAMES, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        next(reader)
        for row in reader:
            nconst = row[0]
            # Solo guardamos si está en el grafo
            if nconst in grafo:
                nombre = row[1]
                anio_nac = row[2] if len(row) > 2 and row[2].isdigit() else "????"
                
                mapa_actores[nconst] = (nombre, anio_nac)
                
                # Índice búsqueda
                nombre_limpio = normalizar_texto(nombre)
                if nombre_limpio not in mapa_nombres: mapa_nombres[nombre_limpio] = []
                mapa_nombres[nombre_limpio].append(nconst)
                
                # --- CANDIDATOS (MODO RANDOM) ---
                # Ahora agregamos a TODOS los que estén en el grafo.
                # Ya pasaron el filtro de calidad (>100 votos en sus películas).
                candidatos.append({'id': nconst, 'name': nombre})

    print(f"   ✅ Todo procesado en {time.time() - inicio:.2f}s.")
    print(f"   🎲 Total de candidatos para 'Voy a tener suerte': {len(candidatos):,}")

    print("6️⃣  Calculando Centralidad Global (Top Teórico)...")
    
    # Separamos nodos por tipo
    nodos_peliculas = []
    nodos_actores = []
    
    for nodo, vecinos in grafo.items():
        grado = len(vecinos)
        if nodo.startswith('tt'):
            nodos_peliculas.append((nodo, grado))
        elif nodo.startswith('nm'):
            nodos_actores.append((nodo, grado))
            
    # Ordenamos por grado (mayor a menor) y tomamos Top 15
    top_peli_teorico = sorted(nodos_peliculas, key=lambda x: x[1], reverse=True)[:15]
    top_actor_teorico = sorted(nodos_actores, key=lambda x: x[1], reverse=True)[:15]
    
    print(f"   🏆 Top Peli: {top_peli_teorico[0][0]} ({top_peli_teorico[0][1]} conexiones)")
    print(f"   🏆 Top Actor: {top_actor_teorico[0][0]} ({top_actor_teorico[0][1]} conexiones)")

    # Empaquetamos todo
    metadata_pack = {
        'peliculas': mapa_peliculas,
        'actores': mapa_actores,
        'nombres': mapa_nombres,
        'generos': sorted(list(lista_generos)),
        'candidatos': candidatos,
        'global_stats': { # <--- NUEVO CAMPO
            'peliculas': top_peli_teorico, # Lista de tuplas (id, grado)
            'actores': top_actor_teorico
        }
    }
    
    return grafo, metadata_pack
    
def ejecutar_etl_ram():
    print("🚀 INICIANDO ETL RAM...")
    
    # 1. Obtener IDs válidos
    ids_validos, ratings_map = obtener_peliculas_validas_con_ratings()
    
    if not ids_validos: return

    # 2. Construir todo
    grafo, meta = construir_grafo_y_metadata(ids_validos, ratings_map)
    
    # 3. Guardar Pickles
    print(f"💾 Guardando {OUTPUT_GRAFO}...")
    with open(OUTPUT_GRAFO, 'wb') as f:
        pickle.dump(grafo, f, protocol=pickle.HIGHEST_PROTOCOL)
        
    print(f"💾 Guardando {OUTPUT_METADATA}...")
    with open(OUTPUT_METADATA, 'wb') as f:
        pickle.dump(meta, f, protocol=pickle.HIGHEST_PROTOCOL)

    print("\n✨ ETL FINALIZADO. Listos para usar en app.py ✨")

if __name__ == "__main__":
    ejecutar_etl_ram()