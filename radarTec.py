import pygame
import serial
import math
import time

# =============================================
# CONFIGURACION — cambia estos valores si es necesario
# =============================================
PUERTO_SERIAL   = 'COM4'
BAUDRATE        = 9600
DISTANCIA_MAX   = 100        # cm — rango maximo del radar
ANCHO           = 800        # pixels de ancho de la ventana
ALTO            = 500        # pixels de alto de la ventana
RADIO_RADAR     = 380        # radio del semicirculo en pixels

# =============================================
# COLORES
# =============================================
NEGRO       = (0,   0,   0)
VERDE_OSCURO = (0,  40,   0)
VERDE       = (0, 255,  70)
VERDE_TENUE = (0,  80,  30)
ROJO        = (255,  0,   0)
BLANCO      = (255,255, 255)
GRIS        = (100,100, 100)

# =============================================
# INICIAR PYGAME
# =============================================
pygame.init()
pantalla = pygame.display.set_mode((ANCHO, ALTO))
pygame.display.set_caption("Radar 2D")
reloj = pygame.time.Clock()
fuente = pygame.font.SysFont('consolas', 14)

# Centro del radar (parte baja central de la pantalla)
cx = ANCHO // 2
cy = ALTO - 20   # un poco arriba del borde inferior

# =============================================
# CONEXION SERIAL
# =============================================
try:
    puerto = serial.Serial(PUERTO_SERIAL, BAUDRATE, timeout=0.01)
    print(f"Conectado a {PUERTO_SERIAL}")
except:
    print(f"No se pudo abrir {PUERTO_SERIAL}. Revisá el puerto.")
    pygame.quit()
    exit()

# =============================================
# ESTADO DEL RADAR
# =============================================
angulo_actual  = 0           # donde apunta el servo ahora
puntos         = []          # lista de (angulo, distancia) detectados
MAX_PUNTOS     = 360         # cuantos puntos guardamos antes de borrar los viejos

# Para calcular velocidad
ultima_deteccion = {}        # { angulo: (distancia, tiempo) }

# =============================================
# FUNCIONES DE DIBUJO
# =============================================

def polar_a_pixel(angulo, distancia):
    """Convierte angulo (grados) y distancia (cm) a coordenadas de pantalla."""
    escala = RADIO_RADAR / DISTANCIA_MAX
    distancia_px = distancia * escala

    # En el radar, 0° es la derecha y 180° es la izquierda
    # Los angulos del servo van de 0 a 180, queremos que se vea como semicirculo arriba
    rad = math.radians(angulo)
    x = cx + distancia_px * math.cos(math.pi - rad)   # espejo horizontal
    y = cy - distancia_px * math.sin(rad)              # y negativo = hacia arriba
    return int(x), int(y)


def dibujar_fondo():
    """Dibuja el fondo negro y el semicirculo verde oscuro."""
    pantalla.fill(NEGRO)

    # Semicirculo relleno verde muy oscuro
    pygame.draw.circle(pantalla, VERDE_OSCURO, (cx, cy), RADIO_RADAR)

    # Tapar la mitad de abajo para que quede solo el semicirculo superior
    pygame.draw.rect(pantalla, NEGRO, (0, cy, ANCHO, ALTO - cy))


def dibujar_circulos():
    """Dibuja los circulos concentricos de referencia (rangos de distancia)."""
    for i in range(1, 5):   # 4 circulos: 25%, 50%, 75%, 100% del rango
        r = int(RADIO_RADAR * i / 4)
        pygame.draw.circle(pantalla, VERDE_TENUE, (cx, cy), r, 1)

        # Etiqueta de distancia en cm
        distancia_label = int(DISTANCIA_MAX * i / 4)
        texto = fuente.render(f"{distancia_label}cm", True, VERDE_TENUE)
        pantalla.blit(texto, (cx + r + 3, cy - 12))


def dibujar_lineas_angulo():
    """Dibuja lineas de referencia cada 30 grados."""
    for a in range(0, 181, 30):
        x, y = polar_a_pixel(a, DISTANCIA_MAX)
        pygame.draw.line(pantalla, VERDE_TENUE, (cx, cy), (x, y), 1)

        # Etiqueta del angulo
        texto = fuente.render(f"{a}°", True, GRIS)
        pantalla.blit(texto, (x - 10, y - 10))


def dibujar_barrido():
    """Dibuja la linea verde brillante del angulo actual."""
    x, y = polar_a_pixel(angulo_actual, DISTANCIA_MAX)
    pygame.draw.line(pantalla, VERDE, (cx, cy), (x, y), 2)


def dibujar_puntos():
    """Dibuja todos los puntos detectados. Los mas recientes mas brillantes."""
    total = len(puntos)
    for i, (a, d, velocidad) in enumerate(puntos):
        if d <= 0 or d > DISTANCIA_MAX:
            continue

        # Opacidad segun antiguedad: los viejos son mas tenues
        brillo = int(80 + 175 * (i / max(total, 1)))
        color = (0, brillo, int(brillo * 0.3))

        x, y = polar_a_pixel(a, d)
        pygame.draw.circle(pantalla, color, (x, y), 4)

        # Si tiene velocidad calculada, mostrarla al lado
        #if velocidad is not None:
            #texto = fuente.render(f"{velocidad:.1f}cm/s", True, BLANCO)
            #pantalla.blit(texto, (x + 6, y - 6))


def dibujar_info():
    """Muestra informacion en la esquina."""
    texto1 = fuente.render(f"Angulo:    {angulo_actual}°", True, VERDE)
    texto2 = fuente.render(f"Puntos:    {len(puntos)}", True, VERDE)
    texto3 = fuente.render(f"Max rango: {DISTANCIA_MAX}cm", True, GRIS)
    pantalla.blit(texto1, (10, 10))
    pantalla.blit(texto2, (10, 28))
    pantalla.blit(texto3, (10, 46))


# =============================================
# LOOP PRINCIPAL
# =============================================
corriendo = True

while corriendo:

    # --- Eventos de pygame ---
    for evento in pygame.event.get():
        if evento.type == pygame.QUIT:
            corriendo = False

    # --- Leer serial SIN bloquear ---
    if puerto.in_waiting > 0:
        try:
            linea = puerto.readline().decode('utf-8').strip()
            partes = linea.split(',')

            if len(partes) == 2:
                angulo   = int(partes[0])
                distancia = int(partes[1])
                angulo_actual = angulo

                # Calcular velocidad si ya teniamos una lectura anterior en ese angulo
                velocidad = None
                if angulo in ultima_deteccion:
                    dist_anterior, tiempo_anterior = ultima_deteccion[angulo]
                    tiempo_ahora = time.time()
                    delta_tiempo = tiempo_ahora - tiempo_anterior
                    delta_dist   = abs(distancia - dist_anterior)

                    if delta_tiempo > 0:
                        velocidad = delta_dist / delta_tiempo   # cm/s

                # Guardar para la proxima comparacion
                ultima_deteccion[angulo] = (distancia, time.time())

                # Agregar punto a la lista
                puntos.append((angulo, distancia, velocidad))

                # Limitar cantidad de puntos guardados
                if len(puntos) > MAX_PUNTOS:
                    puntos.pop(0)

        except (ValueError, IndexError):
            pass   # dato corrupto, se ignora

    # --- Dibujar todo ---
    dibujar_fondo()
    dibujar_circulos()
    dibujar_lineas_angulo()
    dibujar_barrido()
    dibujar_puntos()
    dibujar_info()

    pygame.display.flip()
    reloj.tick(60)

# --- Cerrar todo limpio ---
puerto.close()
pygame.quit()