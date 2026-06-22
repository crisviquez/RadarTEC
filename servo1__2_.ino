#include <Servo.h>

Servo servo;

const int TRIG = 3;
const int ECHO = 5;
const int LED  = 11;
const int SERVOPIN = 9;


int angulo    = 0;
int direccion = 1;

unsigned long ultimoMovimiento = 0;
const int intervaloServo = 20;

// Parpadeo del LED de alerta (independiente del barrido del servo)
unsigned long ultimoToggleLed = 0;
const int intervaloLed = 500; // ms
bool estadoLed = false;

const int DIST_MAX   = 100;     // cm
const int SIN_OBJETO = 400;     // "nada detectado"


long medirDistancia() {
  digitalWrite(TRIG, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);

  // Pausa de 30ms, evita que el barrido se congele si no hay eco
  long tiempoEco = pulseIn(ECHO, HIGH, 30000);
  if (tiempoEco == 0) return SIN_OBJETO;

  long distancia = tiempoEco / 58;
  return (distancia > DIST_MAX) ? SIN_OBJETO : distancia;
}


// Setup
void setup() {
  servo.attach(SERVOPIN);

  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
  pinMode(LED, OUTPUT);

  Serial.begin(9600);
}


void loop() {
  unsigned long ahora = millis();

  // LED rojo intermitente de alerta (parpadea siempre)
  if (ahora - ultimoToggleLed >= intervaloLed) {
    ultimoToggleLed = ahora;
    estadoLed = !estadoLed;
    digitalWrite(LED, estadoLed ? HIGH : LOW);
  }

  // Movimiento del servo y medicion
  if (ahora - ultimoMovimiento >= intervaloServo) {
    ultimoMovimiento = ahora;

    servo.write(angulo);
    delay(15);

    long distancia = medirDistancia();

    // Enviar datos
    Serial.print(angulo);
    Serial.print(",");
    Serial.println(distancia);

    // Cambiar angulo
    angulo += direccion;
    if (angulo >= 180 || angulo <= 0) {
      direccion *= -1;
    }
  }
}
