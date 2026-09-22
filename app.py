import os
import threading
import time

import cv2
import numpy as np
from flask import Flask, jsonify, request, send_from_directory
from ultralytics import YOLO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "yolo11n.pt")

app = Flask(__name__)

modelo = None
modelo_cargando = False
error_modelo = None
modelo_listo = threading.Event()
lock_modelo = threading.Lock()
inicio_carga_modelo = None

TRADUCCIONES = {
    "person": "persona",
    "bicycle": "bicicleta",
    "car": "automóvil",
    "motorcycle": "motocicleta",
    "bus": "autobús",
    "train": "tren",
    "truck": "camión",
    "boat": "barco",
    "bird": "pájaro",
    "cat": "gato",
    "dog": "perro",
    "horse": "caballo",
    "backpack": "mochila",
    "umbrella": "paraguas",
    "handbag": "bolso",
    "tie": "corbata",
    "suitcase": "maleta",
    "bottle": "botella",
    "cup": "taza",
    "fork": "tenedor",
    "knife": "cuchillo",
    "spoon": "cuchara",
    "bowl": "tazón",
    "banana": "banano",
    "apple": "manzana",
    "orange": "naranja",
    "pizza": "pizza",
    "cake": "pastel",
    "chair": "silla",
    "couch": "sofá",
    "potted plant": "planta",
    "bed": "cama",
    "dining table": "mesa",
    "tv": "televisor",
    "laptop": "computador",
    "mouse": "ratón",
    "remote": "control remoto",
    "keyboard": "teclado",
    "cell phone": "teléfono",
    "book": "libro",
    "clock": "reloj",
    "vase": "florero",
    "scissors": "tijeras",
}


def obtener_modelo():
    global modelo, modelo_cargando, error_modelo, inicio_carga_modelo

    if modelo is not None:
        return modelo

    with lock_modelo:
        if modelo is not None:
            return modelo

        if not os.path.isfile(MODEL_PATH):
            raise FileNotFoundError(f"No se encontró el modelo YOLO en {MODEL_PATH}")

        inicio_carga_modelo = time.time()
        modelo_cargando = True
        modelo_listo.clear()
        app.logger.info("Cargando modelo desde %s", MODEL_PATH)

        try:
            modelo = YOLO(MODEL_PATH)
            error_modelo = None
            app.logger.info("Modelo YOLO cargado correctamente")
            return modelo
        except Exception as error:
            error_modelo = str(error)
            app.logger.exception("Error cargando YOLO")
            raise
        finally:
            modelo_cargando = False
            modelo_listo.set()


def precargar_modelo():
    try:
        obtener_modelo()
    except Exception:
        app.logger.exception("La precarga del modelo falló")


threading.Thread(target=precargar_modelo, daemon=True).start()


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/health")
def health():
    if modelo is not None:
        estado = "ok"
    elif modelo_cargando:
        estado = "cargando"
    elif error_modelo:
        estado = "error"
    else:
        estado = "inicializando"

    return jsonify({
        "status": estado,
        "modelo_cargado": modelo is not None,
        "modelo_cargando": modelo_cargando,
        "modelo_error": error_modelo,
        "segundos_cargando": round(time.time() - inicio_carga_modelo, 1) if inicio_carga_modelo else 0,
    })


@app.route("/videos/<path:filename>")
def videos(filename):
    return send_from_directory(BASE_DIR, filename)


@app.route("/favicon.ico")
def favicon():
    return "", 204


@app.route("/detectar", methods=["POST"])
def detectar():
    inicio = time.time()

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
            "error": "El frame está vacío."
        }), 400

    imagen_np = np.frombuffer(datos, dtype=np.uint8)
    frame = cv2.imdecode(imagen_np, cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify({
            "success": False,
            "detected": False,
            "error": "No se pudo decodificar la imagen."
        }), 400

    try:
        if modelo is None:
            if modelo_cargando:
                modelo_listo.wait(timeout=20)
            if modelo is None and modelo_cargando:
                return jsonify({
                    "success": False,
                    "detected": False,
                    "status": "cargando",
                    "error": "El modelo está iniciando. Reintentando en unos segundos."
                }), 503
            if error_modelo:
                return jsonify({
                    "success": False,
                    "detected": False,
                    "status": "error",
                    "error": "No se pudo cargar el modelo.",
                    "detail": error_modelo,
                }), 503
            modelo_local = obtener_modelo()
        else:
            modelo_local = modelo

        alto, ancho = frame.shape[:2]
        max_dimension = 480
        if max(alto, ancho) > max_dimension:
            escala = max_dimension / max(alto, ancho)
            nuevo_ancho = max(1, int(ancho * escala))
            nuevo_alto = max(1, int(alto * escala))
            frame = cv2.resize(frame, (nuevo_ancho, nuevo_alto), interpolation=cv2.INTER_AREA)

        resultados = modelo_local.predict(
            source=frame,
            imgsz=320,
            conf=0.45,
            max_det=10,
            device="cpu",
            verbose=False,
        )

        mejor_objeto = None
        mejor_confianza = 0.0

        if resultados:
            resultado = resultados[0]
            if resultado.boxes is not None:
                for caja in resultado.boxes:
                    try:
                        confianza = float(caja.conf[0])
                        clase = int(caja.cls[0])
                    except Exception:
                        continue

                    if confianza > mejor_confianza:
                        nombre = modelo_local.names.get(clase, str(clase))
                        mejor_objeto = nombre
                        mejor_confianza = confianza

        if mejor_objeto is None:
            return jsonify({
                "success": True,
                "detected": False,
                "object": None,
                "confidence": 0,
                "text": "",
                "processing_time": round(time.time() - inicio, 3)
            })

        nombre_espanol = TRADUCCIONES.get(mejor_objeto.lower(), mejor_objeto)
        if nombre_espanol in ["persona", "bicicleta", "motocicleta", "botella", "mochila", "silla", "mesa", "computador", "planta", "manzana", "naranja", "taza"]:
            texto = f"He detectado una {nombre_espanol}."
        else:
            texto = f"He detectado un {nombre_espanol}."

        return jsonify({
            "success": True,
            "detected": True,
            "object": nombre_espanol,
            "confidence": round(mejor_confianza, 3),
            "text": texto,
            "processing_time": round(time.time() - inicio, 3),
        })

    except Exception as error:
        app.logger.exception("ERROR interno en /detectar")
        return jsonify({
            "success": False,
            "detected": False,
            "error": "Ocurrió un error procesando la imagen.",
            "detail": str(error),
        }), 500


@app.errorhandler(404)
def pagina_no_encontrada(error):
    return jsonify({"success": False, "error": "Ruta no encontrada."}), 404


@app.errorhandler(500)
def error_interno(error):
    app.logger.exception("Error interno de Flask")
    return jsonify({"success": False, "error": "Error interno del servidor."}), 500


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=puerto, debug=False)
