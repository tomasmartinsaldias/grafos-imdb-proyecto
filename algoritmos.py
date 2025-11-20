import heapq

def reconstruir_camino(padres_inicio, padres_fin, punto_choque):
    # Lado Izquierdo
    camino_izq = []
    nodo = punto_choque
    while nodo is not None:
        camino_izq.append(nodo)
        nodo = padres_inicio[nodo]
    
    # Lado Derecho
    camino_der = []
    nodo = punto_choque
    while nodo is not None:
        camino_der.append(nodo)
        nodo = padres_fin[nodo]
    
    return camino_izq[::-1] + camino_der[1:]

def bfs_bidireccional(grafo, inicio_id, fin_id, ids_validos=None):
    if inicio_id == fin_id: return [inicio_id]
    
    # Si alguno de los nodos no existe en el grafo, abortar rápido
    if inicio_id not in grafo or fin_id not in grafo:
        return None

    frontera_inicio = {inicio_id}
    frontera_fin = {fin_id}
    padres_inicio = {inicio_id: None}
    padres_fin = {fin_id: None}
    
    # Contadores para debug
    expandidos = 0
    
    while frontera_inicio and frontera_fin:
        # Balanceo de carga (Truco Pro)
        if len(frontera_inicio) > len(frontera_fin):
            frontera_inicio, frontera_fin = frontera_fin, frontera_inicio
            padres_inicio, padres_fin = padres_fin, padres_inicio

        proxima_frontera = set()
        expandidos += 1
        
        for nodo_actual in frontera_inicio:
            # Choque
            if nodo_actual in padres_fin:
                print(f"¡CONEXIÓN! (Expandidos: {expandidos} iteraciones)")
                camino = reconstruir_camino(padres_inicio, padres_fin, nodo_actual)
                # Fix de orden (asegurar que empiece por el inicio solicitado)
                if camino[0] == inicio_id: return camino
                else: return camino[::-1]

            vecinos = grafo.get(nodo_actual, [])
            for vecino in vecinos:
                if vecino in padres_inicio: continue
                
                # --- PATOVICA (FILTRO) ---
                if ids_validos is not None:
                    # Si es película (tt...) y NO está en la lista permitida -> Skip
                    if vecino.startswith('tt') and vecino not in ids_validos:
                        continue
                
                padres_inicio[vecino] = nodo_actual
                proxima_frontera.add(vecino)

        frontera_inicio = proxima_frontera
    return None


def reconstruir_camino_unidireccional(padres, fin_id):
    """Reconstruye el camino desde el fin hacia el inicio."""
    camino = []
    actual = fin_id
    while actual is not None:
        camino.append(actual)
        actual = padres.get(actual)
    return camino[::-1]

def dijkstra(grafo, inicio_id, fin_id, metadatos, funcion_peso, ids_validos=None):
    """
    Encuentra el camino de menor costo acumulado.
    Recibe una 'funcion_peso' que decide cuánto cuesta cruzar cada arista.
    """
    if inicio_id not in grafo or fin_id not in grafo: return None

    # (Costo, Nodo)
    pq = [(0, inicio_id)]
    costos = {inicio_id: 0}
    padres = {inicio_id: None}
    
    # Early Exit flag
    encontrado = False

    while pq:
        costo_actual, nodo_actual = heapq.heappop(pq)

        # Optimización Lazy
        if costo_actual > costos.get(nodo_actual, float('inf')): continue

        # Meta encontrada
        if nodo_actual == fin_id:
            return reconstruir_camino_unidireccional(padres, fin_id)

        vecinos = grafo.get(nodo_actual, [])
        for vecino in vecinos:
            # 1. Filtro Patovica (Topología)
            if ids_validos is not None:
                if vecino.startswith('tt') and vecino not in ids_validos:
                    continue
            
            # 2. Cálculo del Peso (Matemática de Negocio)
            # Pasamos nodo actual, vecino y el mapa de pelis para que calcule
            peso = funcion_peso(nodo_actual, vecino, metadatos)
            
            nuevo_costo = costo_actual + peso
            
            # 3. Relajación
            if nuevo_costo < costos.get(vecino, float('inf')):
                costos[vecino] = nuevo_costo
                padres[vecino] = nodo_actual
                heapq.heappush(pq, (nuevo_costo, vecino))
                
    return None