import network
import socket
import time
import machine
import ntptime
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

def read_averaged_nonblocking(sample_count=500):
    global restart_requested
    sum_x = sum_y = sum_z = sum_temp = 0
    
    for i in range(sample_count):
        # Check if restart was requested mid-read
        if restart_requested:
            print("Restart requested during read, aborting")
            break
        
        reading = mpu.read()
        sum_x += reading['accel_x']
        sum_y += reading['accel_y']
        sum_z += reading['accel_z']
        sum_temp += reading['temp_c']
    
    samples_taken = i + 1 if not restart_requested else i
    
    return {
        'accel_x': sum_x / samples_taken if samples_taken > 0 else 0,
        'accel_y': sum_y / samples_taken if samples_taken > 0 else 0,
        'accel_z': sum_z / samples_taken if samples_taken > 0 else 0,
        'temp_c': sum_temp / samples_taken if samples_taken > 0 else 0,
        'samples': samples_taken
    }

def add_reading():
    global reading_count, reading_history, start_epoch, is_collecting, last_reading_time, restart_requested
    reading_count += 1
    epoch = int(time.time())
    reading = read_averaged_nonblocking(1000)
    reading_history.append((epoch, reading_count, reading['accel_x'], reading['accel_y'], reading['accel_z'], reading['temp_c'], reading['samples']))
    
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
    csv += "epoch,n,X,Y,Z,degC,samples\n"
    for e, n, x, y, z, t, s in reading_history:
        csv += f"{e},{n},{x:.3f},{y:.3f},{z:.3f},{t:.2f},{s}\n"
    return csv

def handle_request(request_line):
    global restart_requested
    
    if 'GET /restart' in request_line:
        restart_requested = True
        print("Restart requested by user")
        return "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 0\r\n\r\n"
    
    elif 'GET /status' in request_line:
        readings_list = [[e, n, f"{x:.3f}", f"{y:.3f}", f"{z:.3f}", f"{t:.2f}", s] for e, n, x, y, z, t, s in reading_history]
        json_text = f'{{"is_collecting":{str(is_collecting).lower()},"reading_count":{reading_count},"readings":{readings_list}}}'
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
<title>Pico W MPU-6050 Data Collection</title>
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
