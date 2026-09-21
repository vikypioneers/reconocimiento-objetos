// ============================================================
// RECONOCIMIENTO DE OBJETOS - MR.MIND
// ============================================================

const VIDEO_ESPERA = '/videos/espera.mp4';
const VIDEO_HABLANDO = '/videos/hablando.mp4';
let flujoCamara = null;
let analisisEnCurso = false;
let ultimoTexto = '';
let textoPendiente = '';
let vozHabilitada = false;

const estado = document.getElementById("estado");
const objetoDetectado =
    document.getElementById("objetoDetectado");

let stream = null;

let analizando = false;

    if (!vozHabilitada) {
        textoPendiente = texto;
        actualizarEstado('Toca la pantalla para activar la voz.');
        return;
    }

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

function habilitarVoz() {
    vozHabilitada = true;
    if (textoPendiente) {
        const texto = textoPendiente;
        textoPendiente = '';
        hablar(texto);
    }
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
        const controlador = new AbortController();
        const temporizador = window.setTimeout(() => controlador.abort(), 25000);
        const respuesta = await fetch('/detectar', {
            method: 'POST',
            body: datos,
            cache: 'no-store',
            signal: controlador.signal,
        });
        window.clearTimeout(temporizador);
        const tipoContenido = respuesta.headers.get('content-type') || '';
        const cuerpo = await respuesta.text();
        let resultado = {};
        if (cuerpo && tipoContenido.includes('application/json')) {
            resultado = JSON.parse(cuerpo);
        }
        if (!respuesta.ok) {
            throw new Error(resultado.message || `El servidor respondió ${respuesta.status}.`);
        }
        if (!tipoContenido.includes('application/json')) {
            throw new Error('El servidor devolvió una respuesta no válida.');
        }
        if (resultado.success) {
            actualizarEstado(`Detectado: ${resultado.object} (${Math.round(resultado.confidence * 100)}%)`);
            hablar(resultado.text);
        } else {
            actualizarEstado('Cámara activa. Buscando un objeto...');
        }
    } catch (error) {
        const mensaje = error.name === 'AbortError'
            ? 'El servidor tardó demasiado en responder.'
            : error.message || 'No se pudo analizar la imagen.';
        actualizarEstado(mensaje, true);
        console.error('Error analizando la cámara:', error);
    } finally {
        analisisEnCurso = false;
    }
);


    if (!window.isSecureContext && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
        actualizarEstado('La cámara necesita una conexión HTTPS.', true);
        return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
        actualizarEstado('Este navegador no permite usar la cámara.', true);
        console.error('Este navegador no permite acceder a la cámara.');
        return;
    }

    const voces =
        window.speechSynthesis.getVoices();

    console.log(
        "Voces disponibles:",
        voces.length
    );
}


// ============================================================
// INICIAR CÁMARA
// ============================================================

async function iniciarCamara() {

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
        window.setInterval(analizarCamara, 5000);
    } catch (error) {

        console.error(
            "Error iniciando la cámara:",
            error
        );


        actualizarEstado(
            "No se pudo acceder a la cámara."
        );
    }
}

iniciarPrograma();
window.addEventListener('pointerdown', habilitarVoz, { once: true });
window.addEventListener('pagehide', () => {
    window.speechSynthesis?.cancel();
    flujoCamara?.getTracks().forEach(track => track.stop());
});