import pandas as pd
import csv
import time
import pickle
import re
import unicodedata

# --- CONFIGURACIÓN DE ARCHIVOS ---
# Asegúrate de que estos archivos RAW de IMDb estén en la carpeta
RAW_BASICS = "title.basics.tsv"
RAW_PRINCIPALS = "title.principals.tsv"
RAW_RATINGS = "title.ratings.tsv"
RAW_NAMES = "name.basics.tsv"

# Archivos de SALIDA (Los que usará la App)
OUTPUT_GRAFO = "grafo_bacon.pkl"
OUTPUT_METADATA = "metadata_bacon.pkl"

def normalizar_texto(texto):
    """
    Transforma 'Stellan Skarsgård' -> 'stellan skarsgard'
    Transforma 'Samuel L. Jackson' -> 'samuel l jackson'
    """
    if not texto: return ""
    # 1. Minúsculas
    texto = texto.lower()
    # 2. Quitar acentos (Descomposición Unicode: 'á' -> 'a' + '´')
    # El encode('ascii', 'ignore') tira la tilde a la basura y deja la letra
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8')
    # 3. Quitar todo lo que NO sea letra o número (puntos, comas, guiones)
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    return texto.strip()

def obtener_peliculas_validas():
    """
    Paso 1: Escanear title.basics para obtener un SET de IDs que sean 
    realmente 'movie'. Esto sirve para filtrar basura del grafo.
    """
    print(f"🕵️  Analizando {RAW_BASICS} para identificar películas...")
    validas = set()
    try:
        # Leemos solo las columnas necesarias para ahorrar memoria
        # tconst (ID), titleType (tipo)
        chunks = pd.read_csv(RAW_BASICS, sep='\t', usecols=['tconst', 'titleType'], 
                             chunksize=100000, low_memory=False)
        
        for chunk in chunks:
            # Usamos .isin() para filtrar por una lista de opciones
            filtro = chunk['titleType'].isin(['movie', 'tvMovie'])
            movies = chunk[filtro]
            
            validas.update(movies['tconst'])
            
        print(f"   ✅ Se identificaron {len(validas):,} películas válidas.")
        return validas
    except FileNotFoundError:
        print(f"   ❌ Error: No encuentro {RAW_BASICS}")
        return set()

def construir_grafo_desde_raw(peliculas_validas):
    """
    Paso 2: Procesar el gigante title.principals.tsv.
    Usamos chunking para leerlo de a poco.
    Solo guardamos conexiones si:
      - Es actor/actress
      - La película está en el set 'peliculas_validas'
    """
    print(f"🕸️  Construyendo Grafo desde {RAW_PRINCIPALS} (Esto tardará)...")
    inicio = time.time()
    grafo = {}
    
    conexiones_count = 0
    
    try:
        # Columnas: tconst (peli), nconst (actor), category (trabajo)
        chunks = pd.read_csv(RAW_PRINCIPALS, sep='\t', 
                             usecols=['tconst', 'nconst', 'category'], 
                             chunksize=1000000, low_memory=False)
        
        for i, chunk in enumerate(chunks):
            # 1. Filtro de Categoría (Solo Actores)
            # "category" suele ser la columna que dice 'actor', 'actress', 'director'...
            chunk_filtrado = chunk[chunk['category'].isin(['actor', 'actress'])]
            
            # 2. Filtro de Película Válida (Usando el set del paso 1)
            chunk_filtrado = chunk_filtrado[chunk_filtrado['tconst'].isin(peliculas_validas)]
            
            if chunk_filtrado.empty: continue
            
            # 3. Llenado del Grafo (Iteramos sobre el dataframe filtrado)
            # zip es mucho más rápido que iterrows
            for peli, actor in zip(chunk_filtrado['tconst'], chunk_filtrado['nconst']):
                
                # Relación Peli -> Actor
                if peli not in grafo: grafo[peli] = []
                grafo[peli].append(actor)
                
                # Relación Actor -> Peli
                if actor not in grafo: grafo[actor] = []
                grafo[actor].append(peli)
                
                conexiones_count += 1
            
            if i % 5 == 0:
                print(f"... Procesados {(i+1)} millones de filas raw...")

        print(f"   ✅ Grafo terminado: {len(grafo):,} nodos conectados.")
        print(f"   ⏱️ Tiempo de grafo: {time.time() - inicio:.2f}s")
        return grafo

    except FileNotFoundError:
        print(f"   ❌ Error: No encuentro {RAW_PRINCIPALS}")
        return {}

def construir_metadatos(grafo_completo):
    """
    Paso 3: Generar diccionarios de info (Títulos, Nombres, Ratings).
    Solo guardamos info de películas que realmente quedaron en el grafo.
    """
    print("📚 Generando Metadatos...")
    inicio = time.time()
    
    mapa_peliculas = {}
    mapa_actores = {}
    mapa_nombres = {} 
    lista_generos = set()
    candidatos = [] 
    
    # --- A. RATINGS ---
    print("   1/3 Cargando Ratings...")
    ratings = {}
    try:
        # Pandas es overkill aqui, usamos csv normal que es rápido
        with open(RAW_RATINGS, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            next(reader)
            for row in reader:
                try:
                    # tconst -> (avgRating, numVotes)
                    ratings[row[0]] = (float(row[1]), int(row[2]))
                except: continue
    except FileNotFoundError:
        print("   ⚠️ Falta archivo de ratings.")

    # --- B. DETALLES PELÍCULAS ---
    print("   2/3 Detalles de Películas...")
    try:
        with open(RAW_BASICS, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            next(reader)
            for row in reader:
                tconst = row[0]
                # Solo procesamos si la peli está en el grafo (ahorra RAM)
                if tconst in grafo_completo:
                    titulo = row[2]
                    anio = int(row[5]) if row[5].isdigit() else 0
                    generos = row[8].split(',')
                    duracion = int(row[7]) if row[7].isdigit() else 0
                    rat, vot = ratings.get(tconst, (0.0, 0))
                    
                    mapa_peliculas[tconst] = (titulo, anio, generos, duracion, rat, vot)
                    for g in generos: 
                        if g != '\\N': lista_generos.add(g)
    except FileNotFoundError:
        print("   ❌ Falta title.basics.")

    # --- C. NOMBRES ACTORES ---
    print("   3/3 Nombres de Actores...")
    try:
        with open(RAW_NAMES, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            next(reader)
            for row in reader:
                nconst = row[0]
                if nconst in grafo_completo:
                    nombre_original = row[1]
                    birth_year = row[2] if len(row) > 2 and row[2].isdigit() else "????"
                    
                    # Guardamos el nombre ORIGINAL para mostrar en pantalla
                    mapa_actores[nconst] = (nombre_original, birth_year)
                    
                    # CAMBIO CLAVE: Usamos el nombre NORMALIZADO como clave de búsqueda
                    nombre_limpio = normalizar_texto(nombre_original)
                    
                    if nombre_limpio not in mapa_nombres:
                        mapa_nombres[nombre_limpio] = []
                    mapa_nombres[nombre_limpio].append(nconst)
                
                    # Candidatos para 'Voy a tener suerte' (Famosos)
                    # 1. Obtenemos cuántas películas hizo este actor (Grado del nodo)
                    conexiones = len(grafo_completo[nconst])
                    
                    #    - Debe tener ID bajo ("nm000..." -> indica antigüedad/relevancia histórica)
                    #    - Y ADEMÁS debe tener al menos 5 películas conectadas en nuestro grafo.
                    if len(candidatos) < 5000 and conexiones >= 5:
                        candidatos.append({'id': nconst, 'name': nombre})
    except FileNotFoundError:
        print("   ❌ Falta name.basics.")

    print(f"   ✅ Metadatos listos ({time.time() - inicio:.2f}s).")
    
    return {
        'peliculas': mapa_peliculas,
        'actores': mapa_actores,
        'nombres': mapa_nombres,
        'generos': sorted(list(lista_generos)),
        'candidatos': candidatos
    }

def ejecutar_etl_puro():
    print("🚀 INICIANDO ETL PURO (RAW -> PICKLE) ...")
    
    # 1. Identificar qué es una película válida
    peliculas_validas = obtener_peliculas_validas()
    
    if not peliculas_validas:
        print("❌ Abortando: No se pudieron identificar películas.")
        return

    # 2. Construir Grafo desde Cero (Principals)
    grafo = construir_grafo_desde_raw(peliculas_validas)
    
    if not grafo:
        print("❌ Abortando: Grafo vacío.")
        return

    # Guardar Grafo
    print(f"💾 Guardando {OUTPUT_GRAFO}...")
    with open(OUTPUT_GRAFO, 'wb') as f:
        pickle.dump(grafo, f, protocol=pickle.HIGHEST_PROTOCOL)

    # 3. Construir Metadatos (Usando las keys del grafo para filtrar)
    # Pasamos las keys del grafo para no cargar info de actores/pelis que no tienen conexiones
    meta = construir_metadatos(grafo)
    
    # Guardar Metadatos
    print(f"💾 Guardando {OUTPUT_METADATA}...")
    with open(OUTPUT_METADATA, 'wb') as f:
        pickle.dump(meta, f, protocol=pickle.HIGHEST_PROTOCOL)

    print("\n✨ ETL FINALIZADO CORRECTAMENTE ✨")

if __name__ == "__main__":
    ejecutar_etl_puro()