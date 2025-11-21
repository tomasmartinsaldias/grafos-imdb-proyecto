import os
import sqlite3
import time
import requests
import math
from functools import lru_cache
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Importamos la lógica
from algoritmos import bfs_bidireccional, dijkstra 

load_dotenv()
app = Flask(__name__)

TMDB_KEY = os.getenv("TMDB_API_KEY")
DB_NAME = "bacon.db"

# ==========================================
# 1. CACHÉ DE METADATOS (RAM)
# ==========================================
# Guardamos {id_peli: (rating, votos)}
# Esto ocupa muy poca RAM (~5MB) pero acelera el algoritmo 100x
CACHE_METADATA = {}

def cargar_cache_inicial():
    print("🚀 Pre-cargando metadatos (Rating + Votos) en RAM...")
    try:
        if not os.path.exists(DB_NAME):
            print("⚠️ No se encontró la DB. Saltando caché.")
            return

        conn = sqlite3.connect(DB_NAME)
        # Traemos SOLO lo numérico. El título y género se quedan en disco.
        cursor = conn.execute("SELECT id, rating, votos FROM peliculas")
        
        count = 0
        for row in cursor:
            # row[0]=id, row[1]=rating, row[2]=votos
            CACHE_METADATA[row[0]] = (row[1], row[2])
            count += 1
            
        conn.close()
        print(f"✅ Caché lista: {count} películas en memoria.")
    except Exception as e:
        print(f"❌ Error cargando caché: {e}")

# Ejecutamos la carga AL INICIAR LA APP
cargar_cache_inicial()

# ==========================================
# 2. LÓGICA DE PESOS (100% RAM)
# ==========================================

# Ya no reciben 'cursor', reciben '_' (ignorado)
def calcular_peso_casual(u, v, _):
    if v.startswith('nm'): return 0.1
    
    # Consulta a RAM (Instantánea)
    datos = CACHE_METADATA.get(v)
    if datos:
        rating = datos[0]
        if rating is None: return 5.0
        return max(0.1, 10.1 - rating)
    
    return 5.0

def calcular_peso_critico(u, v, _):
    if v.startswith('nm'): return 0.1
    
    # Consulta a RAM (Instantánea)
    datos = CACHE_METADATA.get(v)
    if datos:
        rating, votos = datos
        
        if rating is None or votos is None: return 10.0
        
        # Fórmula del Crítico (Tuneada)
        # 1. Calidad: Base 2.5 (Castigo fuerte a la mediocridad)
        factor_calidad = 2.5 ** (10.0 - rating)
        
        # 2. Fama: Logaritmo al cuadrado (Castigo a blockbusters)
        factor_fama = (math.log10(votos + 1)) ** 2
        
        return factor_calidad * factor_fama
        
    return 50.0

# ==========================================
# 3. GESTIÓN DB Y RUTAS
# ==========================================

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

@app.route('/')
def index():
    # Géneros hardcodeados para no hacer query lenta al inicio
    generos = ["Action", "Adventure", "Animation", "Biography", "Comedy", "Crime", 
               "Documentary", "Drama", "Family", "Fantasy", "History", "Horror", 
               "Music", "Musical", "Mystery", "Romance", "Sci-Fi", "Sport", "Thriller", "War", "Western"]
    return render_template('index.html', generos=["Todos"] + sorted(generos))

@app.route('/api/autocomplete')
def autocomplete():
    query = request.args.get('q', '').lower().strip()
    # Limpieza básica para SQL
    query_limpia = ''.join(c for c in query if c.isalnum() or c.isspace())
    
    if len(query_limpia) < 3: return jsonify([])
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Usamos el índice de nombres limpios
    c.execute("""
        SELECT n.id_actor, a.nombre, a.anio_nac 
        FROM nombres n
        JOIN actores a ON n.id_actor = a.id
        WHERE n.nombre_limpio LIKE ? 
        LIMIT 10
    """, (query_limpia + '%',))
    
    resultados = []
    for row in c.fetchall():
        resultados.append({
            'id': row['id_actor'], 
            'text': f"{row['nombre']} ({row['anio_nac']})"
        })
    
    conn.close()
    return jsonify(resultados)

@app.route('/api/random_actors')
def random_actors():
    try:
        conn = get_db_connection()
        filas = conn.execute("SELECT id, nombre FROM actores ORDER BY RANDOM() LIMIT 2").fetchall()
        conn.close()
        
        if len(filas) < 2: return jsonify({'error': 'Sin datos'})
        
        return jsonify({
            'actor1': {'id': filas[0]['id'], 'name': filas[0]['nombre']},
            'actor2': {'id': filas[1]['id'], 'name': filas[1]['nombre']}
        })
    except:
        return jsonify({'error': 'Error DB'}), 500

@app.route('/api/buscar', methods=['POST'])
def buscar():
    data = request.json
    origen, destino = data.get('actor1'), data.get('actor2')
    filtros = data.get('filtros', {})
    modo = filtros.get('tipo', 'Velocidad')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # --- 1. FILTROS (PATOVICA SQL) ---
    # Solo activamos si el usuario tocó algo
    anio_min, anio_max = filtros.get('anio', [1900, 2025])
    votos_min, votos_max = filtros.get('votos', [0, 10000000])
    rat_min, rat_max = filtros.get('rating', [0.0, 10.0])
    dur_min, dur_max = filtros.get('duracion', [0, 500])
    genero = filtros.get('genero', 'Todos')
    
    ids_validos = None
    usar_filtros = (anio_min > 1900 or anio_max < 2025 or votos_min > 0 or 
                    rat_min > 0.0 or dur_max < 500 or genero != 'Todos')
    
    if usar_filtros:
        print("🛡️ Generando filtro SQL...")
        query = """SELECT id FROM peliculas 
                   WHERE anio BETWEEN ? AND ? 
                   AND votos BETWEEN ? AND ? 
                   AND rating BETWEEN ? AND ?"""
        params = [anio_min, anio_max, votos_min, votos_max, rat_min, rat_max]
        
        if genero != 'Todos':
            query += " AND generos LIKE ?"
            params.append(f"%{genero}%")
            
        cursor.execute(query, params)
        ids_validos = set(row[0] for row in cursor.fetchall())
        print(f"   -> {len(ids_validos)} películas permitidas.")

    # --- 2. ALGORITMO ---
    inicio_ts = time.time()
    
    if modo == 'Velocidad':
        camino_ids = bfs_bidireccional(cursor, origen, destino, ids_validos=ids_validos)
    elif modo == 'Casual':
        # Pasamos None como tercer arg porque usamos la caché global
        camino_ids = dijkstra(cursor, origen, destino, calcular_peso_casual, ids_validos=ids_validos)
    elif modo in ['Critico', 'Crítico']:
        camino_ids = dijkstra(cursor, origen, destino, calcular_peso_critico, ids_validos=ids_validos)
    else:
        camino_ids = None
        
    print(f"   ⏱️ Tiempo Algoritmo: {time.time() - inicio_ts:.4f}s")

    if not camino_ids:
        conn.close()
        return jsonify({'error': 'No se encontró conexión.'})

    # --- 3. TRADUCCIÓN (SQL IN) ---
    placeholders = ','.join(['?'] * len(camino_ids))
    
    # Traer nombres actores
    cursor.execute(f"SELECT id, nombre FROM actores WHERE id IN ({placeholders})", camino_ids)
    info_actores = {row['id']: row['nombre'] for row in cursor.fetchall()}
    
    # Traer info pelis
    cursor.execute(f"SELECT * FROM peliculas WHERE id IN ({placeholders})", camino_ids)
    info_pelis = {row['id']: row for row in cursor.fetchall()}
    
    resultado = []
    for nid in camino_ids:
        item = {'id': nid}
        if nid.startswith('nm'):
            item.update({
                'type': 'person', 
                'title': info_actores.get(nid, 'Desconocido'), 
                'subtitle': 'Actor',
                'img': obtener_imagen_tmdb(nid, 'person')
            })
        elif nid.startswith('tt'):
            p = info_pelis.get(nid)
            if p:
                item.update({
                    'type': 'movie', 
                    'title': p['titulo'], 
                    'subtitle': f"{p['anio']} | ⭐ {p['rating']}",
                    'img': obtener_imagen_tmdb(nid, 'movie')
                })
            else:
                item.update({'type': 'movie', 'title': '?', 'subtitle': '?', 'img': None})
        resultado.append(item)

    cant_p = len(ids_validos) if ids_validos is not None else 50000 
    conn.close()
    
    return jsonify({
        'camino': resultado, 
        'grados': (len(camino_ids)-1)//2,
        'stats': {'peliculas': cant_p, 'actores': 'Muchos'} 
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)