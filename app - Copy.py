import os
import pickle
import time
import random
import requests
import math
from functools import lru_cache
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import re
import unicodedata

from algoritmos import bfs_bidireccional, dijkstra 

load_dotenv()
app = Flask(__name__)

TMDB_KEY = os.getenv("TMDB_API_KEY")

# ==========================================
# 1. VARIABLES GLOBALES
# ==========================================
GRAFO = {}
METADATA = {} 
MAPA_PELICULAS = {} # tconst -> (Titulo, Año, Generos, Duracion, Rating, Votos)
MAPA_ACTORES = {}   
MAPA_NOMBRES = {}   
CANDIDATOS = []     
GENEROS = []        

# ==========================================
# [cite_start]2. FUNCIONES DE PESO (Lógica de Negocio) [cite: 24, 28, 31]
# ==========================================

def calcular_peso_casual(u, v, mapa_pelis):
    """
    Modo Casual: Evita películas malas.
    [cite_start]Costo = 10.1 - Rating. (Peli de 10 cuesta 0.1, Peli de 1 cuesta 9.1) [cite: 30]
    """
    # Si 'v' es un actor, el costo es mínimo (el esfuerzo es ver la peli, no el actor)
    if v.startswith('nm'): return 0.1
    
    # Si 'v' es película, calculamos costo basado en calidad
    if v in mapa_pelis:
        # datos = (Titulo, Año, Generos, Duracion, Rating, Votos)
        rating = mapa_pelis[v][4]
        # Fórmula lineal inversa: Mayor rating = Menor costo
        return max(0.1, 10.1 - rating)
    
    return 5.0 # Costo por defecto para pelis sin datos

def calcular_peso_critico(u, v, mapa_pelis):
    """
    Modo Crítico (Snob): Busca pelis buenas PERO desconocidas.
    Fórmula: 1.3^(10 - Rating) * log10(Votos + 1)
    """
    # Saltar de un actor a una película es "gratis" o muy barato
    if v.startswith('nm'): return 0.1
    
    if v in mapa_pelis:
        # datos = (Titulo, Año, Generos, Duracion, Rating, Votos)
        rating = mapa_pelis[v][4]
        votos = mapa_pelis[v][5]
        
        # 1. Penalización Exponencial a la Mala Calidad
        # Base 2.5 elevada a la "distancia de la perfección"
        factor_calidad = 2.5 ** (10.0 - rating)
        
        # 2. Penalización Logarítmica al Cuadrado a la Fama
        factor_fama = (math.log10(votos + 1))**2
        
        return factor_calidad * factor_fama
        
    return 10.0 # Costo alto por defecto si no hay datos

def normalizar_texto(texto):
    if not texto: return ""
    texto = texto.lower()
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8')
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    return texto.strip()

# ==========================================
# 3. FUNCIONES AUXILIARES & CARGA
# ==========================================

@lru_cache(maxsize=1000)
def obtener_imagen_tmdb(imdb_id, tipo):
    if not TMDB_KEY: return None 
    base_url = "https://api.themoviedb.org/3"
    image_base = "https://image.tmdb.org/t/p/w200"
    try:
        url = f"{base_url}/find/{imdb_id}"
        params = {"api_key": TMDB_KEY, "external_source": "imdb_id"}
        r = requests.get(url, params=params, timeout=1)
        data = r.json()
        path = None
        if tipo == 'person' and data.get('person_results'):
            path = data['person_results'][0].get('profile_path')
        elif tipo == 'movie' and data.get('movie_results'):
            path = data['movie_results'][0].get('poster_path')
        if path: return f"{image_base}{path}"
    except: pass
    return None

def iniciar_servidor():
    global GRAFO, METADATA, MAPA_PELICULAS, MAPA_ACTORES, MAPA_NOMBRES, CANDIDATOS, GENEROS
    print("🚀 Iniciando Servidor Bacon...")
    path_grafo, path_meta = "grafo_bacon.pkl", "metadata_bacon.pkl"
    
    if not os.path.exists(path_grafo):
        print("❌ Faltan pickles. Corre etl.py.")
        return

    with open(path_grafo, 'rb') as f: GRAFO = pickle.load(f)
    with open(path_meta, 'rb') as f:
        METADATA = pickle.load(f)
        MAPA_PELICULAS = METADATA['peliculas']
        MAPA_ACTORES = METADATA['actores']
        MAPA_NOMBRES = METADATA['nombres']
        CANDIDATOS = METADATA['candidatos']
        GENEROS = METADATA['generos']
    print(f"✅ Sistema Listo. {len(GRAFO)} nodos.")

iniciar_servidor()

# ==========================================
# 4. RUTAS
# ==========================================

@app.route('/')
def index():
    return render_template('index.html', generos=["Todos"] + GENEROS)

@app.route('/api/autocomplete')
def autocomplete():
    raw_query = request.args.get('q', '')
    
    # 2. Lo limpiamos (ej: "renee zel")
    query = normalizar_texto(raw_query)
    
    if len(query) < 3: return jsonify([])
    
    sugerencias = []
    count = 0
    
    # 3. Buscamos la clave limpia en nuestro mapa limpio
    for nombre_limpio_clave, ids in MAPA_NOMBRES.items():
        if query in nombre_limpio_clave: 
            for id_actor in ids:
                # Recuperamos el nombre ORIGINAL bonito para mostrar
                datos = MAPA_ACTORES.get(id_actor)
                if datos:
                    nombre_real, anio = datos
                    texto_display = f"{nombre_real} ({anio})"
                    sugerencias.append({'id': id_actor, 'text': texto_display})
                    count += 1
        if count >= 10: break 
            
    return jsonify(sugerencias)

@app.route('/api/random_actors')
def random_actors():
    if not CANDIDATOS: return jsonify({'error': 'Sin datos'})
    a1, a2 = random.choice(CANDIDATOS), random.choice(CANDIDATOS)
    while a1 == a2: a2 = random.choice(CANDIDATOS)
    return jsonify({'actor1': a1, 'actor2': a2})

@app.route('/api/buscar', methods=['POST'])
def buscar():
    data = request.json
    origen, destino = data.get('actor1'), data.get('actor2')
    filtros = data.get('filtros', {})
    
    # 1. Detectar MODO (Velocidad vs Casual vs Crítico)
    modo = filtros.get('tipo', 'Velocidad')
    print(f"🔍 Buscando: {origen} -> {destino} [Modo: {modo}]")

    # 2. Configurar Patovica (Filtros Topológicos)
    anio_min, anio_max = filtros.get('anio', [1900, 2025])
    votos_min, votos_max = filtros.get('votos', [0, 10000000])
    rat_min, rat_max = filtros.get('rating', [0.0, 10.0])
    dur_min, dur_max = filtros.get('duracion', [0, 500])
    genero = filtros.get('genero', 'Todos')
    
    usar_filtros = (anio_min > 1900 or anio_max < 2025 or votos_min > 0 or genero != 'Todos' or rat_min > 0)
    ids_validos = None

    if usar_filtros:
        ids_validos = set()
        for tconst, datos in MAPA_PELICULAS.items():
            _, anio, gens, dur, rat, vot = datos
            if not (anio_min <= anio <= anio_max): continue
            if not (votos_min <= vot <= votos_max): continue
            if not (rat_min <= rat <= rat_max): continue
            if not (dur_min <= dur <= dur_max): continue
            if genero != 'Todos' and genero not in gens: continue
            ids_validos.add(tconst)
        print(f"   🛡️ Filtros activos: {len(ids_validos)} películas.")

    # [cite_start]3. Ejecutar Algoritmo según MODO [cite: 25, 28, 31]
    inicio_ts = time.time()
    
    if modo == 'Velocidad':
        # BFS Bidireccional (Sin pesos)
        camino_ids = bfs_bidireccional(GRAFO, origen, destino, ids_validos=ids_validos)
    
    elif modo == 'Casual':
        # Dijkstra con Penalización Lineal por Rating
        camino_ids = dijkstra(GRAFO, origen, destino, MAPA_PELICULAS, 
                              funcion_peso=calcular_peso_casual, ids_validos=ids_validos)
                              
    elif modo == 'Crítico' or modo == 'Critico': # Por si acaso el tilde
        # Dijkstra con Penalización Exponencial (Índice Snob)
        camino_ids = dijkstra(GRAFO, origen, destino, MAPA_PELICULAS, 
                              funcion_peso=calcular_peso_critico, ids_validos=ids_validos)
    
    else:
        camino_ids = None

    print(f"   ⏱️ Tiempo algoritmo: {time.time() - inicio_ts:.4f}s")

    if not camino_ids:
        return jsonify({'error': 'No se encontró conexión.'})

    # 4. Traducir Resultado
    resultado = []
    for nid in camino_ids:
        item = {'id': nid}
        if nid.startswith('nm'):
            datos = MAPA_ACTORES.get(nid, ('Desconocido', '????'))
            item.update({'type': 'person', 'title': datos[0], 'subtitle': 'Actor', 
                         'img': obtener_imagen_tmdb(nid, 'person')})
        elif nid.startswith('tt'):
            if nid in MAPA_PELICULAS:
                d = MAPA_PELICULAS[nid]
                item.update({'type': 'movie', 'title': d[0], 'subtitle': f"{d[1]} ⭐{d[4]}", 
                             'img': obtener_imagen_tmdb(nid, 'movie')})
            else:
                item.update({'type': 'movie', 'title': '?', 'subtitle': '?', 'img': None})
        resultado.append(item)

    cant_p = len(ids_validos) if ids_validos is not None else len(MAPA_PELICULAS)
    return jsonify({
        'camino': resultado, 
        'grados': (len(camino_ids)-1)//2,
        'stats': {'peliculas': cant_p, 'actores': len(MAPA_ACTORES)}
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)