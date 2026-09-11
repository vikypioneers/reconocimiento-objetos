const camara = document.getElementById('camara');
const captura = document.getElementById('captura');
const videoRobot = document.getElementById('video-robot');

const VIDEO_ESPERA = '/videos/espera.mp4';
const VIDEO_HABLANDO = '/videos/hablando.mp4';
let flujoCamara = null;
let analisisEnCurso = false;
let ultimoTexto = '';

function cambiarVideoRobot(hablando) {
    const videoNuevo = hablando ? VIDEO_HABLANDO : VIDEO_ESPERA;
    if (!videoRobot.src.endsWith(videoNuevo)) {
        videoRobot.src = videoNuevo;
        videoRobot.load();
    }
    videoRobot.play().catch(() => {});
}

function hablar(texto) {
    if (!texto || !('speechSynthesis' in window) || texto === ultimoTexto) return;

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
    const ancho = camara.videoWidth || 640;
    const alto = camara.videoHeight || 480;
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
        if (resultado.success) hablar(resultado.text);
    } catch (error) {
        console.error('Error analizando la cámara:', error);
    } finally {
        analisisEnCurso = false;
    }
}

async function activarCamara() {
    if (!navigator.mediaDevices?.getUserMedia) return;

    try {
        flujoCamara = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
            audio: false,
        });
        camara.srcObject = flujoCamara;
        camara.addEventListener('loadeddata', analizarCamara, { once: true });
        setInterval(analizarCamara, 1500);
    } catch (error) {
        console.error('No se pudo acceder a la cámara:', error);
    }
}

cambiarVideoRobot(false);
activarCamara();
window.addEventListener('pagehide', () => flujoCamara?.getTracks().forEach(track => track.stop()));
