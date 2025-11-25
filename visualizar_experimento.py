import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter

# --- CONFIGURACIÓN ---
ARCHIVO_CSV = "resultados_completo.csv"

print("📊 Cargando datos del experimento...")
try:
    df = pd.read_csv(ARCHIVO_CSV)
except FileNotFoundError:
    print("❌ No encuentro 'resultados_completo.csv'. Ejecuta el experimento primero.")
    exit()

print(f"   ✅ Se analizaron {len(df):,} películas puente encontradas.")

# Configuración de Estilo
sns.set_theme(style="whitegrid")
COLORES = {'Velocidad': '#D32F2F', 'Casual': '#1976D2', 'Crítico': '#388E3C'}

# ==========================================
# 1. DISTRIBUCIÓN DE RATINGS (Calidad)
# ==========================================
print("1️⃣  Generando gráfico de Ratings...")
plt.figure(figsize=(10, 6))

# Boxplot: Muestra la mediana y los rangos
sns.boxplot(x='modo', y='rating', data=df, palette=COLORES, showfliers=False)
plt.title('Distribución de Calidad (Rating IMDb) por Modo', fontsize=14, fontweight='bold')
plt.ylabel('Rating IMDb (0-10)')
plt.xlabel('')
plt.savefig('analisis_ratings.png')
plt.close()

# ==========================================
# 2. DISTRIBUCIÓN DE AÑOS (Época)
# ==========================================
print("2️⃣  Generando gráfico de Años...")
plt.figure(figsize=(12, 6))

# KDE Plot: Muestra la densidad (curvas suaves)
sns.kdeplot(data=df, x='anio', hue='modo', palette=COLORES, fill=True, alpha=0.3, linewidth=2)
plt.title('Preferencias Temporales: ¿En qué época se mueve cada algoritmo?', fontsize=14, fontweight='bold')
plt.xlabel('Año de Estreno')
plt.xlim(1950, 2025) # Enfocamos en la era moderna
plt.ylabel('Densidad de Aparición')
plt.savefig('analisis_anos.png')
plt.close()

# ==========================================
# 3. TOP GÉNEROS POR MODO
# ==========================================
print("3️⃣  Generando gráfico de Géneros...")

# Procesar géneros (están como "Action,Drama" -> hay que separarlos)
data_generos = []

for modo in ['Velocidad', 'Casual', 'Crítico']:
    subdf = df[df['modo'] == modo]
    todos_generos = []
    for g_str in subdf['generos'].dropna():
        todos_generos.extend(g_str.split(','))
    
    # Contamos y tomamos el Top 5
    conteo = Counter(todos_generos)
    total = sum(conteo.values())
    
    for genero, count in conteo.most_common(5):
        data_generos.append({
            'modo': modo,
            'genero': genero,
            'porcentaje': (count / total) * 100
        })

df_gen = pd.DataFrame(data_generos)

plt.figure(figsize=(12, 6))
sns.barplot(data=df_gen, x='modo', y='porcentaje', hue='genero', palette='viridis')
plt.title('Top 5 Géneros Predominantes por Modo', fontsize=14, fontweight='bold')
plt.ylabel('Porcentaje de Aparición (%)')
plt.legend(title='Género', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.tight_layout()
plt.savefig('analisis_generos.png')
plt.close()

print("\n✨ ¡Listo! Se generaron 3 imágenes:")
print("   📄 analisis_ratings.png (Caja)")
print("   📄 analisis_anos.png (Curvas)")
print("   📄 analisis_generos.png (Barras)")