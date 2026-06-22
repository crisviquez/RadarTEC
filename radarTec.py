import pygame
import serial
import math
import time
import collections
 
# =============================================
# CONFIGURACION
# =============================================
PUERTO_SERIAL  = '/dev/cu.usbmodem2023101'
BAUDRATE       = 9600
DISTANCIA_MAX  = 100
SIN_OBJETO     = 400
 
# Ventana — radar a la izquierda, gráfico a la derecha
ANCHO_RADAR  = 900
ANCHO_GRAF   = 380        
ANCHO        = ANCHO_RADAR + ANCHO_GRAF
ALTO         = 560
RADIO_RADAR  = 400
 
# Centro del radar
cx = ANCHO_RADAR // 2
cy = ALTO - 10
 
# Panel del gráfico cartesiano
GRAF_X  = ANCHO_RADAR + 10           
GRAF_Y  = 40                          
GRAF_W  = ANCHO_GRAF - 20            
GRAF_H  = ALTO - 80                  
# Origen del gráfico 
ORIG_X  = GRAF_X + 45
ORIG_Y  = GRAF_Y + GRAF_H - 10
PLOT_W  = GRAF_W - 55
PLOT_H  = GRAF_H - 30
 
# Rango del gráfico (en cm)
GRAF_X_MIN, GRAF_X_MAX = -DISTANCIA_MAX, DISTANCIA_MAX
GRAF_Y_MIN, GRAF_Y_MAX =  0,             DISTANCIA_MAX
 
# =============================================
# COLORES (Rediseño Minimalista)
# =============================================
NEGRO        = (5,   5,   7)       
VERDE_OSCURO = (10, 20,  12)       # Fondo de radar 
VERDE        = (0, 255, 120)       # Barrido principal 
VERDE_TENUE  = (20, 45,  28)      
VERDE_GRILLA = (12, 28,  18)       # Líneas de ángulos 
VERDE_MID    = (0, 160,  80)       
ROJO         = (255, 70,  70)      
AMARILLO     = (255, 200,  0)      # Línea de predicción 
BLANCO       = (240, 240, 245)     
GRIS         = (70,  75,  80)      
GRIS_CLARO   = (140, 145, 150)     
PANEL_BG     = (10,  14,  12)      
PANEL_BORDE  = (25,  50,  35)      
 
# Colores por objeto (Estilo plano moderno)
COLORES_OBJ  = [
    (255,  80,  80),   #Rojo coral
    (60,  165, 255),   #Azul eléctrico
    (255, 150,  30),   #Naranja
    (180,  90, 255),   #Violeta
    (40,  230, 200),   #Turquesa
    (240, 240,  80),   #Amarillo pastel
]
 

pygame.init()
pantalla = pygame.display.set_mode((ANCHO, ALTO))
pygame.display.set_caption("Radar 2D — TEC")
reloj    = pygame.time.Clock()
fuente   = pygame.font.SysFont('consolas', 13)
fuente_g = pygame.font.SysFont('consolas', 15, bold=True)
fuente_p = pygame.font.SysFont('consolas', 11)
fuente_t = pygame.font.SysFont('consolas', 10)
 
# =============================================
# CONEXION SERIAL
# =============================================
try:
    puerto = serial.Serial(PUERTO_SERIAL, BAUDRATE, timeout=0.01)
    print(f"Conectado a {PUERTO_SERIAL}")
    conectado = True
except Exception as e:
    print(f"No se pudo abrir {PUERTO_SERIAL}: {e}")
    print("Modo DEMO activo.")
    conectado = False
 
# =============================================
# ESTADO DEL RADAR
# =============================================
angulo_actual = 0
puntos        = collections.deque(maxlen=180) 
trail_angulos = collections.deque(maxlen=12)  
MAX_AGE_OBJ   = 3.5
objetos       = {}          
_color_map    = {}          
 
# =============================================
# DEMO
# =============================================
_demo_angulo = 0
_demo_dir    = 1
_demo_obj_a  = {'angulo': 55,  'dist': 65.0, 'vel_d': 0.0}
_demo_obj_b  = {'angulo': 115, 'dist': 35.0, 'vel_d': 0.8}
 
def demo_tick():
    global _demo_angulo, _demo_dir
    _demo_obj_b['dist'] += _demo_obj_b['vel_d']
    if _demo_obj_b['dist'] > 90 or _demo_obj_b['dist'] < 15:
        _demo_obj_b['vel_d'] *= -1
    dist = SIN_OBJETO
    for obj in [_demo_obj_a, _demo_obj_b]:
        if abs(_demo_angulo - obj['angulo']) <= 5:
            ruido = math.sin(time.time() * 3) * 1.5
            dist  = max(5, obj['dist'] + ruido)
    _demo_angulo += _demo_dir * 2
    if _demo_angulo >= 180: _demo_angulo = 180; _demo_dir = -1
    if _demo_angulo <= 0:   _demo_angulo = 0;   _demo_dir =  1
    return _demo_angulo, dist
 
# =============================================
# UTILIDADES
# =============================================
def polar_a_pixel(angulo, distancia):
    escala = RADIO_RADAR / DISTANCIA_MAX
    r_px   = distancia * escala
    rad    = math.radians(angulo)
    x = cx + r_px * math.cos(math.pi - rad)
    y = cy - r_px * math.sin(rad)
    return int(x), int(y)
 
def polar_a_cart_cm(angulo, dist):
    rad = math.radians(angulo)
    return dist * math.cos(math.pi - rad), -dist * math.sin(rad)
 
def cart_cm_a_pixel(xc, yc):
    escala = RADIO_RADAR / DISTANCIA_MAX
    return int(cx + xc * escala), int(cy + yc * escala)
 
def bucket(angulo):
    return int(round(angulo / 8.0)) * 8
 
def color_obj(b):
    if b not in _color_map:
        _color_map[b] = len(_color_map) % len(COLORES_OBJ)
    return COLORES_OBJ[_color_map[b]]
 
def cm_a_graf(xc, yc):
    px = ORIG_X + int((xc - GRAF_X_MIN) / (GRAF_X_MAX - GRAF_X_MIN) * PLOT_W)
    py = ORIG_Y - int((yc - GRAF_Y_MIN) / (GRAF_Y_MAX - GRAF_Y_MIN) * PLOT_H)
    return px, py
 
# =============================================
# PREDICCIÓN DE TRAYECTORIA PARABÓLICA
# =============================================
def calcular_prediccion(hist):
    if len(hist) < 3:
        return [], [], []
 
    pts        = list(hist)[-3:]
    x0, y0, t0 = pts[-1]
    xm, ym, tm = pts[-2]
    dt = t0 - tm
    if dt <= 0 or dt > 1.0:
        return [], [], []
 
    vx = (x0 - xm) / dt
    vy = (y0 - ym) / dt
    g  = 980.0                  #Aqui se ajusta a cm/s2 para precisión física real
 
    pred_radar, pred_graf, pred_cm = [], [], []
    T_TOTAL, PASOS = 1.2, 30
 
    for i in range(1, PASOS + 1):
        t  = i * (T_TOTAL / PASOS)
        xp = x0 + vx * t
        yp = y0 + vy * t - 0.5 * g * t * t
 
        pr = cart_cm_a_pixel(xp, yp)
        dx, dy = pr[0] - cx, pr[1] - cy
        if math.hypot(dx, dy) <= RADIO_RADAR + 10:
            pred_radar.append(pr)
 
        yp_graf = -yp   
        if GRAF_X_MIN <= xp <= GRAF_X_MAX and GRAF_Y_MIN <= yp_graf <= GRAF_Y_MAX:
            pred_graf.append(cm_a_graf(xp, yp_graf))
            pred_cm.append((xp, yp_graf))
 
    return pred_radar, pred_graf, pred_cm
 
# =============================================
# TRACKING DE OBJETOS
# =============================================
def actualizar_objeto(angulo, dist, ts):
    if dist >= SIN_OBJETO or dist < 2:
        return
    b = bucket(angulo)
    xc, yc = polar_a_cart_cm(angulo, dist)
 
    if b not in objetos:
        objetos[b] = {
            'dist': dist, 'tiempo': ts, 'vel': 0.0,
            'hist': collections.deque(maxlen=40),
            'pred_radar': [], 'pred_graf': [], 'pred_cm': [],
            'hist_graf': collections.deque(maxlen=40),   
            'angulo': angulo
        }
    else:
        obj = objetos[b]
        dt  = ts - obj['tiempo']
        if dt > 0:
            obj['vel'] = abs(dist - obj['dist']) / dt
        obj['dist']   = dist
        obj['tiempo'] = ts
        obj['angulo'] = angulo
 
    yc_graf = -yc   
    objetos[b]['hist'].append((xc, yc, ts))
    objetos[b]['hist_graf'].append(cm_a_graf(xc, yc_graf))
    pr, pg, pc = calcular_prediccion(objetos[b]['hist'])
    objetos[b]['pred_radar'] = pr
    objetos[b]['pred_graf']  = pg
    objetos[b]['pred_cm']    = pc
 
def limpiar_objetos_viejos():
    ahora   = time.time()
    muertos = [b for b, o in objetos.items() if ahora - o['tiempo'] > MAX_AGE_OBJ]
    for b in muertos:
        del objetos[b]
 
# =============================================
# DIBUJO 
# =============================================
def dibujar_fondo():
    pantalla.fill(NEGRO)
    pygame.draw.circle(pantalla, VERDE_OSCURO, (cx, cy), RADIO_RADAR)
    pygame.draw.rect(pantalla, NEGRO, (0, cy, ANCHO_RADAR, ALTO - cy))
 
def dibujar_circulos():
    for i in range(1, 5):
        r  = int(RADIO_RADAR * i / 4)
        dl = int(DISTANCIA_MAX * i / 4)
        pygame.draw.circle(pantalla, VERDE_TENUE, (cx, cy), r, 1)
        txt = fuente_p.render(f"{dl}cm", True, GRIS)
        pantalla.blit(txt, (cx + r + 4, cy - 14))
 
def dibujar_lineas_angulo():
    for a in range(30, 151, 30):
        x, y = polar_a_pixel(a, DISTANCIA_MAX)
        pygame.draw.line(pantalla, VERDE_GRILLA, (cx, cy), (x, y), 1)
        tx = fuente_p.render(f"{a}°", True, GRIS)
        pantalla.blit(tx, (x - 10, y - 12))
 
def dibujar_trail():
    trail = list(trail_angulos)
    n = len(trail)
    for i, a in enumerate(trail):
        alpha = (i + 1) / n
        g_val = int(5 + alpha * 90) 
        color = (0, g_val, int(g_val * 0.2))
        x, y  = polar_a_pixel(a, DISTANCIA_MAX)
        pygame.draw.line(pantalla, color, (cx, cy), (x, y), 1)
 
def dibujar_barrido():

    x, y = polar_a_pixel(angulo_actual, DISTANCIA_MAX)
    pygame.draw.line(pantalla, VERDE, (cx, cy), (x, y), 2)
 
def dibujar_puntos():
    for a, d in puntos:
        if d >= SIN_OBJETO or d < 2:
            continue
        pygame.draw.circle(pantalla, (0, 70, 35), polar_a_pixel(a, d), 1)
 
def dibujar_objetos_radar():
    ahora = time.time()
    for b, obj in objetos.items():
        if ahora - obj['tiempo'] > MAX_AGE_OBJ:
            continue
        color  = color_obj(b)
        a, d   = obj['angulo'], obj['dist']
        px, py = polar_a_pixel(a, d)
 

        pulso = int(4 + 2 * math.sin(ahora * 5))
        pygame.draw.circle(pantalla, color, (px, py), pulso + 4, 1)
        pygame.draw.circle(pantalla, color, (px, py), 4) 
 
def dibujar_borde_radar():
    pygame.draw.circle(pantalla, VERDE_TENUE, (cx, cy), RADIO_RADAR, 1)
    pygame.draw.line(pantalla, VERDE_TENUE, (cx - RADIO_RADAR, cy), (cx + RADIO_RADAR, cy), 1)
 
def dibujar_info():
    modo_txt   = "DEMO" if not conectado else "ONLINE"
    color_modo = AMARILLO if not conectado else VERDE
    lineas = [
        ("[ SISTEMA RADAR 2D ]",   VERDE,      fuente_g),
        (f"Estado: {modo_txt}",    color_modo, fuente),
        (f"Ángulo: {angulo_actual}°", BLANCO,    fuente),
        (f"Objetos activos: {len(objetos)}", GRIS_CLARO, fuente),
    ]
    y_off = 12
    for txt, color, f in lineas:
        pantalla.blit(f.render(txt, True, color), (15, y_off))
        y_off += f.size("A")[1] + 3
 
# =============================================
# DIBUJO DEL GRÁFICO DE TRAYECTORIA
# =============================================
def dibujar_panel_grafico():
    pygame.draw.rect(pantalla, PANEL_BG, (ANCHO_RADAR, 0, ANCHO_GRAF, ALTO))
    pygame.draw.line(pantalla, PANEL_BORDE, (ANCHO_RADAR, 0), (ANCHO_RADAR, ALTO), 1)
 
    titulo = fuente_g.render("ANÁLISIS DE TRAYECTORIA", True, BLANCO)
    pantalla.blit(titulo, (GRAF_X + 15, 15))
 
    #Se define límites fijos y más pequeños
    NUEVO_ORIG_Y  = 200   
    NUEVO_PLOT_H  = 130   
 
    pygame.draw.rect(pantalla, (6, 8, 7), (ORIG_X, NUEVO_ORIG_Y - NUEVO_PLOT_H, PLOT_W, NUEVO_PLOT_H))
    pygame.draw.rect(pantalla, PANEL_BORDE, (ORIG_X, NUEVO_ORIG_Y - NUEVO_PLOT_H, PLOT_W, NUEVO_PLOT_H), 1)
 
    pasos_x, pasos_y = 4, 4
    for i in range(pasos_x + 1):
        gx = ORIG_X + int(i * PLOT_W / pasos_x)
        pygame.draw.line(pantalla, (12, 22, 16), (gx, NUEVO_ORIG_Y - NUEVO_PLOT_H), (gx, NUEVO_ORIG_Y), 1)
        val_x = int(GRAF_X_MIN + i * (GRAF_X_MAX - GRAF_X_MIN) / pasos_x)
        lbl = fuente_t.render(f"{val_x}", True, GRIS)
        pantalla.blit(lbl, (gx - lbl.get_width() // 2, NUEVO_ORIG_Y + 4))
 
    for i in range(pasos_y + 1):
        gy = NUEVO_ORIG_Y - int(i * NUEVO_PLOT_H / pasos_y)
        pygame.draw.line(pantalla, (12, 22, 16), (ORIG_X, gy), (ORIG_X + PLOT_W, gy), 1)
        val_y = int(GRAF_Y_MIN + i * (GRAF_Y_MAX - GRAF_Y_MIN) / pasos_y)
        lbl = fuente_t.render(f"{val_y}", True, GRIS)
        pantalla.blit(lbl, (ORIG_X - lbl.get_width() - 4, gy - 5))
 

    x0_px = ORIG_X + int((0 - GRAF_X_MIN) / (GRAF_X_MAX - GRAF_X_MIN) * PLOT_W)
    pygame.draw.line(pantalla, PANEL_BORDE, (x0_px, NUEVO_ORIG_Y - NUEVO_PLOT_H), (x0_px, NUEVO_ORIG_Y), 1)
 
    ahora = time.time()
    
    Y_DIVISOR = NUEVO_ORIG_Y + 25
    pygame.draw.line(pantalla, PANEL_BORDE, (GRAF_X + 10, Y_DIVISOR), (ANCHO - 10, Y_DIVISOR), 1)
    
    subtitulo_telemetria = fuente_g.render("TELEMETRÍA EN TIEMPO REAL", True, GRIS_CLARO)
    pantalla.blit(subtitulo_telemetria, (GRAF_X + 15, Y_DIVISOR + 10))
    
    TELEMETRIA_BASE_Y = Y_DIVISOR + 35
 
    for idx, (b, obj) in enumerate(objetos.items()):
        if ahora - obj['tiempo'] > MAX_AGE_OBJ:
            continue
        color = color_obj(b)

        hist_g = []
        for xc, yc, ts in obj['hist']:
            yp_graf = -yc
            px = ORIG_X + int((xc - GRAF_X_MIN) / (GRAF_X_MAX - GRAF_X_MIN) * PLOT_W)
            py = NUEVO_ORIG_Y - int((yp_graf - GRAF_Y_MIN) / (GRAF_Y_MAX - GRAF_Y_MIN) * NUEVO_PLOT_H)
            hist_g.append((px, py))
            
        pts_en_rango = [p for p in hist_g if ORIG_X <= p[0] <= ORIG_X + PLOT_W and NUEVO_ORIG_Y - NUEVO_PLOT_H <= p[1] <= NUEVO_ORIG_Y]
        if len(pts_en_rango) >= 2:
            pygame.draw.lines(pantalla, (color[0]//2, color[1]//2, color[2]//2), False, pts_en_rango, 1)
 
        if hist_g:
            ux, uy = hist_g[-1]
            if ORIG_X <= ux <= ORIG_X + PLOT_W and NUEVO_ORIG_Y - NUEVO_PLOT_H <= uy <= NUEVO_ORIG_Y:
                pygame.draw.circle(pantalla, color, (ux, uy), 4)

        pred_g_nuevo = []
        for xp, yp_cm in obj['pred_cm']:
            px = ORIG_X + int((xp - GRAF_X_MIN) / (GRAF_X_MAX - GRAF_X_MIN) * PLOT_W)
            py = NUEVO_ORIG_Y - int((yp_cm - GRAF_Y_MIN) / (GRAF_Y_MAX - GRAF_Y_MIN) * NUEVO_PLOT_H)
            pred_g_nuevo.append((px, py))
 
        if len(pred_g_nuevo) >= 2:
            for j in range(0, len(pred_g_nuevo) - 1, 2):
                p1, p2 = pred_g_nuevo[j], pred_g_nuevo[j + 1]
                if (ORIG_X <= p1[0] <= ORIG_X + PLOT_W and NUEVO_ORIG_Y - NUEVO_PLOT_H <= p1[1] <= NUEVO_ORIG_Y) and \
                   (ORIG_X <= p2[0] <= ORIG_X + PLOT_W and NUEVO_ORIG_Y - NUEVO_PLOT_H <= p2[1] <= NUEVO_ORIG_Y):
                    pygame.draw.line(pantalla, AMARILLO, p1, p2, 1)
 
            ep = pred_g_nuevo[-1]
            if ORIG_X <= ep[0] <= ORIG_X + PLOT_W and NUEVO_ORIG_Y - NUEVO_PLOT_H <= ep[1] <= NUEVO_ORIG_Y:
                pygame.draw.circle(pantalla, AMARILLO, ep, 3)
 
        y_renglon = TELEMETRIA_BASE_Y + (idx * 26)
        
        if y_renglon < ALTO - 20:
            lbl_id = fuente_t.render(
                f"OBJ {idx+1} -> Dist: {obj['dist']:.0f}cm | Vel: {obj['vel']:.1f}cm/s",
                True, color)
            pantalla.blit(lbl_id, (GRAF_X + 15, y_renglon))
            
            if obj['pred_cm']:
                ex_cm, ey_cm = obj['pred_cm'][-1]
                lbl_imp = fuente_t.render(
                    f"       ↳ Proyección Impacto: ({ex_cm:.0f}, {ey_cm:.0f}) cm", 
                    True, AMARILLO)
                pantalla.blit(lbl_imp, (GRAF_X + 15, y_renglon + 12))
 
# =============================================
# LOOP 
# =============================================
corriendo      = True
ultimo_demo    = time.time()
DEMO_INTERVALO = 0.03
 
while corriendo:
    for evento in pygame.event.get():
        if evento.type == pygame.QUIT:
            corriendo = False
        if evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE:
            corriendo = False
 
    angulo_nuevo = None
    dist_nueva   = None
 
    if conectado:
        if puerto.in_waiting > 0:
            try:
                linea  = puerto.readline().decode('utf-8').strip()
                partes = linea.split(',')
                if len(partes) == 2:
                    angulo_nuevo = int(partes[0])
                    dist_nueva   = float(partes[1])
            except (ValueError, IndexError, UnicodeDecodeError):
                pass
    else:
        ahora = time.time()
        if ahora - ultimo_demo >= DEMO_INTERVALO:
            angulo_nuevo, dist_nueva = demo_tick()
            ultimo_demo = ahora
 
    if angulo_nuevo is not None and dist_nueva is not None:
        angulo_actual = angulo_nuevo
        trail_angulos.append(angulo_actual)
        puntos.append((angulo_nuevo, dist_nueva))
        actualizar_objeto(angulo_nuevo, dist_nueva, time.time())
 
    limpiar_objetos_viejos()
 
    # Trazado de Capas Gráficas
    dibujar_fondo()
    dibujar_circulos()
    dibujar_lineas_angulo()
    dibujar_borde_radar()
    dibujar_trail()
    dibujar_barrido()
    dibujar_puntos()
    dibujar_objetos_radar()
    dibujar_info()
    dibujar_panel_grafico()     
 
    pygame.display.flip()
    reloj.tick(60)
 
if conectado:
    puerto.close()
pygame.quit()