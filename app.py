import os
import time
import threading

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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

# Modelo YOLO.
# Se carga una sola vez y después se reutiliza.
modelo = None
lock_modelo = threading.Lock()


# ============================================================
# CARGAR MODELO YOLO
# ============================================================

def obtener_modelo():
    global modelo

    # Si ya está cargado, reutilizarlo.
    if modelo is not None:
        return modelo

    with lock_modelo:
        if modelo is not None:
            return modelo

        ruta_modelo = os.path.join(BASE_DIR, "yolo11n.pt")

        if not os.path.isfile(ruta_modelo):
            raise FileNotFoundError(
                f"No se encontró el modelo YOLO en: {ruta_modelo}"
            )

        app.logger.info("Cargando modelo YOLO desde: %s", ruta_modelo)
        try:
            from ultralytics import YOLO

            modelo = YOLO(ruta_modelo)
            app.logger.info("Modelo YOLO cargado correctamente.")
            return modelo
        except Exception:
            app.logger.exception("Error cargando el modelo YOLO.")
            raise


# ============================================================
# PÁGINA PRINCIPAL
# ============================================================

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "ok",
        "modelo_cargado": modelo is not None
    })


@app.route("/favicon.ico")
def favicon():
    return "", 204


# ============================================================
# VIDEOS DEL ROBOT
# ============================================================

@app.route("/videos/<path:filename>")
def videos(filename):

    # Los videos deben estar junto a app.py:
    #
    # app.py
    # espera.mp4
    # hablando.mp4

    return send_from_directory(
        BASE_DIR,
        filename
    )


# ============================================================
# DETECCIÓN DE OBJETOS
# ============================================================

@app.route("/detectar", methods=["POST"])
def detectar():

    tiempo_inicio = time.time()

    try:

        app.logger.info(
            "Solicitud POST /detectar recibida."
        )

        # ====================================================
        # 1. COMPROBAR QUE LLEGÓ EL FRAME
        # ====================================================

        if "frame" not in request.files:

            app.logger.warning(
                "La solicitud no contiene 'frame'."
            )

            return jsonify({
                "success": False,
                "detected": False,
                "error": "No se recibió ningún frame."
            }), 400

        archivo = request.files["frame"]

        # ====================================================
        # 2. LEER LOS DATOS DE LA IMAGEN
        # ====================================================

        datos = archivo.read()

        if not datos:

            app.logger.warning(
                "El frame recibido está vacío."
            )

            return jsonify({
                "success": False,
                "detected": False,
                "error": "El frame está vacío."
            }), 400

        # ====================================================
        # 3. CONVERTIR JPEG A IMAGEN OPENCV
        # ====================================================

        imagen_np = np.frombuffer(
            datos,
            dtype=np.uint8
        )

        frame = cv2.imdecode(
            imagen_np,
            cv2.IMREAD_COLOR
        )

        if frame is None:

            app.logger.warning(
                "OpenCV no pudo decodificar el frame."
            )

            return jsonify({
                "success": False,
                "detected": False,
                "error": "No se pudo decodificar la imagen."
            }), 400

        # ====================================================
        # 4. REDUCIR EL TAMAÑO DE LA IMAGEN
        # ====================================================

        alto, ancho = frame.shape[:2]

        max_dimension = 480

        if max(alto, ancho) > max_dimension:

            escala = (
                max_dimension /
                max(alto, ancho)
            )

            nuevo_ancho = max(
                1,
                int(ancho * escala)
            )

            nuevo_alto = max(
                1,
                int(alto * escala)
            )

            frame = cv2.resize(
                frame,
                (
                    nuevo_ancho,
                    nuevo_alto
                ),
                interpolation=cv2.INTER_AREA
            )

        # ====================================================
        # 5. OBTENER MODELO
        # ====================================================

        modelo_local = obtener_modelo()

        # ====================================================
        # 6. EJECUTAR YOLO
        # ====================================================

        resultados = modelo_local.predict(

            source=frame,

            # Imagen de entrada pequeña para reducir consumo.
            imgsz=192,

            # Confianza mínima.
            conf=0.45,

            # Evitar trabajo innecesario en el servidor gratuito.
            max_det=10,

            # Render utiliza CPU.
            device="cpu",

            # No imprimir información innecesaria.
            verbose=False
        )

        # ====================================================
        # 7. VARIABLES PARA LA MEJOR DETECCIÓN
        # ====================================================

        mejor_objeto = None
        mejor_confianza = 0.0

        # ====================================================
        # 8. PROCESAR RESULTADOS
        # ====================================================

        if resultados:

            resultado = resultados[0]

            if resultado.boxes is not None:

                for caja in resultado.boxes:

                    try:

                        confianza = float(
                            caja.conf[0]
                        )

                        clase = int(
                            caja.cls[0]
                        )

                    except Exception:

                        continue

                    # Solo conservar la detección
                    # con mayor confianza.
                    if confianza > mejor_confianza:

                        nombre = modelo_local.names.get(
                            clase,
                            str(clase)
                        )

                        mejor_objeto = nombre

                        mejor_confianza = confianza

        # ====================================================
        # 9. TRADUCIR OBJETOS AL ESPAÑOL
        # ====================================================

        traducciones = {

            "person": "persona",

            "bicycle": "bicicleta",
            "car": "carro",
            "motorcycle": "motocicleta",
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
            "sports ball": "balón",
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
            "hair drier": "secador de cabello",
            "toothbrush": "cepillo de dientes"
        }

        if mejor_objeto:

            mejor_objeto = traducciones.get(
                mejor_objeto.lower(),
                mejor_objeto
            )

        # ====================================================
        # 10. SI NO SE DETECTÓ NINGÚN OBJETO
        # ====================================================

        if mejor_objeto is None:

            tiempo_procesamiento = round(
                time.time() - tiempo_inicio,
                3
            )

            return jsonify({

                "success": True,

                "detected": False,

                "object": None,

                "confidence": 0,

                "text": "",

                "processing_time": tiempo_procesamiento
            })

        # ====================================================
        # 11. CREAR TEXTO PARA TTS
        # ====================================================

        # Casos especiales para que la frase suene natural.
        if mejor_objeto == "persona":

            texto = "He detectado una persona."

        elif mejor_objeto in [
            "bicicleta",
            "motocicleta",
            "botella",
            "mochila",
            "silla",
            "mesa",
            "computador",
            "planta",
            "manzana",
            "naranja",
            "taza"
        ]:

            texto = (
                f"He detectado una "
                f"{mejor_objeto}."
            )

        else:

            texto = (
                f"He detectado un "
                f"{mejor_objeto}."
            )

        # ====================================================
        # 12. TIEMPO DE PROCESAMIENTO
        # ====================================================

        tiempo_procesamiento = round(
            time.time() - tiempo_inicio,
            3
        )

        # ====================================================
        # 13. REGISTRAR DETECCIÓN
        # ====================================================

        app.logger.info(

            "Objeto detectado: %s | "
            "confianza: %.3f | "
            "tiempo: %.3fs",

            mejor_objeto,

            mejor_confianza,

            tiempo_procesamiento
        )

        # ====================================================
        # 14. RESPUESTA JSON
        # ====================================================

        return jsonify({

            "success": True,

            "detected": True,

            "object": mejor_objeto,

            "confidence": round(
                mejor_confianza,
                3
            ),

            "text": texto,

            "processing_time":
                tiempo_procesamiento
        })

    # ========================================================
    # ERROR GENERAL
    # ========================================================

    except Exception as error:

        app.logger.exception(
            "ERROR INTERNO EN /detectar"
        )

        return jsonify({

            "success": False,

            "detected": False,

            "error":
                "Ocurrió un error procesando la imagen.",

            "detail":
                str(error)

        }), 500


# ============================================================
# MANEJADOR DE ERRORES 404
# ============================================================

@app.errorhandler(404)
def pagina_no_encontrada(error):

    return jsonify({

        "success": False,

        "error": "Ruta no encontrada."

    }), 404


# ============================================================
# MANEJADOR DE ERRORES 500
# ============================================================

@app.errorhandler(500)
def error_interno(error):

    app.logger.exception(
        "Error interno de Flask."
    )

    return jsonify({

        "success": False,

        "error": "Error interno del servidor."

    }), 500


# ============================================================
# INICIO LOCAL
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