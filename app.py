import os

import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import matplotlib.pyplot as plt
import requests
from collections import deque
import time
import json



firebase_secrets = st.secrets["firebase"]
firebase_secrets_dict = json.loads(json.dumps(dict(firebase_secrets)))

json_path = "/tmp/lifealert-40baf-firebase-adminsdk-fbsvc-5bdb920efa.json"  # Linux/macOS
if os.name == "nt":
    json_path = "C:\\Windows\\Temp\\lifealert-40baf-firebase-adminsdk-fbsvc-5bdb920efa.json"  # Windows

with open(json_path, "w") as json_file:
    json.dump(firebase_secrets_dict, json_file, indent=4)  # `indent=4`

# read
if not firebase_admin._apps:
    cred = credentials.Certificate(json_path)
    firebase_admin.initialize_app(cred, {"databaseURL": firebase_secrets["database_url"]})

#
sensor_ref = db.reference("sensorData")

# Data Storage (Rolling Window)
WINDOW_SIZE = 50
timestamps = deque(maxlen=WINDOW_SIZE)
heart_rate = deque(maxlen=WINDOW_SIZE)
temperature = deque(maxlen=WINDOW_SIZE)
acc_x, acc_y, acc_z = deque(maxlen=WINDOW_SIZE), deque(maxlen=WINDOW_SIZE), deque(maxlen=WINDOW_SIZE)
gyro_x, gyro_y, gyro_z = deque(maxlen=WINDOW_SIZE), deque(maxlen=WINDOW_SIZE), deque(maxlen=WINDOW_SIZE)

# Centered Page Title
st.markdown("<h1 style='text-align: center;'> Real-Time Sensor Monitoring Dashboard</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align: center; color: orange;'> Data updates every second (smooth animations)</h4>", unsafe_allow_html=True)

# Emergency & Location Status Placeholder
status_placeholder = st.empty()

# Create 4 Subplots
fig, axes = plt.subplots(4, 1, figsize=(10, 5), sharex=True)

# Define Titles & Styles
titles = ["Heart Rate (BPM)", "Temperature (°C)", "Acceleration (m/s²)", "Gyroscope (rad/s)"]
colors = ["purple", "green", "blue", "red"]
markers = ["s", "^", "o", "D"]
linestyles = ["-", "-", "--", "-."]

# Initialize Empty Plots
for ax, title, color, marker, linestyle in zip(axes, titles, colors, markers, linestyles):
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.grid(True)
    ax.set_ylabel(title, fontsize=12)
    ax.plot([], [], linestyle=linestyle, marker=marker, color=color, label=title)

# Dynamic Update Section
chart_placeholder = st.empty()

# Discord Webhook Configuration
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1336791999172313138/IbW-LUezfaqIEoihgNqRmwG0kwA_3l3jMvYvDJc_o5LBkWjqhfKxg8VaXSjksHj2Qfxw"  # Replace with your actual webhook URL
last_emergency_status = False  # To track emergency changes and avoid duplicate alerts

# Function to Send Discord Alerts
def send_discord_alert(data):
    """ Sends an emergency alert to Discord """
    message = {
        "username": "LifeAlertBot",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/564/564619.png",
        "embeds": [{
            "title": "🚨 **Emergency Alert!**",
            "description": f"💓 **Heart Rate:** {data.get('heart_rate', 'N/A')} bpm\n"
                           f"🌡 **Temperature:** {data.get('temperature', 'N/A')}°C\n"
                           f"📍 **Location:** ({data.get('lat', 'N/A')}, {data.get('lng', 'N/A')})",
            "color": 16711680
        }]
    }

    response = requests.post(DISCORD_WEBHOOK_URL, json=message, headers={"Content-Type": "application/json"})
    if response.status_code == 204:
        print("✅ Emergency alert sent to Discord!")
    else:
        print(f"⚠️ Failed to send alert: {response.status_code}")

#  Function to Update Data
def update_data():
    global timestamps, heart_rate, temperature, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, last_emergency_status

    # **Retrieve Firebase Data**
    data = sensor_ref.get()
    if not data:
        st.warning("⚠️ No data found in Firebase.")
        return

    records = []
    for key, value in data.items():
        records.append({
            "timestamp": value.get("timestamp", None),
            "heart_rate": value.get("heart_rate", None),
            "temperature": value.get("temperature", None),
            "acc_x": value.get("imu", {}).get("ax", None),
            "acc_y": value.get("imu", {}).get("ay", None),
            "acc_z": value.get("imu", {}).get("az", None),
            "gyro_x": value.get("imu", {}).get("gx", None),
            "gyro_y": value.get("imu", {}).get("gy", None),
            "gyro_z": value.get("imu", {}).get("gz", None),
            "lat": value.get("location", {}).get("lat", None),
            "lng": value.get("location", {}).get("lng", None),
            "emergency": value.get("emergency", False),
        })

    df = pd.DataFrame(records).sort_values(by="timestamp")
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y-%m-%d %H:%M:%S")
    df["time_only"] = df["timestamp"].dt.strftime("%H:%M:%S")

    if not df.empty:
        latest_time = df["time_only"].iloc[-1]
        timestamps.append(latest_time)
        heart_rate.append(df["heart_rate"].iloc[-1])
        temperature.append(df["temperature"].iloc[-1])

        acc_x.append(df["totalAcc"].iloc[-1])
        gyro_x.append(df["totalGyro"].iloc[-1])

        # **Update Emergency & Location Status**
        latest_lat = df["lat"].iloc[-1] if not df["lat"].isna().all() else "N/A"
        latest_lng = df["lng"].iloc[-1] if not df["lng"].isna().all() else "N/A"
        emergency_status = df["emergency"].iloc[-1]
        fall_status = df["fall_detect"].iloc[-1]

        emergency_text = "🚨 **Emergency Alert!**" if emergency_status or fall_status else "✅ **Normal Status**"
        status_placeholder.subheader(f"{emergency_text} | 🌍 Location: ({latest_lat}, {latest_lng})")

        # **Trigger Discord Alert if Emergency**
        if emergency_status and not last_emergency_status:  # Prevents duplicate alerts
            send_discord_alert({
                "heart_rate": df["heart_rate"].iloc[-1],
                "temperature": df["temperature"].iloc[-1],
                "lat": latest_lat,
                "lng": latest_lng
            })

        last_emergency_status = emergency_status  # Update the last known emergency status

    # **Update Plots**
    # **(Heart Rate)**
    axes[0].clear()
    axes[0].plot(timestamps, heart_rate, linestyle="-", marker="s", color="purple", label="Avg BPM")
    axes[0].set_xticks(range(len(timestamps)))  # 设置 X 轴刻度
    axes[0].set_xticklabels(timestamps, rotation=45)  # 旋转时间轴
    axes[0].legend()

    # **(Temperature)**
    axes[1].clear()
    axes[1].plot(timestamps, temperature, linestyle="-", marker="^", color="green", label="Temperature (°C)")
    axes[1].set_xticks(range(len(timestamps)))
    axes[1].set_xticklabels(timestamps, rotation=45)
    axes[1].legend()

    # **(Total Acceleration)**
    axes[2].clear()
    axes[2].plot(timestamps, acc_x, linestyle="--", marker="o", color="red", label="Total Acceleration (m/s²)")
    axes[2].set_xticks(range(len(timestamps)))
    axes[2].set_xticklabels(timestamps, rotation=45)
    axes[2].legend()

    # **(Total Gyroscope)**
    axes[3].clear()
    axes[3].plot(timestamps, gyro_x, linestyle="-.", marker="D", color="blue", label="Total Gyroscope (rad/s)")
    axes[3].set_xticks(range(len(timestamps)))
    axes[3].set_xticklabels(timestamps, rotation=45)
    axes[3].legend()

    chart_placeholder.pyplot(fig, clear_figure=False)

#  Start Real-Time Updates
while True:
    update_data()
    time.sleep(1)

