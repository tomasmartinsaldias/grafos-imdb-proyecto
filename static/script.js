document.addEventListener('DOMContentLoaded', () => {
    // Inicializar componentes
    setupAutocomplete('actor1-input', 'actor1-id', 'actor1-suggestions');
    setupAutocomplete('actor2-input', 'actor2-id', 'actor2-suggestions');
    
    // Inicializar los Sliders Dobles
    initDualSlider('year-min', 'year-max', 'year-disp');
    initDualSlider('rating-min', 'rating-max', 'rating-disp');
    initDualSlider('dur-min', 'dur-max', 'dur-disp');
    
    // Inicializar Tooltips y Filtros de celular
    setupTooltips();
    setupMobileFilters();
    
    // Listener del botón buscar
    document.getElementById('search-btn').addEventListener('click', performSearch);
    document.getElementById('lucky-btn').addEventListener('click', performLuckySearch);
        // Habilitar búsqueda con tecla ENTER en los inputs
    ['actor1-input', 'actor2-input'].forEach(id => {
        document.getElementById(id).addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                // Opcional: Cerrar sugerencias si están abiertas
                document.getElementById('actor1-suggestions').innerHTML = '';
                document.getElementById('actor2-suggestions').innerHTML = '';
                
                // Disparar búsqueda
                performSearch();
            }
        });
    });
});

// --- 1. LÓGICA DE BÚSQUEDA ---
async function performSearch() {
    const actor1 = document.getElementById('actor1-id').value;
    const actor2 = document.getElementById('actor2-id').value;
    
    // Referencias UI
    const container = document.getElementById('results-container');
    const loader = document.getElementById('loading');
    const errorEl = document.getElementById('error-msg');
    const degreeBox = document.getElementById('degree-display');
    const degreeNum = document.getElementById('degree-count');
    const statsDisplay = document.getElementById('graph-stats');
    const btn = document.getElementById('search-btn');
    const resultsWrapper = document.getElementById('results-wrapper'); 

    // 1. Limpieza inicial
    errorEl.classList.add('hidden');
    degreeBox.classList.add('hidden');
    container.innerHTML = '';
    
    if (resultsWrapper) { 
        resultsWrapper.style.display = 'none'; 
    }
    
    if (!actor1 || !actor2) {
        errorEl.textContent = "Por favor selecciona ambos actores de la lista.";
        errorEl.classList.remove('hidden'); return;
    }

    // 2. Estado de Carga (UX)
    const originalBtnText = btn.innerText;
    btn.innerText = "⏳ Buscando...";
    btn.disabled = true;
    btn.style.opacity = "0.7";
    loader.classList.remove('hidden');

    // 3. Recolección de Filtros
    const filtros = {
        anio: [parseFloat(document.getElementById('year-min').value), parseFloat(document.getElementById('year-max').value)],
        rating: [parseFloat(document.getElementById('rating-min').value), parseFloat(document.getElementById('rating-max').value)],
        duracion: [parseInt(document.getElementById('dur-min').value), parseInt(document.getElementById('dur-max').value)],
        votos: [parseInt(document.getElementById('votes-min').value), parseInt(document.getElementById('votes-max').value)],
        genero: document.getElementById('genre-select').value,
        tipo: document.querySelector('input[name="mode"]:checked').value
    };

    try {
        const response = await fetch('/api/buscar', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ actor1, actor2, filtros })
        });
        
        // 🚨 USAMOS response.json() para simplicidad, asumiendo que tu backend ya está estable.
        const data = await response.json(); 

        // --- A. MOSTRAR ESTADÍSTICAS ---
        if (data.stats) {
            statsDisplay.innerHTML = `(${data.stats.peliculas.toLocaleString()} películas, ${data.stats.actores.toLocaleString()} actores)`;
            degreeBox.classList.remove('hidden');
        }

        // --- B. MANEJO DE ERRORES ---
        if (data.error) {
            errorEl.textContent = data.error;
            errorEl.classList.remove('hidden');
            
            degreeNum.textContent = "⛔"; 
            degreeNum.style.color = "#555";
            return; 
        }

        // --- C. MANEJO DE ÉXITO ---
        degreeNum.textContent = data.grados;
        degreeNum.style.color = "var(--red-oscar)";
        
        if (resultsWrapper) {
            resultsWrapper.style.display = 'flex'; 
        }

        // 🔥 Renderizado de Tarjetas (La única lógica que importa)
        data.camino.forEach((step, index) => {
            const tipoUrl = step.id.startsWith('nm') ? 'name' : 'title';
            const imdbUrl = `https://www.imdb.com/${tipoUrl}/${step.id}/`;

            const cardLink = document.createElement('a');
            cardLink.className = 'card-link';
            cardLink.href = imdbUrl;
            cardLink.target = "_blank";

            const card = document.createElement('div');
            card.className = 'card';
            
            let mediaContent = '';
            if (step.img) {
                // RENDERIZAMOS DIRECTAMENTE. Si la URL es mala, el onerror se encargará.
                mediaContent = `<img src="${step.img}" onerror="this.parentNode.innerHTML='<div class=\\'card-placeholder\\'>${step.type === 'person' ? '👤' : '🎬'}</div>'">`;
            } else {
                mediaContent = `<div class="card-placeholder">${step.type === 'person' ? '👤' : '🎬'}</div>`;
            }
            
            card.innerHTML = `
                ${mediaContent}
                <div class="card-info">
                    <div class="card-title">${step.title}</div>
                    <div class="card-sub">${step.subtitle}</div>
                </div>
            `;
            
            cardLink.appendChild(card);
            container.appendChild(cardLink);
            
            if (index < data.camino.length - 1) {
                const arrow = document.createElement('div');
                arrow.className = 'arrow';
                arrow.innerHTML = '➔';
                container.appendChild(arrow);
            }
        });

    } catch (e) {
        console.error("Error en la obtención o parseo de datos:", e);
        errorEl.textContent = "Error de conexión con el servidor. (Verificar la URL de TMDB en Python)";
        errorEl.classList.remove('hidden');
        
        if (resultsWrapper) { 
            resultsWrapper.style.display = 'none'; 
        }
    } finally {
        // --- 4. RESTAURAR ESTADO ---
        loader.classList.add('hidden');
        btn.innerText = originalBtnText;
        btn.disabled = false;
        btn.style.opacity = "1";
    }
}

// --- 2. AUTOCOMPLETE ---
function setupAutocomplete(inputId, hiddenId, suggestionId) {
    const input = document.getElementById(inputId);
    const hidden = document.getElementById(hiddenId);
    const box = document.getElementById(suggestionId);
    let timeout = null;

    input.addEventListener('input', () => {
        hidden.value = ''; 
        input.style.borderColor = 'var(--gold-medium)';
        input.classList.remove('actor-selected'); // <-- NUEVO: Quitar color si el usuario escribe
        
        clearTimeout(timeout);
        const val = input.value;
        if(val.length < 3) { box.innerHTML = ''; return; }

        timeout = setTimeout(async () => {
            try {
                const res = await fetch(`/api/autocomplete?q=${val}`);
                const data = await res.json();
                
                box.innerHTML = '';
                if (data.length === 0) {
                    // ... (sin resultados)
                    return;
                }

                data.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'suggestion-item';
                    div.textContent = item.text;
                    div.onclick = () => {
                        input.value = item.text.split('(')[0].trim();
                        hidden.value = item.id;
                        box.innerHTML = '';
                        input.style.borderColor = 'var(--gold-dark)';
                        input.style.borderWidth = '2px';
                        input.classList.add('actor-selected'); // <-- NUEVO: Añadir color al seleccionar
                    };
                    box.appendChild(div);
                });
            } catch(e) { console.log(e); }
        }, 300);
    });
    
    document.addEventListener('click', (e) => { if (e.target !== input) box.innerHTML = ''; });
}

// --- 3. SLIDERS DOBLES ---
function initDualSlider(minId, maxId, dispId) {
    const sliderMin = document.getElementById(minId);
    const sliderMax = document.getElementById(maxId);
    const display = document.getElementById(dispId);
    const track = sliderMin.parentElement.querySelector('.slider-track');

    function update() {
        let minVal = parseFloat(sliderMin.value);
        let maxVal = parseFloat(sliderMax.value);

        if (minVal > maxVal - 0.1) {
            if (this === sliderMin) sliderMin.value = maxVal;
            else sliderMax.value = minVal;
            minVal = parseFloat(sliderMin.value);
            maxVal = parseFloat(sliderMax.value);
        }

        display.textContent = `${minVal} - ${maxVal}`;

        const range = sliderMin.max - sliderMin.min;
        const percent1 = ((minVal - sliderMin.min) / range) * 100;
        const percent2 = ((maxVal - sliderMin.min) / range) * 100;
        track.style.background = `linear-gradient(to right, #ddd ${percent1}%, #801B1D ${percent1}%, #801B1D ${percent2}%, #ddd ${percent2}%)`;
    }

    sliderMin.addEventListener('input', update);
    sliderMax.addEventListener('input', update);
    update();
}

// --- 4. TOOLTIPS FLOTANTES ---
function setupTooltips() {
    const tooltip = document.getElementById('global-tooltip');
    const icons = document.querySelectorAll('.help-icon');

    icons.forEach(icon => {
        icon.addEventListener('mouseenter', () => {
            const text = icon.getAttribute('data-tooltip');
            if (!text) return;
            tooltip.innerText = text;
            tooltip.classList.add('visible');
            const rect = icon.getBoundingClientRect();
            const left = rect.right + 15; 
            const top = rect.top - 10;    
            tooltip.style.left = `${left}px`;
            tooltip.style.top = `${top}px`;
        });
        icon.addEventListener('mouseleave', () => {
            tooltip.classList.remove('visible');
        });
    });
}

async function performLuckySearch() {
    const loader = document.getElementById('loading');
    const errorEl = document.getElementById('error-msg');
    const btn = document.getElementById('lucky-btn');
    
    // Animación simple: girar el dado mientras carga
    btn.style.transition = 'transform 0.5s';
    btn.style.transform = 'rotate(360deg)';
    
    try {
        const response = await fetch('/api/random_actors');
        const data = await response.json();
        
        if (data.error) {
            errorEl.textContent = data.error;
            errorEl.classList.remove('hidden');
            return;
        }
        
        // 1. Rellenar Inputs Visuales
        document.getElementById('actor1-input').value = data.actor1.name;
        document.getElementById('actor2-input').value = data.actor2.name;
        
        // 2. Rellenar IDs Ocultos (Crucial para la búsqueda)
        document.getElementById('actor1-id').value = data.actor1.id;
        document.getElementById('actor2-id').value = data.actor2.id;
        
        // 3. Efecto visual de selección
        document.getElementById('actor1-input').classList.add('actor-selected');
        document.getElementById('actor2-input').classList.add('actor-selected');
        
        // 4. Disparar la búsqueda automáticamente
        performSearch();
        
    } catch (e) {
        console.error(e);
        errorEl.textContent = "Error conectando con el oráculo del cine.";
        errorEl.classList.remove('hidden');
    } finally {
        // Resetear rotación del dado
        setTimeout(() => { btn.style.transform = 'rotate(0deg)'; }, 500);
    }
}

function setupMobileFilters() {
    const toggleBtn = document.getElementById('filter-toggle-btn');
    const filtersBody = document.getElementById('filters-body');
    const toggleIcon = document.getElementById('toggle-icon');

    if (!toggleBtn || !filtersBody) return; // Salir si no estamos en la página correcta
    
    // En la carga inicial, asumimos que estamos en desktop si el ancho es > 768px
    // En mobile, el sidebar.header ya tiene cursor: pointer;

    toggleBtn.addEventListener('click', () => {
        // Solo aplicar el toggle si estamos en una pantalla pequeña
        if (window.innerWidth <= 768) {
            filtersBody.classList.toggle('is-open');
            toggleBtn.classList.toggle('active');
            
            // Lógica para cambiar la flecha
            if (filtersBody.classList.contains('is-open')) {
                toggleIcon.textContent = '▲';
            } else {
                toggleIcon.textContent = '▼';
            }
        }
    });
}