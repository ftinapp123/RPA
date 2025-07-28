from pymavlink import mavutil
from pymavlink.dialects.v20 import common as mavlink2
import time

#--------------------------
# PARAMETERS
#--------------------------
TARGET_ALTITUDE = 20  # Takeoff altitude in meters

# Replace these with real coordinates in SITL if needed
WAYPOINTS = [
    (-36.8333201, -73.0334569, 35),  # WP1
    (-36.8331226, -73.0301632, 25),  # WP2
]

#--------------------------
# 1. CONNECT TO SITL
#--------------------------
master = mavutil.mavlink_connection('udp:0.0.0.0:14550')
print("Waiting for heartbeat...")
master.wait_heartbeat()
print(f"Connected to system {master.target_system}, component {master.target_component}")

#--------------------------
# 2. SET MODE TO GUIDED
#--------------------------
mode = 'GUIDED'
mode_id = master.mode_mapping()[mode]
master.mav.set_mode_send(
    master.target_system,
    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
    mode_id)
print(f"Set mode to {mode}")
time.sleep(1)

#--------------------------
# 3. ARM THE DRONE
#--------------------------
master.mav.command_long_send(
    master.target_system,
    master.target_component,
    mavlink2.MAV_CMD_COMPONENT_ARM_DISARM,
    0, 1, 0, 0, 0, 0, 0, 0)
master.motors_armed_wait()
print("Drone armed!")

#--------------------------
# 4. TAKEOFF
#--------------------------
master.mav.command_long_send(
    master.target_system,
    master.target_component,
    mavlink2.MAV_CMD_NAV_TAKEOFF,
    0, 0, 0, 0, 0, 0, 0, TARGET_ALTITUDE)
print(f"Takeoff to {TARGET_ALTITUDE} m")
time.sleep(8)  # Wait a few seconds for takeoff

#--------------------------
# 5. UPLOAD MISSION
#--------------------------
print("Uploading mission...")

master.waypoint_clear_all_send()
master.waypoint_count_send(len(WAYPOINTS))

for i, (lat, lon, alt) in enumerate(WAYPOINTS):
    msg = mavlink2.MAVLink_mission_item_message(
        target_system=master.target_system,
        target_component=master.target_component,
        seq=i,
        frame=mavlink2.MAV_FRAME_GLOBAL_RELATIVE_ALT,
        command=mavlink2.MAV_CMD_NAV_WAYPOINT,
        current=1 if i == 0 else 0,
        autocontinue=1,
        param1=0, param2=0, param3=0, param4=0,
        x=lat,
        y=lon,
        z=alt,
        mission_type=0
    )
    master.mav.send(msg)
    ack = master.recv_match(type='MISSION_REQUEST', blocking=True)
    print(f"Sent WP {i}, got request for seq {ack.seq}")

print("Mission uploaded!")

#--------------------------
# 6. START MISSION
#--------------------------
print("Switching to AUTO mode...")
mode = 'AUTO'
mode_id = master.mode_mapping()[mode]
master.mav.set_mode_send(
    master.target_system,
    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
    mode_id)
time.sleep(1)

print("Mission started!")

#--------------------------
# 7. MONITOR LOCATION (Optional)
#--------------------------
try:
    while True:
        msg = master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=10)
        if msg:
            lat = msg.lat / 1e7
            lon = msg.lon / 1e7
            alt = msg.relative_alt / 1000.0
            print(f"Lat: {lat}, Lon: {lon}, Alt: {alt:.1f} m")
except KeyboardInterrupt:
    print("Stopped by user.")
