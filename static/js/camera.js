// ============================================================
// RECONOCIMIENTO DE OBJETOS - MR.MIND
// ============================================================

const camera = document.getElementById("camera");
const canvas = document.getElementById("canvas");
const robotVideo = document.getElementById("robotVideo");


// ============================================================
// VARIABLES
// ============================================================

let stream = null;

let analizando = false;

let esperandoHablar = false;

let objetoPendiente = null;

let ultimoObjeto = null;

let ultimoTiempo = 0;

let vozDisponible = false;


// ============================================================
// INICIAR
// ============================================================

document.addEventListener("DOMContentLoaded", () => {

    iniciarCamara();

    cargarVoces();

    if ("speechSynthesis" in window) {

        window.speechSynthesis.onvoiceschanged =
            cargarVoces;
    }

});


// ============================================================
// CARGAR VOCES
// ============================================================

function cargarVoces() {

    if (!("speechSynthesis" in window)) {
        return;
    }

    const voces =
        window.speechSynthesis.getVoices();

    if (voces.length > 0) {

        vozDisponible = true;

        console.log(
            "Voces disponibles:",
            voces.length
        );
    }
}


// ============================================================
// INICIAR CÁMARA
// ============================================================

async function iniciarCamara() {

    try {

        stream =
            await navigator.mediaDevices.getUserMedia({

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

        camera.srcObject = stream;

        await camera.play();

        console.log(
            "Cámara iniciada correctamente."
        );

        // Esperar a que la cámara tenga dimensiones.
        esperarVideo();

    }

    catch (error) {

        console.error(
            "Error iniciando la cámara:",
            error
        );

    }

}


// ============================================================
// ESPERAR A QUE EL VIDEO DE CÁMARA ESTÉ LISTO
// ============================================================

function esperarVideo() {

    if (
        camera.videoWidth > 0 &&
        camera.videoHeight > 0
    ) {

        console.log(
            "Cámara lista:",
            camera.videoWidth,
            "x",
            camera.videoHeight
        );

        iniciarCicloReconocimiento();

        return;
    }

    setTimeout(
        esperarVideo,
        500
    );

}


// ============================================================
// CICLO DE RECONOCIMIENTO
// ============================================================

async function iniciarCicloReconocimiento() {

    while (stream) {

        if (
            !analizando &&
            !esperandoHablar
        ) {

            await analizarObjeto();

        }

        // No saturar el servidor.
        await esperar(4000);

    }

}


// ============================================================
// ANALIZAR OBJETO
// ============================================================

async function analizarObjeto() {

    if (analizando) {
        return;
    }

    if (esperandoHablar) {
        return;
    }

    if (
        !camera.videoWidth ||
        !camera.videoHeight
    ) {

        return;
    }

    analizando = true;

    try {

        // ====================================================
        // PREPARAR CANVAS
        // ====================================================

        const ancho =
            Math.min(
                camera.videoWidth,
                480
            );

        const escala =
            ancho /
            camera.videoWidth;

        const alto =
            Math.round(
                camera.videoHeight *
                escala
            );

        canvas.width = ancho;

        canvas.height = alto;

        const contexto =
            canvas.getContext("2d");

        contexto.drawImage(
            camera,
            0,
            0,
            ancho,
            alto
        );


        // ====================================================
        // CONVERTIR A JPEG
        // ====================================================

        const imagen =
            await new Promise(
                resolve => {

                    canvas.toBlob(
                        resolve,
                        "image/jpeg",
                        0.65
                    );

                }
            );


        if (!imagen) {

            console.error(
                "No se pudo crear la imagen."
            );

            return;
        }


        // ====================================================
        // FORM DATA
        // ====================================================

        const formData =
            new FormData();

        formData.append(
            "frame",
            imagen,
            "camera.jpg"
        );


        // ====================================================
        // ENVIAR AL SERVIDOR
        // ====================================================

        const respuesta =
            await fetch(
                "/detectar",
                {
                    method: "POST",
                    body: formData
                }
            );


        // ====================================================
        // COMPROBAR RESPUESTA
        // ====================================================

        if (!respuesta.ok) {

            const errorTexto =
                await respuesta.text();

            console.error(
                "Error /detectar:",
                respuesta.status,
                errorTexto
            );

            return;
        }


        const resultado =
            await respuesta.json();


        console.log(
            "Detección:",
            resultado
        );


        // ====================================================
        // COMPROBAR RESULTADO
        // ====================================================

        if (!resultado.success) {

            console.error(
                "Error del servidor:",
                resultado.error
            );

            return;
        }


        if (!resultado.detected) {

            return;
        }


        const objeto =
            resultado.object;

        const texto =
            resultado.text;


        if (!objeto || !texto) {

            return;
        }


        // ====================================================
        // EVITAR REPETICIONES
        // ====================================================

        const ahora =
            Date.now();

        const mismoObjeto =
            objeto === ultimoObjeto;

        const hanPasadoDiezSegundos =
            ahora - ultimoTiempo >
            10000;


        if (
            mismoObjeto &&
            !hanPasadoDiezSegundos
        ) {

            console.log(
                "Objeto repetido:",
                objeto
            );

            return;
        }


        ultimoObjeto =
            objeto;

        ultimoTiempo =
            ahora;


        // ====================================================
        // PROGRAMAR HABLA
        // ====================================================

        programarHabla(
            objeto,
            texto
        );

    }

    catch (error) {

        console.error(
            "Error analizando la cámara:",
            error
        );

    }

    finally {

        analizando = false;

    }

}


// ============================================================
// ESPERAR 5 SEGUNDOS
// ============================================================

function programarHabla(
    objeto,
    texto
) {

    if (esperandoHablar) {
        return;
    }

    esperandoHablar = true;

    objetoPendiente =
        objeto;


    console.log(
        "Objeto detectado:",
        objeto
    );

    console.log(
        "Esperando 5 segundos..."
    );


    // ========================================================
    // OPCIONAL: MOSTRAR OBJETO EN PANTALLA
    // ========================================================

    mostrarObjeto(
        objeto
    );


    setTimeout(
        () => {

            hablar(
                texto
            );

        },
        5000
    );

}


// ============================================================
// MOSTRAR OBJETO
// ============================================================

function mostrarObjeto(
    objeto
) {

    const elemento =
        document.getElementById(
            "objetoDetectado"
        );

    if (!elemento) {
        return;
    }

    elemento.textContent =
        objeto;

}


// ============================================================
// HABLAR
// ============================================================

function hablar(
    texto
) {

    if (
        !("speechSynthesis" in window)
    ) {

        console.error(
            "El navegador no soporta texto a voz."
        );

        volverAEspera();

        return;
    }


    // Cancelar cualquier voz anterior.
    window.speechSynthesis.cancel();


    // ========================================================
    // CAMBIAR VIDEO
    // ========================================================

    cambiarAVideoHablando();


    // ========================================================
    // CREAR MENSAJE
    // ========================================================

    const mensaje =
        new SpeechSynthesisUtterance(
            texto
        );


    mensaje.lang =
        "es-ES";

    mensaje.rate =
        0.95;

    mensaje.pitch =
        1;

    mensaje.volume =
        1;


    // ========================================================
    // BUSCAR VOZ EN ESPAÑOL
    // ========================================================

    const voces =
        window.speechSynthesis
            .getVoices();


    const vozEspanol =
        voces.find(
            voz =>
                voz.lang
                    .toLowerCase()
                    .startsWith("es")
        );


    if (vozEspanol) {

        mensaje.voice =
            vozEspanol;

    }


    // ========================================================
    // CUANDO COMIENZA A HABLAR
    // ========================================================

    mensaje.onstart =
        () => {

            console.log(
                "Robot hablando:",
                texto
            );

            cambiarAVideoHablando();

        };


    // ========================================================
    // CUANDO TERMINA
    // ========================================================

    mensaje.onend =
        () => {

            console.log(
                "Robot terminó de hablar."
            );

            volverAEspera();

        };


    // ========================================================
    // ERROR
    // ========================================================

    mensaje.onerror =
        error => {

            console.error(
                "Error TTS:",
                error
            );

            volverAEspera();

        };


    // ========================================================
    // HABLAR
    // ========================================================

    window.speechSynthesis.speak(
        mensaje
    );

}


// ============================================================
// VIDEO HABLANDO
// ============================================================

function cambiarAVideoHablando() {

    if (!robotVideo) {
        return;
    }


    robotVideo.pause();


    robotVideo.src =
        "/videos/hablando.mp4";


    robotVideo.loop =
        true;


    robotVideo.muted =
        true;


    robotVideo.load();


    const promesa =
        robotVideo.play();


    if (promesa) {

        promesa.catch(
            error => {

                console.warn(
                    "No se pudo reproducir hablando.mp4:",
                    error
                );

            }
        );

    }

}


// ============================================================
// VIDEO ESPERA
// ============================================================

function volverAEspera() {

    if (robotVideo) {

        robotVideo.pause();


        robotVideo.src =
            "/videos/espera.mp4";


        robotVideo.loop =
            true;


        robotVideo.muted =
            true;


        robotVideo.load();


        const promesa =
            robotVideo.play();


        if (promesa) {

            promesa.catch(
                error => {

                    console.warn(
                        "No se pudo reproducir espera.mp4:",
                        error
                    );

                }
            );

        }

    }


    esperandoHablar =
        false;

    objetoPendiente =
        null;


    console.log(
        "Robot volvió a espera."
    );

}


// ============================================================
// FUNCIÓN ESPERA
// ============================================================

function esperar(
    milisegundos
) {

    return new Promise(
        resolve =>
            setTimeout(
                resolve,
                milisegundos
            )
    );

}


// ============================================================
// DETENER CÁMARA
// ============================================================

function detenerCamara() {

    if (!stream) {
        return;
    }


    stream
        .getTracks()
        .forEach(
            track =>
                track.stop()
        );


    stream =
        null;

}


// ============================================================
// PANTALLA COMPLETA
// ============================================================

async function pantallaCompleta() {

    try {

        const elemento =
            document.documentElement;


        if (
            !document.fullscreenElement
        ) {

            await elemento.requestFullscreen();

        }

        else {

            await document.exitFullscreen();

        }

    }

    catch (error) {

        console.error(
            "No se pudo activar pantalla completa:",
            error
        );

    }

}
