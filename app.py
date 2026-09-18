import os
import time

import cv2
import numpy as np

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_from_directory
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

app = Flask(
    __name__,
    template_folder=BASE_DIR,
    static_folder=os.path.join(BASE_DIR, "static"),
    static_url_path="/static"
)

modelo = None


# ============================================================
# CARGAR YOLO SOLAMENTE CUANDO SE NECESITE
# ============================================================

def obtener_modelo():

    global modelo

    if modelo is not None:
        return modelo

    try:

        # Importación tardía.
        # Así la página principal puede abrir aunque YOLO
        # todavía no haya sido cargado.
        from ultralytics import YOLO

        ruta_modelo = os.path.join(
            BASE_DIR,
            "yolo11n.pt"
        )

        if not os.path.isfile(ruta_modelo):

            raise FileNotFoundError(
                f"No se encontró yolo11n.pt en: {ruta_modelo}"
            )

        app.logger.info(
            "Cargando modelo YOLO: %s",
            ruta_modelo
        )

        modelo = YOLO(ruta_modelo)

        app.logger.info(
            "Modelo YOLO cargado correctamente."
        )

        return modelo

    except Exception as error:

        app.logger.exception(
            "No se pudo cargar YOLO."
        )

        raise error


# ============================================================
# PÁGINA PRINCIPAL
# ============================================================

@app.route("/")
def inicio():

    ruta_index = os.path.join(
        BASE_DIR,
        "index.html"
    )

    if not os.path.isfile(ruta_index):

        return (
            "ERROR: No se encontró index.html en la raíz del proyecto.",
            500
        )

    return render_template("index.html")


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "ok",
        "modelo_cargado": modelo is not None
    })


# ============================================================
# SERVIR VIDEOS
# ============================================================

@app.route("/videos/<path:nombre>")
def servir_video(nombre):

    ruta_video = os.path.join(
        BASE_DIR,
        nombre
    )

    if not os.path.isfile(ruta_video):

        return jsonify({
            "success": False,
            "error": "Video no encontrado",
            "archivo": nombre
        }), 404

    return send_from_directory(
        BASE_DIR,
        nombre
    )


# ============================================================
# DETECCIÓN DE OBJETOS
# ============================================================

@app.route("/detectar", methods=["POST"])
def detectar():

    tiempo_inicio = time.time()

    try:

        # ----------------------------------------------------
        # COMPROBAR FRAME
        # ----------------------------------------------------

        if "frame" not in request.files:

            return jsonify({
                "success": False,
                "detected": False,
                "error": "No se recibió ningún frame."
            }), 400

        archivo = request.files["frame"]

        datos = archivo.read()

        if not datos:

            return jsonify({
                "success": False,
                "detected": False,
                "error": "El frame recibido está vacío."
            }), 400

        # ----------------------------------------------------
        # CONVERTIR FRAME
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
                "error": "No se pudo interpretar la imagen."
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
        # OBTENER MODELO
        # ----------------------------------------------------

        modelo_local = obtener_modelo()

        # ----------------------------------------------------
        # REALIZAR DETECCIÓN
        # ----------------------------------------------------

        resultados = modelo_local.predict(

            source=frame,

            imgsz=192,

            conf=0.45,

            device="cpu",

            verbose=False
        )

        # ----------------------------------------------------
        # BUSCAR OBJETO CON MAYOR CONFIANZA
        # ----------------------------------------------------

        objeto_original = None

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

                        nombres = modelo_local.names

                        if isinstance(
                            nombres,
                            dict
                        ):

                            nombre = nombres.get(
                                clase,
                                str(clase)
                            )

                        else:

                            nombre = nombres[clase]

                        objeto_original = nombre

                        confianza_maxima = confianza

        # ----------------------------------------------------
        # TRADUCCIONES AL ESPAÑOL
        # ----------------------------------------------------

        traducciones = {

            "person": "persona",

            "bicycle": "bicicleta",

            "car": "carro",

            "motorcycle": "motocicleta",

            "airplane": "avión",

            "bus": "autobús",

            "train": "tren",

            "truck": "camión",

            "boat": "barco",

            "traffic light": "semáforo",

            "fire hydrant": "hidrante",

            "stop sign": "señal de pare",

            "parking meter": "parquímetro",

            "bench": "banca",

            "bird": "pájaro",

            "cat": "gato",

            "dog": "perro",

            "horse": "caballo",

            "sheep": "oveja",

            "cow": "vaca",

            "elephant": "elefante",

            "bear": "oso",

            "zebra": "cebra",

            "giraffe": "jirafa",

            "backpack": "mochila",

            "umbrella": "paraguas",

            "handbag": "bolso",

            "tie": "corbata",

            "suitcase": "maleta",

            "frisbee": "frisbee",

            "skis": "esquís",

            "snowboard": "tabla de snowboard",

            "sports ball": "pelota",

            "kite": "cometa",

            "baseball bat": "bate de béisbol",

            "baseball glove": "guante de béisbol",

            "skateboard": "patineta",

            "surfboard": "tabla de surf",

            "tennis racket": "raqueta de tenis",

            "bottle": "botella",

            "wine glass": "copa",

            "cup": "taza",

            "fork": "tenedor",

            "knife": "cuchillo",

            "spoon": "cuchara",

            "bowl": "tazón",

            "banana": "banano",

            "apple": "manzana",

            "sandwich": "sándwich",

            "orange": "naranja",

            "broccoli": "brócoli",

            "carrot": "zanahoria",

            "hot dog": "perro caliente",

            "pizza": "pizza",

            "donut": "dona",

            "cake": "pastel",

            "chair": "silla",

            "couch": "sofá",

            "potted plant": "planta",

            "bed": "cama",

            "dining table": "mesa",

            "toilet": "inodoro",

            "tv": "televisor",

            "laptop": "computador",

            "mouse": "ratón",

            "remote": "control remoto",

            "keyboard": "teclado",

            "cell phone": "teléfono",

            "microwave": "microondas",

            "oven": "horno",

            "toaster": "tostadora",

            "sink": "lavamanos",

            "refrigerator": "nevera",

            "book": "libro",

            "clock": "reloj",

            "vase": "florero",

            "scissors": "tijeras",

            "teddy bear": "oso de peluche",

            "hair drier": "secador",

            "toothbrush": "cepillo de dientes"
        }

        # ----------------------------------------------------
        # TRADUCIR
        # ----------------------------------------------------

        objeto = None

        if objeto_original:

            objeto = traducciones.get(
                objeto_original.lower(),
                objeto_original
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
                        time.time() - tiempo_inicio,
                        3
                    )
            })

        # ----------------------------------------------------
        # ARTÍCULOS
        # ----------------------------------------------------

        objetos_femeninos = {

            "persona",
            "bicicleta",
            "motocicleta",
            "avión",
            "señal de pare",
            "banca",
            "mochila",
            "maleta",
            "botella",
            "copa",
            "taza",
            "cuchara",
            "manzana",
            "naranja",
            "zanahoria",
            "pizza",
            "silla",
            "mesa",
            "planta",
            "cama",
            "nevera",
            "raqueta de tenis",
            "pelota"
        }

        articulo = (
            "una"
            if objeto in objetos_femeninos
            else "un"
        )

        # ----------------------------------------------------
        # FRASE
        # ----------------------------------------------------

        texto = (
            f"He detectado {articulo} {objeto}."
        )

        # ----------------------------------------------------
        # TIEMPO
        # ----------------------------------------------------

        tiempo_procesamiento = round(
            time.time() - tiempo_inicio,
            3
        )

        app.logger.info(
            "Objeto detectado: %s | confianza: %.2f | tiempo: %.2fs",
            objeto,
            confianza_maxima,
            tiempo_procesamiento
        )

        # ----------------------------------------------------
        # RESPUESTA
        # ----------------------------------------------------

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

            "processing_time":
                tiempo_procesamiento
        })

    except Exception as error:

        app.logger.exception(
            "ERROR EN /detectar"
        )

        return jsonify({

            "success": False,

            "detected": False,

            "error": "Error procesando la detección.",

            "detail": str(error)

        }), 500


# ============================================================
# ERROR 404
# ============================================================

@app.errorhandler(404)
def error_404(error):

    return jsonify({

        "success": False,

        "error": "Ruta no encontrada."

    }), 404


# ============================================================
# ERROR 500
# ============================================================

@app.errorhandler(500)
def error_500(error):

    app.logger.exception(
        "ERROR 500 DE FLASK"
    )

    return jsonify({

        "success": False,

        "error": "Error interno del servidor."

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
