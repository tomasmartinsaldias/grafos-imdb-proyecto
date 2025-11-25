import os
import pickle
import time
import random
import requests
import math
import json
from functools import lru_cache
from collections import Counter
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import re
import unicodedata

# Importamos tus algoritmos
from algoritmos import bfs_bidireccional, dijkstra 

load_dotenv()
app = Flask(__name__)

TMDB_KEY = os.getenv("TMDB_API_KEY")
STATS_FILE = "stats_puentes.json"

# ==========================================
# 1. FUNCIONES DE CARGA Y PERSISTENCIA
# ==========================================

def cargar_stats():
    """Carga stats. Si el formato es viejo (plano), lo resetea al nuevo formato jerárquico."""
    estructura_base = {
        'Velocidad': Counter(),
        'Casual': Counter(),
        'Crítico': Counter()
    }
    
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                data = json.load(f)
                # Verificamos si tiene la estructura nueva (claves por modo)
                if 'Velocidad' in data:
                    return {
                        'Velocidad': Counter(data['Velocidad']),
                        'Casual': Counter(data['Casual']),
                        'Crítico': Counter(data.get('Crítico', {})) # .get por si acaso
                    }
                else:
                    print("⚠️ Formato de stats antiguo detectado. Reiniciando base de datos de stats.")
                    return estructura_base
        except Exception as e:
            print(f"⚠️ Error leyendo stats: {e}")
            return estructura_base
    return estructura_base

def guardar_stats_seguro(stats_dict):
    """
    Guarda las estadísticas protegiendo contra errores de disco.
    Si falla, NO detiene la aplicación.
    """
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(stats_dict, f)
    except Exception as e:
        print(f"⚠️ Error guardando stats: {e}")


# Variables Globales
GRAFO = {}
METADATA = {} 
MAPA_PELICULAS = {} 
MAPA_ACTORES = {}   
MAPA_NOMBRES = {}   
CANDIDATOS = []     
GENEROS = []
STATS_PUENTES = cargar_stats()
TOP_TEORICO = []

# ==========================================
# 2. LÓGICA DE NEGOCIO (PESOS)
# ==========================================

def calcular_peso_casual(u, v, mapa_pelis):
    if v.startswith('nm'): return 0.1
    if v in mapa_pelis:
        rating = mapa_pelis[v][4]
        return max(0.1, 10.1 - rating)
    return 5.0 

def calcular_peso_critico(u, v, mapa_pelis):
    if v.startswith('nm'): return 0.1
    if v in mapa_pelis:
        rating = mapa_pelis[v][4]
        votos = mapa_pelis[v][5]
        factor_calidad = 2.5 ** (10.0 - rating)
        factor_fama = (math.log10(votos + 1))**2
        return factor_calidad * factor_fama
    return 10.0

def normalizar_texto(texto):
    if not texto: return ""
    texto = texto.lower()
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8')
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    return texto.strip()

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
    global GRAFO, METADATA, MAPA_PELICULAS, MAPA_ACTORES, MAPA_NOMBRES, CANDIDATOS, GENEROS, TOP_TEORICO
    
    print("🚀 Iniciando Servidor Bacon...")
    path_grafo, path_meta = "grafo_bacon.pkl", "metadata_bacon.pkl"
    
    if not os.path.exists(path_grafo):
        print("❌ ERROR CRÍTICO: No encuentro grafo_bacon.pkl. EJECUTA 'python etl.py' PRIMERO.")
        return

    try:
        with open(path_grafo, 'rb') as f: GRAFO = pickle.load(f)
        with open(path_meta, 'rb') as f:
            METADATA = pickle.load(f)
            MAPA_PELICULAS = METADATA['peliculas']
            MAPA_ACTORES = METADATA['actores']
            MAPA_NOMBRES = METADATA['nombres']
            CANDIDATOS = METADATA['candidatos']
            GENEROS = METADATA['generos']
            TOP_TEORICO = METADATA.get('top_teorico', [])
            
        print(f"✅ Sistema Listo. {len(GRAFO)} nodos cargados.")
    except Exception as e:
        print(f"❌ Error cargando Pickles: {e}")

# Inicializamos
iniciar_servidor()

# ==========================================
# 3. RUTAS FLASK
# ==========================================

@app.route('/')
def index():
    return render_template('index.html', generos=["Todos"] + GENEROS)

@app.route('/api/autocomplete')
def autocomplete():
    try:
        raw_query = request.args.get('q', '')
        query = normalizar_texto(raw_query)
        if len(query) < 3: return jsonify([])
        
        sugerencias = []
        count = 0
        for nombre_limpio_clave, ids in MAPA_NOMBRES.items():
            if query in nombre_limpio_clave: 
                for id_actor in ids:
                    datos = MAPA_ACTORES.get(id_actor)
                    if datos:
                        nombre_real, anio = datos
                        sugerencias.append({'id': id_actor, 'text': f"{nombre_real} ({anio})"})
                        count += 1
            if count >= 10: break 
        return jsonify(sugerencias)
    except Exception as e:
        print(f"Error autocomplete: {e}")
        return jsonify([])

@app.route('/api/random_actors')
def random_actors():
    if not CANDIDATOS: return jsonify({'error': 'Sin datos'})
    a1, a2 = random.choice(CANDIDATOS), random.choice(CANDIDATOS)
    while a1 == a2: a2 = random.choice(CANDIDATOS)
    return jsonify({'actor1': a1, 'actor2': a2})

@app.route('/api/buscar', methods=['POST'])
def buscar():
    try:
        data = request.json
        origen, destino = data.get('actor1'), data.get('actor2')
        filtros = data.get('filtros', {})
        modo = filtros.get('tipo', 'Velocidad')
        
        print(f"🔍 Buscando: {origen} -> {destino} [Modo: {modo}]")

        # Configuración de Filtros
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

        # Ejecución del Algoritmo
        inicio_ts = time.time()
        
        if modo == 'Velocidad':
            camino_ids = bfs_bidireccional(GRAFO, origen, destino, ids_validos=ids_validos)
        elif modo == 'Casual':
            camino_ids = dijkstra(GRAFO, origen, destino, MAPA_PELICULAS, 
                                funcion_peso=calcular_peso_casual, ids_validos=ids_validos)
        elif modo in ['Crítico', 'Critico']:
            camino_ids = dijkstra(GRAFO, origen, destino, MAPA_PELICULAS, 
                                funcion_peso=calcular_peso_critico, ids_validos=ids_validos)
        else:
            camino_ids = None

        print(f"   ⏱️ Tiempo: {time.time() - inicio_ts:.4f}s")

        if not camino_ids:
            return jsonify({'error': 'No se encontró conexión.'})

        # --- REGISTRO DE ESTADÍSTICAS (ACTORES Y PELIS) ---
        # Aquí usamos guardar_stats_seguro para contar todo
        # [CAMBIAR SOLO ESTE BLOQUE DE REGISTRO DE ESTADÍSTICAS]
        try:
            nuevos_items = []
            if len(camino_ids) > 2:
                for nid in camino_ids[1:-1]: 
                    nuevos_items.append(nid)
            
            if nuevos_items:
                # Detectamos el modo usado
                modo_actual = filtros.get('tipo', 'Velocidad')
                
                # Normalizamos por si el frontend manda "Critico" sin tilde
                if modo_actual == 'Critico': modo_actual = 'Crítico'
                
                # Guardamos en la cubeta correspondiente
                if modo_actual in STATS_PUENTES:
                    STATS_PUENTES[modo_actual].update(nuevos_items)
                    guardar_stats_seguro(STATS_PUENTES)
                    
        except Exception as e:
            print(f"⚠️ Error guardando stats: {e}")
        # --------------------------------------------------

        # Traducir Resultado para el frontend
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

    except Exception as e:
        print(f"❌ ERROR FATAL EN BÚSQUEDA: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/stats_comparativa')
def stats_comparativa():
    try:
        resultado_global = {}
        
        # 1. PROCESAR ESTADÍSTICAS DE USUARIOS (Velocidad, Casual, Crítico)
        for modo, contador in STATS_PUENTES.items():
            top_movies = []
            top_actors = []
            
            for nid, count in contador.most_common(20):
                if nid.startswith('tt'):
                    datos = MAPA_PELICULAS.get(nid)
                    if datos:
                        top_movies.append({
                            'titulo': datos[0],
                            'anio': datos[1],
                            'count': f"{count} usos", # Etiqueta personalizada
                            'img': obtener_imagen_tmdb(nid, 'movie')
                        })
                elif nid.startswith('nm'):
                    datos = MAPA_ACTORES.get(nid)
                    if datos:
                        top_actors.append({
                            'titulo': datos[0],
                            'anio': 'Actor',
                            'count': f"{count} usos",
                            'img': obtener_imagen_tmdb(nid, 'person')
                        })
            
            resultado_global[modo] = {
                'peliculas': top_movies[:10],
                'actores': top_actors[:10]
            }
            
        # 2. PROCESAR ESTADÍSTICA TEÓRICA (GLOBAL / CENTRALIDAD)
        # Recuperamos lo que guardó el ETL
        stats_teoricas = METADATA.get('global_stats', {'peliculas': [], 'actores': []})
        
        global_movies = []
        for nid, grado in stats_teoricas['peliculas']:
            datos = MAPA_PELICULAS.get(nid)
            if datos:
                global_movies.append({
                    'titulo': datos[0],
                    'anio': datos[1],
                    'count': f"{grado} conex.", # Etiqueta distinta
                    'img': obtener_imagen_tmdb(nid, 'movie')
                })
                
        global_actors = []
        for nid, grado in stats_teoricas['actores']:
            datos = MAPA_ACTORES.get(nid)
            if datos:
                global_actors.append({
                    'titulo': datos[0],
                    'anio': 'Actor',
                    'count': f"{grado} conex.",
                    'img': obtener_imagen_tmdb(nid, 'person')
                })
        
        # Agregamos la llave 'Global' al resultado final
        resultado_global['Global'] = {
            'peliculas': global_movies[:10],
            'actores': global_actors[:10]
        }

        return jsonify(resultado_global)
        
    except Exception as e:
        print(f"Error stats comparativa: {e}")
        return jsonify({})
    
@app.route('/dashboard')
def dashboard():
    """Renderiza la página de estadísticas"""
    return render_template('dashboard.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)