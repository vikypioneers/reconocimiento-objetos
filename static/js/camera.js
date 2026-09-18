const video = document.getElementById("camera");
const canvas = document.getElementById("canvas");
const robotVideo = document.getElementById("robotVideo");

let flujoCamara = null;

let esperandoHablar = false;
let analisisEnCurso = false;

let ultimoObjeto = null;
let ultimoTiempoDeteccion = 0;


// =====================================================
// INICIAR CÁMARA
// =====================================================

async function iniciarCamara() {

    try {

        flujoCamara = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: "user",
                width: {
                    ideal: 480
                },
                height: {
                    ideal: 360
                }
            },
            audio: false
        });

        video.srcObject = flujoCamara;

        console.log("Cámara iniciada correctamente.");

        iniciarAnalisis();

    } catch (error) {

        console.error("No se pudo iniciar la cámara:", error);

    }
}


// =====================================================
// ANALIZAR CÁMARA
// =====================================================

async function analizarCamara() {

    if (analisisEnCurso) {
        return;
    }

    if (esperandoHablar) {
        return;
    }

    if (!video.videoWidth || !video.videoHeight) {
        return;
    }

    analisisEnCurso = true;

    try {

        // ---------------------------------------------
        // Tamaño reducido para ahorrar memoria
        // ---------------------------------------------

        const ancho = 480;

        const escala = ancho / video.videoWidth;

        canvas.width = ancho;
        canvas.height = Math.round(
            video.videoHeight * escala
        );

        const contexto = canvas.getContext("2d");

        contexto.drawImage(
            video,
            0,
            0,
            canvas.width,
            canvas.height
        );

        // ---------------------------------------------
        // Convertir frame a JPEG
        // ---------------------------------------------

        const blob = await new Promise(resolve => {

            canvas.toBlob(
                resolve,
                "image/jpeg",
                0.65
            );

        });

        if (!blob) {
            return;
        }

        // ---------------------------------------------
        // Enviar al servidor
        // ---------------------------------------------

        const datos = new FormData();

        datos.append(
            "frame",
            blob,
            "frame.jpg"
        );

        const respuesta = await fetch(
            "/detectar",
            {
                method: "POST",
                body: datos
            }
        );

        // ---------------------------------------------
        // Evitar error Unexpected token <
        // ---------------------------------------------

        if (!respuesta.ok) {

            const textoError = await respuesta.text();

            console.error(
                "Error del servidor:",
                respuesta.status,
                textoError
            );

            return;
        }

        const resultado = await respuesta.json();

        console.log("Resultado:", resultado);

        if (!resultado.success) {
            return;
        }

        if (!resultado.detected) {
            return;
        }

        const objeto = resultado.object;
        const texto = resultado.text;

        if (!objeto || !texto) {
            return;
        }

        // ---------------------------------------------
        // Evitar hablar repetidamente del mismo objeto
        // ---------------------------------------------

        const ahora = Date.now();

        const mismoObjeto =
            objeto === ultimoObjeto;

        const muyReciente =
            ahora - ultimoTiempoDeteccion < 10000;

        if (mismoObjeto && muyReciente) {
            return;
        }

        ultimoObjeto = objeto;
        ultimoTiempoDeteccion = ahora;

        // ---------------------------------------------
        // Esperar 5 segundos y hablar
        // ---------------------------------------------

        programarHabla(texto, objeto);

    } catch (error) {

        console.error(
            "Error analizando la cámara:",
            error
        );

    } finally {

        analisisEnCurso = false;

    }
}


// =====================================================
// ESPERAR 5 SEGUNDOS
// =====================================================

function programarHabla(texto, objeto) {

    if (esperandoHablar) {
        return;
    }

    esperandoHablar = true;

    console.log(
        `Objeto detectado: ${objeto}.`
    );

    console.log(
        "Esperando 5 segundos antes de hablar..."
    );

    setTimeout(() => {

        hablar(texto);

    }, 5000);
}


// =====================================================
// TEXTO A VOZ
// =====================================================

function hablar(texto) {

    if (!("speechSynthesis" in window)) {

        console.error(
            "El navegador no soporta síntesis de voz."
        );

        volverAEspera();

        return;
    }

    window.speechSynthesis.cancel();

    const mensaje =
        new SpeechSynthesisUtterance(texto);

    mensaje.lang = "es-ES";
    mensaje.rate = 0.95;
    mensaje.pitch = 1;
    mensaje.volume = 1;

    // ---------------------------------------------
    // Cambiar robot a hablando
    // ---------------------------------------------

    cambiarRobotHablar();

    mensaje.onstart = () => {

        console.log("Robot hablando...");

        cambiarRobotHablar();

    };

    mensaje.onend = () => {

        console.log("Robot terminó de hablar.");

        volverAEspera();

    };

    mensaje.onerror = (error) => {

        console.error(
            "Error en TTS:",
            error
        );

        volverAEspera();

    };

    window.speechSynthesis.speak(mensaje);
}


// =====================================================
// VIDEO HABLANDO
// =====================================================

function cambiarRobotHablar() {

    if (!robotVideo) {
        return;
    }

    const rutaActual =
        robotVideo.getAttribute("src");

    if (rutaActual === "/videos/hablando.mp4") {
        return;
    }

    robotVideo.src =
        "/videos/hablando.mp4";

    robotVideo.loop = true;

    robotVideo.play().catch(error => {

        console.warn(
            "No se pudo reproducir hablando.mp4:",
            error
        );

    });
}


// =====================================================
// VIDEO ESPERA
// =====================================================

function volverAEspera() {

    if (robotVideo) {

        robotVideo.src =
            "/videos/espera.mp4";

        robotVideo.loop = true;

        robotVideo.play().catch(error => {

            console.warn(
                "No se pudo reproducir espera.mp4:",
                error
            );

        });
    }

    esperandoHablar = false;

    console.log(
        "Robot volvió al estado de espera."
    );
}


// =====================================================
// BUCLE DE ANÁLISIS
// =====================================================

async function cicloAnalisis() {

    while (flujoCamara) {

        if (!esperandoHablar) {

            await analizarCamara();

        }

        await esperar(5000);
    }
}


function esperar(ms) {

    return new Promise(resolve => {

        setTimeout(resolve, ms);

    });
}


function iniciarAnalisis() {

    cicloAnalisis();

}


// =====================================================
// DETENER CÁMARA
// =====================================================

function detenerCamara() {

    if (flujoCamara) {

        flujoCamara
            .getTracks()
            .forEach(track => track.stop());

        flujoCamara = null;
    }

}


// =====================================================
// INICIAR
// =====================================================

iniciarCamara();
