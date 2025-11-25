document.addEventListener('DOMContentLoaded', () => {
    console.log("🎬 Iniciando Bacon App...");

    // 1. Inicializar Componentes (Protegidos con try-catch individual)
    try { setupAutocomplete('actor1-input', 'actor1-id', 'actor1-suggestions'); } catch(e){ console.error("Error Autocomplete 1:", e); }
    try { setupAutocomplete('actor2-input', 'actor2-id', 'actor2-suggestions'); } catch(e){ console.error("Error Autocomplete 2:", e); }
    
    try {
        initDualSlider('year-min', 'year-max', 'year-disp');
        initDualSlider('rating-min', 'rating-max', 'rating-disp');
        initDualSlider('dur-min', 'dur-max', 'dur-disp');
    } catch(e) { console.error("Error Sliders:", e); }
    
    try { setupTooltips(); } catch(e) { console.error("Error Tooltips:", e); }

    // 2. Listeners de Botones (LO MÁS IMPORTANTE)
    const btnSearch = document.getElementById('search-btn');
    const btnLucky = document.getElementById('lucky-btn');

    if (btnSearch) {
        btnSearch.addEventListener('click', performSearch);
        console.log("✅ Botón BUSCAR activado");
    } else {
        console.error("❌ No encuentro el botón 'search-btn' en el HTML");
    }

    if (btnLucky) {
        btnLucky.addEventListener('click', performLuckySearch);
        console.log("✅ Botón SUERTE activado");
    } else {
        console.error("❌ No encuentro el botón 'lucky-btn' en el HTML");
    }

    // Tecla Enter
    ['actor1-input', 'actor2-input'].forEach(id => {
        const el = document.getElementById(id);
        if(el) {
            el.addEventListener('keypress', function (e) {
                if (e.key === 'Enter') {
                    document.getElementById('actor1-suggestions').innerHTML = '';
                    document.getElementById('actor2-suggestions').innerHTML = '';
                    performSearch();
                }
            });
        }
    });

    // 3. Cargar Estadísticas (Al final, para no bloquear lo anterior)
    updateComparisonStats();
});

// --- LÓGICA DE BÚSQUEDA ---
async function performSearch() {
    console.log("🖱️ Click en Buscar detectado");
    const actor1 = document.getElementById('actor1-id').value;
    const actor2 = document.getElementById('actor2-id').value;
    
    const container = document.getElementById('results-container');
    const loader = document.getElementById('loading');
    const errorEl = document.getElementById('error-msg');
    const degreeBox = document.getElementById('degree-display');
    const degreeNum = document.getElementById('degree-count');
    const statsDisplay = document.getElementById('graph-stats');
    const btn = document.getElementById('search-btn');
    
    // Limpieza
    errorEl.classList.add('hidden');
    degreeBox.classList.add('hidden');
    container.innerHTML = '';
    
    if (!actor1 || !actor2) {
        errorEl.textContent = "⚠️ Selecciona ambos actores de la lista sugerida.";
        errorEl.classList.remove('hidden'); 
        return;
    }

    // Estado de Carga
    const originalBtnText = btn.innerText;
    btn.innerText = "⏳ Buscando...";
    btn.disabled = true;
    loader.classList.remove('hidden');

    // Recolección de Filtros
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
        
        if (!response.ok) throw new Error(`Error servidor: ${response.status}`);

        const data = await response.json();

        if (data.stats) {
            if(statsDisplay) statsDisplay.innerHTML = `(${data.stats.peliculas.toLocaleString()} películas)`;
            degreeBox.classList.remove('hidden');
        }

        if (data.error) {
            errorEl.textContent = data.error;
            errorEl.classList.remove('hidden');
            if(degreeNum) {
                degreeNum.textContent = "⛔"; 
                degreeNum.style.color = "#555";
            }
            return; 
        }

        // Éxito
        if(degreeNum) {
            degreeNum.textContent = data.grados;
            degreeNum.style.color = "var(--red-oscar)";
        }

        // Renderizado
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

        // Actualizar estadísticas globales después de búsqueda exitosa
        updateComparisonStats();

    } catch (e) {
        console.error("Error en búsqueda:", e);
        errorEl.textContent = "Error de conexión o servidor.";
        errorEl.classList.remove('hidden');
    } finally {
        loader.classList.add('hidden');
        btn.innerText = originalBtnText;
        btn.disabled = false;
    }
}

// --- AUTOCOMPLETE ---
function setupAutocomplete(inputId, hiddenId, suggestionId) {
    const input = document.getElementById(inputId);
    const hidden = document.getElementById(hiddenId);
    const box = document.getElementById(suggestionId);
    if(!input || !hidden || !box) return;

    let timeout = null;

    input.addEventListener('input', () => {
        hidden.value = ''; 
        input.classList.remove('actor-selected');
        
        clearTimeout(timeout);
        const val = input.value;
        if(val.length < 3) { box.innerHTML = ''; return; }

        timeout = setTimeout(async () => {
            try {
                const res = await fetch(`/api/autocomplete?q=${val}`);
                const data = await res.json();
                
                box.innerHTML = '';
                data.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'suggestion-item';
                    div.textContent = item.text;
                    div.onclick = () => {
                        input.value = item.text.split('(')[0].trim();
                        hidden.value = item.id;
                        box.innerHTML = '';
                        input.classList.add('actor-selected');
                    };
                    box.appendChild(div);
                });
            } catch(e) { console.error(e); }
        }, 300);
    });
    
    document.addEventListener('click', (e) => { if (e.target !== input) box.innerHTML = ''; });
}

// --- SLIDERS ---
function initDualSlider(minId, maxId, dispId) {
    const sliderMin = document.getElementById(minId);
    const sliderMax = document.getElementById(maxId);
    const display = document.getElementById(dispId);
    if(!sliderMin || !sliderMax) return; 

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

// --- TOOLTIPS ---
function setupTooltips() {
    const tooltip = document.getElementById('global-tooltip');
    const icons = document.querySelectorAll('.help-icon');
    if(!tooltip) return;

    icons.forEach(icon => {
        icon.addEventListener('mouseenter', () => {
            const text = icon.getAttribute('data-tooltip');
            if (!text) return;
            tooltip.innerText = text;
            tooltip.classList.add('visible');
            const rect = icon.getBoundingClientRect();
            tooltip.style.left = `${rect.right + 15}px`;
            tooltip.style.top = `${rect.top - 10}px`;
        });
        icon.addEventListener('mouseleave', () => {
            tooltip.classList.remove('visible');
        });
    });
}

// --- RANDOM (LUCKY) ---
async function performLuckySearch() {
    console.log("🎲 Random click");
    const loader = document.getElementById('loading');
    const errorEl = document.getElementById('error-msg');
    const btn = document.getElementById('lucky-btn');
    
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
        
        document.getElementById('actor1-input').value = data.actor1.name;
        document.getElementById('actor2-input').value = data.actor2.name;
        document.getElementById('actor1-id').value = data.actor1.id;
        document.getElementById('actor2-id').value = data.actor2.id;
        
        document.getElementById('actor1-input').classList.add('actor-selected');
        document.getElementById('actor2-input').classList.add('actor-selected');
        
        performSearch();
        
    } catch (e) {
        console.error(e);
        errorEl.textContent = "Error buscando actores aleatorios.";
        errorEl.classList.remove('hidden');
    } finally {
        setTimeout(() => { btn.style.transform = 'rotate(0deg)'; }, 500);
    }
}

// --- ESTADÍSTICAS COMPARATIVAS ---
async function updateComparisonStats() {
    console.log("📊 Actualizando dashboard...");
    try {
        const res = await fetch('/api/stats_comparativa');
        if(!res.ok) return;
        
        const data = await res.json();
        
        // Función auxiliar para crear tarjetas
        const createCards = (list, containerId, icon) => {
            const container = document.getElementById(containerId);
            if (!container) return;

            if (list.length === 0) {
                container.innerHTML = '<div style="color:#777; font-style:italic; padding:10px;">Aún no hay datos. ¡Haz una búsqueda!</div>';
                return;
            }

            container.innerHTML = list.map(item => {
                // Usamos imagen si viene, si no, el placeholder
                const imgHtml = item.img 
                    ? `<img src="${item.img}" onerror="this.parentNode.innerHTML='${icon}'">`
                    : icon;

                return `
                <div class="stat-card" title="${item.titulo}">
                    <div class="stat-img-box">${imgHtml}</div>
                    <div class="stat-info">
                        <div class="stat-title">${item.titulo}</div>
                        <div class="stat-count">🔥 ${item.count} usos</div>
                    </div>
                </div>`;
            }).join('');
        };

        // Renderizar Películas
        createCards(data.peliculas, 'stats-movies-list', '🎬');
        
        // Renderizar Actores
        createCards(data.actores, 'stats-actors-list', '👤');

    } catch (e) { 
        console.warn("Error cargando dashboard", e); 
    }
}