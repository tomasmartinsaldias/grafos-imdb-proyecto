import os
import sqlite3
import time
import requests
import math
import json
from functools import lru_cache
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Importamos tus algoritmos
from algoritmos import bfs_bidireccional, dijkstra, dijkstra_bidireccional

load_dotenv()
app = Flask(__name__)

TMDB_KEY = os.getenv("TMDB_API_KEY")
DB_NAME = "bacon.db"
STATS_DB = "stats.db"
GLOBAL_STATS_FILE = "global_stats.json"

# ==========================================
# 1. GESTIÓN DE ESTADÍSTICAS (SQLITE)
# ==========================================
def init_stats_db():
    try:
        with sqlite3.connect(STATS_DB) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS hits (
                    id TEXT,
                    tipo TEXT,
                    modo TEXT,
                    count INTEGER DEFAULT 1,
                    PRIMARY KEY (id, modo)
                )
            ''')
    except Exception as e:
        print(f"⚠️ Error iniciando stats.db: {e}")

init_stats_db()

def guardar_hit_stats(id_entidad, tipo, modo):
    try:
        with sqlite3.connect(STATS_DB) as conn:
            conn.execute("""
                INSERT INTO hits (id, tipo, modo, count) VALUES (?, ?, ?, 1)
                ON CONFLICT(id, modo) DO UPDATE SET count = count + 1
            """, (id_entidad, tipo, modo))
            conn.commit()
    except Exception as e:
        print(f"Error guardando stat: {e}")

# ==========================================
# 2. CACHÉ & UTILS
# ==========================================
CACHE_METADATA = {}

def cargar_cache_inicial():
    print("🚀 Pre-cargando metadatos...")
    if not os.path.exists(DB_NAME): return
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.execute("SELECT id, rating, votos FROM peliculas")
        for row in cursor:
            CACHE_METADATA[row[0]] = (row[1], row[2])
        conn.close()
        print(f"✅ Caché lista: {len(CACHE_METADATA)} pelis en RAM.")
    except: pass

cargar_cache_inicial()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@lru_cache(maxsize=2000)
def obtener_imagen_tmdb(imdb_id, tipo):
    if not TMDB_KEY: return None 
    base_url = "https://api.themoviedb.org/3"
    image_base = "https://image.tmdb.org/t/p/w200"
    try:
        url = f"{base_url}/find/{imdb_id}"
        params = {"api_key": TMDB_KEY, "external_source": "imdb_id"}
        r = requests.get(url, params=params, timeout=0.5)
        data = r.json()
        path = None
        if tipo == 'person' and data.get('person_results'):
            path = data['person_results'][0].get('profile_path')
        elif tipo == 'movie' and data.get('movie_results'):
            path = data['movie_results'][0].get('poster_path')
        if path: return f"{image_base}{path}"
    except: pass
    return None

# Funciones de peso
def calcular_peso_casual(u, v, _):
    if v.startswith('nm'): return 0.1
    datos = CACHE_METADATA.get(v)
    if datos:
        rating = datos[0]
        return max(0.1, 10.1 - (rating or 0))
    return 5.0

def calcular_peso_critico(u, v, _):
    if v.startswith('nm'): return 0.1
    datos = CACHE_METADATA.get(v)
    if datos:
        rating, votos = datos
        if not rating or not votos: return 10.0
        return (2.5 ** (10.0 - rating)) * ((math.log10(votos + 1)) ** 2)
    return 50.0

# ==========================================
# 3. RUTAS
# ==========================================

@app.route('/')
def index():
    generos = ["Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary", "Drama", "Family", "Fantasy", "Horror", "Romance", "Sci-Fi", "Thriller"]
    return render_template('index.html', generos=["Todos"] + sorted(generos))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/autocomplete')
def autocomplete():
    query = request.args.get('q', '').lower().strip()
    query_limpia = ''.join(c for c in query if c.isalnum() or c.isspace())
    if len(query_limpia) < 3: return jsonify([])
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT n.id_actor, a.nombre, a.anio_nac FROM nombres n JOIN actores a ON n.id_actor = a.id WHERE n.nombre_limpio LIKE ? LIMIT 10", (query_limpia + '%',))
        res = [{'id': r['id_actor'], 'text': f"{r['nombre']} ({r['anio_nac']})"} for r in c.fetchall()]
        conn.close()
        return jsonify(res)
    except: return jsonify([])

@app.route('/api/random_actors')
def random_actors():
    try:
        conn = get_db_connection()
        filas = conn.execute("SELECT id, nombre FROM actores ORDER BY RANDOM() LIMIT 2").fetchall()
        conn.close()
        return jsonify({
            'actor1': {'id': filas[0]['id'], 'name': filas[0]['nombre']},
            'actor2': {'id': filas[1]['id'], 'name': filas[1]['nombre']}
        })
    except: return jsonify({'error': 'Error DB'}), 500

@app.route('/api/buscar', methods=['POST'])
def buscar():
    try:
        data = request.json
        origen, destino = data.get('actor1'), data.get('actor2')
        filtros = data.get('filtros', {})
        modo = filtros.get('tipo', 'Velocidad')
        
        # Filtros
        anio_min, anio_max = filtros.get('anio', [1900, 2025])
        votos_min, votos_max = filtros.get('votos', [0, 10000000])
        rat_min, rat_max = filtros.get('rating', [0.0, 10.0])
        dur_min, dur_max = filtros.get('duracion', [0, 500])
        genero = filtros.get('genero', 'Todos')
        
        ids_validos = None
        usar_filtros = (anio_min > 1900 or anio_max < 2025 or votos_min > 0 or rat_min > 0.0 or genero != 'Todos')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if usar_filtros:
            query = "SELECT id FROM peliculas WHERE anio BETWEEN ? AND ? AND votos BETWEEN ? AND ? AND rating BETWEEN ? AND ?"
            params = [anio_min, anio_max, votos_min, votos_max, rat_min, rat_max]
            if genero != 'Todos':
                query += " AND generos LIKE ?"
                params.append(f"%{genero}%")
            cursor.execute(query, params)
            ids_validos = set(row[0] for row in cursor.fetchall())

        # Algoritmo
        if modo == 'Velocidad': camino_ids = bfs_bidireccional(cursor, origen, destino, ids_validos)
        elif modo == 'Casual': camino_ids = dijkstra_bidireccional(cursor, origen, destino, calcular_peso_casual, ids_validos)
        elif modo in ['Critico', 'Crítico']: camino_ids = dijkstra_bidireccional(cursor, origen, destino, calcular_peso_critico, ids_validos)
        else: camino_ids = None

        if not camino_ids:
            conn.close()
            return jsonify({'error': 'No se encontró conexión.'})

        # --- GUARDAR STATS ---
        try:
            modo_db = 'Crítico' if modo == 'Critico' else modo
            for nid in camino_ids[1:-1]:
                tipo = 'movie' if nid.startswith('tt') else 'actor'
                guardar_hit_stats(nid, tipo, modo_db)
        except Exception as e: 
            print(f"Stats error: {e}")

        # Traducción y Respuesta
        placeholders = ','.join(['?'] * len(camino_ids))
        cursor.execute(f"SELECT id, nombre FROM actores WHERE id IN ({placeholders})", camino_ids)
        actores = {r['id']: r['nombre'] for r in cursor.fetchall()}
        cursor.execute(f"SELECT * FROM peliculas WHERE id IN ({placeholders})", camino_ids)
        pelis = {r['id']: r for r in cursor.fetchall()}
        
        # Obtenemos total de actores para estadísticas (FIX CRASH)
        total_actores = cursor.execute("SELECT count(*) FROM actores").fetchone()[0]
        
        res = []
        for nid in camino_ids:
            if nid.startswith('nm'):
                res.append({'id': nid, 'type': 'person', 'title': actores.get(nid, '?'), 'img': obtener_imagen_tmdb(nid, 'person')})
            else:
                p = pelis.get(nid)
                t = p['titulo'] if p else '?'
                # RESTAURADO: Subtítulo con año y rating
                sub = f"{p['anio']} | ⭐ {p['rating']}" if p else ""
                res.append({'id': nid, 'type': 'movie', 'title': t, 'subtitle': sub, 'img': obtener_imagen_tmdb(nid, 'movie')})

        conn.close()
        return jsonify({
            'camino': res, 
            'grados': (len(camino_ids)-1)//2, 
            'stats': {
                'peliculas': len(ids_validos) if ids_validos else 'Todas',
                'actores': total_actores # <--- AGREGADO PARA EVITAR CRASH JS
            }
        })
    except Exception as e:
        print(f"SERVER ERROR: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/stats_comparativa')
def stats_comparativa():
    resultado = {}
    try:
        # 1. GLOBAL (Desde JSON pre-calculado)
        if os.path.exists(GLOBAL_STATS_FILE):
            with open(GLOBAL_STATS_FILE, 'r') as f:
                raw_global = json.load(f)
                for cat in ['peliculas', 'actores']:
                    for item in raw_global.get(cat, []):
                        item['img'] = obtener_imagen_tmdb(item['id'], 'movie' if cat == 'peliculas' else 'person')
                resultado['Global'] = raw_global
        
        # 2. MODOS (Desde SQL stats.db)
        conn_stats = sqlite3.connect(STATS_DB)
        conn_bacon = get_db_connection()
        
        for modo in ['Velocidad', 'Casual', 'Crítico']:
            cursor = conn_stats.execute("SELECT id, count, tipo FROM hits WHERE modo=? ORDER BY count DESC LIMIT 20", (modo,))
            top_p, top_a = [], []
            
            for nid, count, tipo in cursor.fetchall():
                if tipo == 'movie':
                    r = conn_bacon.execute("SELECT titulo, anio FROM peliculas WHERE id=?", (nid,)).fetchone()
                    if r: top_p.append({'titulo': r['titulo'], 'count': f"{count} usos", 'img': obtener_imagen_tmdb(nid, 'movie')})
                else:
                    r = conn_bacon.execute("SELECT nombre FROM actores WHERE id=?", (nid,)).fetchone()
                    if r: top_a.append({'titulo': r['nombre'], 'count': f"{count} usos", 'img': obtener_imagen_tmdb(nid, 'person')})
            
            resultado[modo] = {'peliculas': top_p, 'actores': top_a}
            
        conn_stats.close()
        conn_bacon.close()
        return jsonify(resultado)
    except Exception as e:
        print(f"Stats error: {e}")
        return jsonify({})

if __name__ == '__main__':
    app.run(debug=True, port=5000)