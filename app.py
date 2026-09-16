import os
import cv2
import random
import threading
import time
import numpy as np
from flask import Flask, jsonify, request, send_file, render_template_string
from ultralytics import YOLO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

HTML_PAGE = '''
<!doctype html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Detector Automático</title>
  <style>
    :root {
      --fondo: #04151d;
      --color: #e8fff7;
    }

    * {
      box-sizing: border-box;
      -webkit-font-smoothing: antialiased;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--fondo);
      color: var(--color);
      font-family: Arial, Helvetica, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }

    #robot-video {
      position: fixed;
      inset: 0;
      width: 100vw;
      height: 100vh;
      object-fit: cover;
      background: var(--fondo);
      display: block;
      outline: none;
      border: none;
      z-index: 1;
    }

    #camara {
      display: none;
      position: fixed;
      left: -9999px;
      top: -9999px;
    }

    #captura {
      display: none;
    }
  </style>
</head>
<body>
  <video id="robot-video" autoplay muted loop playsinline></video>
  <video id="camara" autoplay muted playsinline></video>
  <canvas id="captura"></canvas>

  <script>
    const camara = document.getElementById('camara');
    const captura = document.getElementById('captura');
    const videoRobot = document.getElementById('robot-video');

    const VIDEO_ESPERA = '/videos/espera.mp4';
    const VIDEO_HABLANDO = '/videos/hablando.mp4';

    let flujoCamara = null;
    let analisisEnCurso = false;
    let ultimoTexto = '';
    let intervaloCaptura = null;

    function cambiarVideoRobot(hablando) {
      const videoNuevo = hablando ? VIDEO_HABLANDO : VIDEO_ESPERA;
      if (!videoRobot.src || !videoRobot.src.endsWith(videoNuevo)) {
        videoRobot.src = videoNuevo;
        videoRobot.load();
      }
      videoRobot.play().catch(() => {});
    }

    function hablar(texto) {
      if (!texto || texto === ultimoTexto || !(window.speechSynthesis)) return;

      ultimoTexto = texto;
      window.speechSynthesis.cancel();

      const voz = new SpeechSynthesisUtterance(texto);
      voz.lang = 'es-ES';
      voz.rate = 0.95;
      voz.volume = 1.0;
      voz.onstart = () => cambiarVideoRobot(true);
      voz.onend = () => {
        cambiarVideoRobot(false);
        ultimoTexto = '';
      };
      voz.onerror = () => {
        cambiarVideoRobot(false);
        ultimoTexto = '';
      };

      window.speechSynthesis.speak(voz);
    }

    async function analizarCamara() {
      if (!flujoCamara || analisisEnCurso || camara.readyState < 2) return;

      analisisEnCurso = true;
      const ancho = camara.videoWidth || 640;
      const alto = camara.videoHeight || 480;
      captura.width = ancho;
      captura.height = alto;

      const ctx = captura.getContext('2d');
      ctx.drawImage(camara, 0, 0, ancho, alto);

      try {
        const blob = await new Promise((resolve, reject) => {
          captura.toBlob((imagen) => {
            if (imagen) resolve(imagen);
            else reject(new Error('La captura de la cámara no es válida'));
          }, 'image/jpeg', 0.82);
        });

        const datos = new FormData();
        datos.append('frame', blob, 'frame.jpg');

        const respuesta = await fetch('/detectar', {
          method: 'POST',
          body: datos,
          cache: 'no-store'
        });

        if (!respuesta.ok) {
          throw new Error('No fue posible analizar la imagen');
        }

        const resultado = await respuesta.json();
        if (resultado.success && resultado.text) {
          hablar(resultado.text);
        }
      } catch (error) {
        console.error('Error analizando la cámara:', error);
      } finally {
        analisisEnCurso = false;
      }
    }

    async function iniciarPrograma() {
      cambiarVideoRobot(false);

      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        console.error('La cámara no es accesible en este navegador.');
        return;
      }

      try {
        flujoCamara = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: 'environment' },
            width: { ideal: 1280 },
            height: { ideal: 720 }
          },
          audio: false
        });

        camara.srcObject = flujoCamara;
        await camara.play();

        intervaloCaptura = window.setInterval(analizarCamara, 1600);
      } catch (error) {
        console.error('No se pudo acceder a la cámara:', error);
      }
    }

    iniciarPrograma();

    window.addEventListener('pagehide', () => {
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      if (intervaloCaptura) clearInterval(intervaloCaptura);
      if (flujoCamara) {
        flujoCamara.getTracks().forEach((track) => track.stop());
      }
    });
  </script>
</body>
</html>
'''

# =====================================================================
# 0. GENERADOR AUTOMÁTICO DE VIDEOS DE PRUEBA
# =====================================================================
def crear_videos_de_prueba():
    ancho, alto, fps = 640, 480, 30
    cuatrocc = cv2.VideoWriter_fourcc(*'mp4v')
    
    espera_path = os.path.join(BASE_DIR, "espera.mp4")
    hablando_path = os.path.join(BASE_DIR, "hablando.mp4")

    if not os.path.exists(espera_path):
        out = cv2.VideoWriter(espera_path, cuatrocc, fps, (ancho, alto))
        for i in range(90):
            frame = np.zeros((alto, ancho, 3), dtype=np.uint8)
            cv2.circle(frame, (320, 240), 120, (0, 255, 0), 3)
            alto_ojo = 5 if (60 < i < 70) else 25 
            cv2.ellipse(frame, (270, 200), (20, alto_ojo), 0, 0, 360, (0, 255, 0), -1)
            cv2.ellipse(frame, (370, 200), (20, alto_ojo), 0, 0, 360, (0, 255, 0), -1)
            cv2.line(frame, (290, 300), (350, 300), (0, 255, 0), 5)
            out.write(frame)
        out.release()

    if not os.path.exists(hablando_path):
        out = cv2.VideoWriter(hablando_path, cuatrocc, fps, (ancho, alto))
        for i in range(60):
            frame = np.zeros((alto, ancho, 3), dtype=np.uint8)
            cv2.circle(frame, (320, 240), 120, (0, 0, 255), 3)
            cv2.ellipse(frame, (270, 200), (20, 25), 0, 0, 360, (0, 0, 255), -1)
            cv2.ellipse(frame, (370, 200), (20, 25), 0, 0, 360, (0, 0, 255), -1)
            radio_boca = int(15 + 15 * np.sin(i * 0.5))
            cv2.circle(frame, (320, 300), radio_boca, (0, 0, 255), -1)
            out.write(frame)
        out.release()

crear_videos_de_prueba()

# =====================================================================
# 1. ESTADO DEL DETECTOR
# =====================================================================
modelo = None
primera_deteccion_global = True
lock_deteccion = threading.Lock()
estado_ia = "espera"
objetos_registrados = {}

# =====================================================================
# 2. DICCIONARIO EN ESPAÑOL Y DATOS CURIOSOS
# =====================================================================
TRADUCTOR_Y_DATOS = {
    "Rocas y piedras rojizas": {"nombre": "rocas y piedras rojizas", "genero": "f_p", "curiosidad": "¿Sabías que Marte es rojo por el hierro de sus rocas, que se ha oxidado y formado una especie de óxido parecido al de una bicicleta vieja?"},
    "Pequeños cráteres": {"nombre": "pequeños cráteres", "genero": "m_p", "curiosidad": "¿Sabías que Marte tiene muchísimos cráteres porque su atmósfera es mucho más delgada que la de la Tierra y deja pasar más meteoritos?"},
    "Rover espacial": {"nombre": "rover espacial", "genero": "m", "curiosidad": "¿Sabías que algunos rovers de Marte pueden tomar fotografías, analizar rocas y recorrer el planeta sin que nadie los controle directamente desde allí?"},
    "Bandera de Marte": {"nombre": "bandera de Marte", "genero": "f", "curiosidad": "¿Sabías que Marte no tiene una bandera oficial como los países de la Tierra? Las banderas que vemos son símbolos de exploración y ciencia."},
    "Casco de astronauta": {"nombre": "casco de astronauta", "genero": "m", "curiosidad": "¿Sabías que un astronauta no podría respirar en Marte porque su atmósfera es demasiado delgada y está compuesta principalmente por dióxido de carbono?"},
    "Tubos y recipientes científicos": {"nombre": "tubos y recipientes científicos", "genero": "m_p", "curiosidad": "¿Sabías que los científicos estudian las rocas marcianas para descubrir pistas sobre si Marte tuvo agua líquida en el pasado?"},
    "Módulo o base espacial": {"nombre": "módulo o base espacial", "genero": "m", "curiosidad": "¿Sabías que vivir en Marte sería como vivir dentro de una nave espacial, protegido del frío extremo, la radiación y la falta de aire respirable?"},
    "person": {"nombre": "persona", "genero": "f", "curiosidad": "¿Sabías que el cerebro humano consume alrededor del 20% de la energía del cuerpo mientras estudias?"},
    "tie": {"nombre": "corbata", "genero": "f", "curiosidad": "¿Sabías que la corbata se originó en el siglo XVII como parte del uniforme militar de los soldados croatas?"},
    "backpack": {"nombre": "mochila", "genero": "f", "curiosidad": "¿Sabías que se recomienda que la mochila escolar no supere el 10% al 15% de tu peso corporal?"},
    "umbrella": {"nombre": "paraguas", "genero": "m", "curiosidad": "¿Sabías que los primeros paraguas se inventaron en la antigua China hace más de 3,000 años para protegerse del sol?"},
    "handbag": {"nombre": "bolso", "genero": "m", "curiosidad": "¿Sabías que en el siglo XVIII los bolsos eran utilizados principalmente por hombres para llevar monedas y documentos?"},
    "suitcase": {"nombre": "maleta", "genero": "f", "curiosidad": "¿Sabías que las maletas con ruedas no se inventaron hasta 1970, después de la llegada del ser humano a la Luna?"},
    "glasses": {"nombre": "gafas", "genero": "f_p", "curiosidad": "¿Sabías que las primeras gafas de lectura se fabricaron en Italia en el siglo XIII con cristales de cuarzo?"},
    "shoe": {"nombre": "zapato", "genero": "m", "curiosidad": "¿Sabías que la costumbre de usar zapatos diferentes para el pie izquierdo y derecho comenzó en el siglo XIX?"},
    "hat": {"nombre": "sombrero", "genero": "m", "curiosidad": "¿Sabías que en la Edad Media el tipo de sombrero que usaba una persona indicaba su clase social y profesión?"},
    "coat": {"nombre": "abrigo", "genero": "m", "curiosidad": "¿Sabías que la lana de los abrigos retiene el aire caliente atrapado cerca del cuerpo para aislar el frío?"},
    "book": {"nombre": "libro", "genero": "m", "curiosidad": "¿Sabías que leer apenas 20 minutos al día te expone a más de 1.8 millones de palabras al año?"},
    "notebook": {"nombre": "cuaderno", "genero": "m", "curiosidad": "¿Sabías que tomar apuntes a mano activa más áreas cerebrales asociadas a la memoria que escribir en teclado?"},
    "pencil": {"nombre": "lápiz", "genero": "m", "curiosidad": "¿Sabías que un solo lápiz de grafito contiene suficiente material para trazar una línea continua de 55 kilómetros?"},
    "pen": {"nombre": "bolígrafo", "genero": "m", "curiosidad": "¿Sabías que la diminuta bola de acero en la punta de un bolígrafo gira miles de veces al escribir?"},
    "pencil sharpener": {"nombre": "sacapuntas", "genero": "m", "curiosidad": "¿Sabías que antes de inventarse el sacapuntas en 1828, los estudiantes afilaban sus lápices con pequeñas navajas?"},
    "scissors": {"nombre": "tijeras", "genero": "f_p", "curiosidad": "¿Sabías que en las clases de geometría las tijeras ayudan a comprender visualmente simetrías y cortes axiales?"},
    "eraser": {"nombre": "borrador", "genero": "m", "curiosidad": "¿Sabías que antes de usarse la goma de borrar en el siglo XVIII, se empleaban migas de pan fresco para limpiar grafito?"},
    "ruler": {"nombre": "regla", "genero": "f", "curiosidad": "¿Sabías que la regla estandarizada más antigua conocida fue hallada en el valle del Indo y tiene más de 4,000 años?"},
    "calculator": {"nombre": "calculadora", "genero": "f", "curiosidad": "¿Sabías que la primera calculadora mecánica fue creada por Blaise Pascal en 1642 para sumar cuentas de impuestos?"},
    "folder": {"nombre": "carpeta", "genero": "f", "curiosidad": "¿Sabías que clasificar tus proyectos por colores o materias reduce el estrés y mejora el rendimiento escolar?"},
    "cell phone": {"nombre": "teléfono celular", "genero": "m", "curiosidad": "¿Sabías que un celular actual posee millones de veces más capacidad de cálculo que la computadora del Apolo 11?"},
    "laptop": {"nombre": "computadora portátil", "genero": "f", "curiosidad": "¿Sabías que la primera laptop comercial creada en 1981 pesaba más de 10 kilogramos y tenía una pantalla diminuta?"},
    "mouse": {"nombre": "ratón de computadora", "genero": "m", "curiosidad": "¿Sabías que el primer prototipo de ratón fue diseñado en 1964 por Douglas Engelbart y su cubierta era de madera?"},
    "keyboard": {"nombre": "teclado", "genero": "m", "curiosidad": "¿Sabías que la distribución QWERTY se diseñó en el siglo XIX para desacelerar la mecanografía y evitar traba de teclas?"},
    "tv": {"nombre": "televisor", "genero": "m", "curiosidad": "¿Sabías que las primeras transmisiones de televisión pública en vivo comenzaron a mediados de la década de 1930?"},
    "remote": {"nombre": "control remoto", "genero": "m", "curiosidad": "¿Sabías que el primer control remoto de televisión sin cables funcionaba emitiendo destellos de luz hacia la pantalla?"},
    "microwave": {"nombre": "horno microondas", "genero": "m", "curiosidad": "¿Sabías que la tecnología del microondas se descubrió por accidente cuando un radar derritió un chocolate en un bolsillo?"},
    "toaster": {"nombre": "tostadora", "genero": "f", "curiosidad": "¿Sabías que la tostadora eléctrica comercial se inventó antes de que existiera el pan rebanado de fábrica?"},
    "refrigerator": {"nombre": "refrigerador", "genero": "m", "curiosidad": "¿Sabías que antes de la refrigeración eléctrica se almacenaban grandes bloques de hielo traídos de montañas o lagos?"},
    "oven": {"nombre": "horno", "genero": "m", "curiosidad": "¿Sabías que en excavaciones arqueológicas se han descubierto hornos de barro de más de 4,000 años de antigüedad?"},
    "apple": {"nombre": "manzana", "genero": "f", "curiosidad": "¿Sabías que entregar una manzana a los maestros era una antigua costumbre del siglo XIX en zonas rurales como aporte de alimento?"},
    "banana": {"nombre": "banano", "genero": "m", "curiosidad": "¿Sabías que los bananos contienen vitamina B6 y potasio, minerales clave para prevenir la fatiga durante los exámenes?"},
    "sandwich": {"nombre": "sándwich", "genero": "m", "curiosidad": "¿Sabías que un refrigerio balanceado a media mañana le proporciona al cerebro la glucosa ideal para prestar atención?"},
    "orange": {"nombre": "naranja", "genero": "f", "curiosidad": "¿Sabías que en el idioma inglés la palabra para la fruta 'orange' existió siglos antes de usarse para nombrar el color?"},
    "broccoli": {"nombre": "brócoli", "genero": "m", "curiosidad": "¿Sabías que el brócoli fue desarrollado en la antigua Italia mediante selección de plantas silvestres de mostaza?"},
    "carrot": {"nombre": "zanahoria", "genero": "f", "curiosidad": "¿Sabías que las zanahorias originales eran de color morado o amarillo y la variedad naranja se popularizó en Holanda?"},
    "pizza": {"nombre": "pizza", "genero": "f", "curiosidad": "¿Sabías que los tres ingredientes de la pizza Margarita representan los colores de la bandera de Italia?"},
    "donut": {"nombre": "dona", "genero": "f", "curiosidad": "¿Sabías que el orificio central de las donas se creó para permitir una cocción uniforme en el aceite caliente?"},
    "cake": {"nombre": "pastel", "genero": "m", "curiosidad": "¿Sabías que encender velas sobre pasteles tiene sus orígenes en homenajes de la antigua Grecia hacia la luna?"},
    "hot dog": {"nombre": "perro caliente", "genero": "m", "curiosidad": "¿Sabías que este platillo fue popularizado en eventos deportivos por vendedores ambulantes a finales del siglo XIX?"},
    "bottle": {"nombre": "botella de agua", "genero": "f", "curiosidad": "¿Sabías que mantenerte bien hidratado en el colegio ayuda a mantener la atención y mejora la memoria a corto plazo?"},
    "cup": {"nombre": "taza", "genero": "f", "curiosidad": "¿Sabías que las tazas de cerámica retienen el calor gracias a la baja conductividad térmica del material horneado?"},
    "fork": {"nombre": "tenedor", "genero": "m", "curiosidad": "¿Sabías que en el siglo XI el uso del tenedor causó polémica en Europa por ser considerado un lujo innecesario?"},
    "knife": {"nombre": "cuchillo", "genero": "m", "curiosidad": "¿Sabías que los cuchillos de mesa tienen la punta redondeada desde 1637 para promover la etiqueta pacífica al comer?"},
    "spoon": {"nombre": "cuchara", "genero": "f", "curiosidad": "¿Sabías que las primeras cucharas prehistóricas conocidas se fabricaban a partir de conchas marinas u óseas?"},
    "bowl": {"nombre": "tazón", "genero": "m", "curiosidad": "¿Sabías que la alfarería para fabricar tazones de barro se desarrolló de forma independiente en diversas culturas humanas?"},
    "wine glass": {"nombre": "copa de vidrio", "genero": "f", "curiosidad": "¿Sabías que la fabricación del vidrio requiere calentar arena de sílice a más de 1,500 grados Celsius?"},
    "chair": {"nombre": "silla", "genero": "f", "curiosidad": "¿Sabías que mantener una postura erguida en la silla de clase evita contracturas y reduce la fatiga muscular?"},
    "desk": {"nombre": "escritorio", "genero": "m", "curiosidad": "¿Sabías que estudiar en un escritorio limpio y despejado ayuda al cerebro a enfocar su atención sin distracciones visuales?"},
    "couch": {"nombre": "sofá", "genero": "m", "curiosidad": "¿Sabías que la palabra 'sofá' proviene del término árabe 'suffah', que describía un banco cubierto con cojines?"},
    "bed": {"nombre": "cama", "genero": "f", "curiosidad": "¿Sabías que durante el sueño tu cerebro procesa, consolida y fija los conocimientos aprendidos durante las clases?"},
    "potted plant": {"nombre": "planta en maceta", "genero": "f", "curiosidad": "¿Sabías que tener plantas vivas en las aulas de clase ayuda a purificar el aire y reduce los niveles de estrés?"},
    "clock": {"nombre": "reloj", "genero": "m", "curiosidad": "¿Sabías que organizar tu tiempo de estudio en bloques de 25 minutos con descansos mejora mucho tu concentración?"},
    "vase": {"nombre": "florero", "genero": "m", "curiosidad": "¿Sabías que en la antigua Grecia los floreros y vasijas ilustraban mitos que servían como libros educativos de la época?"},
    "sports ball": {"nombre": "balón", "genero": "m", "curiosidad": "¿Sabías que la práctica de deportes durante el recreo libera endorfinas que aumentan la agilidad mental en clase?"},
    "baseball bat": {"nombre": "bate de béisbol", "genero": "m", "curiosidad": "¿Sabías que los primeros bates de béisbol eran tallados a mano por los propios jugadores en madera de fresno?"},
    "baseball glove": {"nombre": "guante de béisbol", "genero": "m", "curiosidad": "¿Sabías que los primeros guantes de béisbol se introdujeron en 1870 para proteger las manos de las atrapadas?"},
    "skateboard": {"nombre": "patineta", "genero": "f", "curiosidad": "¿Sabías que la patineta se inventó en California en la década de 1950 para practicar surf sobre el asfalto?"},
    "surfboard": {"nombre": "tabla de surf", "genero": "f", "curiosidad": "¿Sabías que las primeras tablas de surf hawaianas estaban talladas en madera maciza y medían más de 4 metros?"},
    "tennis racket": {"nombre": "raqueta de tenis", "genero": "f", "curiosidad": "¿Sabías que antes del siglo XX las cuerdas de las raquetas de tenis se elaboraban con fibras naturales de tripa?"},
    "frisbee": {"nombre": "frisbi", "genero": "m", "curiosidad": "¿Sabías que el frisbi nació cuando estudiantes universitarios empezaron a lanzarse moldes de tartas de una panadería?"},
    "kite": {"nombre": "cometa", "genero": "f", "curiosidad": "¿Sabías que Benjamín Franklin utilizó una cometa en 1752 durante una tormenta para demostrar la naturaleza eléctrica del rayo?"},
    "skis": {"nombre": "esquís", "genero": "m_p", "curiosidad": "¿Sabías que los hallazgos arqueológicos muestran que el uso de esquís para desplazarse por la nieve tiene más de 5,000 años?"},
    "snowboard": {"nombre": "tabla de nieve", "genero": "f", "curiosidad": "¿Sabías que el snowboard nació en la década de 1960 cuando un padre unió dos esquís para el entretenimiento de sus hijos?"},
    "bird": {"nombre": "pájaro", "genero": "m", "curiosidad": "¿Sabías que las aves son los únicos descendientes directos sobrevivientes del grupo de los dinosaurios terópodos?"},
    "cat": {"nombre": "gato", "genero": "m", "curiosidad": "¿Sabías que los gatos poseen más de 20 músculos dedicados únicamente al control del movimiento de cada oreja?"},
    "dog": {"nombre": "perro", "genero": "m", "curiosidad": "¿Sabías que el sentido del olfato en los perros es entre 10,000 y 100,000 veces más agudo que el de los humanos?"},
    "horse": {"nombre": "caballo", "genero": "m", "curiosidad": "¿Sabías que los caballos pueden dormir tanto de pie gracias a un sistema especial de bloqueo en sus articulaciones?"},
    "sheep": {"nombre": "oveja", "genero": "f", "curiosidad": "¿Sabías que la lana de oveja crece de manera continua y ha sido utilizada para textiles desde el Neolítico?"},
    "cow": {"nombre": "vaca", "genero": "f", "curiosidad": "¿Sabías que las vacas tienen un estómago dividido en cuatro cavidades para digerir la celulosa de las plantas?"},
    "elephant": {"nombre": "elefante", "genero": "m", "curiosidad": "¿Sabías que la trompa del elefante no tiene huesos pero cuenta con más de 40,000 músculos individuales?"},
    "bear": {"nombre": "oso", "genero": "m", "curiosidad": "¿Sabías que durante la hibernación invernal el ritmo cardíaco de un oso reduce significativamente su frecuencia?"},
    "zebra": {"nombre": "cebra", "genero": "f", "curiosidad": "¿Sabías que las rayas del pelaje de la cebra son únicas en cada individuo, funcionando de forma similar a una huella dactilar?"},
    "giraffe": {"nombre": "jirafa", "genero": "f", "curiosidad": "¿Sabías que a pesar de tener un cuello tan largo, la jirafa tiene exactamente 7 vértebras cervicales, igual que los humanos?"},
    "bicycle": {"nombre": "bicicleta", "genero": "f", "curiosidad": "¿Sabías que la primera bicicleta se diseñó en 1817 en Alemania y no contaba con pedales, se impulsaba corriendo?"},
    "car": {"nombre": "automóvil", "genero": "m", "curiosidad": "¿Sabías que un auto moderno estándar está compuesto por más de 30,000 piezas y componentes individuales?"},
    "motorcycle": {"nombre": "motocicleta", "genero": "f", "curiosidad": "¿Sabías que las primeras motocicletas experimentales registradas en el siglo XIX funcionaban con calderas de vapor?"},
    "airplane": {"nombre": "avión", "genero": "m", "curiosidad": "¿Sabías que las alas de un avión generan sustentación gracias al principio físico propuesto por Daniel Bernoulli?"},
    "bus": {"nombre": "autobús", "genero": "m", "curiosidad": "¿Sabías que el transporte escolar en autobús es considerado estadísticamente una de las formas más seguras de traslado?"},
    "train": {"nombre": "tren", "genero": "m", "curiosidad": "¿Sabías que la invención de la locomotora de vapor impulsó la Revolución Industrial en el siglo XIX?"},
    "truck": {"nombre": "camión", "genero": "m", "curiosidad": "¿Sabías que debido a su gran masa, un camión de carga requiere una distancia de frenado mucho mayor que un automóvil?"},
    "boat": {"nombre": "barco", "genero": "m", "curiosidad": "¿Sabías que el principio de Arquímedes explica por qué un gran barco de acero logra flotar en el agua al desplazar volumen?"},
    "traffic light": {"nombre": "semáforo", "genero": "m", "curiosidad": "¿Sabías que el primer semáforo del mundo se instaló en Londres en 1868 y funcionaba con luces de gas?"},
    "stop sign": {"nombre": "señal de pare", "genero": "f", "curiosidad": "¿Sabías que la forma octagonal de la señal de pare se eligió para que los conductores la reconozcan incluso cubierta de nieve?"},
    "fire hydrant": {"nombre": "hidrante", "genero": "m", "curiosidad": "¿Sabías que la patente original del hidrante se destruyó irónicamente en un incendio en la oficina de patentes en 1836?"},
    "teddy bear": {"nombre": "oso de peluche", "genero": "m", "curiosidad": "¿Sabías que el nombre en inglés 'Teddy Bear' se creó en honor al presidente estadounidense Theodore Roosevelt?"},
    "hair drier": {"nombre": "secador de pelo", "genero": "m", "curiosidad": "¿Sabías que el primer secador de pelo mecánico fue inventado en un salón de belleza en Francia en 1890?"},
    "toothbrush": {"nombre": "cepillo de dientes", "genero": "m", "curiosidad": "¿Sabías que antes del nylon en 1938, las cerdas de los cepillos de dientes se elaboraban con pelo animal?"},
    "light bulb": {"nombre": "bombilla", "genero": "f", "curiosidad": "¿Sabías que Thomas Edison perfeccionó la bombilla en 1879 probando miles de materiales para el filamento?"},
    "lamp": {"nombre": "lámpara", "genero": "f", "curiosidad": "¿Sabías que una adecuada iluminación en tu zona de estudio previene la fatiga ocular y mejora la velocidad de lectura?"},
    "clock tower": {"nombre": "torre de reloj", "genero": "f", "curiosidad": "¿Sabías que en la Edad Media las torres con reloj eran la única referencia de hora precisa para toda una ciudad?"},
    "globe": {"nombre": "globo terráqueo", "genero": "m", "curiosidad": "¿Sabías que el globo terráqueo preservado más antiguo fue construido en Núremberg en 1492, antes del viaje de Colón?"},
    "microscope": {"nombre": "microscopio", "genero": "m", "curiosidad": "¿Sabías que la invención del microscopio en el siglo XVII permitió a Robert Hooke descubrir las células por primera vez?"},
    "telescope": {"nombre": "telescopio", "genero": "m", "curiosidad": "¿Sabías que Galileo Galilei fue de los primeros en apuntar un telescopio al cielo, descubriendo las lunas de Júpiter?"},
    "compass": {"nombre": "brújula", "genero": "f", "curiosidad": "¿Sabías que la brújula funciona porque la Tierra se comporta como un gigantesco imán gracias a su núcleo de hierro?"}
}

CONECTORES_INICIO = ["Mira, estoy viendo", "Veo por aquí", "Fíjate, acabo de notar", "Estoy observando", "Por aquí hay"]
CONECTORES_CONTINUACION = ["Y también veo", "Mira, también encontré", "Por cierto, detecto", "Ah, y también hay", "Además, observo"]

# =====================================================================
# 3. MÓDULO DE ANÁLISIS VISUAL REAL (COLOR Y TAMAÑO)
# =====================================================================
def obtener_color_dominante(region_crop):
    """Calcula el color dominante en espacio HSV descartando fondos muy oscuros o muy brillantes."""
    if region_crop.size == 0:
        return None
    
    hsv = cv2.cvtColor(region_crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([0, 30, 30]), np.array([180, 255, 225]))
    hsv_filtrado = hsv[mask > 0]
    
    if len(hsv_filtrado) < 50:
        return None

    h_promedio = np.median(hsv_filtrado[:, 0])
    s_promedio = np.median(hsv_filtrado[:, 1])
    v_promedio = np.median(hsv_filtrado[:, 2])

    if s_promedio < 40 and v_promedio > 180:
        return "blanco"
    elif v_promedio < 45:
        return "negro"
    elif s_promedio < 40:
        return "gris"

    if h_promedio < 10 or h_promedio > 170:
        return "rojo"
    elif 10 <= h_promedio < 25:
        return "naranja"
    elif 25 <= h_promedio < 35:
        return "amarillo"
    elif 35 <= h_promedio < 85:
        return "verde"
    elif 85 <= h_promedio < 130:
        return "azul"
    elif 130 <= h_promedio < 170:
        return "morado"
    
    return None

def describir_objeto(info, color, area_relativa, cantidad):
    """Genera la descripción respetando género y concordancia gramatical."""
    nombre = info["nombre"]
    genero = info["genero"]

    if cantidad > 1:
        art = "unos" if "m" in genero else "unas"
        if color:
            adj_color = color if color in ["gris", "azul"] else (color + "s" if color.endswith(("o", "a", "e")) else color)
            if genero.startswith("f") and adj_color.endswith("os"):
                adj_color = adj_color[:-2] + "as"
            desc_basica = f"{cantidad} {nombre}s {adj_color}"
        else:
            desc_basica = f"{cantidad} {nombre}s"
    else:
        if genero == "m":
            art = "un"
            adj_color = color
        elif genero == "f":
            art = "una"
            adj_color = color[:-1] + "a" if (color and color.endswith("o")) else color
        elif genero == "m_p":
            art = "unos"
            adj_color = color + "s" if (color and color.endswith(("o", "a"))) else color
        elif genero == "f_p":
            art = "unas"
            adj_color = color[:-1] + "as" if (color and color.endswith("o")) else color

        if color:
            desc_basica = f"{art} {nombre} de color {color}"
        else:
            desc_basica = f"{art} {nombre}"

    if area_relativa > 0.35:
        tamano = "Bastante grande en pantalla"
    elif area_relativa < 0.05:
        tamano = "Pequeño"
    else:
        tamano = ""

    if tamano:
        return f"{desc_basica}, que se ve {tamano.lower()}"
    return desc_basica

# =====================================================================
# 4. SERVIDOR WEB
# =====================================================================
@app.get("/")
def pagina_principal():
    return render_template_string(HTML_PAGE)


@app.get("/estado")
def obtener_estado():
    return jsonify(estado=estado_ia)


@app.post("/detectar")
def detectar_frame():
    return reconocer_imagen()


@app.post("/recognize")
def reconocer_imagen():
    archivo = request.files.get("image") or request.files.get("frame")
    if archivo is None:
        return jsonify(success=False, message="No se recibió ninguna imagen"), 400

    contenido = archivo.read()
    if not contenido:
        return jsonify(success=False, message="La imagen está vacía"), 400

    frame_camara = None
    try:
        datos_frame = np.frombuffer(contenido, dtype=np.uint8)
        frame_camara = cv2.imdecode(datos_frame, cv2.IMREAD_COLOR)
        if frame_camara is None:
            return jsonify(success=False, message="La imagen no es válida"), 400

        with lock_deteccion:
            resultado = analizar_frame(frame_camara)
    except Exception as error:
        app.logger.exception("Error procesando el fotograma")
        return jsonify(
            success=False,
            message="El servidor no pudo procesar la imagen.",
            error=error.__class__.__name__,
        ), 503
    finally:
        # Limpiar referencias temporales para evitar memoria acumulada bajo flujo continuo.
        if 'datos_frame' in locals():
            del datos_frame
        if frame_camara is not None:
            frame_camara = None

    return jsonify(resultado)


@app.get("/videos/<nombre_video>")
def servir_video(nombre_video):
    videos = {
        "espera.mp4": "espera.mp4",
        "hablando.mp4": "hablando.mp4",
    }
    archivo = videos.get(nombre_video)
    if archivo is None:
        return jsonify(error="Video no encontrado"), 404
    return send_file(os.path.join(BASE_DIR, archivo), mimetype="video/mp4")


@app.get("/static/<nombre_video>")
def servir_video_compatibilidad(nombre_video):
    return servir_video(nombre_video)


# =====================================================================
# 5. DETECCIÓN DE FOTOGRAMAS ENVIADOS POR EL NAVEGADOR
# =====================================================================
def analizar_frame(frame_camara):
    global modelo, primera_deteccion_global

    if modelo is None:
        modelo = YOLO(os.path.join(BASE_DIR, "yolo11n.pt"))

    alto_original, ancho_original = frame_camara.shape[:2]
    lado_mayor = max(alto_original, ancho_original)
    if lado_mayor > 640:
        escala = 640 / lado_mayor
        frame_camara = cv2.resize(
            frame_camara,
            (int(ancho_original * escala), int(alto_original * escala)),
            interpolation=cv2.INTER_AREA,
        )

    results = modelo(frame_camara, imgsz=256, conf=0.45, verbose=False)
    alto_frame, ancho_frame = frame_camara.shape[:2]
    area_total = alto_frame * ancho_frame
    detecciones = []

    for result in results:
        for box in result.boxes:
            confianza = float(box.conf[0])
            id_clase = int(box.cls[0])
            nombre_ingles = modelo.names[id_clase]
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            detecciones.append({
                "objeto": nombre_ingles,
                "confianza": confianza,
                "box": (x1, y1, x2, y2),
            })

    if not detecciones:
        objetos_registrados.clear()
        return {
            "success": False,
            "message": "No se pudo reconocer el objeto. Intenta nuevamente.",
            "estado": estado_ia,
        }

    deteccion = max(detecciones, key=lambda item: item["confianza"])
    obj_ingles = deteccion["objeto"]
    tiempo_actual = time.time()
    registro = objetos_registrados.setdefault(obj_ingles, {
        "inicio": tiempo_actual,
        "anunciado": False,
    })
    for objeto_registrado in list(objetos_registrados):
        if objeto_registrado != obj_ingles:
            del objetos_registrados[objeto_registrado]

    puede_anunciar = (
        tiempo_actual - registro["inicio"] >= 3.0 and not registro["anunciado"]
    )
    x1, y1, x2, y2 = deteccion["box"]
    corte_objeto = frame_camara[max(0, y1):min(alto_frame, y2), max(0, x1):min(ancho_frame, x2)]
    color_detectado = obtener_color_dominante(corte_objeto)
    area_relativa = ((x2 - x1) * (y2 - y1)) / area_total
    cantidad = sum(item["objeto"] == obj_ingles for item in detecciones)

    info_objeto = TRADUCTOR_Y_DATOS.get(obj_ingles, {
        "nombre": obj_ingles.replace("_", " "),
        "genero": "m",
        "curiosidad": "",
    })
    descripcion = describir_objeto(info_objeto, color_detectado, area_relativa, cantidad)
    curiosidad = info_objeto.get("curiosidad", "")
    frase_completa = ""
    if puede_anunciar:
        conector = random.choice(
            CONECTORES_INICIO if primera_deteccion_global else CONECTORES_CONTINUACION
        )
        primera_deteccion_global = False
        frase_completa = f"{conector} {descripcion}. {curiosidad}".strip()
        registro["anunciado"] = True
    return {
        "success": True,
        "object": info_objeto["nombre"],
        "confidence": round(deteccion["confianza"], 4),
        "information": curiosidad or "No hay información adicional disponible.",
        "description": descripcion,
        "text": frase_completa,
        "estado": estado_ia,
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
