import pickle
import random
import heapq
import math
import time
import os
import csv
from collections import Counter

# --- CONFIGURACIÓN ---
NUM_SIMULACIONES_EXTRA = 50000 # Cuántas MÁS quieres hacer
ARCHIVO_SALIDA = "resultados_completo.csv"
PATH_GRAFO = "grafo_bacon.pkl"
PATH_META = "metadata_bacon.pkl"
MIN_CONEXIONES = 15 

print(f"🧪 INICIANDO EXPERIMENTO OPTIMIZADO (Bidireccional + Resume)")

# ==========================================
# 1. CARGA DE DATOS
# ==========================================
print("1️⃣  Cargando Pickles...")
if not os.path.exists(PATH_GRAFO): print("❌ Faltan pickles"); exit()

with open(PATH_GRAFO, 'rb') as f: GRAFO = pickle.load(f)
with open(PATH_META, 'rb') as f: 
    METADATA = pickle.load(f)
    MAPA_PELICULAS = METADATA['peliculas']

todos = [k for k in GRAFO.keys() if k.startswith('nm')]
CANDIDATOS = [n for n in todos if len(GRAFO[n]) >= MIN_CONEXIONES]
print(f"   ✅ Grafo en RAM. Candidatos VIP: {len(CANDIDATOS):,}")

# ==========================================
# 2. ALGORITMOS OPTIMIZADOS (BIDIRECCIONALES)
# ==========================================
IDX_R = 4; IDX_V = 5

def get_peso_casual(rating): return max(0.1, 10.1 - rating)
def get_peso_critico(rating, votos): return (2.5 ** (10.0 - rating)) * ((math.log10(votos + 1)) ** 2)

# --- BFS BIDIRECCIONAL (VELOCIDAD) ---
def bfs_bi_fast(inicio, fin):
    if inicio == fin: return [inicio]
    frontera_a, frontera_b = {inicio}, {fin}
    padres_a, padres_b = {inicio: None}, {fin: None}
    
    # Limite de seguridad (si busca demasiado, corta)
    visitados_count = 0 
    
    while frontera_a and frontera_b:
        if len(frontera_a) > len(frontera_b):
            frontera_a, frontera_b = frontera_b, frontera_a
            padres_a, padres_b = padres_b, padres_a
            
        nueva = set()
        for u in frontera_a:
            visitados_count += 1
            if visitados_count > 8000: return None # CORTAR SI ES MUY LARGO
            
            if u in padres_b: # Choque
                # Reconstruir camino (simplificado)
                camino = []
                curr = u
                while curr: camino.append(curr); curr = padres_a[curr]
                curr = padres_b[u]
                while curr: camino.append(curr); curr = padres_b[curr]
                return camino # No importa el orden para la estadística
            
            for v in GRAFO.get(u, []):
                if v not in padres_a:
                    padres_a[v] = u
                    nueva.add(v)
        frontera_a = nueva
    return None

# --- DIJKSTRA BIDIRECCIONAL (CASUAL / CRITICO) ---
def dijkstra_bi_fast(inicio, fin, modo):
    pq_fwd = [(0, inicio)]; pq_rev = [(0, fin)]
    cost_fwd = {inicio: 0}; cost_rev = {fin: 0}
    parent_fwd = {inicio: None}; parent_rev = {fin: None}
    
    mu = float('inf')
    meet = None
    visited_fwd = set(); visited_rev = set()
    
    # Cacheo de función de peso para velocidad
    get_meta = MAPA_PELICULAS.get
    
    def calc_peso(id_peli):
        d = get_meta(id_peli)
        if not d: return 5.0
        if modo == 'casual': return get_peso_casual(d[IDX_R])
        return get_peso_critico(d[IDX_R], d[IDX_V])

    while pq_fwd and pq_rev:
        if pq_fwd[0][0] + pq_rev[0][0] >= mu: break # Criterio de parada

        # Balanceo
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
            # Peso
            w = 0.1 if v.startswith('nm') else calc_peso(v)
            
            nd = dist + w
            if nd < active_c.get(v, float('inf')):
                active_c[v] = nd
                active_par[v] = u
                heapq.heappush(active_pq, (nd, v))
                
                if v in other_c:
                    tot = nd + other_c[v]
                    if tot < mu:
                        mu = tot
                        meet = v
    
    # Reconstruir si hubo encuentro
    if meet:
        camino = []
        curr = meet
        while curr: camino.append(curr); curr = parent_fwd[curr]
        curr = parent_rev[meet] # Empezar desde padre para no duplicar meet
        while curr: camino.append(curr); curr = parent_rev[curr]
        return camino
    return None

# ==========================================
# 3. EJECUCIÓN (CON APPEND)
# ==========================================
simulaciones_hechas = 0
modo_apertura = 'w'

# Chequear si retomamos
if os.path.exists(ARCHIVO_SALIDA):
    with open(ARCHIVO_SALIDA, 'r', encoding='utf-8') as f:
        simulaciones_hechas = sum(1 for row in f) - 1 # Restar header
    if simulaciones_hechas > 0:
        print(f"   📂 Retomando archivo existente con {simulaciones_hechas} registros.")
        modo_apertura = 'a' # Append
    else:
        simulaciones_hechas = 0

print(f"2️⃣  Ejecutando {NUM_SIMULACIONES_EXTRA} nuevas simulaciones...")
t_inicio = time.time()
buffer = []

# Si es nuevo, escribimos header
if modo_apertura == 'w':
    with open(ARCHIVO_SALIDA, 'w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(['sim_id', 'modo', 'pelicula_id', 'titulo', 'anio', 'rating', 'generos'])

for i in range(1, NUM_SIMULACIONES_EXTRA + 1):
    # Feedback
    if i % 10 == 0:
        dt = time.time() - t_inicio
        vel = i / dt
        eta = (NUM_SIMULACIONES_EXTRA - i) / vel / 60
        print(f"\r   🚀 +{i} sims | Total: {simulaciones_hechas + i} | ETA: {eta:.1f} min | {vel:.1f} s/s   ", end="", flush=True)

    try:
        origen, destino = random.sample(CANDIDATOS, 2)
        
        # 1. BFS Bidireccional (Gatekeeper)
        c_vel = bfs_bi_fast(origen, destino)
        if not c_vel: continue # Sin conexión o muy lejos
        
        # Guardar Velocidad
        res = [('Velocidad', c_vel)]
        
        # 2. Casual (Bi-Dijkstra)
        c_cas = dijkstra_bi_fast(origen, destino, 'casual')
        if c_cas: res.append(('Casual', c_cas))
        
        # 3. Crítico (Bi-Dijkstra)
        c_crit = dijkstra_bi_fast(origen, destino, 'critico')
        if c_crit: res.append(('Crítico', c_crit))

        # Procesar para CSV
        for modo, camino in res:
            pelis = [n for n in camino if n.startswith('tt')]
            for pid in pelis:
                d = MAPA_PELICULAS.get(pid)
                if d:
                    # sim_id es correlativo global
                    buffer.append([simulaciones_hechas + i, modo, pid, d[0], d[1], d[4], ",".join(d[2])])

    except Exception: continue

    # Volcar a disco cada 100 sims
    if len(buffer) >= 500:
        with open(ARCHIVO_SALIDA, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerows(buffer)
        buffer = []

# Final flush
if buffer:
    with open(ARCHIVO_SALIDA, 'a', newline='', encoding='utf-8') as f:
        csv.writer(f).writerows(buffer)

print(f"\n\n✅ ¡Listo! Total acumulado: {simulaciones_hechas + i} simulaciones en {ARCHIVO_SALIDA}")