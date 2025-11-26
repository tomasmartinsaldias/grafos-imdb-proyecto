import pickle
import random
import heapq
import math
import time
import os
import csv
from collections import Counter

# --- CONFIGURACIÓN ---
NUM_SIMULACIONES_EXTRA = 50000 
ARCHIVO_SALIDA = "resultados_completo.csv" # Puedes cambiarlo a "resultados_v2.csv" para empezar limpio
PATH_GRAFO = "grafo_bacon.pkl"
PATH_META = "metadata_bacon.pkl"
MIN_CONEXIONES = 15 

print(f"🧪 INICIANDO SIMULACIÓN FULL (PELÍCULAS + ACTORES)")

# ==========================================
# 1. CARGA DE DATOS
# ==========================================
print("1️⃣  Cargando Pickles...")
if not os.path.exists(PATH_GRAFO): print("❌ Faltan pickles"); exit()

with open(PATH_GRAFO, 'rb') as f: GRAFO = pickle.load(f)
with open(PATH_META, 'rb') as f: 
    METADATA = pickle.load(f)
    MAPA_PELICULAS = METADATA['peliculas']
    MAPA_ACTORES = METADATA['actores'] # Ahora cargamos actores también

todos = [k for k in GRAFO.keys() if k.startswith('nm')]
CANDIDATOS = [n for n in todos if len(GRAFO[n]) >= MIN_CONEXIONES]
print(f"   ✅ Grafo en RAM. Candidatos VIP: {len(CANDIDATOS):,}")

# ==========================================
# 2. ALGORITMOS OPTIMIZADOS
# ==========================================
IDX_R = 4; IDX_V = 5

def get_peso_casual(rating): return max(0.1, 10.1 - rating)
def get_peso_critico(rating, votos): return (2.5 ** (10.0 - rating)) * ((math.log10(votos + 1)) ** 2)

# --- BFS BIDIRECCIONAL ---
def bfs_bi_fast(inicio, fin):
    if inicio == fin: return [inicio]
    frontera_a, frontera_b = {inicio}, {fin}
    padres_a, padres_b = {inicio: None}, {fin: None}
    visitados_count = 0 
    
    while frontera_a and frontera_b:
        if len(frontera_a) > len(frontera_b):
            frontera_a, frontera_b = frontera_b, frontera_a
            padres_a, padres_b = padres_b, padres_a
            
        nueva = set()
        for u in frontera_a:
            visitados_count += 1
            if visitados_count > 8000: return None 
            
            if u in padres_b: 
                camino = []
                curr = u
                while curr: camino.append(curr); curr = padres_a[curr]
                curr = padres_b[u]
                while curr: camino.append(curr); curr = padres_b[curr]
                return camino
            
            for v in GRAFO.get(u, []):
                if v not in padres_a:
                    padres_a[v] = u
                    nueva.add(v)
        frontera_a = nueva
    return None

# --- DIJKSTRA BIDIRECCIONAL ---
def dijkstra_bi_fast(inicio, fin, modo):
    pq_fwd = [(0, inicio)]; pq_rev = [(0, fin)]
    cost_fwd = {inicio: 0}; cost_rev = {fin: 0}
    parent_fwd = {inicio: None}; parent_rev = {fin: None}
    mu = float('inf'); meet = None
    visited_fwd = set(); visited_rev = set()
    
    get_meta = MAPA_PELICULAS.get
    
    def calc_peso(id_peli):
        d = get_meta(id_peli)
        if not d: return 5.0
        if modo == 'casual': return get_peso_casual(d[IDX_R])
        return get_peso_critico(d[IDX_R], d[IDX_V])

    while pq_fwd and pq_rev:
        if pq_fwd[0][0] + pq_rev[0][0] >= mu: break 

        if len(pq_fwd) <= len(pq_rev):
            dist, u = heapq.heappop(pq_fwd)
            active_c, other_c = cost_fwd, cost_rev
            active_pq, active_vis = pq_fwd, visited_fwd
            active_par = parent_fwd
        else:
            dist, u = heapq.heappop(pq_rev)
            active_c, other_c = cost_rev, cost_fwd
            active_pq, active_vis = pq_rev, visited_rev
            active_par = parent_rev
            
        if u in active_vis: continue
        active_vis.add(u)
        
        for v in GRAFO.get(u, []):
            w = 0.1 if v.startswith('nm') else calc_peso(v)
            nd = dist + w
            if nd < active_c.get(v, float('inf')):
                active_c[v] = nd
                active_par[v] = u
                heapq.heappush(active_pq, (nd, v))
                if v in other_c:
                    tot = nd + other_c[v]
                    if tot < mu: mu = tot; meet = v
    
    if meet:
        camino = []
        curr = meet
        while curr: camino.append(curr); curr = parent_fwd[curr]
        curr = parent_rev[meet] 
        while curr: camino.append(curr); curr = parent_rev[curr]
        return camino
    return None

# ==========================================
# 3. EJECUCIÓN
# ==========================================
simulaciones_hechas = 0
modo_apertura = 'w'

if os.path.exists(ARCHIVO_SALIDA):
    with open(ARCHIVO_SALIDA, 'r', encoding='utf-8') as f:
        simulaciones_hechas = sum(1 for row in f) - 1
    if simulaciones_hechas > 0:
        print(f"   📂 Agregando a archivo existente ({simulaciones_hechas} registros previos).")
        modo_apertura = 'a'
    else:
        simulaciones_hechas = 0

print(f"2️⃣  Ejecutando {NUM_SIMULACIONES_EXTRA} simulaciones...")
t_inicio = time.time()
buffer = []

if modo_apertura == 'w':
    with open(ARCHIVO_SALIDA, 'w', newline='', encoding='utf-8') as f:
        # Usamos las mismas columnas para compatibilidad, pero 'generos' puede ser 'ACTOR'
        csv.writer(f).writerow(['sim_id', 'modo', 'id', 'titulo_nombre', 'anio', 'rating', 'generos_tipo'])

for i in range(1, NUM_SIMULACIONES_EXTRA + 1):
    if i % 10 == 0:
        dt = time.time() - t_inicio
        vel = i / dt
        eta = (NUM_SIMULACIONES_EXTRA - i) / vel / 60
        print(f"\r   🚀 +{i} sims | Total Rows: {simulaciones_hechas} | ETA: {eta:.1f} min | {vel:.1f} s/s   ", end="", flush=True)

    try:
        origen, destino = random.sample(CANDIDATOS, 2)
        res = []
        
        # 1. Velocidad
        c = bfs_bi_fast(origen, destino)
        if c: res.append(('Velocidad', c))
        
        # Si hay conexión, seguimos
        if c:
            c2 = dijkstra_bi_fast(origen, destino, 'casual')
            if c2: res.append(('Casual', c2))
            c3 = dijkstra_bi_fast(origen, destino, 'critico')
            if c3: res.append(('Crítico', c3))

        # PROCESAR RESULTADOS (PELIS + ACTORES)
        for modo, camino in res:
            # Ignoramos origen y destino (extremos), solo lo del medio cuenta como "Puente"
            puentes = camino[1:-1]
            
            for nid in puentes:
                # CASO PELÍCULA
                if nid.startswith('tt'):
                    d = MAPA_PELICULAS.get(nid)
                    if d:
                        # sim_id, modo, id, titulo, anio, rating, generos
                        buffer.append([simulaciones_hechas + i, modo, nid, d[0], d[1], d[4], ",".join(d[2])])
                
                # CASO ACTOR
                elif nid.startswith('nm'):
                    d = MAPA_ACTORES.get(nid)
                    if d:
                        # Para mantener la estructura del CSV:
                        # rating -> Dejamos vacío o 0
                        # generos -> Ponemos "ACTOR" para filtrar después
                        buffer.append([simulaciones_hechas + i, modo, nid, d[0], d[1], "", "ACTOR"])

    except Exception: continue

    if len(buffer) >= 500:
        with open(ARCHIVO_SALIDA, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerows(buffer)
            simulaciones_hechas += len(buffer)
        buffer = []

if buffer:
    with open(ARCHIVO_SALIDA, 'a', newline='', encoding='utf-8') as f:
        csv.writer(f).writerows(buffer)

print(f"\n\n✅ ¡Terminado! Datos guardados en '{ARCHIVO_SALIDA}'.")