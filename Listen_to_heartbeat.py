from pymavlink import mavutil

# Connect to UDP port 14550 where SITL sends the data
connection = mavutil.mavlink_connection('udp:0.0.0.0:14550')

# Wait for the first heartbeat
print("Waiting for heartbeat...")
connection.wait_heartbeat()
print(f"Heartbeat from system (system {connection.target_system} component {connection.target_component})")

# Request some telemetry (like GPS)
while True:
    msg = connection.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
    print(f"Lat: {msg.lat / 1e7}, Lon: {msg.lon / 1e7}, Alt: {msg.relative_alt / 1000.0} m")
