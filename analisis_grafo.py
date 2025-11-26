import pickle
import os
import matplotlib.pyplot as plt

# --- CONFIGURACIÓN ---
PATH_GRAFO = "grafo_bacon.pkl"
CARPETA_SALIDA = "visualizaciones"
NOMBRE_ARCHIVO = "distribucion_grafo_con_stats.png"

def cargar_grafo():
    if not os.path.exists(PATH_GRAFO):
        print(f"❌ Error: No encuentro '{PATH_GRAFO}'.")
        return None
    
    print(f"📂 Cargando grafo...")
    with open(PATH_GRAFO, 'rb') as f:
        return pickle.load(f)

def generar_visualizacion(grafo):
    print("🎨 Generando gráficos...")
    
    # --- 1. PROCESAMIENTO DE DATOS ---
    total_nodos = len(grafo)
    nodos_actores = 0
    nodos_peliculas = 0
    one_hit_wonders = 0 # Contaremos los nodos con solo 1 conexión
    grados = []
    
    for nodo_id, vecinos in grafo.items():
        grado = len(vecinos)
        grados.append(grado)
        
        # Clasificación por tipo
        if nodo_id.startswith('nm'):
            nodos_actores += 1
        elif nodo_id.startswith('tt'):
            nodos_peliculas += 1
            
        # Detección de nodos hoja (One-Hit Wonders)
        if grado == 1:
            one_hit_wonders += 1

    # Cálculo de porcentaje
    pct_one_hit = (one_hit_wonders / total_nodos) * 100

    # --- 2. CONFIGURACIÓN VISUAL ---
    plt.style.use('ggplot')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    
    titulo_principal = f'Análisis del Grafo Bacon\nTotal Nodos: {total_nodos:,} | Aristas: {sum(grados)//2:,}'
    fig.suptitle(titulo_principal, fontsize=16)

    # --- GRÁFICO 1: DONUT CHART (Composición) ---
    ax1.pie([nodos_peliculas, nodos_actores], 
            labels=['Películas', 'Actores'], 
            autopct='%1.1f%%', startangle=90, 
            colors=['#ff9999','#66b3ff'], pctdistance=0.85, explode=(0.05, 0))
    ax1.add_artist(plt.Circle((0,0), 0.70, fc='white')) # Agujero dona
    ax1.set_title('Proporción del Universo')

    # --- GRÁFICO 2: HISTOGRAMA (Conectividad) ---
    # Histograma Logarítmico
    n, bins, patches = ax2.hist(grados, bins=100, color='#86bf91', edgecolor='black', alpha=0.7, log=True)
    
    ax2.set_title('Distribución de Conectividad (Log Scale)')
    ax2.set_xlabel('Cantidad de Conexiones (Grado)')
    ax2.set_ylabel('Frecuencia (Cant. de Nodos)')
    ax2.grid(True, which="both", ls="-", alpha=0.2)

    # --- CAJA DE ESTADÍSTICAS (Aquí agregamos el dato) ---
    texto_stats = (
        f"📊 ESTADÍSTICAS CLAVE:\n"
        f"─────────────────────\n"
        f"• One-Hit Wonders: {pct_one_hit:.1f}%\n"
        f"  (Nodos con 1 sola conexión)\n\n"
        f"• Max Conexiones: {max(grados):,}\n"
        f"• Promedio: {sum(grados)/total_nodos:.2f}"
    )
    
    # Insertamos la caja de texto en la esquina superior derecha del gráfico 2
    ax2.text(0.95, 0.95, texto_stats, transform=ax2.transAxes, 
             fontsize=11, verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))

    # --- 3. GUARDADO ---
    if not os.path.exists(CARPETA_SALIDA):
        os.makedirs(CARPETA_SALIDA)
    
    ruta_final = os.path.join(CARPETA_SALIDA, NOMBRE_ARCHIVO)
    print(f"💾 Guardando imagen actualizada en: {ruta_final}")
    plt.savefig(ruta_final, dpi=300, bbox_inches='tight')
    plt.close()
    print("✨ ¡Reporte actualizado con éxito!")

if __name__ == "__main__":
    grafo = cargar_grafo()
    if grafo:
        generar_visualizacion(grafo)