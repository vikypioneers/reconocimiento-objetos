import base64
import binascii
import os

import cv2
import numpy as np
from flask import Flask, jsonify, render_template_string, request
from ultralytics import YOLO


app = Flask(__name__)
model = None

NOMBRES = {
    "person": "persona",
    "cell phone": "telefono celular",
    "laptop": "computadora portatil",
    "book": "libro",
    "bottle": "botella",
    "chair": "silla",
    "backpack": "mochila",
    "car": "automovil",
    "dog": "perro",
    "cat": "gato",
    "cup": "taza",
}

HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Detector inteligente</title>
  <style>
    :root { color-scheme: dark; font-family: system-ui, sans-serif; }
    body { margin: 0; min-height: 100vh; background: #101820; color: #f5f7fa; }
    main { width: min(920px, calc(100% - 32px)); margin: 0 auto; padding: 42px 0; }
    h1 { margin: 0 0 8px; font-size: clamp(2rem, 5vw, 3.5rem); }
    p { color: #b9c6d3; }
    .panel { margin-top: 28px; padding: 18px; background: #172532; border: 1px solid #294052; border-radius: 12px; }
    video { display: block; width: 100%; max-height: 540px; object-fit: contain; background: #071016; border-radius: 8px; }
    .actions { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 16px; }
    button { border: 0; border-radius: 7px; padding: 11px 16px; color: #071016; background: #62e6b5; font-weight: 700; cursor: pointer; }
    button.secondary { background: #b9c6d3; }
    #status { min-height: 24px; margin: 16px 0 0; color: #62e6b5; }
    #results { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
    .result { padding: 7px 10px; background: #294052; border-radius: 6px; }
  </style>
</head>
<body>
  <main>
    <h1>Detector inteligente</h1>
    <p>Activa la camara para reconocer objetos en tiempo real.</p>
    <section class="panel">
      <video id="camera" autoplay muted playsinline></video>
      <div class="actions">
        <button id="start">Activar camara</button>
        <button id="stop" class="secondary">Detener</button>
      </div>
      <div id="status">Camara desactivada.</div>
      <div id="results"></div>
    </section>
  </main>
  <script>
    const video = document.querySelector('#camera');
    const status = document.querySelector('#status');
    const results = document.querySelector('#results');
    let stream;
    let timer;

    async function detect() {
      if (!stream || video.readyState < 2) return;
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext('2d').drawImage(video, 0, 0);
      const response = await fetch('/detect', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({image: canvas.toDataURL('image/jpeg', 0.75)})
      });
      if (!response.ok) return;
      const data = await response.json();
      results.innerHTML = data.objects.length
        ? data.objects.map(object => `<span class="result">${object.name} (${object.confidence}%)</span>`).join('')
        : '<span class="result">No se detectaron objetos</span>';
    }

    document.querySelector('#start').onclick = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({video: true, audio: false});
        video.srcObject = stream;
        status.textContent = 'Camara activa. Analizando...';
        clearInterval(timer);
        timer = setInterval(detect, 1500);
      } catch (error) {
        status.textContent = 'No se pudo acceder a la camara: ' + error.message;
      }
    };

    document.querySelector('#stop').onclick = () => {
      clearInterval(timer);
      stream?.getTracks().forEach(track => track.stop());
      stream = undefined;
      video.srcObject = null;
      status.textContent = 'Camara desactivada.';
      results.innerHTML = '';
    };
  </script>
</body>
</html>
"""


def get_model():
    global model
    if model is None:
        model = YOLO("yolo11n.pt")
    return model


@app.get("/")
def index():
    return render_template_string(HTML)


@app.post("/detect")
def detect():
    payload = request.get_json(silent=True) or {}
    encoded_image = payload.get("image", "")
    if "," not in encoded_image:
        return jsonify({"error": "Imagen no valida"}), 400

    try:
        image_bytes = base64.b64decode(encoded_image.split(",", 1)[1])
        image_array = cv2.imdecode(
            np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        if image_array is None:
            raise ValueError("No se pudo leer la imagen")

        detector = get_model()
        predictions = detector(image_array, imgsz=320, conf=0.45, verbose=False)
        objects = []
        for result in predictions:
            for box in result.boxes:
                class_id = int(box.cls[0])
                english_name = detector.names[class_id]
                objects.append({
                    "name": NOMBRES.get(english_name, english_name),
                    "confidence": round(float(box.conf[0]) * 100),
                })
        return jsonify({"objects": objects})
    except (ValueError, TypeError, binascii.Error) as error:
        return jsonify({"error": str(error)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)