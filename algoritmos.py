import heapq

# ==========================================
# 1. FUNCIÓN COMÚN DE ACCESO A DATOS (SOLO ARISTAS)
# ==========================================
def obtener_vecinos_sql(cursor, nodo_id, ids_validos=None):
    """
    Consulta la tabla 'aristas' para obtener vecinos.
    Soporta filtrado: si es una película ('tt...'), verifica si está en ids_validos.
    """
    # Usamos la tabla ARISTAS que generó tu ETL
    cursor.execute("SELECT destino FROM aristas WHERE origen = ?", (nodo_id,))
    
    # Obtenemos lista plana de resultados
    todos = [fila[0] for fila in cursor.fetchall()]

    # Si no hay filtros activos, devolvemos todo rápido
    if ids_validos is None:
        return todos

    # Si hay filtros, debemos validar las películas
    vecinos_filtrados = []
    for vecino in todos:
        if vecino.startswith('tt'): # Es una película
            if vecino in ids_validos:
                vecinos_filtrados.append(vecino)
        else: # Es un actor (los actores siempre pasan el filtro)
            vecinos_filtrados.append(vecino)
            
    return vecinos_filtrados

# ==========================================
# 2. BFS BIDIRECCIONAL (VELOCIDAD)
# ==========================================
def reconstruir_camino_bfs(padres_inicio, padres_fin, punto_choque):
    """Une las dos mitades del camino para BFS."""
    camino_izq = []
    nodo = punto_choque
    while nodo is not None:
        camino_izq.append(nodo)
        nodo = padres_inicio[nodo]
    
    camino_der = []
    nodo = punto_choque
    while nodo is not None:
        camino_der.append(nodo)
        nodo = padres_fin[nodo]
    
    return camino_izq[::-1] + camino_der[1:]

def bfs_bidireccional(cursor, inicio_id, fin_id, ids_validos=None):
    if inicio_id == fin_id: return [inicio_id]

    frontera_inicio = {inicio_id}
    frontera_fin = {fin_id}
    padres_inicio = {inicio_id: None}
    padres_fin = {fin_id: None}
    
    while frontera_inicio and frontera_fin:
        if len(frontera_inicio) > len(frontera_fin):
            frontera_inicio, frontera_fin = frontera_fin, frontera_inicio
            padres_inicio, padres_fin = padres_fin, padres_inicio

        proxima_frontera = set()
        
        for nodo_actual in frontera_inicio:
            if nodo_actual in padres_fin:
                camino = reconstruir_camino_bfs(padres_inicio, padres_fin, nodo_actual)
                return camino if camino[0] == inicio_id else camino[::-1]

            vecinos = obtener_vecinos_sql(cursor, nodo_actual, ids_validos)
            
            for vecino in vecinos:
                if vecino in padres_inicio: continue
                padres_inicio[vecino] = nodo_actual
                proxima_frontera.add(vecino)

        frontera_inicio = proxima_frontera
    return None

# ==========================================
# 3. DIJKSTRA BIDIRECCIONAL SQL (CASUAL/CRÍTICO)
# ==========================================
def dijkstra_bidireccional_sql(cursor, inicio, fin, funcion_peso, ids_validos=None):
    """
    Dijkstra Bidireccional optimizado para SQL usando tabla ARISTAS.
    """
    # Colas de prioridad: (costo, nodo_actual)
    q_f = [(0, inicio)]
    q_b = [(0, fin)]
    
    dist_f = {inicio: 0}
    dist_b = {fin: 0}
    parent_f = {inicio: None}
    parent_b = {fin: None}
    
    visited_f = set()
    visited_b = set()
    
    mejor_costo = float('inf')
    nodo_cruce = None
    
    while q_f and q_b:
        # --- Expansión Forward ---
        if q_f:
            costo_u, u = heapq.heappop(q_f)
            
            if costo_u < mejor_costo:
                if u in dist_b:
                    total = costo_u + dist_b[u]
                    if total < mejor_costo:
                        mejor_costo = total
                        nodo_cruce = u
                        
                if u not in visited_f:
                    visited_f.add(u)
                    # AQUÍ ESTABA EL ERROR: Ahora usa la función correcta definida arriba
                    vecinos = obtener_vecinos_sql(cursor, u, ids_validos)
                    
                    for v in vecinos:
                        peso = funcion_peso(u, v, None) 
                        nuevo_costo = costo_u + peso
                        
                        if v not in dist_f or nuevo_costo < dist_f[v]:
                            dist_f[v] = nuevo_costo
                            parent_f[v] = u
                            heapq.heappush(q_f, (nuevo_costo, v))

        # --- Expansión Backward ---
        if q_b:
            costo_v, v = heapq.heappop(q_b)
            
            if costo_v < mejor_costo:
                if v in dist_f:
                    total = costo_v + dist_f[v]
                    if total < mejor_costo:
                        mejor_costo = total
                        nodo_cruce = v

                if v not in visited_b:
                    visited_b.add(v)
                    vecinos = obtener_vecinos_sql(cursor, v, ids_validos)
                    
                    for u in vecinos:
                        peso = funcion_peso(v, u, None)
                        nuevo_costo = costo_v + peso
                        
                        if u not in dist_b or nuevo_costo < dist_b[u]:
                            dist_b[u] = nuevo_costo
                            parent_b[u] = v
                            heapq.heappush(q_b, (nuevo_costo, u))
                            
        # Criterio de parada
        if mejor_costo != float('inf') and q_f and q_b:
             if q_f[0][0] + q_b[0][0] >= mejor_costo:
                 break
                 
    if nodo_cruce:
        # Reconstrucción del camino
        path = []
        curr = nodo_cruce
        while curr:
            path.append(curr)
            curr = parent_f[curr]
        path.reverse()
        
        curr = parent_b[nodo_cruce]
        while curr:
            path.append(curr)
            curr = parent_b[curr]
            
        return list(dict.fromkeys(path)) 
        
    return None