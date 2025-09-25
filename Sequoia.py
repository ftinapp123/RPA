#!/usr/bin/env python3
"""
pixhawk_sequoia.py

Sistema de trigger para fotografía aérea:
Pixhawk → Raspberry Pi Zero → Parrot Sequoia

El autopiloto Pixhawk envía pulsos TTL de 5V al GPIO de la RPi Zero,
que ejecuta comandos gphoto2 para capturar imágenes con la Parrot Sequoia.

Autor: Sistema automatizado de captura aérea
Fecha: 2025

Hardware:
- Raspberry Pi Zero W (recomendada por WiFi integrado)
- Parrot Sequoia conectada por USB
- Conexión GPIO desde Pixhawk

Instalación:
sudo apt update
sudo apt install gphoto2 libgphoto2-dev python3-rpi.gpio
pip3 install RPi.GPIO

Conexiones:
Pixhawk AUX OUT → RPi GPIO 18 (Pin 12)
Pixhawk GND    → RPi GND (Pin 6)
Pixhawk 5V     → RPi 5V (Pin 2) - Opcional para alimentar RPi
"""

import RPi.GPIO as GPIO
import subprocess
import time
import logging
import threading
from datetime import datetime
import os
import json

# Configuración de logging
log_file = '/home/frank/camera_trigger.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)


class PixhawkSequoiaTrigger:
    def __init__(self, trigger_pin=18, status_led_pin=24):
        # Configuración de pines
        self.trigger_pin = trigger_pin  # Pin para recibir señal del Pixhawk
        self.status_led_pin = status_led_pin  # Pin para LED de estado (opcional)

        # Variables de control
        self.capture_count = 0
        self.last_trigger_time = 0
        self.is_capturing = False
        self.session_start_time = datetime.now()

        # Configuración de captura
        self.photo_directory = '/home/pi/aerial_photos'
        self.debounce_time = 0.1  # 100ms - ajustar según frecuencia del Pixhawk
        self.capture_timeout = 30  # 30 segundos timeout por captura

        # Estadísticas
        self.stats = {
            'total_triggers': 0,
            'successful_captures': 0,
            'failed_captures': 0,
            'session_start': self.session_start_time.isoformat()
        }

        # Inicializar
        self.setup_directories()
        self.setup_gpio()
        self.test_camera_connection()

    def setup_directories(self):
        """Crear directorios necesarios"""
        try:
            os.makedirs(self.photo_directory, exist_ok=True)
            logger.info(f"Directorio de fotos: {self.photo_directory}")
        except Exception as e:
            logger.error(f"Error creando directorios: {e}")

    def setup_gpio(self):
        """Configurar pines GPIO"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Pin de trigger - entrada con pull-down (espera 5V del Pixhawk)
            GPIO.setup(self.trigger_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

            # Pin de LED de estado (opcional)
            if self.status_led_pin:
                GPIO.setup(self.status_led_pin, GPIO.OUT)
                GPIO.output(self.status_led_pin, GPIO.LOW)

            # Configurar interrupción en flanco ascendente (pulso positivo de 5V)
            GPIO.add_event_detect(
                self.trigger_pin,
                GPIO.RISING,  # Flanco ascendente para pulso TTL
                callback=self.pixhawk_trigger_callback,
                bouncetime=100  # 100ms debounce por hardware
            )

            logger.info(f"GPIO configurado - Pin trigger: {self.trigger_pin}")
            self.blink_status_led(3, 0.2)  # 3 parpadeos rápidos = listo

        except Exception as e:
            logger.error(f"Error configurando GPIO: {e}")

    def test_camera_connection(self):
        """Probar conexión inicial con la cámara"""
        try:
            logger.info("Probando conexión con Parrot Sequoia...")

            result = subprocess.run([
                'gphoto2', '--auto-detect'
            ], capture_output=True, text=True, timeout=10)

            if 'Parrot' in result.stdout or 'Sequoia' in result.stdout:
                logger.info("✓ Parrot Sequoia detectada correctamente")
                self.blink_status_led(2, 0.5)  # 2 parpadeos lentos = cámara OK
                return True
            else:
                logger.warning("⚠ Cámara no detectada en la prueba inicial")
                logger.debug(f"Salida gphoto2: {result.stdout}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("✗ Timeout probando conexión de cámara")
            return False
        except Exception as e:
            logger.error(f"✗ Error probando cámara: {e}")
            return False

    def pixhawk_trigger_callback(self, channel):
        """Callback ejecutado cuando el Pixhawk envía un pulso"""
        current_time = time.time()

        # Debounce por software
        if current_time - self.last_trigger_time < self.debounce_time:
            return

        self.last_trigger_time = current_time
        self.stats['total_triggers'] += 1

        if self.is_capturing:
            logger.warning(f"Trigger #{self.stats['total_triggers']} ignorado - captura en proceso")
            return

        logger.info(f"¡TRIGGER PIXHAWK #{self.stats['total_triggers']} detectado en pin {channel}!")

        # Encender LED de estado
        self.set_status_led(True)

        # Ejecutar captura en hilo separado para no bloquear GPIO
        capture_thread = threading.Thread(
            target=self.execute_capture,
            args=(self.stats['total_triggers'],),
            daemon=True
        )
        capture_thread.start()

    def execute_capture(self, trigger_number):
        """Ejecutar captura de imagen"""
        self.is_capturing = True
        start_time = time.time()

        try:
            # Generar nombre de archivo con timestamp y número de trigger
            timestamp = datetime.now()
            filename = f"aerial_{timestamp.strftime('%Y%m%d_%H%M%S')}_T{trigger_number:05d}.jpg"
            filepath = os.path.join(self.photo_directory, filename)

            logger.info(f"Ejecutando captura #{trigger_number}: {filename}")

            # Ejecutar comando gphoto2
            result = subprocess.run([
                'gphoto2',
                '--capture-image-and-download',
                '--filename', filepath,
                '--force-overwrite'
            ], capture_output=True, text=True, timeout=self.capture_timeout)

            capture_time = time.time() - start_time

            if result.returncode == 0:
                # Captura exitosa
                self.capture_count += 1
                self.stats['successful_captures'] += 1

                # Obtener tamaño del archivo
                try:
                    file_size = os.path.getsize(filepath) / 1024 / 1024  # MB
                    logger.info(
                        f"✓ Captura #{trigger_number} EXITOSA - {filename} ({file_size:.1f}MB) en {capture_time:.1f}s")
                except:
                    logger.info(f"✓ Captura #{trigger_number} EXITOSA - {filename} en {capture_time:.1f}s")

                # Parpadeo de éxito
                self.blink_status_led(1, 0.1)  # 1 parpadeo rápido = éxito

            else:
                # Error en captura
                self.stats['failed_captures'] += 1
                logger.error(f"✗ Captura #{trigger_number} FALLÓ en {capture_time:.1f}s")
                logger.error(f"Error gphoto2: {result.stderr}")

                # Parpadeo de error
                self.blink_status_led(3, 0.1)  # 3 parpadeos rápidos = error

        except subprocess.TimeoutExpired:
            self.stats['failed_captures'] += 1
            logger.error(f"✗ Captura #{trigger_number} TIMEOUT después de {self.capture_timeout}s")
            self.blink_status_led(5, 0.1)  # 5 parpadeos = timeout

        except Exception as e:
            self.stats['failed_captures'] += 1
            logger.error(f"✗ Error inesperado en captura #{trigger_number}: {e}")
            self.blink_status_led(3, 0.1)

        finally:
            self.is_capturing = False
            self.set_status_led(False)

    def set_status_led(self, state):
        """Controlar LED de estado"""
        if self.status_led_pin:
            GPIO.output(self.status_led_pin, GPIO.HIGH if state else GPIO.LOW)

    def blink_status_led(self, times, delay):
        """Parpadear LED de estado"""
        if not self.status_led_pin:
            return

        def blink():
            for _ in range(times):
                GPIO.output(self.status_led_pin, GPIO.HIGH)
                time.sleep(delay)
                GPIO.output(self.status_led_pin, GPIO.LOW)
                time.sleep(delay)

        # Ejecutar parpadeo en hilo separado
        blink_thread = threading.Thread(target=blink, daemon=True)
        blink_thread.start()

    def get_statistics(self):
        """Obtener estadísticas del sistema"""
        uptime = datetime.now() - self.session_start_time
        success_rate = (self.stats['successful_captures'] / max(self.stats['total_triggers'], 1)) * 100

        return {
            **self.stats,
            'uptime_seconds': uptime.total_seconds(),
            'success_rate_percent': success_rate,
            'current_status': 'capturing' if self.is_capturing else 'ready'
        }

    def save_statistics(self):
        """Guardar estadísticas en archivo JSON"""
        try:
            stats_file = os.path.join(self.photo_directory, 'session_stats.json')
            with open(stats_file, 'w') as f:
                json.dump(self.get_statistics(), f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando estadísticas: {e}")

    def print_status(self):
        """Imprimir estado actual del sistema"""
        stats = self.get_statistics()
        print("\n" + "=" * 50)
        print("ESTADO DEL SISTEMA PIXHAWK-SEQUOIA")
        print("=" * 50)
        print(f"Triggers recibidos:    {stats['total_triggers']}")
        print(f"Capturas exitosas:     {stats['successful_captures']}")
        print(f"Capturas fallidas:     {stats['failed_captures']}")
        print(f"Tasa de éxito:         {stats['success_rate_percent']:.1f}%")
        print(f"Estado actual:         {stats['current_status']}")
        print(
            f"Tiempo de operación:   {int(stats['uptime_seconds'] // 3600):02d}:{int((stats['uptime_seconds'] % 3600) // 60):02d}:{int(stats['uptime_seconds'] % 60):02d}")
        print(f"Directorio fotos:      {self.photo_directory}")
        print("=" * 50)

    def cleanup(self):
        """Limpiar recursos al salir"""
        logger.info("Limpiando recursos...")
        self.save_statistics()
        GPIO.cleanup()
        logger.info("Sistema detenido correctamente")


def test_trigger(trigger_system):
    """Función para probar el sistema manualmente"""
    print("\n--- MODO PRUEBA ---")
    print("Simulando pulso del Pixhawk...")

    # Simular trigger
    trigger_system.pixhawk_trigger_callback(trigger_system.trigger_pin)

    # Esperar a que termine la captura
    time.sleep(3)
    while trigger_system.is_capturing:
        print("Esperando que termine la captura...")
        time.sleep(1)

    print("Prueba completada")


def main():
    """Función principal"""
    print("=" * 60)
    print("SISTEMA TRIGGER PIXHAWK → RASPBERRY PI → PARROT SEQUOIA")
    print("=" * 60)

    # Crear sistema de trigger
    trigger_system = PixhawkSequoiaTrigger(
        trigger_pin=18,  # GPIO 18 (Pin 12) - conectar señal del Pixhawk
        status_led_pin=24  # GPIO 24 (Pin 18) - LED indicador opcional
    )

    try:
        print(f"\nSistema iniciado correctamente")
        print(f"Pin de trigger: GPIO {trigger_system.trigger_pin}")
        print(f"Directorio de fotos: {trigger_system.photo_directory}")
        print("\nEsperando señales del Pixhawk...")
        print("Presiona Ctrl+C para salir")
        print("(Presiona 't' + Enter para trigger manual, 's' + Enter para estadísticas)\n")

        # Mostrar estado cada 30 segundos
        last_status_time = 0

        # Loop principal
        while True:
            current_time = time.time()

            # Mostrar estado periódicamente
            if current_time - last_status_time > 30:
                trigger_system.print_status()
                last_status_time = current_time

            # Comando de prueba por teclado (opcional)
            try:
                import select
                import sys

                if select.select([sys.stdin], [], [], 0.1)[0]:
                    command = input().strip().lower()
                    if command == 't':
                        test_trigger(trigger_system)
                    elif command == 's':
                        trigger_system.print_status()
                    elif command == 'q':
                        break
            except:
                pass

            time.sleep(0.1)  # Small delay to prevent high CPU usage

    except KeyboardInterrupt:
        print("\n\nInterrumpido por usuario")
        trigger_system.print_status()

    except Exception as e:
        logger.error(f"Error inesperado: {e}")

    finally:
        trigger_system.cleanup()


if __name__ == "__main__":
    main()