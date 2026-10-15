// 1. Variable para almacenar los datos dinámicos
let particulasData = null;
// 2. Inicialización de OpenLayers Map

// Capa base: Mapa de OpenStreetMap con estilo oscuro (usando filtro CSS luego o CartoDB Dark Matter si es posible, aquí usaremos OSM estándar)
const baseLayer = new ol.layer.Tile({
    source: new ol.source.OSM()
});

// Fuente y Capa Vectorial para las partículas
const vectorSource = new ol.source.Vector();

// Estilo dinámico basado en el slider
const vectorLayer = new ol.layer.Vector({
    source: vectorSource,
    style: function (feature) {
        const size = parseInt(document.getElementById('size-slider').value);
        return new ol.style.Style({
            image: new ol.style.Circle({
                radius: size,
                fill: new ol.style.Fill({ color: 'rgba(251, 191, 36, 0.9)' }), // bg-amber-400
                stroke: new ol.style.Stroke({ color: 'rgba(180, 83, 9, 1)', width: 2 }) // borde más oscuro
            })
        });
    }
});

// Configuración de la vista (Centrado en México)
// Coordenadas aproximadas: lon -92, lat 20
const view = new ol.View({
    center: ol.proj.fromLonLat([-90.55, 19.85]),
    zoom: 8,
    minZoom: 3,
    maxZoom: 18
});

const map = new ol.Map({
    target: 'map',
    layers: [baseLayer, vectorLayer],
    view: view
});

// 3. Lógica de Actualización y Animación
let features = [];
let reproduciendo = false;
let animationId = null;
let startTime = null;
let startIndice = 0;
let endIndice = 0;
let duracion = 1000;

const slider = document.getElementById('time-slider');
const btnPlay = document.getElementById('btn-play');
const speedInput = document.getElementById('speed-input');
const hourDisplay = document.getElementById('hour-display');
const sizeSlider = document.getElementById('size-slider');
const sizeDisplay = document.getElementById('size-display');


slider.step = '0.001';

// Mantiene la actualización manual intacta para el estado inicial y cuando se arrastra el slider
function actualizarMapa(indiceHora) {
    if (!particulasData || !particulasData.lista[indiceHora]) return;
    const datosHora = particulasData.lista[indiceHora];
    hourDisplay.textContent = datosHora.hora;
    const puntos = datosHora.particulas;

    if (features.length === 0) {
        puntos.forEach(punto => {
            const coord = ol.proj.fromLonLat([punto.lon, punto.lat]);
            const feature = new ol.Feature({ geometry: new ol.geom.Point(coord) });
            features.push(feature);
            vectorSource.addFeature(feature);
        });
    } else {
        puntos.forEach((punto, index) => {
            if (features[index]) {
                const coord = ol.proj.fromLonLat([punto.lon, punto.lat]);
                features[index].setGeometry(new ol.geom.Point(coord));
            }
        });
    }
}

function interpolarPuntos(progreso) {
    const puntosInicio = particulasData.lista[startIndice].particulas;
    const puntosFin = particulasData.lista[endIndice].particulas;

    features.forEach((feature, index) => {
        const lonInicio = puntosInicio[index].lon;
        const latInicio = puntosInicio[index].lat;
        const lonFin = puntosFin[index].lon;
        const latFin = puntosFin[index].lat;

        // Fórmula de interpolación lineal
        const lonActual = lonInicio + (lonFin - lonInicio) * progreso;
        const latActual = latInicio + (latFin - latInicio) * progreso;

        const coord = ol.proj.fromLonLat([lonActual, latActual]);
        feature.setGeometry(new ol.geom.Point(coord));
    });
}

// NUEVO: Ciclo de renderizado nativo del navegador para animaciones suaves
function loopAnimacion(timestamp) {
    if (!startTime) startTime = timestamp;
    const progresoCálculo = (timestamp - startTime) / duracion;
    const progreso = Math.min(progresoCálculo, 1);

    interpolarPuntos(progreso);

    const horaInicio = particulasData.lista[startIndice].hora;
    const horaFin = particulasData.lista[endIndice].hora;
    hourDisplay.textContent = (horaInicio + (horaFin - horaInicio) * progreso).toFixed(1);

    // NUEVO: Mueve el deslizador suavemente a la par que la animación
    slider.value = startIndice + progreso;

    if (progreso < 1) {
        animationId = requestAnimationFrame(loopAnimacion);
    } else {
        if (reproduciendo) {
            startTime = null;
            startIndice = endIndice;

            if (startIndice >= particulasData.lista.length - 1) {
                startIndice = 0;
                slider.value = 0;
                actualizarMapa(0);
            } else {
                slider.value = startIndice;
            }

            endIndice = startIndice + 1;
            animationId = requestAnimationFrame(loopAnimacion);
        }
    }
}

// 4. Eventos de la Interfaz

// Movimiento manual del slider de tiempo
slider.addEventListener('input', (e) => {
    if (!particulasData) return;
    if (reproduciendo) btnPlay.click(); // Pausar automáticamente si el usuario interviene

    const valorDecimal = parseFloat(e.target.value);
    startIndice = Math.floor(valorDecimal);

    // Evitar desbordamiento en el índice final
    endIndice = Math.min(startIndice + 1, particulasData.lista.length - 1);

    const progreso = valorDecimal - startIndice;

    // Actualizar partículas y hora en vivo al arrastrar
    interpolarPuntos(progreso);

    const horaInicio = particulasData.lista[startIndice].hora;
    const horaFin = particulasData.lista[endIndice].hora;
    hourDisplay.textContent = (horaInicio + (horaFin - horaInicio) * progreso).toFixed(1);
});

btnPlay.addEventListener('click', () => {
    if (!particulasData) return;
    if (reproduciendo) {
        // Pausar
        cancelAnimationFrame(animationId);
        btnPlay.textContent = "Reproducir";
        btnPlay.classList.replace('bg-rose-600', 'bg-indigo-600');
        btnPlay.classList.replace('hover:bg-rose-500', 'hover:bg-indigo-500');
        reproduciendo = false;

    } else {
        // Reproducir
        duracion = parseInt(speedInput.value) || 1000;
        btnPlay.textContent = "Pausar";
        btnPlay.classList.replace('bg-indigo-600', 'bg-rose-600');
        btnPlay.classList.replace('hover:bg-indigo-500', 'hover:bg-rose-500');
        reproduciendo = true;

        startIndice = parseInt(slider.value);

        // Si el usuario presiona "Play" estando al final de la línea de tiempo, forzamos el reinicio a 0
        if (startIndice >= particulasData.lista.length - 1) {
            startIndice = 0;
            slider.value = 0;
            actualizarMapa(0);
        }

        endIndice = startIndice + 1;
        startTime = null;

        animationId = requestAnimationFrame(loopAnimacion);
    }
});

// Actualización dinámica de la velocidad si se cambia mientras reproduce
speedInput.addEventListener('change', () => {
    duracion = parseInt(speedInput.value) || 1000;
});

sizeSlider.addEventListener('input', (e) => {
    sizeDisplay.textContent = `${e.target.value}px`;
    vectorLayer.changed();
});

// 5. Consumo del backend FastAPI (/api/simular)
const btnSimular = document.getElementById('btn-simular');
const statusEl = document.getElementById('status');

function detenerAnimacion() {
    if (reproduciendo) btnPlay.click();
}

async function simular() {
    detenerAnimacion();
    const params = new URLSearchParams({
        lat_ini: document.getElementById('lat-ini').value,
        lon_ini: document.getElementById('lon-ini').value,
        tipo_crudo: document.getElementById('tipo-crudo').value,
        horas: document.getElementById('horas').value,
        n_particulas: document.getElementById('n-particulas').value
    });
    btnSimular.disabled = true;
    statusEl.textContent = 'Simulando...';
    try {
        const response = await fetch(`/api/simular?${params}`);
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP ${response.status}`);
        }
        particulasData = await response.json();

        // Reiniciar capa y estado
        vectorSource.clear();
        features = [];
        slider.max = particulasData.lista.length - 1;
        slider.value = 0;
        startIndice = 0;
        endIndice = Math.min(1, particulasData.lista.length - 1);
        actualizarMapa(0);

        view.animate({
            center: ol.proj.fromLonLat([parseFloat(params.get('lon_ini')), parseFloat(params.get('lat_ini'))]),
            zoom: 8, duration: 500
        });
        statusEl.textContent = `Listo: ${particulasData.lista.length - 1} h, ${particulasData.lista[0].particulas.length} partículas.`;
    } catch (error) {
        console.error('Error en /api/simular:', error);
        statusEl.textContent = `Error: ${error.message}`;
    } finally {
        btnSimular.disabled = false;
    }
}

btnSimular.addEventListener('click', simular);
simular(); // simulación inicial con los valores por defecto
