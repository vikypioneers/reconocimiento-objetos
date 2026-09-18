import os
import time

import cv2
import numpy as np

from flask import Flask, render_template, request, jsonify, send_from_directory
from ultralytics import YOLO


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

modelo = None


# ============================================================
# CARGAR MODELO SOLO CUANDO SEA NECESARIO
# ============================================================

def obtener_modelo():

    global modelo

    if modelo is not None:
        return modelo

    ruta_modelo = os.path.join(
        BASE_DIR,
        "yolo11n.pt"
    )

    if not os.path.exists(ruta_modelo):

        raise FileNotFoundError(
            f"No existe yolo11n.pt en {ruta_modelo}"
        )

    app.logger.info(
        "Cargando YOLO desde %s",
        ruta_modelo
    )

    modelo = YOLO(ruta_modelo)

    app.logger.info(
        "YOLO cargado correctamente"
    )

    return modelo


# ============================================================
# INICIO
# ============================================================

@app.route("/")
def inicio():

    return render_template("index.html")


# ============================================================
# HEALTH
# ============================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "ok",
        "modelo_cargado": modelo is not None
    })


# ============================================================
# VIDEOS
# ============================================================

@app.route("/videos/<path:nombre>")
def servir_video(nombre):

    ruta = os.path.join(
        BASE_DIR,
        nombre
    )

    if not os.path.isfile(ruta):

        return jsonify({
            "error": "Video no encontrado",
            "archivo": nombre
        }), 404

    return send_from_directory(
        BASE_DIR,
        nombre
    )


# ============================================================
# DETECTAR
# ============================================================

@app.route("/detectar", methods=["POST"])
def detectar():

    inicio = time.time()

    try:

        # ----------------------------------------------------
        # FRAME
        # ----------------------------------------------------

        if "frame" not in request.files:

            return jsonify({
                "success": False,
                "detected": False,
                "error": "No se recibió frame"
            }), 400

        archivo = request.files["frame"]

        datos = archivo.read()

        if not datos:

            return jsonify({
                "success": False,
                "detected": False,
                "error": "Frame vacío"
            }), 400

        # ----------------------------------------------------
        # CONVERTIR IMAGEN
        # ----------------------------------------------------

        array = np.frombuffer(
            datos,
            dtype=np.uint8
        )

        frame = cv2.imdecode(
            array,
            cv2.IMREAD_COLOR
        )

        if frame is None:

            return jsonify({
                "success": False,
                "detected": False,
                "error": "Imagen inválida"
            }), 400

        # ----------------------------------------------------
        # REDUCIR IMAGEN
        # ----------------------------------------------------

        alto, ancho = frame.shape[:2]

        limite = 480

        if max(alto, ancho) > limite:

            escala = limite / max(
                alto,
                ancho
            )

            nuevo_ancho = int(
                ancho * escala
            )

            nuevo_alto = int(
                alto * escala
            )

            frame = cv2.resize(
                frame,
                (
                    nuevo_ancho,
                    nuevo_alto
                ),
                interpolation=cv2.INTER_AREA
            )

        # ----------------------------------------------------
        # MODELO
        # ----------------------------------------------------

        modelo_local = obtener_modelo()

        # ----------------------------------------------------
        # YOLO
        # ----------------------------------------------------

        resultados = modelo_local.predict(

            source=frame,

            imgsz=192,

            conf=0.45,

            device="cpu",

            verbose=False
        )

        # ----------------------------------------------------
        # BUSCAR MEJOR DETECCIÓN
        # ----------------------------------------------------

        objeto = None

        confianza_maxima = 0.0

        if resultados:

            resultado = resultados[0]

            if resultado.boxes is not None:

                for caja in resultado.boxes:

                    confianza = float(
                        caja.conf[0]
                    )

                    if confianza > confianza_maxima:

                        clase = int(
                            caja.cls[0]
                        )

                        nombre = modelo_local.names.get(
                            clase,
                            str(clase)
                        )

                        objeto = nombre

                        confianza_maxima = confianza

        # ----------------------------------------------------
        # TRADUCCIONES
        # ----------------------------------------------------

        traducciones = {

            "person": "persona",
            "bicycle": "bicicleta",
            "car": "carro",
            "motorcycle": "motocicleta",
            "bus": "autobús",
            "train": "tren",
            "truck": "camión",
            "boat": "barco",

            "bird": "pájaro",
            "cat": "gato",
            "dog": "perro",
            "horse": "caballo",
            "sheep": "oveja",
            "cow": "vaca",

            "backpack": "mochila",
            "umbrella": "paraguas",
            "handbag": "bolso",
            "suitcase": "maleta",

            "bottle": "botella",
            "cup": "taza",
            "fork": "tenedor",
            "knife": "cuchillo",
            "spoon": "cuchara",

            "banana": "banano",
            "apple": "manzana",
            "orange": "naranja",
            "pizza": "pizza",
            "cake": "pastel",

            "chair": "silla",
            "couch": "sofá",
            "bed": "cama",
            "dining table": "mesa",

            "tv": "televisor",
            "laptop": "computador",
            "mouse": "ratón",
            "keyboard": "teclado",
            "cell phone": "teléfono",

            "book": "libro",
            "clock": "reloj"
        }

        if objeto:

            objeto =
                traducciones.get(
                    objeto.lower(),
                    objeto
                )

        # ----------------------------------------------------
        # SIN DETECCIÓN
        # ----------------------------------------------------

        if objeto is None:

            return jsonify({

                "success": True,

                "detected": False,

                "object": None,

                "confidence": 0,

                "text": "",

                "processing_time":
                    round(
                        time.time() - inicio,
                        3
                    )
            })

        # ----------------------------------------------------
        # TEXTO
        # ----------------------------------------------------

        objetos_femeninos = {
            "persona",
            "bicicleta",
            "motocicleta",
            "botella",
            "taza",
            "mochila",
            "maleta",
            "silla",
            "mesa",
            "manzana",
            "naranja"
        }

        articulo = (
            "una"
            if objeto in objetos_femeninos
            else "un"
        )

        texto = (
            f"He detectado {articulo} {objeto}."
        )

        # ----------------------------------------------------
        # RESPUESTA
        # ----------------------------------------------------

        tiempo = round(
            time.time() - inicio,
            3
        )

        app.logger.info(
            "Detectado %s | confianza %.2f | %.2fs",
            objeto,
            confianza_maxima,
            tiempo
        )

        return jsonify({

            "success": True,

            "detected": True,

            "object": objeto,

            "confidence":
                round(
                    confianza_maxima,
                    3
                ),

            "text": texto,

            "processing_time": tiempo
        })

    except Exception as error:

        app.logger.exception(
            "ERROR EN /detectar"
        )

        return jsonify({

            "success": False,

            "detected": False,

            "error":
                "Error procesando la detección",

            "detail":
                str(error)

        }), 500


# ============================================================
# ERRORES
# ============================================================

@app.errorhandler(404)
def error_404(error):

    return jsonify({
        "success": False,
        "error": "Ruta no encontrada"
    }), 404


@app.errorhandler(500)
def error_500(error):

    app.logger.exception(
        "ERROR 500 DE FLASK"
    )

    return jsonify({
        "success": False,
        "error": "Error interno del servidor"
    }), 500


# ============================================================
# EJECUCIÓN LOCAL
# ============================================================

if __name__ == "__main__":

    puerto = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=puerto,
        debug=False
    )
