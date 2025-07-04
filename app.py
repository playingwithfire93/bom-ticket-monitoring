
import hashlib
import json
from datetime import UTC, datetime

import requests
from bs4 import BeautifulSoup
from bs4.element import Comment
from flask import Flask, jsonify, render_template_string
from flask_socketio import SocketIO
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app)

# Track previous states for change detection
previous_states = {}
previous_contents = {}

# Track change counts for each website
change_counts = {}

# Track if there are new changes for notification
new_changes_detected = True

# Real ticket monitoring URLs
URLS = [
    {"label": "Wicked", "url": "https://wickedelmusical.com/"},
    {"label": "Wicked elenco", "url": "https://wickedelmusical.com/elenco"},
    {"label": "Wicked entradas", "url": "https://tickets.wickedelmusical.com/espectaculo/wicked-el-musical/W01"},
    {"label": "Los Miserables", "url": "https://miserableselmusical.es/"},
    {"label": "Los Miserables elenco", "url": "https://miserableselmusical.es/elenco"},
    {"label": "Los Miserables entradas", "url": "https://tickets.miserableselmusical.es/espectaculo/los-miserables/M01"},
    {"label": "The Book of Mormon", "url": "https://thebookofmormonelmusical.es"},
    {"label": "The Book of Mormon elenco", "url": "https://thebookofmormonelmusical.es/elenco/"},
    {"label": "The Book of Mormon entradas", "url": "https://tickets.thebookofmormonelmusical.es/espectaculo/the-book-of-mormon-el-musical/BM01"},
    {"label": "Buscando a Audrey", "url": "https://buscandoaaudrey.com"},
    {"label": "Houdini", "url": "https://www.houdinielmusical.com"}
]

def hash_url_content(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")

        # Remove tags that usually include changing content
        for tag in soup(["script", "style", "noscript", "meta", "iframe", "link", "svg"]):
            tag.decompose()

        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Remove common dynamic elements by class/id
        dynamic_selectors = [
            ".date_info", ".timestamp", "#ad", ".ads", ".cookie-banner", "#cookies", ".tracker"
        ]
        for selector in dynamic_selectors:
            for tag in soup.select(selector):
                tag.decompose()

        # Normalize whitespace and strip
        content_text = soup.get_text(separator=" ", strip=True)
        normalized_text = " ".join(content_text.split())

        return hashlib.md5(normalized_text.encode("utf-8")).hexdigest()
    except Exception as e:
        return f"ERROR: {str(e)}"

def extract_normalized_date_info(url):
    """Get normalized text content from .date_info element."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    date_info = soup.select_one('.date_info')
    if not date_info:
        return None

    text = date_info.get_text(strip=True)
    return ' '.join(text.split()).lower()

import difflib

def find_differences(old_text, new_text):
    """Generate a diff showing changes between old and new content."""
    diff = difflib.unified_diff(
        old_text.splitlines(), 
        new_text.splitlines(), 
        fromfile='anterior', 
        tofile='actual', 
        lineterm=""
    )
    return "\n".join(diff)

def broadcast_change(url, data):
    socketio.emit('update', {'url': url, 'data': data})

latest_changes = []

def scrape_all_sites():
    global previous_states, previous_contents, change_counts
    changes_list = []
    now = datetime.now(UTC).isoformat()
    
    for item in URLS:
        label = item["label"]
        url = item["url"]

        # Get current full content
        current_content = ""
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Remove scripts, styles, etc. but keep the full text
            for tag in soup(["script", "style", "noscript", "meta", "iframe", "link", "svg"]):
                tag.decompose()
            
            # Remove comments
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
            
            current_content = soup.get_text(separator=" ", strip=True)
        except Exception as e:
            current_content = f"Error al obtener contenido: {str(e)}"
        if "buscandoaaudrey.com" in url:
            state = hash_audrey_content(url)
        else:
            state = extract_normalized_date_info(url)
            if state is None:
                state = hash_url_content(url)
            state = extract_normalized_date_info(url)
            if state is None:
                state = hash_url_content(url)

        last_state = previous_states.get(url)
        last_content = previous_contents.get(url, "")
        change_details = ""
        differences = ""
        
        if last_state is None:
            status = "Primer chequeo 👀"
            change_details = "Primera vez que se monitorea este sitio web"
            differences = "No hay contenido anterior para comparar"
            change_counts[url] = 0
        elif last_state != state:
            status = "¡Actualizado! 🎉"
            change_details = "Se detectaron cambios en el contenido del sitio web"
            change_counts[url] = change_counts.get(url, 0) + 1
            if last_content and current_content != last_content:
                differences = find_differences(last_content, current_content)
            else:
                differences = "Contenido modificado pero no se pudieron detectar diferencias específicas"
            broadcast_change(url, status)
        else:
            status = "Sin cambios ✨"
            change_details = "El contenido permanece igual desde la última verificación"
            differences = "Sin diferencias detectadas"
            if url not in change_counts:
                change_counts[url] = 0

        previous_states[url] = state
        previous_contents[url] = current_content

        changes_list.append({
            "label": label,
            "url": url,
            "status": status,
            "timestamp": now,
            "hash_actual": state,
            "hash_anterior": last_state,
            "detalles_cambio": change_details,
            "contenido_completo": current_content,
            "contenido_anterior": last_content,
            "diferencias_detectadas": differences,
            "longitud_contenido": len(current_content),
            "change_count": change_counts[url],
            "fecha_legible": datetime.now(UTC).strftime("%d/%m/%Y %H:%M:%S UTC")
        })
    
    return changes_list

def background_checker():
    global latest_changes
    while True:
        latest_changes = scrape_all_sites()
        time.sleep(30)  # Check every 30 seconds

# Start background checker
threading.Thread(target=background_checker, daemon=True).start()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Ticket Monitor Dashboard</title>
  <style>
    body {
      font-family: 'Georgia', serif;
      margin: 0;
      padding: 0;
      min-height: 100vh;
      /* Remove static background */
      /* background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 50%, #fecfef 100%); */
      overflow-x: hidden;
    }
    .animated-bg {
      position: fixed;
      top: 0; left: 0; width: 100vw; height: 100vh;
      z-index: -2;
      background: linear-gradient(120deg, #ffb6e6 0%, #fecfef 50%, #ffb6e6 100%);
      background-size: 200% 200%;
      animation: bgMove 10s ease-in-out infinite alternate;
    }
    @keyframes bgMove {
      0% { background-position: 0% 50%; }
      100% { background-position: 100% 50%; }
    }
    .floating-sparkle {
      position: absolute;
      font-size: 2em;
      pointer-events: none;
      opacity: 0.7;
      animation: floatSparkle 8s linear infinite;
    }
    .floating-sparkle.s1 { left: 10vw; top: 20vh; animation-delay: 0s; }
    .floating-sparkle.s2 { left: 80vw; top: 30vh; animation-delay: 2s; }
    .floating-sparkle.s3 { left: 50vw; top: 70vh; animation-delay: 4s; }
    .floating-sparkle.s4 { left: 30vw; top: 80vh; animation-delay: 1s; }
    .floating-sparkle.s5 { left: 70vw; top: 10vh; animation-delay: 3s; }
    @keyframes floatSparkle {
      0% { transform: translateY(0) scale(1) rotate(0deg); opacity: 0.7; }
      50% { transform: translateY(-40px) scale(1.2) rotate(10deg); opacity: 1; }
      100% { transform: translateY(0) scale(1) rotate(-10deg); opacity: 0.7; }
    }
    h1 {
      text-align: center;
      color: #d63384;
      font-size: 2.5em;
      text-shadow: 2px 2px 4px rgba(214, 51, 132, 0.3);
      margin: 20px 0;
      font-weight: bold;
    }
    .slideshow-container {
      max-width: 1100px; /* was 800px */
      margin: 30px auto;
      position: relative;
      border-radius: 28px;
      overflow: hidden;
      box-shadow: 0 8px 25px rgba(214, 51, 132, 0.3);
      border: 3px solid #ff69b4;
      background: linear-gradient(
        120deg,
        #ffe0f7 0%,
        #ffb6e6 25%,
        #ff69b4 50%,
        #ffc0cb 75%,
        #ffe0f7 100%
      );
      background-size: 400% 400%;
      animation: sliderMove 8s linear infinite alternate;
    }

@keyframes sliderMove {
  0% { background-position: 0% 50%; }
  100% { background-position: 100% 50%; }
}
    .slide {
      display: none;
      width: 100%;
    }
    /* Make the images taller too */
.slide img {
  width: 100%;
  height: 520px; /* was 400px */
  object-fit: contain;
  display: block;
  margin: 0 auto;
}
    table {
      width: 90%;
      margin: 20px auto;
      border-collapse: collapse;
      background: rgba(255, 255, 255, 0.9);
      border-radius: 15px;
      overflow: hidden;
      box-shadow: 0 8px 25px rgba(214, 51, 132, 0.2);
      border: 2px solid #ff69b4;
    }
    th, td {
      padding: 15px;
      border-bottom: 1px solid #ffb3d9;
      text-align: left;
      font-weight: 500;
    }
    th {
      background: linear-gradient(135deg, #ff69b4, #d63384);
      color: #fff;
      font-weight: bold;
      text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
    }
    tr:hover {
      background: #ffe6f2;
      transform: scale(1.02);
      transition: all 0.3s ease;
    }
    td {
      color: #8b2c5c;
    }
    .sparkle {
      position: absolute;
      color: #ff69b4;
      animation: sparkle 2s infinite;
    }
    @keyframes sparkle {
      0%, 100% { opacity: 0; transform: scale(0.8); }
      50% { opacity: 1; transform: scale(1.2); }
    }
    .notification-popup {
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: linear-gradient(135deg, #ff69b4, #ffc0cb);
      border: 3px solid #d63384;
      border-radius: 20px;
      padding: 30px;
      box-shadow: 0 10px 30px rgba(214, 51, 132, 0.4);
      z-index: 1000;
      text-align: center;
      color: #fff;
      display: none;
      max-width: 400px;
    }
    .notification-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.5);
      z-index: 999;
      display: none;
    }
    .popup-button {
      background: #fff;
      color: #d63384;
      border: 2px solid #d63384;
      padding: 10px 20px;
      border-radius: 15px;
      margin: 10px;
      cursor: pointer;
      font-weight: bold;
      text-decoration: none;
      display: inline-block;
    }
    .popup-button:hover {
      background: #d63384;
      color: #fff;
    }
    .status-updated {
      background: linear-gradient(135deg, #ff69b4, #ffc0cb);
      color: #fff;
      padding: 5px 10px;
      border-radius: 15px;
      font-weight: bold;
    }
    .status-no-change {
      color: #8b2c5c;
    }
    .last-checked {
      text-align: center;
      color: #d63384;
      font-weight: bold;
      margin: 20px 0;
    }
    .change-badge {
      background: linear-gradient(135deg, #ff6b6b, #ff8e53);
      color: white;
      border-radius: 12px;
      padding: 2px 8px;
      font-size: 0.8em;
      font-weight: bold;
      margin-left: 8px;
      display: inline-block;
      min-width: 20px;
      text-align: center;
      box-shadow: 0 2px 4px rgba(255, 107, 107, 0.3);
    }
    .change-badge.zero {
      background: #ddd;
      color: #666;
    }
    .json-popup {
      position: fixed;
      top: 5%;
      left: 5%;
      width: 90%;
      height: 90%;
      background: white;
      border: 3px solid #d63384;
      border-radius: 20px;
      z-index: 2000;
      display: none;
      overflow: hidden;
    }
    .json-popup-header {
      background: linear-gradient(135deg, #ff69b4, #d63384);
      color: white;
      padding: 15px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .json-popup-content {
      height: calc(100% - 80px);
      overflow: auto;
      padding: 20px;
      background: #f8f9fa;
    }
    .json-code {
      background: #2d3748;
      color: #e2e8f0;
      padding: 20px;
      border-radius: 10px;
      font-family: 'Courier New', monospace;
      font-size: 12px;
      line-height: 1.4;
      white-space: pre-wrap;
      word-wrap: break-word;
      max-height: 100%;
      overflow: auto;
    .highlighted-bg {
  position: relative;
  margin: 30px auto 0 auto;
  max-width: 900px;
  border-radius: 25px;
  overflow: hidden;
  box-shadow: 0 8px 25px rgba(214, 51, 132, 0.15);
  border: 4px solid #ff69b4;
  background: linear-gradient(
    120deg,
    #ffe0f7 0%,
    #ffb6e6 25%,
    #ff69b4 50%,
    #ffc0cb 75%,
    #ffe0f7 100%
  );
  background-size: 400% 400%;
  animation: highlightMove 6s linear infinite alternate;
  padding: 30px 0 20px 0;
}

@keyframes highlightMove {
  0% { background-position: 0% 50%; }
  100% { background-position: 100% 50%; }
}
    .close-json-btn {
      background: white;
      color: #d63384;
      border: none;
      padding: 8px 15px;
      border-radius: 10px;
      cursor: pointer;
      font-weight: bold;
    }
    .close-json-btn:hover {
      background: #f0f0f0;
    }
    * {
    cursor: url(https://cur.cursors-4u.net/special/spe-3/spe302.ani), 
           url(https://cur.cursors-4u.net/special/spe-3/spe302.png), 
           auto !important;
}
    .json-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.7);
      z-index: 1999;
      display: none;
    }
  </style>
</head>
<!-- Add this inside your <head> or at the top of your HTML -->
<style type="text/css">
* {
  cursor: url(https://cur.cursors-4u.net/special/spe-3/spe302.ani), url(https://cur.cursors-4u.net/special/spe-3/spe302.png), auto !important;
}
</style>
<a href="https://www.cursors-4u.com/cursor/2011/02/18/cute-bow-tie-hearts-blinking-blue-and-pink-pointer.html" target="_blank" title="Cute Bow Tie Hearts Blinking Blue and Pink Pointer">
  <img src="https://cur.cursors-4u.net/cursor.png" border="0" alt="Cute Bow Tie Hearts Blinking Blue and Pink Pointer" style="position:absolute; top: 0px; right: 0px;" />
</a>
<body>

<h1>✨ Ticket Monitor Dashboard ✨</h1>

<div class="animated-bg"></div>
<div class="floating-sparkle s1">✨</div>
<div class="floating-sparkle s2">💖</div>
<div class="floating-sparkle s3">🌸</div>
<div class="floating-sparkle s4">💕</div>
<div class="floating-sparkle s5">✨</div>

<div class="notification-overlay" id="notificationOverlay"></div>
<div class="notification-popup" id="notificationPopup">
  <h2>✨ New Changes Detected! ✨</h2>
  <p>💖 Fresh ticket updates are available! 💖</p>
  <div>
    <button class="popup-button" onclick="viewJsonFromPopup()">📄 View JSON Data</button>
    <button class="popup-button" onclick="closeNotification()">Close</button>
  </div>
</div>

<div class="json-overlay" id="jsonOverlay" onclick="closeJsonPopup()"></div>
<div class="json-popup" id="jsonPopup">
  <div class="json-popup-header">
    <h3>📄 JSON Changes Data</h3>
    <button class="close-json-btn" onclick="closeJsonPopup()">✕ Close</button>
  </div>
  <div class="json-popup-content">
    <div class="json-code" id="jsonContent">Loading...</div>
  </div>
</div>
<div class="highlighted-bg">
  <div class="slideshow-container">
    <div class="slide">
      <img src="https://paginasdigital.es/wp-content/uploads/2024/12/wicked-portada.jpg" alt="Wicked1">
    </div>
    <div class="slide">
      <img src="https://images.ctfassets.net/sjxdiqjbm079/3WMcDT3PaFgjIinkfvmh1L/cf88d0afc6280931ee110ac47ec573a8/01_LES_MIS_TOUR_02_24_0522_PJZEDIT_v002.jpg?w=708&h=531&fm=webp&fit=fill" alt="Los Miserables">
    </div>
    <div class="slide">
      <img src="https://www.princeofwalestheatre.co.uk/wp-content/uploads/2024/02/BOM-hi-res-Turn-it-off-Nov-2023-9135-hi-res.webp" alt="Book of Mormon">
    </div>
    <div class="slide"> 
      <img src="/static/AUDREY1.jpg" alt="Buscando a Audrey">
    </div>
    <div class="slide">
      <img src="/static/HOUDINI1.jpg" alt="Houdini">
    </div>
    <div class="slide">
      <img src="/static/WICKED1.jpg" alt="Wicked1">
    </div>
    <div class="slide">
      <img src="/static/LESMIS1.jpg" alt="Los Miserables1">
    </div>
    <div class="slide">
      <img src="/static/BOM1.jpg" alt="Book of Mormon1">
    </div>
    <div class="slide">
      <img src="/static/WICKED2.jpg" alt="Wicked2">
    </div>
    <div class="slide">
      <img src="/static/LESMIS2.jpg" alt="Los Miserables2">
    </div>
    <div class="slide">
      <img src="/static/BOM2.jpg" alt="Book of Mormon2">
    </div>
    <div class="slide">
      <img src="/static/WICKED3.jpg" alt="Wicked3">
    </div>
    <div class="slide">
      <img src="/static/LESMIS3.png" alt="Los Miserables3">
    </div>
    <div class="slide">
      <img src="/static/BOM3.jpg" alt="Book of Mormon3">
    </div>
    <div class="slide">
      <img src="/static/WICKED4.jpg" alt="Wicked4">
    </div>
    <div class="slide">
      <img src="/static/LESMIS4.jpg" alt="Los Miserables4">
    </div>
    <div class="slide">
      <img src="/static/BOM4.jpg" alt="Book of Mormon4">
    </div>
    <div class="slide">
      <img src="/static/WICKED5.jpg" alt="Wicked5">
    </div>
    <div class="slide">
      <img src="/static/LESMIS5.jpg" alt="Los Miserables5">
    </div>
    <div class="slide">
      <img src="/static/BOM5.jpg" alt="Book of Mormon5">
    </div>
    <div class="slide">
      <img src="/static/WICKED6.jpg" alt="Wicked6">
    </div>
    <div class="slide">
      <img src="/static/LESMIS6.jpg" alt="Los Miserables6">
    </div>
    <div class="slide">
      <img src="/static/BOM6.jpg" alt="Book of Mormon6">
    </div>
    <div class="slide">
      <img src="/static/WICKED7.jpg" alt="Wicked7">
    </div>
    <div class="slide">
      <img src="/static/LESMIS7.jpg" alt="Los Miserables7">
    </div>
    <div class="slide">
      <img src="/static/BOM7.jpg" alt="Book of Mormon7">
    </div>
</div>

<div class="last-checked" id="lastChecked">Last Checked: Loading...</div>



<table id="changesTable">
  <tr>
    <th>Show/Website</th>
    <th>Cambios</th>
    <th>URL</th>
    <th>Status</th>
    <th>Last Update</th>
  </tr>
  <td colspan="5" style="text-align: center;">Loading ticket data...</td>
</table>

<script>
  let slideIndex = 0;
  showSlides();

  function showSlides() {
    let slides = document.getElementsByClassName("slide");
    if (slides.length === 0) return;
    
    for (let i = 0; i < slides.length; i++) {
      slides[i].style.display = "none";
    }
    slideIndex++;
    if (slideIndex > slides.length) { slideIndex = 1; }
    slides[slideIndex-1].style.display = "block";
    setTimeout(showSlides, 3000);
  }

  function showNotification() {
    document.getElementById('notificationOverlay').style.display = 'block';
    document.getElementById('notificationPopup').style.display = 'block';
    
    // Play notification sound
    playNotificationSound();
  }
  
  function playNotificationSound() {
    try {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      
      const playTone = (frequency, startTime, duration) => {
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.setValueAtTime(frequency, startTime);
        oscillator.type = 'sine';
        
        gainNode.gain.setValueAtTime(0, startTime);
        gainNode.gain.linearRampToValueAtTime(0.1, startTime + 0.01);
        gainNode.gain.exponentialRampToValueAtTime(0.01, startTime + duration);
        
        oscillator.start(startTime);
        oscillator.stop(startTime + duration);
      };
      
      const now = audioContext.currentTime;
      playTone(523.25, now, 0.2);        // C5
      playTone(659.25, now + 0.1, 0.2);  // E5
      playTone(783.99, now + 0.2, 0.3);  // G5
    } catch (e) {
      console.log('Audio not supported');
    }
  }

  function closeNotification() {
    document.getElementById('notificationOverlay').style.display = 'none';
    document.getElementById('notificationPopup').style.display = 'none';
  }

  function viewJsonFromPopup() {
    showJsonPopup();
    closeNotification();
  }
  
  async function showJsonPopup() {
    document.getElementById('jsonOverlay').style.display = 'block';
    document.getElementById('jsonPopup').style.display = 'block';
    document.getElementById('jsonContent').textContent = 'Loading JSON data...';
    
    try {
      const response = await fetch('/api/changes.json');
      const jsonData = await response.text();
      document.getElementById('jsonContent').textContent = jsonData;
    } catch (error) {
      document.getElementById('jsonContent').textContent = 'Error loading JSON data: ' + error.message;
    }
  }
  
  function closeJsonPopup() {
    document.getElementById('jsonOverlay').style.display = 'none';
    document.getElementById('jsonPopup').style.display = 'none';
  }

  async function updateTicketData() {
    try {
      const response = await fetch('/api/ticket-changes');
      const data = await response.json();
      
      document.getElementById('lastChecked').textContent = 
        'Last Checked: ' + new Date().toLocaleString();
      
      const table = document.getElementById('changesTable');
      table.innerHTML = `
        <tr>
          <th>Show/Website</th>
           <th>Cambios</th>
          <th>URL</th>
          <th>Status</th>
          <th>Last Update</th>
        </tr>
      `;
      
      let hasUpdates = false;
      data.forEach(item => {
        const row = table.insertRow();
        const changeCount = item.change_count || 0;
        const badgeClass = changeCount === 0 ? 'change-badge zero' : 'change-badge';
        
        row.innerHTML = `
          <td>${item.label}</td>
          <td><span class="${badgeClass}">${changeCount}</span></td>
          <td><a href="${item.url}" target="_blank" style="color: #d63384;">${item.url}</a></td>
          <td class="${item.status.includes('Actualizado') ? 'status-updated' : 'status-no-change'}">${item.status}</td>
          <td>${new Date(item.timestamp).toLocaleString()}</td>
        `;
        
        if (item.status.includes('Actualizado')) {
          hasUpdates = true;
          row.style.background = 'linear-gradient(135deg, #ffe4f1, #ffc0cb)';
        }
      });
      
      if (hasUpdates) {
        showNotification();
      }
      
    } catch (error) {
      console.error('Error fetching ticket data:', error);
      document.getElementById('lastChecked').textContent = 'Error loading data';
    }
  }

  // Initial load and periodic updates
  updateTicketData();
  setInterval(updateTicketData, 5000); // Check every 5 seconds
</script>

</body>
</html>
"""
def hash_audrey_content(url):
    """Solo chequea el contenido relevante de Buscando a Audrey"""
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")

        # Elimina scripts, estilos, banners, etc.
        for tag in soup(["script", "style", "noscript", "meta", "iframe", "link", "svg"]):
            tag.decompose()
        # Elimina banners o elementos dinámicos conocidos (ajusta el selector según la web)
        for tag in soup.select(".banner, .dynamic, .cookie-banner, .ads, .date, .timestamp"):
            tag.decompose()

        # Aquí puedes seleccionar solo una parte relevante, por ejemplo:
        # main_content = soup.select_one("main")  # o el selector adecuado
        # content_text = main_content.get_text(separator=" ", strip=True) if main_content else soup.get_text(separator=" ", strip=True)

        content_text = soup.get_text(separator=" ", strip=True)
        normalized_text = " ".join(content_text.split())
        return hashlib.md5(normalized_text.encode("utf-8")).hexdigest()
    except Exception as e:
        return f"ERROR: {str(e)}"
      
@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)
@app.route('/changes')
def changes_dummy():
    return "Not implemented", 200
@app.route('/api/changes.json')
def get_changes_json():
    """Get detailed changes data as JSON"""
    global latest_changes
    
    # Filter only updated websites
    updated_sites = [c for c in latest_changes if "Actualizado" in c.get("status", "")]
    
    now = datetime.now(UTC).isoformat()
    
    # Create response with proper formatting
    response_data = {
        "resumen": {
            "total_sitios_monitoreados": len(latest_changes),
            "sitios_actualizados": len(updated_sites),
            "ultimo_chequeo": now,
            "fecha_legible": datetime.now(UTC).strftime("%d/%m/%Y %H:%M:%S UTC")
        },
        "sitios_web_actualizados": updated_sites
    }
    
    # Return pretty-printed JSON
    response = app.response_class(
        response=json.dumps(response_data, indent=2, ensure_ascii=False),
        status=200,
        mimetype='application/json'
    )
    return response

@app.route('/api/ticket-changes')
def get_ticket_changes():
    """Get ticket changes for the dashboard"""
    global latest_changes
    return jsonify(latest_changes)

@app.route('/api/check-changes')
def check_changes():
    """Check if there are any new changes"""
    try:
        has_new_changes = any(item.get('status', '').find('Actualizado') != -1 for item in latest_changes)
        return {"new_changes": has_new_changes}
    except:
        return {"new_changes": False}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
