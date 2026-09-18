// ============================================================
// RECONOCIMIENTO DE OBJETOS - MR.MIND
// ============================================================

const camera = document.getElementById("camera");
const canvas = document.getElementById("canvas");
const robotVideo = document.getElementById("robotVideo");

const estado = document.getElementById("estado");
const objetoDetectado =
    document.getElementById("objetoDetectado");

let stream = null;

let analizando = false;

let esperandoHablar = false;

let ultimoObjeto = null;

let ultimoTiempo = 0;


// ============================================================
// INICIAR
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    () => {

        iniciarCamara();

        cargarVoces();

        if ("speechSynthesis" in window) {

            window.speechSynthesis.onvoiceschanged =
                cargarVoces;
        }
    }
);


// ============================================================
// VOCES
// ============================================================

function cargarVoces() {

    if (!("speechSynthesis" in window)) {
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

        if (!navigator.mediaDevices ||
            !navigator.mediaDevices.getUserMedia) {

            throw new Error(
                "Este navegador no permite acceder a la cámara."
            );
        }

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


        actualizarEstado(
            "Cámara activa. Observando..."
        );


        esperarVideo();


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


// ============================================================
// ESPERAR A QUE LA CÁMARA TENGA IMAGEN
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


        await esperar(3000);
    }
}


// ============================================================
// ANALIZAR OBJETO
// ============================================================

async function analizarObjeto() {

    if (
        analizando ||
        esperandoHablar
    ) {
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

        actualizarEstado(
            "Analizando..."
        );


        // ----------------------------------------------------
        // TAMAÑO
        // ----------------------------------------------------

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


        // ----------------------------------------------------
        // DIBUJAR CÁMARA
        // ----------------------------------------------------

        const contexto =
            canvas.getContext("2d");


        contexto.drawImage(

            camera,

            0,
            0,

            ancho,
            alto
        );


        // ----------------------------------------------------
        // CREAR JPEG
        // ----------------------------------------------------

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


        // ----------------------------------------------------
        // FORM DATA
        // ----------------------------------------------------

        const formData =
            new FormData();


        formData.append(

            "frame",

            imagen,

            "camera.jpg"
        );


        // ----------------------------------------------------
        // ENVIAR AL SERVIDOR
        // ----------------------------------------------------

        const respuesta =
            await fetch(

                "/detectar",

                {

                    method: "POST",

                    body: formData
                }
            );


        // ----------------------------------------------------
        // ERROR HTTP
        // ----------------------------------------------------

        if (!respuesta.ok) {

            const errorTexto =
                await respuesta.text();


            console.error(

                "Error /detectar:",

                respuesta.status,

                errorTexto
            );


            actualizarEstado(
                "Error de detección."
            );


            return;
        }


        // ----------------------------------------------------
        // JSON
        // ----------------------------------------------------

        const resultado =
            await respuesta.json();


        console.log(
            "Resultado:",
            resultado
        );


        if (!resultado.success) {

            console.error(
                resultado.error
            );

            actualizarEstado(
                "Error procesando imagen."
            );

            return;
        }


        // ----------------------------------------------------
        // SIN DETECCIÓN
        // ----------------------------------------------------

        if (!resultado.detected) {

            actualizarEstado(
                "Observando..."
            );

            return;
        }


        // ----------------------------------------------------
        // OBJETO
        // ----------------------------------------------------

        const objeto =
            resultado.object;


        const texto =
            resultado.text;


        if (
            !objeto ||
            !texto
        ) {
            return;
        }


        // ----------------------------------------------------
        // EVITAR REPETICIONES
        // ----------------------------------------------------

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


        // ----------------------------------------------------
        // PROGRAMAR HABLA
        // ----------------------------------------------------

        programarHabla(

            objeto,

            texto
        );


    } catch (error) {

        console.error(

            "Error analizando cámara:",

            error
        );


        actualizarEstado(
            "Error de conexión."
        );


    } finally {

        analizando = false;
    }
}


// ============================================================
// PROGRAMAR HABLA
// ============================================================

function programarHabla(
    objeto,
    texto
) {

    if (esperandoHablar) {
        return;
    }


    esperandoHablar = true;


    mostrarObjeto(
        objeto
    );


    actualizarEstado(
        "Objeto detectado. Preparando respuesta..."
    );


    console.log(
        "Objeto detectado:",
        objeto
    );


    console.log(
        "Esperando 5 segundos..."
    );


    // --------------------------------------------------------
    // ESPERAR 5 SEGUNDOS
    // --------------------------------------------------------

    setTimeout(
        () => {

            hablar(texto);

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

    if (!objetoDetectado) {
        return;
    }


    objetoDetectado.textContent =
        objeto;
}


// ============================================================
// HABLAR
// ============================================================

function hablar(texto) {

    if (
        !("speechSynthesis" in window)
    ) {

        console.error(
            "El navegador no soporta texto a voz."
        );


        volverAEspera();

        return;
    }


    window.speechSynthesis.cancel();


    // --------------------------------------------------------
    // CAMBIAR VIDEO
    // --------------------------------------------------------

    cambiarAVideoHablando();


    actualizarEstado(
        "Hablando..."
    );


    // --------------------------------------------------------
    // CREAR VOZ
    // --------------------------------------------------------

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


    // --------------------------------------------------------
    // BUSCAR VOZ ESPAÑOLA
    // --------------------------------------------------------

    const voces =
        window.speechSynthesis.getVoices();


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


    // --------------------------------------------------------
    // INICIO
    // --------------------------------------------------------

    mensaje.onstart =
        () => {

            console.log(
                "Robot hablando:",
                texto
            );

            actualizarEstado(
                "Hablando..."
            );
        };


    // --------------------------------------------------------
    // FINAL
    // --------------------------------------------------------

    mensaje.onend =
        () => {

            console.log(
                "Robot terminó de hablar."
            );


            volverAEspera();
        };


    // --------------------------------------------------------
    // ERROR
    // --------------------------------------------------------

    mensaje.onerror =
        error => {

            console.error(
                "Error TTS:",
                error
            );


            volverAEspera();
        };


    // --------------------------------------------------------
    // HABLAR
    // --------------------------------------------------------

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
// VOLVER A ESPERA
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


    actualizarEstado(
        "Observando..."
    );


    console.log(
        "Robot volvió a espera."
    );
}


// ============================================================
// ESTADO
// ============================================================

function actualizarEstado(
    texto
) {

    if (!estado) {
        return;
    }


    estado.textContent =
        texto;
}


// ============================================================
// ESPERAR
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
            track => track.stop()
        );


    stream = null;
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

        } else {

            await document.exitFullscreen();
        }


    } catch (error) {

        console.error(
            "No se pudo activar pantalla completa:",
            error
        );
    }
}
