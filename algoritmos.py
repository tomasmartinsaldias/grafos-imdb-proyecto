import heapq

# ==========================================
# 1. BFS BIDIRECCIONAL (SQL VERSION)
# ==========================================

def obtener_vecinos_sql(cursor, nodo_id):
    """Consulta la DB para obtener los vecinos de un nodo."""
    # El índice que creamos en el ETL hace que esto tarde microsegundos
    cursor.execute("SELECT destino FROM aristas WHERE origen = ?", (nodo_id,))
    return [fila[0] for fila in cursor.fetchall()]

def reconstruir_camino(padres_inicio, padres_fin, punto_choque):
    """Une las dos mitades del camino."""
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
    """
    BFS adaptado para SQL.
    'cursor': Conexión a la base de datos bacon.db
    """
    if inicio_id == fin_id: return [inicio_id]

    frontera_inicio = {inicio_id}
    frontera_fin = {fin_id}
    padres_inicio = {inicio_id: None}
    padres_fin = {fin_id: None}
    
    while frontera_inicio and frontera_fin:
        # Balanceo de carga
        if len(frontera_inicio) > len(frontera_fin):
            frontera_inicio, frontera_fin = frontera_fin, frontera_inicio
            padres_inicio, padres_fin = padres_fin, padres_inicio

        proxima_frontera = set()
        
        for nodo_actual in frontera_inicio:
            if nodo_actual in padres_fin:
                camino = reconstruir_camino(padres_inicio, padres_fin, nodo_actual)
                return camino if camino[0] == inicio_id else camino[::-1]

            # CONSULTA SQL (Lazy Loading)
            vecinos = obtener_vecinos_sql(cursor, nodo_actual)
            
            for vecino in vecinos:
                if vecino in padres_inicio: continue
                
                # Patovica (Filtros)
                if ids_validos is not None:
                    if vecino.startswith('tt') and vecino not in ids_validos:
                        continue
                
                padres_inicio[vecino] = nodo_actual
                proxima_frontera.add(vecino)

        frontera_inicio = proxima_frontera
    return None

# ==========================================
# 2. DIJKSTRA (SQL VERSION)
# ==========================================

def reconstruir_camino_uni(padres, fin_id):
    camino = []
    actual = fin_id
    while actual is not None:
        camino.append(actual)
        actual = padres.get(actual)
    return camino[::-1]

def dijkstra(cursor, inicio_id, fin_id, funcion_peso, ids_validos=None):
    """
    Dijkstra adaptado a SQL.
    'funcion_peso' recibe (u, v, cursor) para consultar ratings al vuelo.
    """
    pq = [(0, inicio_id)]
    costos = {inicio_id: 0}
    padres = {inicio_id: None}
    
    while pq:
        costo_actual, nodo_actual = heapq.heappop(pq)

        if costo_actual > costos.get(nodo_actual, float('inf')): continue
        if nodo_actual == fin_id:
            return reconstruir_camino_uni(padres, fin_id)

        # CONSULTA SQL
        vecinos = obtener_vecinos_sql(cursor, nodo_actual)
        
        for vecino in vecinos:
            if ids_validos is not None:
                if vecino.startswith('tt') and vecino not in ids_validos:
                    continue
            
            # Calculamos peso pasando el cursor
            peso = funcion_peso(nodo_actual, vecino, cursor)
            
            nuevo_costo = costo_actual + peso
            
            if nuevo_costo < costos.get(vecino, float('inf')):
                costos[vecino] = nuevo_costo
                padres[vecino] = nodo_actual
                heapq.heappush(pq, (nuevo_costo, vecino))
                
    return None