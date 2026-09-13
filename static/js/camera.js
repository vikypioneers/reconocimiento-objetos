const camara = document.getElementById('camara');
const captura = document.getElementById('captura');
const videoRobot = document.getElementById('video-robot');
const visorVacio = document.getElementById('visor-vacio');
const estado = document.getElementById('estado');
const mensaje = document.getElementById('mensaje');
const resultado = document.getElementById('resultado');
const objeto = document.getElementById('objeto');
const confianza = document.getElementById('confianza');
const descripcion = document.getElementById('descripcion');
const informacion = document.getElementById('informacion');
const activarCamara = document.getElementById('activar-camara');
const capturarObjeto = document.getElementById('capturar-objeto');
const escucharInformacion = document.getElementById('escuchar-informacion');
const detenerAudio = document.getElementById('detener-audio');

const VIDEO_ESPERA = '/videos/espera.mp4';
const VIDEO_HABLANDO = '/videos/hablando.mp4';
let flujoCamara = null;
let textoParaLeer = '';

function actualizarEstado(texto, tipo = '') {
    estado.textContent = texto;
    estado.className = `status ${tipo ? `status-${tipo}` : ''}`;
}

function cambiarVideoRobot(hablando) {
    const videoNuevo = hablando ? VIDEO_HABLANDO : VIDEO_ESPERA;
    if (!videoRobot.src.endsWith(videoNuevo)) {
        videoRobot.src = videoNuevo;
        videoRobot.load();
    }
    videoRobot.play().catch(() => {});
}

function detenerAudioRobot() {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    cambiarVideoRobot(false);
}

function escucharTexto() {
    if (!textoParaLeer || !('speechSynthesis' in window)) {
        mensaje.textContent = 'Este navegador no permite síntesis de voz.';
        mensaje.classList.add('error');
        return;
    }
    detenerAudioRobot();
    const voz = new SpeechSynthesisUtterance(textoParaLeer);
    voz.lang = 'es-ES';
    voz.rate = 0.95;
    voz.onstart = () => cambiarVideoRobot(true);
    voz.onend = () => cambiarVideoRobot(false);
    voz.onerror = () => cambiarVideoRobot(false);
    window.speechSynthesis.speak(voz);
}

async function activarCamaraEnDispositivo() {
    if (!navigator.mediaDevices?.getUserMedia) {
        actualizarEstado('No compatible', 'error');
        mensaje.textContent = 'Tu navegador no permite acceder a la cámara. Usa Chrome, Safari o Edge actualizado.';
        mensaje.classList.add('error');
        return;
    }
    try {
        flujoCamara = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
            audio: false,
        });
        camara.srcObject = flujoCamara;
        await camara.play();
        camara.hidden = false;
        visorVacio.hidden = true;
        activarCamara.disabled = true;
        capturarObjeto.disabled = false;
        actualizarEstado('Cámara activa', 'active');
        mensaje.classList.remove('error');
        mensaje.textContent = 'Apunta al objeto y pulsa “Reconocer objeto”.';
    } catch (error) {
        const rechazado = error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError';
        actualizarEstado('Cámara bloqueada', 'error');
        mensaje.classList.add('error');
        mensaje.textContent = rechazado
            ? 'Permiso rechazado. Autoriza la cámara en la configuración del navegador y vuelve a intentarlo.'
            : `No se pudo activar la cámara: ${error.message}`;
    }
}

async function reconocerObjeto() {
    if (!flujoCamara || camara.readyState < 2) return;
    capturarObjeto.disabled = true;
    resultado.hidden = true;
    mensaje.classList.remove('error');
    mensaje.textContent = 'Analizando la imagen...';
    const ancho = camara.videoWidth || 640;
    const alto = camara.videoHeight || 480;
    captura.width = ancho;
    captura.height = alto;
    captura.getContext('2d').drawImage(camara, 0, 0, ancho, alto);
    try {
        const imagen = await new Promise((resolve, reject) => {
            captura.toBlob(blob => blob ? resolve(blob) : reject(new Error('No se pudo capturar la imagen.')), 'image/jpeg', 0.82);
        });
        const datos = new FormData();
        datos.append('image', imagen, 'camara.jpg');
        const respuesta = await fetch('/recognize', { method: 'POST', body: datos, cache: 'no-store' });
        const datosResultado = await respuesta.json();
        if (!respuesta.ok || !datosResultado.success) throw new Error(datosResultado.message || 'No se pudo reconocer el objeto.');
        objeto.textContent = datosResultado.object;
        confianza.textContent = `${Math.round(datosResultado.confidence * 100)}%`;
        descripcion.textContent = datosResultado.description || '';
        informacion.textContent = datosResultado.information || 'No hay información adicional disponible.';
        textoParaLeer = datosResultado.text || `${datosResultado.object}. ${datosResultado.information}`;
        escucharInformacion.disabled = false;
        resultado.hidden = false;
        mensaje.textContent = 'Objeto reconocido. Puedes escuchar la información.';
    } catch (error) {
        mensaje.classList.add('error');
        mensaje.textContent = error.message;
    } finally {
        capturarObjeto.disabled = false;
    }
}

activarCamara.addEventListener('click', activarCamaraEnDispositivo);
capturarObjeto.addEventListener('click', reconocerObjeto);
escucharInformacion.addEventListener('click', escucharTexto);
detenerAudio.addEventListener('click', detenerAudioRobot);
cambiarVideoRobot(false);

window.addEventListener('pagehide', () => {
    detenerAudioRobot();
    flujoCamara?.getTracks().forEach(track => track.stop());
});