import pickle
import random
import heapq
import math
import time
import os

# --- CONFIGURACIÓN ---
NUM_TESTS = 50  # Número de pruebas (50 es suficiente para ver el patrón)
PATH_GRAFO = "grafo_bacon.pkl"
PATH_META = "metadata_bacon.pkl"

print(f"⏱️  INICIANDO BENCHMARK: Dijkstra Standard vs. Bidireccional (Riguroso)")

# ==========================================
# 1. CARGA DE DATOS
# ==========================================
print("1️⃣  Cargando Grafo en RAM...")
if not os.path.exists(PATH_GRAFO):
    print("❌ Error: No se encuentran los archivos .pkl")
    exit()

with open(PATH_GRAFO, 'rb') as f: GRAFO = pickle.load(f)
with open(PATH_META, 'rb') as f: 
    METADATA = pickle.load(f)
    MAPA_PELICULAS = METADATA['peliculas']

# Filtramos candidatos bien conectados
candidatos = [n for n in GRAFO.keys() if n.startswith('nm') and len(GRAFO[n]) > 10]
print(f"   ✅ Grafo cargado. {len(candidatos):,} candidatos.")

# ==========================================
# 2. FUNCIÓN DE PESO (CRÍTICO)
# ==========================================
def get_peso_critico(u, v):
    if v.startswith('nm'): return 0.1
    datos = MAPA_PELICULAS.get(v)
    if datos:
        rating = datos[4]
        votos = datos[5]
        return (2.5 ** (10.0 - rating)) * ((math.log10(votos + 1)) ** 2)
    return 50.0

# ==========================================
# 3. ALGORITMOS
# ==========================================

def dijkstra_standard(inicio, fin):
    """Dijkstra Unidireccional Clásico"""
    pq = [(0, inicio)]
    costos = {inicio: 0}
    
    while pq:
        costo, u = heapq.heappop(pq)
        
        if costo > costos.get(u, float('inf')): continue
        if u == fin: return costo
        
        for v in GRAFO.get(u, []):
            peso = get_peso_critico(u, v)
            nc = costo + peso
            if nc < costos.get(v, float('inf')):
                costos[v] = nc
                heapq.heappush(pq, (nc, v))
    return None

from collections import defaultdict
import heapq
import math

# ==========================================
# 1. ARMAR EL GRAFO REVERTIDO (NECESARIO)
# ==========================================

# Solo correr esto una vez después de cargar GRAFO
GRAFO_REV = defaultdict(list)
for u, vs in GRAFO.items():
    for v in vs:
        GRAFO_REV[v].append(u)

# ==========================================
# 2. ALGORITMO BIDIRECCIONAL FORMAL
# ==========================================

def dijkstra_bidireccional(inicio, fin):
    """Dijkstra Bidireccional Correcto para grafos con pesos positivos Arbitrarios."""

    # Casos borde
    if inicio == fin:
        return 0.0
    if inicio not in GRAFO or fin not in GRAFO:
        return None

    # Forward (inicio → fin)
    pq_fwd = [(0.0, inicio)]
    dist_fwd = {inicio: 0.0}
    visited_fwd = set()
    last_fwd = None  # último nodo settleado

    # Reverse (fin → inicio)
    pq_rev = [(0.0, fin)]
    dist_rev = {fin: 0.0}
    visited_rev = set()
    last_rev = None  # último nodo settleado

    # Mejor solución encontrada hasta ahora
    mu = float('inf')

    # Bucle principal
    while pq_fwd and pq_rev:

        # ===========================
        # Elegir lado a expandir:
        # expandir el lado con menor clave de heap
        # ===========================
        expand_forward = pq_fwd[0][0] <= pq_rev[0][0]

        if expand_forward:
            # ------------------------------------
            # EXPANSIÓN FORWARD
            # ------------------------------------
            dist_u, u = heapq.heappop(pq_fwd)

            if u in visited_fwd:
                continue
            visited_fwd.add(u)
            last_fwd = u

            # Check de cruce
            if u in dist_rev:
                mu = min(mu, dist_u + dist_rev[u])

            # Criterio de parada correcto
            if last_rev is not None:
                if dist_fwd[last_fwd] + dist_rev[last_rev] >= mu:
                    break

            # Expandir vecinos forward
            for v in GRAFO.get(u, []):
                peso = get_peso_critico(u, v)
                nd = dist_u + peso
                if nd < dist_fwd.get(v, float('inf')):
                    dist_fwd[v] = nd
                    heapq.heappush(pq_fwd, (nd, v))

        else:
            # ------------------------------------
            # EXPANSIÓN REVERSE
            # ------------------------------------
            dist_u, u = heapq.heappop(pq_rev)

            if u in visited_rev:
                continue
            visited_rev.add(u)
            last_rev = u

            # Check de cruce
            if u in dist_fwd:
                mu = min(mu, dist_fwd[u] + dist_u)

            # Criterio de parada correcto
            if last_fwd is not None:
                if dist_fwd[last_fwd] + dist_rev[last_rev] >= mu:
                    break

            # Expandir vecinos reverse (usando grafo invertido)
            for v in GRAFO_REV.get(u, []):
                peso = get_peso_critico(v, u)  # OJO: invertido
                nd = dist_u + peso
                if nd < dist_rev.get(v, float('inf')):
                    dist_rev[v] = nd
                    heapq.heappush(pq_rev, (nd, v))

    # ==========================================
    # Fin: retornar mejor solución encontrada
    # ==========================================
    return mu if mu != float('inf') else None


# ==========================================
# 4. EL DUELO
# ==========================================
print("\n2️⃣  Ejecutando comparativa...")
print(f"{'#':<5} | {'Uni (s)':<10} | {'Bi (s)':<10} | {'Speedup':<10} | {'Estado'}")
print("-" * 55)

tiempos_uni = []
tiempos_bi = []

for i in range(1, NUM_TESTS + 1):
    try:
        origen, destino = random.sample(candidatos, 2)
        
        # Uni
        t0 = time.time()
        res_uni = dijkstra_standard(origen, destino)
        t_uni = time.time() - t0
        
        if res_uni is None: continue

        # Bi
        t0 = time.time()
        res_bi = dijkstra_bidireccional(origen, destino)
        t_bi = time.time() - t0
        
        # Validación (Tolerancia float)
        match = False
        if res_bi is not None:
            diff = abs(res_uni - res_bi)
            # Tolerancia pequeña por errores de punto flotante
            if diff < 0.0001: match = True
            
        tiempos_uni.append(t_uni)
        tiempos_bi.append(t_bi)
        
        speedup = t_uni / t_bi if t_bi > 0 else 0
        
        estado = '✅' if match else f'❌ ({res_uni:.2f} vs {res_bi:.2f})'
        print(f"{i:<5} | {t_uni:.4f}     | {t_bi:.4f}     | {speedup:.1f}x       | {estado}")
        
    except KeyboardInterrupt: break
    except Exception as e: print(f"Error: {e}")

# ==========================================
# 5. RESULTADOS
# ==========================================
if tiempos_uni:
    avg_uni = sum(tiempos_uni) / len(tiempos_uni)
    avg_bi = sum(tiempos_bi) / len(tiempos_bi)
    total_speedup = avg_uni / avg_bi

    print("\n" + "="*40)
    print("🏁 RESULTADOS FINALES")
    print("="*40)
    print(f"Promedio Unidireccional: {avg_uni:.4f} segundos")
    print(f"Promedio Bidireccional:  {avg_bi:.4f} segundos")
    print(f"🚀 MEJORA TOTAL:         {total_speedup:.2f}x MÁS RÁPIDO")
    print("="*40)