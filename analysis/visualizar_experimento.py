import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os

# --- CONFIGURACIÓN ---
ARCHIVO_CSV = "resultados_completo.csv"
CARPETA_SALIDA = "visualizaciones"

if not os.path.exists(CARPETA_SALIDA):
    os.makedirs(CARPETA_SALIDA)

print("📊 Cargando datos del experimento...")
try:
    # low_memory=False evita advertencias si hay mezcla de tipos
    df = pd.read_csv(ARCHIVO_CSV, low_memory=False)
except FileNotFoundError:
    print(f"❌ Error: No encuentro '{ARCHIVO_CSV}'.")
    exit()

# --- FIX CRÍTICO: ESTANDARIZAR NOMBRES DE COLUMNAS ---
# Si el CSV viene de la versión vieja, renombramos las columnas para que coincidan con la nueva
mapa_nombres = {
    'pelicula_id': 'id',
    'titulo': 'titulo_nombre',
    'generos': 'generos_tipo'
}
df.rename(columns=mapa_nombres, inplace=True)
# -----------------------------------------------------

print(f"   ✅ Datos cargados: {len(df):,} registros.")

# Limpieza: Separar Películas de Actores
# Ahora sí encontrará 'id' sin fallar
df_movies = df[df['id'].astype(str).str.startswith('tt')].copy()
df_actors = df[df['id'].astype(str).str.startswith('nm')].copy()

# Convertir numéricos (con manejo de errores por si hay basura)
df_movies['rating'] = pd.to_numeric(df_movies['rating'], errors='coerce')
df_movies['anio'] = pd.to_numeric(df_movies['anio'], errors='coerce')

print(f"   🎬 Películas: {len(df_movies):,}")
print(f"   👤 Actores: {len(df_actors):,}")

# Estilos
sns.set_theme(style="whitegrid", context="talk")
COLORES = {'Velocidad': '#D32F2F', 'Casual': '#1976D2', 'Crítico': '#388E3C'}
MODOS_ORDEN = ['Velocidad', 'Casual', 'Crítico']

# ==========================================
# 1. DISTRIBUCIONES (AÑOS Y RATINGS)
# ==========================================
print("1️⃣  Generando Distribuciones...")

# Ratings
plt.figure(figsize=(10, 6))
sns.boxplot(x='modo', y='rating', data=df_movies, palette=COLORES, order=MODOS_ORDEN, showfliers=False)
plt.title('Calidad (Rating) por Modo', fontweight='bold')
plt.ylim(3, 10); plt.xlabel(''); plt.ylabel('Rating IMDb')
plt.tight_layout()
plt.savefig(f'{CARPETA_SALIDA}/1_distribucion_ratings.png')
plt.close()

# Años
plt.figure(figsize=(12, 6))
try:
    sns.kdeplot(data=df_movies, x='anio', hue='modo', palette=COLORES, hue_order=MODOS_ORDEN, fill=True, alpha=0.3, linewidth=2)
    plt.title('Épocas Predominantes por Modo', fontweight='bold')
    plt.xlim(1960, 2025); plt.xlabel('Año'); plt.ylabel('Densidad')
    plt.tight_layout()
    plt.savefig(f'{CARPETA_SALIDA}/2_distribucion_anos.png')
except Exception as e:
    print(f"⚠️ No se pudo generar gráfico de años (posible falta de datos): {e}")
plt.close()

# ==========================================
# 2. RANKING TOP 10 PELÍCULAS (SEGMENTADO)
# ==========================================
print("2️⃣  Generando Ranking Películas por Modo...")

fig, axes = plt.subplots(1, 3, figsize=(24, 10), sharey=False)
fig.suptitle('🏆 Top 10 Películas "Puente" según el Modo', fontsize=24, fontweight='bold', y=1.05)

for i, modo in enumerate(MODOS_ORDEN):
    ax = axes[i]
    subset = df_movies[df_movies['modo'] == modo]
    
    if not subset.empty:
        # Usamos 'titulo_nombre' que ahora seguro existe
        top = subset['titulo_nombre'].value_counts().head(10)
        
        sns.barplot(x=top.values, y=top.index, ax=ax, color=COLORES[modo], edgecolor='black')
        ax.set_title(modo, color=COLORES[modo], fontweight='bold', fontsize=20)
        ax.set_xlabel('Apariciones')
        
        for j, v in enumerate(top.values):
            ax.text(v + (v*0.02), j, f"{v}", va='center', fontsize=12, fontweight='bold')
    else:
        ax.text(0.5, 0.5, "Sin datos", ha='center')

plt.tight_layout()
plt.savefig(f'{CARPETA_SALIDA}/3_ranking_peliculas.png', bbox_inches='tight')
plt.close()

# ==========================================
# 3. RANKING TOP 10 ACTORES (SEGMENTADO)
# ==========================================
print("3️⃣  Generando Ranking Actores por Modo...")

fig, axes = plt.subplots(1, 3, figsize=(24, 10), sharey=False)
fig.suptitle('👤 Top 10 Actores "Puente" según el Modo', fontsize=24, fontweight='bold', y=1.05)

for i, modo in enumerate(MODOS_ORDEN):
    ax = axes[i]
    subset = df_actors[df_actors['modo'] == modo]
    
    if not subset.empty:
        top = subset['titulo_nombre'].value_counts().head(10)
        
        sns.barplot(x=top.values, y=top.index, ax=ax, color=COLORES[modo], alpha=0.7, edgecolor='black')
        ax.set_title(modo, color=COLORES[modo], fontweight='bold', fontsize=20)
        ax.set_xlabel('Apariciones')
        
        for j, v in enumerate(top.values):
            ax.text(v + (v*0.02), j, f"{v}", va='center', fontsize=12, fontweight='bold')
    else:
        ax.text(0.5, 0.5, "Sin datos suficientes", ha='center')

plt.tight_layout()
plt.savefig(f'{CARPETA_SALIDA}/4_ranking_actores.png', bbox_inches='tight')
plt.close()

# ==========================================
# 4. BENCHMARK: UNIDIRECCIONAL VS BIDIRECCIONAL
# ==========================================
print("4️⃣  Generando Gráfico de Performance (Benchmark)...")

datos_bench = {
    'Algoritmo': ['BFS (Velocidad)', 'Dijkstra (Ponderado)'],
    'Unidireccional': [0.312, 1.901],  
    'Bidireccional':  [0.004, 0.292],  
    'Speedup':        ['78x', '6.5x']
}

x = np.arange(len(datos_bench['Algoritmo']))
width = 0.35

fig, ax = plt.subplots(figsize=(12, 7))
rects1 = ax.bar(x - width/2, datos_bench['Unidireccional'], width, label='Unidireccional (Lento)', color='#B0BEC5')
rects2 = ax.bar(x + width/2, datos_bench['Bidireccional'], width, label='Bidireccional (Optimizado)', color='#2E7D32')

ax.set_ylabel('Tiempo Promedio por Búsqueda (Segundos)')
ax.set_title('Impacto de la Optimización Bidireccional (Rigurosa)', fontsize=20, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(datos_bench['Algoritmo'], fontsize=16)
ax.legend(fontsize=14)

def autolabel(rects):
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height:.3f}s',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 5), textcoords="offset points",
                    ha='center', va='bottom', fontsize=12, fontweight='bold')

autolabel(rects1)
autolabel(rects2)

for i in range(len(x)):
    speedup_val = datos_bench['Speedup'][i]
    y_pos = datos_bench['Unidireccional'][i] + 0.1
    ax.text(x[i], y_pos, f"🚀 {speedup_val} más rápido", 
            ha='center', color='#C62828', fontweight='bold', fontsize=14)

plt.ylim(0, 2.5)
plt.tight_layout()
plt.savefig(f'{CARPETA_SALIDA}/5_benchmark_performance.png')
plt.close()

print("\n✨ ¡Todo listo! Revisa la carpeta 'visualizaciones/'.")