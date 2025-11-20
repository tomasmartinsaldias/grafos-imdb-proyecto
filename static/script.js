document.addEventListener('DOMContentLoaded', () => {
    // Inicializar componentes
    setupAutocomplete('actor1-input', 'actor1-id', 'actor1-suggestions');
    setupAutocomplete('actor2-input', 'actor2-id', 'actor2-suggestions');
    
    // Inicializar los Sliders Dobles
    initDualSlider('year-min', 'year-max', 'year-disp');
    initDualSlider('rating-min', 'rating-max', 'rating-disp');
    initDualSlider('dur-min', 'dur-max', 'dur-disp');
    
    // Inicializar Tooltips
    setupTooltips();
    
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

// --- 1. LÓGICA DE BÚSQUEDA (Aquí estaba el problema de los grados) ---
async function performSearch() {
    const actor1 = document.getElementById('actor1-id').value;
    const actor2 = document.getElementById('actor2-id').value;
    
    const container = document.getElementById('results-container');
    const loader = document.getElementById('loading');
    const errorEl = document.getElementById('error-msg');
    
    const degreeBox = document.getElementById('degree-display');
    const degreeNum = document.getElementById('degree-count');
    const statsDisplay = document.getElementById('graph-stats'); // El span de stats
    
    // Limpieza inicial
    errorEl.classList.add('hidden');
    degreeBox.classList.add('hidden');
    container.innerHTML = '';
    
    if (!actor1 || !actor2) {
        errorEl.textContent = "Por favor selecciona ambos actores de la lista.";
        errorEl.classList.remove('hidden'); return;
    }

    loader.classList.remove('hidden');

    // Filtros (IGUAL QUE ANTES)
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
        
        const data = await response.json();
        loader.classList.add('hidden'); // Ocultamos loader

        // --- 1. MOSTRAR ESTADÍSTICAS (SIEMPRE QUE HAYA) ---
        // Ahora lo hacemos fuera de la validación de éxito/error
        if (data.stats) {
            statsDisplay.innerHTML = `(${data.stats.peliculas.toLocaleString()} películas, ${data.stats.actores.toLocaleString()} actores)`;
            degreeBox.classList.remove('hidden'); // Mostramos la barra
        }

        // --- 2. MANEJO DE ERRORES (CAMINO NO ENCONTRADO) ---
        if (data.error) {
            errorEl.textContent = data.error;
            errorEl.classList.remove('hidden');
            
            // Si hay error, cambiamos el título de grados por algo visualmente claro
            degreeNum.textContent = "⛔"; 
            degreeNum.style.color = "#555"; // Color gris para indicar "vacío"
            return; // Cortamos aquí, no hay tarjetas que renderizar
        }

        // --- 3. MANEJO DE ÉXITO ---
        degreeNum.textContent = data.grados;
        degreeNum.style.color = "var(--red-oscar)"; // Restauramos el rojo

        // Pre-Carga de imágenes (IGUAL)
        const imagePromises = data.camino.map(step => {
            return new Promise((resolve) => {
                if (!step.img) { resolve(null); return; }
                const imgObj = new Image();
                imgObj.src = step.img;
                imgObj.onload = () => resolve(step.img);
                imgObj.onerror = () => resolve(null); 
            });
        });
        await Promise.all(imagePromises);

        // Renderizado de Tarjetas (IGUAL)
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
        console.error(e);
        loader.classList.add('hidden');
        errorEl.textContent = "Error de conexión con el servidor.";
        errorEl.classList.remove('hidden');
    }
}

// --- 2. AUTOCOMPLETE ---
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