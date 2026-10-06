#!/usr/bin/env python3

# Capture data from remote Pico over Wi-Fi and save to CSV file.
# The CSV file will be named with the timestamp of the collection start.
# J.Beale 6-Oct-2026

import requests
import json
import time
import datetime
from pathlib import Path

PICO_URL = 'http://192.168.1.140'
POLL_INTERVAL = 2.0  # seconds
MAX_READINGS = 20
RETRY_ATTEMPTS = 3
RETRY_DELAY = 1.0  # seconds

def get_with_retry(url, timeout=5, max_retries=RETRY_ATTEMPTS):
    """GET request with retry logic for timeouts and connection errors"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            if attempt < max_retries - 1:
                print(f"Timeout/connection error (attempt {attempt + 1}/{max_retries}): {type(e).__name__}")
                time.sleep(RETRY_DELAY)
            else:
                print(f"Failed after {max_retries} attempts: {type(e).__name__}")
                raise
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            raise

def check_pico_version():
    """Check Pico firmware version"""
    try:
        response = get_with_retry(f'{PICO_URL}/version')
        info = response.json()
        print(f"Pico version: {info.get('version', 'unknown')}")
        print(f"Features: {', '.join(info.get('features', []))}")
        return True
    except Exception as e:
        print(f"Could not reach Pico or get version: {e}")
        return False

def wait_for_collection_start():
    """Wait until the top of the next 10-minute interval"""
    now = datetime.datetime.now()
    next_interval = ((now.minute // 10) + 1) * 10
    if next_interval == 60:
        next_interval = 0
        # Handle midnight rollover
        if now.hour == 23:
            target = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            target = now.replace(hour=now.hour + 1, minute=0, second=0, microsecond=0)
    else:
        target = now.replace(minute=next_interval, second=0, microsecond=0)

    wait_seconds = (target - now).total_seconds()
    print(f"Waiting {wait_seconds:.1f} seconds for top of 10-minute interval...")
    time.sleep(wait_seconds)

def collect_accel_data():
    """Poll Pico status endpoint and save data to CSV"""
    # Check version first
    check_pico_version()

    # Wait for collection start
    wait_for_collection_start()

    # Request restart on Pico
    print("Requesting collection restart...")
    try:
        get_with_retry(f'{PICO_URL}/restart')
    except Exception as e:
        print(f"Warning: Could not send restart command: {e}")

    start_time = datetime.datetime.now()
    timestamp = start_time.strftime('%Y-%m-%d_%H-%M-%S')
    csv_filename = f'{timestamp}_accel.csv'

    print(f"Started new measurement cycle at {timestamp}")

    readings_collected = 0
    csv_data = []

    while readings_collected < MAX_READINGS:
        try:
            # Poll status endpoint with retry
            response = get_with_retry(f'{PICO_URL}/status')
            data = response.json()

            is_collecting = data.get('is_collecting', False)
            reading_count = data.get('reading_count', 0)
            readings = data.get('readings', [])

            print(f"Progress: {reading_count}/{MAX_READINGS}")

            # Store all readings received so far
            if readings:
                csv_data = readings
                readings_collected = len(readings)

            # Check if collection is complete
            if not is_collecting and reading_count >= MAX_READINGS:
                print("Collection complete on Pico")
                break

        except requests.exceptions.Timeout:
            print(f"Timeout on poll attempt (will retry)")
            time.sleep(RETRY_DELAY)
            continue
        except requests.exceptions.ConnectionError:
            print(f"Connection error (will retry)")
            time.sleep(RETRY_DELAY)
            continue
        except Exception as e:
            print(f"Error polling status: {e}")
            time.sleep(RETRY_DELAY)
            continue

        # Wait before next poll
        time.sleep(POLL_INTERVAL)

    # Write CSV file
    if csv_data:
        with open(csv_filename, 'w', newline='') as f:
            f.write("epoch,n,MPU_X,MPU_Y,MPU_Z,degC,ADXL_X,ADXL_Y,ADXL_Z,samples\n")
            for row in csv_data:
                # row format: [epoch, n, mpu_x, mpu_y, mpu_z, temp, adxl_x, adxl_y, adxl_z, samples]
                f.write(f"{int(row[0])},{int(row[1])},{float(row[2]):.4f},{float(row[3]):.4f},{float(row[4]):.4f},{float(row[5]):.2f},{float(row[6]):.4f},{float(row[7]):.4f},{float(row[8]):.4f},{int(row[9])}\n")
        print(f"Data saved to {csv_filename} ({len(csv_data)} readings)")
    else:
        print("No data collected")

if __name__ == '__main__':
    try:
        while True:
            collect_accel_data()
            time.sleep(5) # wait a few seconds before starting the next cycle
    except KeyboardInterrupt:
        print("\nCollection interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
