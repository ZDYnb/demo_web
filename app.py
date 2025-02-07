

import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import matplotlib.pyplot as plt
from collections import deque
import time

# **1️⃣ Streamlit Page Config**
st.set_page_config(page_title="📊 Real-Time Sensor Dashboard", layout="wide")

# **2️⃣ Connect to Firebase**
# Access credentials from Streamlit secrets
firebase_creds = st.secrets["firebase_service_account"]

# Directly use the credentials dictionary from Streamlit secrets to initialize Firebase
cred = credentials.Certificate(firebase_creds)

DATABASE_URL = "https://lifealert-40baf-default-rtdb.firebaseio.com/"
firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})
sensor_ref = db.reference("sensorData")

# **3️⃣ Data Storage (Rolling Window)**
WINDOW_SIZE = 50
timestamps = deque(maxlen=WINDOW_SIZE)
heart_rate = deque(maxlen=WINDOW_SIZE)
temperature = deque(maxlen=WINDOW_SIZE)
acc_x, acc_y, acc_z = deque(maxlen=WINDOW_SIZE), deque(maxlen=WINDOW_SIZE), deque(maxlen=WINDOW_SIZE)
gyro_x, gyro_y, gyro_z = deque(maxlen=WINDOW_SIZE), deque(maxlen=WINDOW_SIZE), deque(maxlen=WINDOW_SIZE)

# **4️⃣ Centered Page Title**
st.markdown("<h1 style='text-align: center;'>📡 Real-Time Sensor Monitoring Dashboard</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align: center; color: orange;'>⚡ Data updates every second (smooth animations)</h4>", unsafe_allow_html=True)

# **5️⃣ Emergency & Location Status Placeholder**
status_placeholder = st.empty()

# **6️⃣ Create 4 Subplots**
fig, axes = plt.subplots(4, 1, figsize=(10, 5), sharex=True)

# **Define Titles & Styles**
titles = ["Heart Rate (BPM)", "Temperature (°C)", "Acceleration (m/s²)", "Gyroscope (rad/s)"]
colors = ["purple", "green", "blue", "red"]
markers = ["s", "^", "o", "D"]
linestyles = ["-", "-", "--", "-."]

# **Initialize Empty Plots**
for ax, title, color, marker, linestyle in zip(axes, titles, colors, markers, linestyles):
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.grid(True)
    ax.set_ylabel(title, fontsize=12)
    ax.plot([], [], linestyle=linestyle, marker=marker, color=color, label=title)

# **7️⃣ Dynamic Update Section**
chart_placeholder = st.empty()

# **8️⃣ Discord Webhook Configuration**
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1337435754955276310/jXfMK5hSL2hFZeOWj1BYy7ylsIFnGhQTUDuE9zIRlXpWyfzjtzcGbRM7R_Jn_hjHDBt7"  # Replace with your actual webhook URL
last_emergency_status = False  # To track emergency changes and avoid duplicate alerts

# **9️⃣ Function to Send Discord Alerts**
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

# **🔟 Function to Update Data**
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
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

    if not df.empty:
        latest_time = df["timestamp"].iloc[-1]
        timestamps.append(latest_time)
        heart_rate.append(df["heart_rate"].iloc[-1])
        temperature.append(df["temperature"].iloc[-1])
        acc_x.append(df["acc_x"].iloc[-1])
        acc_y.append(df["acc_y"].iloc[-1])
        acc_z.append(df["acc_z"].iloc[-1])
        gyro_x.append(df["gyro_x"].iloc[-1])
        gyro_y.append(df["gyro_y"].iloc[-1])
        gyro_z.append(df["gyro_z"].iloc[-1])

        # **Update Emergency & Location Status**
        latest_lat = df["lat"].iloc[-1] if not df["lat"].isna().all() else "N/A"
        latest_lng = df["lng"].iloc[-1] if not df["lng"].isna().all() else "N/A"
        emergency_status = df["emergency"].iloc[-1]

        emergency_text = "🚨 **Emergency Alert!**" if emergency_status else "✅ **Normal Status**"
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
    axes[0].clear()
    axes[0].plot(timestamps, heart_rate, linestyle="-", marker="s", color="purple", label="Avg BPM")
    axes[0].legend()

    axes[1].clear()
    axes[1].plot(timestamps, temperature, linestyle="-", marker="^", color="green", label="Temperature (°C)")
    axes[1].legend()

    axes[2].clear()
    axes[2].plot(timestamps, acc_x, linestyle="--", marker="o", color="red", label="Acc X")
    axes[2].plot(timestamps, acc_y, linestyle="--", marker="o", color="blue", label="Acc Y")
    axes[2].plot(timestamps, acc_z, linestyle="--", marker="o", color="green", label="Acc Z")
    axes[2].legend()

    axes[3].clear()
    axes[3].plot(timestamps, gyro_x, linestyle="-.", marker="D", color="red", label="Gyro X")
    axes[3].plot(timestamps, gyro_y, linestyle="-.", marker="D", color="blue", label="Gyro Y")
    axes[3].plot(timestamps, gyro_z, linestyle="-.", marker="D", color="green", label="Gyro Z")
    axes[3].legend()

    chart_placeholder.pyplot(fig, clear_figure=False)

# **🔟 Start Real-Time Updates**
while True:
    update_data()
    time.sleep(1)

