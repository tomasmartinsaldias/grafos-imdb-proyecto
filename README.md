# 🎬 Teoría de Grafos Aplicada a la Industria Cinematográfica

> **¿Existe un hilo invisible que conecta toda la industria cinematográfica?**

[![Live Demo](https://img.shields.io/badge/Demo-Live_App-FF4500?style=for-the-badge&logo=render)](https://bacon-directors-cut.onrender.com/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=flat-square)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0-green?style=flat-square)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/SQLite-Data_Storage-blue?style=flat-square)](https://www.sqlite.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Analytics-336791?style=flat-square)](https://www.postgresql.org/)

## 📄 Introducción

La teoría de los **'Seis Grados de Separación'** postula que estamos a pocos pasos de cualquier persona en el mundo. En el cine, esto crea una red masiva y compleja de actores y películas compuesta por más de **600.000 nodos y 1.400.000 conexiones**.

Este proyecto trasciende la búsqueda del camino más corto entre dos actores. **Transforma el grafo en un sistema de recomendación cultural**. Utilizando algoritmos de búsqueda y funciones de costo personalizadas, el sistema prioriza rutas basándose en la calidad cinematográfica o la popularidad, permitiendo al usuario **sumergirse en la historia del cine, en lugar de solo observar la superficie**.

[**📥 Leer la Investigación Completa (PDF)**](static/docs/monografia.pdf) - *Documento académico detallando la ingeniería de Big Data, restricciones de memoria y validación con Montecarlo.*

---

## 🚀 Live Demo

¡La aplicación está desplegada y funcionando! Puedes probarla aquí:

### [👉 https://bacon-directors-cut.onrender.com/](https://bacon-directors-cut.onrender.com/)

---

## 🛠 Arquitectura & Tech Stack

El desafío principal de este proyecto fue procesar un grafo de gran escala en un entorno de producción con **restricciones estrictas de memoria (512MB RAM)**. Para lograrlo, se diseñó una arquitectura híbrida:

### 1. Core & Algoritmos
* **Python 3**: Implementación pura de estructuras de datos y lógica de grafos.
* **Algoritmos**: Diseño *from-scratch* de **BFS Bidireccional** y **Dijkstra Bidireccional**.
* **Performance**: Se logró una reducción del tiempo de búsqueda promedio de **0,9s a 0,004s (78x)** y de **1,9s a 0,292s (6,5x)** comparado con enfoques unidireccionales tradicionales.
* **Lógica de Negocio**: Implementación de funciones de peso dinámicas (logarítmicas y exponenciales) para penalizar contenido de baja calidad en tiempo real sin reconstruir el grafo.

### 2. Ingeniería de Datos (Estrategia Híbrida)
* **Grafo Estático (SQLite)**: Dado que cargar el grafo completo serializado en RAM excedía la memoria del servidor gratuito, se migró a **SQLite** (`data/bacon.db`). Se optimizaron las lecturas de disco mediante índices para mitigar la latencia I/O.
* **Analytics (PostgreSQL)**: Se implementó una base de datos externa para registrar tendencias de búsqueda y persistir datos, superando la volatilidad del sistema de archivos de los contenedores *serverless*.

### 3. ETL Pipeline
* **Pandas & NumPy**: Pipeline de extracción y transformación de datasets masivos de IMDb (`.tsv`), limpieza de "islas" (nodos desconectados) y normalización de texto.

---

## 📂 Estructura del Proyecto

```text
/
├── analysis/          # Notebooks de Jupyter (Simulaciones Montecarlo, Benchmarks)
├── data/              # Almacenamiento de datos
│   └── bacon.db       # Grafo serializado en SQLite (Git LFS / Binary)
├── static/            # Assets (CSS, JS) y Documentación (PDF)
├── templates/         # Vistas HTML (Frontend)
├── algoritmos.py      # Implementación optimizada de Dijkstra y BFS
├── app.py             # API Flask y Rutas
├── etl.py             # Pipeline de extracción y transformación
└── requirements.txt   # Dependencias del proyecto
````

## ⚙️ Instalación y Uso Local

**1. Clonar el repositorio**

```bash
git clone [https://github.com/tu-usuario/bacon-project.git](https://github.com/tu-usuario/bacon-project.git)
cd bacon-project
```

**2. Instalar dependencias**

```bash
pip install -r requirements.txt
```

**3. Configurar Variables de Entorno**
Crea un archivo `.env` en la raíz con las siguientes variables (opcionales):

  * `TMDB_API_KEY`: Para obtener pósters e imágenes (Opcional).
  * `DATABASE_URL`: URL de conexión a PostgreSQL (Opcional, solo para analytics).

**4. Iniciar el Servidor**

```bash
python app.py
```

Visita `http://localhost:5000` en tu navegador.

-----

📊 Insights del Análisis

Las simulaciones de Montecarlo realizadas sobre el grafo revelaron comportamientos emergentes según el algoritmo utilizado:

  * **Modo Velocidad**: Exhibe un sesgo marcado hacia el cine contemporáneo (2000-2024). Este fenómeno se correlaciona con el crecimiento exponencial del volumen de producción y la densidad de actores activos en la industria moderna, lo que aumenta la probabilidad estadística de encontrar conexiones recientes.
  * **Modo Casual**: Prioriza el Canon Popular, utilizando películas de alta aceptación masiva (ej. The Godfather) como puentes principales.
  * **Modo Crítico**: Al penalizar la popularidad y premiar el rating, el algoritmo "aplana la curva temporal", redescubriendo clásicos de culto de los años 70 y 90 para realizar conexiones de mayor calidad artística.

-----

## 👤 Autor

**Tomás Martín Saldías** - *Data Science Student*
[LinkedIn](https://www.linkedin.com/in/tom%C3%A1s-sald%C3%ADas/)


