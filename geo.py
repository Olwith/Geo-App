import streamlit as st
import sqlite3
import folium
from geopy.geocoders import Nominatim
from streamlit_folium import folium_static
from flask import Flask
from flask_socketio import SocketIO,emit
import threading

# Initialize Flask and SocketIO
flask_app = Flask(__name__)
socketio = SocketIO(flask_app)

# SQLite Database Functions
def create_connection():
    conn = sqlite3.connect('events.db')
    return conn

def create_table():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_event(event_type, severity, description, latitude, longitude):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO events (event_type, severity, description, latitude, longitude)
        VALUES (?, ?, ?, ?, ?)
    ''', (event_type, severity, description, latitude, longitude))
    conn.commit()
    conn.close()

def get_events():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM events ORDER BY timestamp DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows

# Function to geocode the location using Geopy
def geocode_location(location):
    geolocator = Nominatim(user_agent="event_reporter")
    location = geolocator.geocode(location)
    if location:
        return location.latitude, location.longitude
    else:
        return None, None

# Initialize SQLite database
create_table()

# Function to run the Flask app in a separate thread
def run_flask():
    socketio.run(flask_app, port=5000)

# Start Flask app in a thread
threading.Thread(target=run_flask, daemon=True).start()

# Streamlit UI
st.title("Crowdsourced Event Reporting Map")

# Event Reporting Form
event_type = st.selectbox("Event Type", ["Road Closure", "Accident", "Construction", "Other"])
severity = st.selectbox("Severity", ["Low", "Medium", "High"])
description = st.text_input("Description")
location = st.text_input("Location (Address or Description)")

if st.button("Report Event"):
    latitude, longitude = geocode_location(location)
    if latitude is not None and longitude is not None:
        add_event(event_type, severity, description, latitude, longitude)
        socketio.emit('new_event', {
            'event_type': event_type,
            'severity': severity,
            'description': description,
            'latitude': latitude,
            'longitude': longitude
        })
        st.success("Event reported successfully!")
    else:
        st.error("Could not geocode the location. Please try again.")

# Function to display the map with events
def display_map(events):
    event_map = folium.Map(location=[-1.286389, 36.817223], zoom_start=6)  # Centered on Kenya
    for event in events:
        folium.Marker(
            location=[event[4], event[5]],
            popup=f"{event[1]}: {event[3]} (Severity: {event[2]})",
            icon=folium.Icon(color='red' if event[2] == 'High' else 'orange' if event[2] == 'Medium' else 'green')
        ).add_to(event_map)
    folium_static(event_map)

# Load existing events on startup
if 'events' not in st.session_state:
    st.session_state['events'] = get_events()

# Display initial map
display_map(st.session_state['events'])

# Event listener for new events
@socketio.on('new_event')
def handle_new_event(data):
    st.session_state['events'].append(data)
    display_map(st.session_state['events'])

