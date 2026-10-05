#!/usr/bin/env python3

# Pico W MPU-6050 & ADXL313 Data Collection
# Collects accelerometer data from MPU-6050 and ADXL313 sensors on a Raspberry Pi Pico W
# Provides a web interface to view the collected data in CSV format and restart the collection process.
# J.Beale 10-Oct-2026

import network
import socket
import time
import machine
import ntptime
import json
from config import SSID, PASSWORD
from mpu6050 import MPU6050

# WiFi setup
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

while not wlan.isconnected():
    print("Connecting...")
    time.sleep(1)

print(f"Connected: {wlan.ifconfig()}")

# Sync time from NTP
try:
    ntptime.settime()
    print("Time synced from NTP")
except:
    print("NTP sync failed")

# I2C setup
i2c = machine.I2C(0, scl=machine.Pin(17), sda=machine.Pin(16), freq=400000)
mpu = MPU6050(i2c, 0x68)

# ADXL313 setup
class ADXL313:
    def __init__(self, i2c, addr=0x1D):
        self.i2c = i2c
        self.addr = addr
        self.SENSITIVITY = 1024.0  # LSB/g for ±16g range

        # Check device is present
        if addr not in i2c.scan():
            raise OSError(f"ADXL313 not found at address 0x{addr:02x}")

        # Enable measurement mode
        self.i2c.writeto_mem(self.addr, 0x2D, bytes([0x08]))
        # Full resolution, ±16g
        self.i2c.writeto_mem(self.addr, 0x31, bytes([0x0B]))
        print("ADXL313 initialized")

    def read(self):
        """Read acceleration values"""
        data = self.i2c.readfrom_mem(self.addr, 0x32, 6)

        # Convert 6 bytes to three signed 16-bit values
        x = data[0] | (data[1] << 8)
        y = data[2] | (data[3] << 8)
        z = data[4] | (data[5] << 8)

        if x & 0x8000: x -= 65536
        if y & 0x8000: y -= 65536
        if z & 0x8000: z -= 65536

        return {
            'accel_x': x / self.SENSITIVITY,
            'accel_y': y / self.SENSITIVITY,
            'accel_z': z / self.SENSITIVITY
        }

adxl = ADXL313(i2c, 0x1D)

# Collection state
reading_count = 0
reading_history = []
start_epoch = None
is_collecting = False
last_reading_time = 0
restart_requested = False

def start_collection():
    global reading_count, reading_history, start_epoch, is_collecting, last_reading_time, restart_requested
    reading_count = 0
    reading_history = []
    start_epoch = None
    is_collecting = True
    last_reading_time = time.ticks_ms()
    restart_requested = False
    print("Started new collection")

def handle_http_requests():
    """Process any pending HTTP requests without blocking"""
    try:
        conn, addr = server.accept()
        conn.settimeout(1.0)
        try:
            request = conn.recv(1024).decode()
            request_line = request.split('\r\n')[0]
            response = handle_request(request_line)
            conn.sendall(response.encode())
        except OSError:
            pass
        finally:
            conn.close()
    except OSError:
        pass

def read_averaged_nonblocking(sample_count=1000, chunk_size=100):
    global restart_requested
    mpu_sum_x = mpu_sum_y = mpu_sum_z = mpu_sum_temp = 0
    adxl_sum_x = adxl_sum_y = adxl_sum_z = 0
    total_samples = 0

    # Read in chunks, processing HTTP between each chunk
    for chunk_start in range(0, sample_count, chunk_size):
        chunk_end = min(chunk_start + chunk_size, sample_count)

        # Read a chunk of samples
        for i in range(chunk_start, chunk_end):
            # Check if restart was requested mid-read
            if restart_requested:
                print("Restart requested during read, aborting")
                break

            # Read both sensors interleaved
            mpu_reading = mpu.read()
            mpu_sum_x += mpu_reading['accel_x']
            mpu_sum_y += mpu_reading['accel_y']
            mpu_sum_z += mpu_reading['accel_z']
            mpu_sum_temp += mpu_reading['temp_c']

            adxl_reading = adxl.read()
            adxl_sum_x += adxl_reading['accel_x']
            adxl_sum_y += adxl_reading['accel_y']
            adxl_sum_z += adxl_reading['accel_z']

            total_samples += 1

        # After each chunk, process any waiting HTTP requests
        handle_http_requests()

        if restart_requested:
            break

    samples_taken = total_samples

    return {
        'mpu_x': mpu_sum_x / samples_taken if samples_taken > 0 else 0,
        'mpu_y': mpu_sum_y / samples_taken if samples_taken > 0 else 0,
        'mpu_z': mpu_sum_z / samples_taken if samples_taken > 0 else 0,
        'temp_c': mpu_sum_temp / samples_taken if samples_taken > 0 else 0,
        'adxl_x': adxl_sum_x / samples_taken if samples_taken > 0 else 0,
        'adxl_y': adxl_sum_y / samples_taken if samples_taken > 0 else 0,
        'adxl_z': adxl_sum_z / samples_taken if samples_taken > 0 else 0,
        'samples': samples_taken
    }

def add_reading():
    global reading_count, reading_history, start_epoch, is_collecting, last_reading_time, restart_requested
    reading_count += 1
    epoch = int(time.time())
    reading = read_averaged_nonblocking(1000)
    reading_history.append((epoch, reading_count,
                           reading['mpu_x'], reading['mpu_y'], reading['mpu_z'], reading['temp_c'],
                           reading['adxl_x'], reading['adxl_y'], reading['adxl_z'],
                           reading['samples']))

    if start_epoch is None:
        start_epoch = epoch

    print(f"Reading #{reading_count}: {reading['samples']} samples")

    if reading_count >= 20:
        is_collecting = False
        print(f"Collection complete: {reading_count} readings")

    last_reading_time = time.ticks_ms()

def build_csv():
    csv = ""
    if reading_history:
        start_e = reading_history[0][0]
        last_e = reading_history[-1][0]
        tm_start = time.gmtime(start_e)
        tm_last = time.gmtime(last_e)
        start_str = f"{tm_start[0]:04d}-{tm_start[1]:02d}-{tm_start[2]:02d} {tm_start[3]:02d}:{tm_start[4]:02d}:{tm_start[5]:02d}"
        last_str = f"{tm_last[0]:04d}-{tm_last[1]:02d}-{tm_last[2]:02d} {tm_last[3]:02d}:{tm_last[4]:02d}:{tm_last[5]:02d}"
        csv = f"# Start: {start_str}  Last: {last_str}\n"
    csv += "epoch,n,MPU_X,MPU_Y,MPU_Z,degC,ADXL_X,ADXL_Y,ADXL_Z,samples\n"
    for e, n, mx, my, mz, t, ax, ay, az, s in reading_history:
        csv += f"{e},{n},{mx:.4f},{my:.4f},{mz:.4f},{t:.2f},{ax:.4f},{ay:.4f},{az:.4f},{s}\n"
    return csv

def handle_request(request_line):
    global restart_requested

    if 'GET /restart' in request_line:
        restart_requested = True
        print("Restart requested by user")
        return "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 0\r\n\r\n"

    elif 'GET /status' in request_line:
        readings_list = [[e, n, float(f"{mx:.4f}"), float(f"{my:.4f}"), float(f"{mz:.4f}"), float(f"{t:.2f}"), float(f"{ax:.4f}"), float(f"{ay:.4f}"), float(f"{az:.4f}"), s]
                        for e, n, mx, my, mz, t, ax, ay, az, s in reading_history]
        data = {"is_collecting": is_collecting, "reading_count": reading_count, "readings": readings_list}
        json_text = json.dumps(data)
        return f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(json_text)}\r\n\r\n{json_text}"

    elif 'GET / ' in request_line:
        csv = build_csv()
        if is_collecting:
            status = f"Reading {reading_count} of 20"
            button = '<button onclick="fetch(\'/restart\').then(() => location.reload())">Restart</button>'
            refresh_meta = '<meta http-equiv="refresh" content="1">'
        else:
            status = "Complete"
            button = '<button onclick="fetch(\'/restart\').then(() => location.reload())">Restart</button>'
            refresh_meta = ''

        html = f"""<html>
<head>
<title>Pico W MPU-6050 & ADXL313 Data Collection</title>
{refresh_meta}
<style>
body {{ font-family: monospace; }}
h1 {{ color: #333; }}
button {{ padding: 8px 16px; font-size: 14px; cursor: pointer; }}
#data {{ border: 1px solid #ccc; padding: 10px; background: #f9f9f9; white-space: pre-wrap; font-size: 12px; }}
</style>
</head>
<body>
<h1>{status} <span style="margin-left: 20px;">{button}</span></h1>
<pre>{csv}</pre>
</body>
</html>"""
        return f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(html)}\r\n\r\n{html}"

    else:
        return "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n"

# HTTP server
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('', 80))
server.listen(1)
server.setblocking(False)
print("Server listening on http://192.168.1.140")

start_collection()

while True:
    # Handle HTTP requests
    try:
        conn, addr = server.accept()
        conn.settimeout(1.0)
        try:
            request = conn.recv(1024).decode()
            request_line = request.split('\r\n')[0]
            response = handle_request(request_line)
            conn.sendall(response.encode())
        except OSError:
            pass
        finally:
            conn.close()
    except OSError:
        pass

    # Check if restart was requested
    if restart_requested:
        start_collection()

    # Trigger next reading if it's time
    if is_collecting and time.ticks_diff(time.ticks_ms(), last_reading_time) >= 2000:
        add_reading()

    time.sleep(0.01)
  
