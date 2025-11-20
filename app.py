import os
import sqlite3
import time
import requests
import math
from functools import lru_cache
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Importamos la lógica adaptada a SQL
from algoritmos import bfs_bidireccional, dijkstra 

load_dotenv()
app = Flask(__name__)

TMDB_KEY = os.getenv("TMDB_API_KEY")
DB_NAME = "bacon.db"

# ==========================================
# 1. GESTIÓN DE BASE DE DATOS
# ==========================================

def get_db_connection():
    """Abre una conexión a SQLite optimizada para lectura."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # Permite acceder a columnas por nombre
    return conn

# ==========================================
# 2. LÓGICA DE PESOS (Consultas SQL puntuales)
# ==========================================

def obtener_datos_peli(cursor, peli_id):
    """Helper para sacar rating y votos de la DB."""
    # Cacheamos en memoria de Python? No hace falta, SQLite tiene su propia caché.
    cursor.execute("SELECT rating, votos FROM peliculas WHERE id = ?", (peli_id,))
    return cursor.fetchone()

def calcular_peso_casual(u, v, cursor):
    if v.startswith('nm'): return 0.1
    
    row = obtener_datos_peli(cursor, v)
    if row:
        rating = row['rating']
        return max(0.1, 10.1 - rating)
    return 5.0

def calcular_peso_critico(u, v, cursor):
    if v.startswith('nm'): return 0.1
    
    row = obtener_datos_peli(cursor, v)
    if row:
        rating = row['rating']
        votos = row['votos']
        
        # Base 2.5 (Calidad) y Log^2 (Fama)
        factor_calidad = 2.5 ** (10.0 - rating)
        factor_fama = (math.log10(votos + 1)) ** 2
        return factor_calidad * factor_fama
        
    return 50.0

# ==========================================
# 3. RUTAS WEB
# ==========================================

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

@app.route('/')
def index():
    # Obtenemos géneros de la DB dinámicamente
    conn = get_db_connection()
    # Truco: SQLite no tiene array de géneros, están como string "Drama,Action".
    # Para hacerlo simple, hardcodeamos los más comunes o hacemos una query pesada.
    # Por velocidad, hardcodeamos los principales.
    generos_comunes = ["Action", "Adventure", "Comedy", "Crime", "Drama", "Fantasy", 
                       "Horror", "Mystery", "Romance", "Sci-Fi", "Thriller"]
    conn.close()
    return render_template('index.html', generos=["Todos"] + sorted(generos_comunes))

@app.route('/api/autocomplete')
def autocomplete():
    query = request.args.get('q', '').lower().strip()
    # Limpieza manual simple (idealmente usaríamos la misma función normalizar)
    query_limpia = ''.join(c for c in query if c.isalnum() or c.isspace())
    
    if len(query_limpia) < 3: return jsonify([])
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Búsqueda SQL eficiente usando el índice idx_nombres_limpio
    # LIKE 'tom%' usa el índice. LIKE '%tom%' NO lo usa (sería lento).
    c.execute("""
        SELECT n.id_actor, a.nombre, a.anio_nac 
        FROM nombres n
        JOIN actores a ON n.id_actor = a.id
        WHERE n.nombre_limpio LIKE ? 
        LIMIT 10
    """, (query_limpia + '%',))
    
    resultados = []
    for row in c.fetchall():
        texto = f"{row['nombre']} ({row['anio_nac']})"
        resultados.append({'id': row['id_actor'], 'text': texto})
    
    conn.close()
    return jsonify(resultados)

@app.route('/api/random_actors')
def random_actors():
    conn = get_db_connection()
    # ORDER BY RANDOM() en tablas grandes es lento, pero con 300k actores es aceptable.
    # Si es lento, podríamos optimizar seleccionando IDs aleatorios en Python.
    filas = conn.execute("SELECT id, nombre FROM actores ORDER BY RANDOM() LIMIT 2").fetchall()
    conn.close()
    
    if len(filas) < 2: return jsonify({'error': 'Sin datos'})
    
    return jsonify({
        'actor1': {'id': filas[0]['id'], 'name': filas[0]['nombre']},
        'actor2': {'id': filas[1]['id'], 'name': filas[1]['nombre']}
    })

@app.route('/api/buscar', methods=['POST'])
def buscar():
    data = request.json
    origen, destino = data.get('actor1'), data.get('actor2')
    filtros = data.get('filtros', {})
    modo = filtros.get('tipo', 'Velocidad')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # --- 1. PATOVICA SQL (Filtros) ---
    anio_min, anio_max = filtros.get('anio', [1900, 2025])
    votos_min, votos_max = filtros.get('votos', [0, 10000000])
    rat_min, rat_max = filtros.get('rating', [0.0, 10.0])
    dur_min, dur_max = filtros.get('duracion', [0, 500])
    genero = filtros.get('genero', 'Todos')
    
    ids_validos = None
    usar_filtros = (anio_min > 1900 or anio_max < 2025 or votos_min > 0 or 
                    rat_min > 0 or genero != 'Todos')
    
    if usar_filtros:
        print("🛡️ Generando filtro SQL...")
        query = "SELECT id FROM peliculas WHERE anio BETWEEN ? AND ? AND votos BETWEEN ? AND ? AND rating BETWEEN ? AND ?"
        params = [anio_min, anio_max, votos_min, votos_max, rat_min, rat_max]
        
        if genero != 'Todos':
            query += " AND generos LIKE ?"
            params.append(f"%{genero}%")
            
        cursor.execute(query, params)
        # Convertimos a SET para búsqueda rápida O(1) en Python
        ids_validos = set(row[0] for row in cursor.fetchall())
        print(f"   -> {len(ids_validos)} películas permitidas.")

    # --- 2. EJECUCIÓN ---
    inicio_ts = time.time()
    
    if modo == 'Velocidad':
        camino_ids = bfs_bidireccional(cursor, origen, destino, ids_validos=ids_validos)
    elif modo == 'Casual':
        camino_ids = dijkstra(cursor, origen, destino, calcular_peso_casual, ids_validos=ids_validos)
    elif modo in ['Critico', 'Crítico']:
        camino_ids = dijkstra(cursor, origen, destino, calcular_peso_critico, ids_validos=ids_validos)
    else:
        camino_ids = None
        
    print(f"   ⏱️ Tiempo: {time.time() - inicio_ts:.4f}s")

    if not camino_ids:
        conn.close()
        return jsonify({'error': 'No se encontró conexión.'})

    # --- 3. TRADUCCIÓN (SQL IN) ---
    # Buscamos los detalles de todos los nodos del camino en una sola query
    placeholders = ','.join(['?'] * len(camino_ids))
    
    # Traer actores
    cursor.execute(f"SELECT id, nombre FROM actores WHERE id IN ({placeholders})", camino_ids)
    info_actores = {row['id']: row['nombre'] for row in cursor.fetchall()}
    
    # Traer pelis
    cursor.execute(f"SELECT * FROM peliculas WHERE id IN ({placeholders})", camino_ids)
    info_pelis = {row['id']: row for row in cursor.fetchall()}
    
    resultado = []
    for nid in camino_ids:
        item = {'id': nid}
        if nid.startswith('nm'):
            nombre = info_actores.get(nid, 'Desconocido')
            item.update({'type': 'person', 'title': nombre, 'subtitle': 'Actor',
                         'img': obtener_imagen_tmdb(nid, 'person')})
        elif nid.startswith('tt'):
            p = info_pelis.get(nid)
            if p:
                item.update({'type': 'movie', 'title': p['titulo'], 
                             'subtitle': f"{p['anio']} | ⭐ {p['rating']}",
                             'img': obtener_imagen_tmdb(nid, 'movie')})
            else:
                item.update({'type': 'movie', 'title': '?', 'subtitle': '?', 'img': None})
        resultado.append(item)

    # Estadística rápida (estimada para no matar la DB contando todo siempre)
    # Si hay filtro, usamos el len(ids_validos). Si no, un número fijo aproximado.
    cant_p = len(ids_validos) if ids_validos is not None else 50000 
    
    conn.close()
    
    return jsonify({
        'camino': resultado, 
        'grados': (len(camino_ids)-1)//2,
        'stats': {'peliculas': cant_p, 'actores': 'Muchos'} 
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)