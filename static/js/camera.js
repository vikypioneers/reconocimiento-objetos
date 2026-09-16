const camara = document.getElementById('camara');
const captura = document.getElementById('captura');
const videoRobot = document.getElementById('video-robot');
const estado = document.getElementById('estado');

const VIDEO_ESPERA = '/videos/espera.mp4';
const VIDEO_HABLANDO = '/videos/hablando.mp4';
let flujoCamara = null;
let analisisEnCurso = false;
let ultimoTexto = '';

function actualizarEstado(texto, error = false) {
    estado.textContent = texto;
    estado.classList.toggle('error', error);
}

function cambiarVideoRobot(hablando) {
    const videoNuevo = hablando ? VIDEO_HABLANDO : VIDEO_ESPERA;
    if (!videoRobot.src.endsWith(videoNuevo)) {
        videoRobot.src = videoNuevo;
        videoRobot.load();
    }
    videoRobot.play().catch(() => {});
}

function hablar(texto) {
    if (!texto || texto === ultimoTexto || !('speechSynthesis' in window)) return;

    ultimoTexto = texto;
    window.speechSynthesis.cancel();
    const voz = new SpeechSynthesisUtterance(texto);
    voz.lang = 'es-ES';
    voz.rate = 0.95;
    voz.onstart = () => cambiarVideoRobot(true);
    voz.onend = () => cambiarVideoRobot(false);
    voz.onerror = () => cambiarVideoRobot(false);
    window.speechSynthesis.speak(voz);
}

async function analizarCamara() {
    if (!flujoCamara || analisisEnCurso || camara.readyState < 2) return;

    analisisEnCurso = true;
    const escala = Math.min(1, 640 / (camara.videoWidth || 640));
    const ancho = Math.round((camara.videoWidth || 640) * escala);
    const alto = Math.round((camara.videoHeight || 480) * escala);
    captura.width = ancho;
    captura.height = alto;
    captura.getContext('2d').drawImage(camara, 0, 0, ancho, alto);

    try {
        const imagen = await new Promise((resolve, reject) => {
            captura.toBlob(blob => blob ? resolve(blob) : reject(new Error('Captura inválida')), 'image/jpeg', 0.8);
        });
        const datos = new FormData();
        datos.append('frame', imagen, 'camara.jpg');
        const respuesta = await fetch('/detectar', { method: 'POST', body: datos, cache: 'no-store' });
        const resultado = await respuesta.json();
        if (resultado.success) {
            actualizarEstado(`Detectado: ${resultado.object} (${Math.round(resultado.confidence * 100)}%)`);
            hablar(resultado.text);
        } else {
            actualizarEstado('Cámara activa. Buscando un objeto...');
        }
    } catch (error) {
        actualizarEstado('No se pudo analizar la imagen.', true);
        console.error('Error analizando la cámara:', error);
    } finally {
        analisisEnCurso = false;
    }
}

async function iniciarPrograma() {
    cambiarVideoRobot(false);

    if (!navigator.mediaDevices?.getUserMedia) {
        actualizarEstado('Este navegador no permite usar la cámara.', true);
        console.error('Este navegador no permite acceder a la cámara.');
        return;
    }

    try {
        flujoCamara = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: { ideal: 'environment' },
                width: { ideal: 640 },
                height: { ideal: 360 },
            },
            audio: false,
        });
        camara.srcObject = flujoCamara;
        await camara.play();
        actualizarEstado('Cámara activa. Analizando...');
        camara.addEventListener('loadeddata', analizarCamara, { once: true });
        window.setInterval(analizarCamara, 3000);
    } catch (error) {
        actualizarEstado('Permiso de cámara denegado o cámara no disponible.', true);
        console.error('No se pudo acceder a la cámara:', error);
    }
}

iniciarPrograma();
window.addEventListener('pagehide', () => {
    window.speechSynthesis?.cancel();
    flujoCamara?.getTracks().forEach(track => track.stop());
});