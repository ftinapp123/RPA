from pymavlink import mavutil
import time

# ======================
# CONFIGURACIÓN
# ======================
serial_port = '/dev/serial0'  # Puerto UART (ajusta si usas otro)
baud_rate = 57600  # Baudios típicos de TELEM2

FLIGHT_MODE = {
    "STABILIZE": 0,
    "ACRO": 1,
    "ALT_HOLD": 2,
    "AUTO": 3,
    "GUIDED": 4,
    "LOITER": 5,
    "RTL": 6,
    "LAND": 9,
    "POSHOLD": 16,
    "BRAKE": 17
}


def arm_desarm(status):
    if status == "arm":
        master.mav.command_long_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,  # Confirmación
            1,  # Param1 = 1 para armar
            0, 0, 0, 0, 0, 0
        )
    if status == "desarm":
        master.mav.command_long_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,  # Confirmación
            0,  # Param1 = 0 para desarmar
            0, 0, 0, 0, 0, 0
        )


# ======================
# CONEXIÓN
# ======================
print(f"Conectando a {serial_port} a {baud_rate} baudios...")
master = mavutil.mavlink_connection(serial_port, baud=baud_rate)

print("Esperando HEARTBEAT...")
master.wait_heartbeat()
print(f"Conectado: sysid={master.target_system}, compid={master.target_component}")

# ======================
# ARMAR DRON
# ======================
print("Armando el dron...")
arm_desarm("arm")

time.sleep(2)

# ======================
# CAMBIAR A STABILIZE
# ======================
print("Cambiando a modo STABILIZE...")
master.set_mode(FLIGHT_MODE["STABILIZE"])  # Modo 0 = STABILIZE en ArduCopter
time.sleep(4)

# ======================
# CAMBIAR A ALT_HOLD
# ======================
print("Cambiando a modo ALT_HOLD...")
master.set_mode(FLIGHT_MODE["ALT_HOLD"])  # Modo 2 = ALT_HOLD en ArduCopter
time.sleep(5)

# ======================
# DESARMAR DRON
# ======================
print("Desarmando el dron...")
arm_desarm("desarm")
print("Proceso completo.")