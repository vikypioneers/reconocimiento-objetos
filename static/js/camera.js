const camara = document.getElementById('camara');
const captura = document.getElementById('captura');
const videoRobot = document.getElementById('video-robot');
const estado = document.getElementById('estado');

const VIDEO_ESPERA = '/videos/espera.mp4';
const VIDEO_HABLANDO = '/videos/hablando.mp4';

let flujoCamara = null;
let analisisEnCurso = false;
let esperandoHablar = false;
let ultimoObjeto = '';
let temporizadorHabla = null;
let intervaloAnalisis = null;


// ======================================================
// ESTADO
// ======================================================

function actualizarEstado(texto, error = false) {
    if (!estado) return;

    estado.textContent = texto;
    estado.classList.toggle('error', error);
}


// ======================================================
// VIDEOS DEL ROBOT
// ======================================================

function cambiarVideoRobot(hablando) {

    const videoNuevo = hablando
        ? VIDEO_HABLANDO
        : VIDEO_ESPERA;

    const videoActual = videoRobot.getAttribute('data-video');

    if (videoActual !== videoNuevo) {

        videoRobot.pause();

        videoRobot.src = videoNuevo;

        videoRobot.setAttribute(
            'data-video',
            videoNuevo
        );

        videoRobot.load();
    }

    videoRobot.play().catch(() => {});
}


// ======================================================
// HABLAR
// ======================================================

function hablar(texto) {

    if (
        !texto ||
        !('speechSynthesis' in window)
    ) {
        esperandoHablar = false;
        cambiarVideoRobot(false);
        return;
    }

    window.speechSynthesis.cancel();

    const voz = new SpeechSynthesisUtterance(texto);

    voz.lang = 'es-ES';
    voz.rate = 0.95;
    voz.pitch = 1;
    voz.volume = 1;

    voz.onstart = () => {

        esperandoHablar = false;

        cambiarVideoRobot(true);

        actualizarEstado(
            'Hablando...'
        );
    };

    voz.onend = () => {

        esperandoHablar = false;

        cambiarVideoRobot(false);

        actualizarEstado(
            'Cámara activa. Buscando un objeto...'
        );
    };

    voz.onerror = () => {

        esperandoHablar = false;

        cambiarVideoRobot(false);

        actualizarEstado(
            'Cámara activa. Buscando un objeto...'
        );
    };

    window.speechSynthesis.speak(voz);
}


// ======================================================
// ESPERA DE 5 SEGUNDOS
// ======================================================

function programarHabla(texto, objeto) {

    if (!texto || esperandoHablar) {
        return;
    }

    esperandoHablar = true;

    actualizarEstado(
        `Detecté ${objeto}. Preparando información...`
    );

    // Cancelar temporizador anterior
    if (temporizadorHabla) {
        clearTimeout(temporizadorHabla);
    }

    temporizadorHabla = setTimeout(() => {

        temporizadorHabla = null;

        hablar(texto);

    }, 5000);
}


// ======================================================
// ANALIZAR CÁMARA
// ======================================================

async function analizarCamara() {

    if (
        !flujoCamara ||
        analisisEnCurso ||
        esperandoHablar ||
        camara.readyState < 2
    ) {
        return;
    }

    analisisEnCurso = true;

    try {

        const escala = Math.min(
            1,
            640 / (camara.videoWidth || 640)
        );

        const ancho = Math.round(
            (camara.videoWidth || 640) * escala
        );

        const alto = Math.round(
            (camara.videoHeight || 480) * escala
        );

        captura.width = ancho;
        captura.height = alto;

        const ctx = captura.getContext('2d');

        ctx.drawImage(
            camara,
            0,
            0,
            ancho,
            alto
        );

        const imagen = await new Promise(
            (resolve, reject) => {

                captura.toBlob(
                    blob => {

                        if (blob) {
                            resolve(blob);
                        } else {
                            reject(
                                new Error(
                                    'No se pudo capturar la cámara.'
                                )
                            );
                        }

                    },
                    'image/jpeg',
                    0.75
                );
            }
        );


        const datos = new FormData();

        datos.append(
            'frame',
            imagen,
            'camara.jpg'
        );


        const respuesta = await fetch(
            '/detectar',
            {
                method: 'POST',
                body: datos,
                cache: 'no-store'
            }
        );


        // ==================================================
        // IMPORTANTE:
        // NO intentar hacer response.json() si hay 502/500
        // ==================================================

        if (!respuesta.ok) {

            let mensaje = `Servidor respondió ${respuesta.status}`;

            try {

                const textoError =
                    await respuesta.text();

                if (textoError) {
                    console.error(
                        'Respuesta del servidor:',
                        textoError.substring(0, 500)
                    );
                }

            } catch (_) {}

            throw new Error(mensaje);
        }


        const resultado =
            await respuesta.json();


        if (
            resultado.success &&
            resultado.text &&
            resultado.object
        ) {

            actualizarEstado(
                `Detectado: ${resultado.object} (${Math.round(
                    resultado.confidence * 100
                )}%)`
            );


            // Evita repetir inmediatamente el mismo objeto
            if (
                resultado.object !== ultimoObjeto
            ) {

                ultimoObjeto =
                    resultado.object;

                programarHabla(
                    resultado.text,
                    resultado.object
                );
            }

        } else {

            // Si no detecta nada,
            // no hacemos hablar al robot.

            actualizarEstado(
                'Cámara activa. Buscando un objeto...'
            );

        }

    } catch (error) {

        console.error(
            'Error analizando la cámara:',
            error
        );

        actualizarEstado(
            'El servidor no está disponible temporalmente.',
            true
        );

    } finally {

        analisisEnCurso = false;
    }
}


// ======================================================
// INICIAR
// ======================================================

async function iniciarPrograma() {

    cambiarVideoRobot(false);

    if (
        !navigator.mediaDevices ||
        !navigator.mediaDevices.getUserMedia
    ) {

        actualizarEstado(
            'Este navegador no permite usar la cámara.',
            true
        );

        return;
    }


    try {

        flujoCamara =
            await navigator.mediaDevices.getUserMedia({

                video: {

                    facingMode: {
                        ideal: 'environment'
                    },

                    width: {
                        ideal: 640
                    },

                    height: {
                        ideal: 360
                    }
                },

                audio: false
            });


        camara.srcObject =
            flujoCamara;

        await camara.play();


        actualizarEstado(
            'Cámara activa. Buscando un objeto...'
        );


        // Primera detección
        setTimeout(
            analizarCamara,
            1500
        );


        // Analizar cada 5 segundos
        intervaloAnalisis =
            window.setInterval(
                analizarCamara,
                5000
            );


    } catch (error) {

        actualizarEstado(
            'Permiso de cámara denegado o cámara no disponible.',
            true
        );

        console.error(
            'No se pudo acceder a la cámara:',
            error
        );
    }
}


// ======================================================
// LIMPIEZA
// ======================================================

window.addEventListener(
    'pagehide',
    () => {

        if (
            'speechSynthesis' in window
        ) {
            window.speechSynthesis.cancel();
        }

        if (temporizadorHabla) {
            clearTimeout(
                temporizadorHabla
            );
        }

        if (intervaloAnalisis) {
            clearInterval(
                intervaloAnalisis
            );
        }

        if (flujoCamara) {

            flujoCamara
                .getTracks()
                .forEach(
                    track => track.stop()
                );
        }
    }
);


// ======================================================
// ARRANCAR
// ======================================================

iniciarPrograma();
