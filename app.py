from flask import Flask, jsonify, render_template_string
import os
from datetime import datetime, UTC
import requests
import hashlib
import json
from bs4 import BeautifulSoup
from bs4.element import Comment
from telegram import Bot

app = Flask(__name__)
previous_states = {}
change_log = []  # <-- Add this line
MAX_LOG_ENTRIES = 50  # Show last 50 changes
TELEGRAM_TOKEN = '7763897628:AAEQVDEOBfHmWHbyfeF_Cx99KrJW2ILlaw0'
CHAT_ID = '553863319'

def send_telegram_text(url, changes, timestamp):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        message = (
            f"🎭 Ticket Alert!\n"
            f"🌐 URL: {url}\n"
            f"🕒 Cambio detectado: {timestamp}\n"
            f"📄 Cambios:\n{changes[:3500]}"
        )
        bot.send_message(chat_id=CHAT_ID, text=message)
        print("✅ Telegram message sent!")
    except Exception as e:
        print(f"❌ Telegram error: {e}")
    
@app.route("/")
def home():
  return render_template_string("""
  <!DOCTYPE html>
  <html lang="es">
  <head>
    <meta charset="UTF-8">
    <title>🎟️ Ticket Monitor</title>
    <style>
      body {
        font-family: 'Segoe UI', sans-serif;
        background-color: #DFDBE5;
        background-image: url("data:image/svg+xml,%3Csvg width='24' height='24' viewBox='0 0 24 24' xmlns='http://www.w3.org/2000/svg'%3E%3Ctitle%3Ehoundstooth%3C/title%3E%3Cg fill='%23f9629f' fill-opacity='0.4' fill-rule='evenodd'%3E%3Cpath d='M0 18h6l6-6v6h6l-6 6H0M24 18v6h-6M24 0l-6 6h-6l6-6M12 0v6L0 18v-6l6-6H0V0'/%3E%3C/g%3E%3C/svg%3E");
        margin: 0;
        padding: 2rem;
        color: #4b006e;
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
      }
      .dashboard {
        max-width: 1100px;
        margin: 0 auto;
        padding: 0 1rem;
        width: 100%;
        display: flex;
        flex-direction: column;
        align-items: center;
      }
      .header {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-bottom: 1rem;
        gap: 2rem;
        width: 100%;
      }
      h1 {
        font-size: 2.2rem;
        text-align: center;
        color: #d63384;
        text-shadow: 0 1px 2px rgba(0,0,0,0.1);
        margin-bottom: 1.5rem;
        width: 100%;
      }
      .grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 2rem; /* <-- Cambia este valor para más o menos espacio */
        justify-items: center;
        align-items: stretch;
        width: 100%;
      }
      .card {
        background: #fff0f7;
        border: 2px dashed #f472b6;
        padding: 1.2rem 1rem;
        border-radius: 1rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transition: transform 0.2s ease, box-shadow 0.3s ease;
        min-height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;IS IT POSSIBLE TO ADD A LOG OF  
        
        text-align: center;
        width: 100%;
        max-width: 340px;
        color: #e11d48; /* <-- TEXTO ROSA */
    }
      .card a {
        word-break: break-all;
        overflow-wrap: anywhere;
        display: inline-block;
        max-width: 100%;
        text-align: center;
      }
      .card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
      }
      .card h3 {
        margin-top: 0;
        margin-bottom: 0.5rem;
        font-size: 1.2rem;
        color: #e11d48;
        width: 100%;
      }
      .card p {
        margin: 0.2rem 0;
        font-size: 0.95rem;
        color: #9d174d;
        width: 100%;
      }
      .card:nth-child(even) {
        background-color: #fff7fb;
      }
      .card.updated {
        animation: flashBorder 1.2s ease;
      }
      @keyframes flashBorder {
        0% { border-color: #f43f5e; box-shadow: 0 0 0 0 rgba(244,63,94,0.7); }
        50% { border-color: #fb7185; box-shadow: 0 0 8px 4px rgba(244,63,94,0.3); }
        100% { border-color: #ec4899; box-shadow: none; }
      }
      #toast {
        position: fixed;
        bottom: 1rem;
        right: 1rem;
        background: #ec4899;
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 1rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        display: none;
        z-index: 9999;
        animation: fadeInOut 0.6s ease-in-out forwards;
      }
      @keyframes fadeInOut {
        0% { opacity: 0; transform: translateY(20px); }
        10% { opacity: 1; transform: translateY(0); }
        90% { opacity: 1; }
        100% { opacity: 0; transform: translateY(20px); }
      }
      @keyframes glow {
        0% { box-shadow: 0 0 10px #ec4899; }
        100% { box-shadow: none; }
      }
      .card.recent-change {
        animation: glow 1s ease-in-out 3;
      }
      #loadingIndicator {
        text-align: center;
        font-style: italic;
        color: #c026d3;
        margin-top: 1rem;
        width: 100%;
      }
      @media (max-width: 900px) {
        .grid {
          grid-template-columns: repeat(2, 1fr);
        }
      }
      @media (max-width: 600px) {
        .grid {
          grid-template-columns: 1fr;
        }
      }
      </style>
  </head>
  <body>
    <h1>🌸✨ Ticket Monitoring Dashboard ✨🌸</h1>
    <div class="dashboard">
    <div class="header">
  <p id="lastChecked" class="last-checked">Last Checked: ...</p>
  <div class="card" style="padding:0.5rem 0.5rem; max-width:180px; min-height:auto; background:#ffe4f1; border-color:#ec4899;">
    💖 Auto-refreshing
  </div>
</div>
    <div id="changesList" class="grid">
      <div class="card"><span>⏳</span> <span>Loading updates...</span></div>
    </div>
    </div>
    <div id="toast">Cambio detectado</div>
    <audio id="notifSound" preload="auto">
    <source src="{{ url_for('static', filename='door-bell-sound-99933.mp3') }}" type="audio/mpeg">
    </audio>
    <p id="loadingIndicator">🔎 Checking for updates...</p>
    <script>
    function showToast(message) {
      const toast = document.getElementById("toast");
      toast.textContent = message;
      toast.style.display = "block";
      toast.style.animation = "fadeInOut 4s ease-in-out forwards";
      setTimeout(() => {
      toast.style.display = "none";
      }, 4000);
    }
    async function update() {
      document.getElementById("loadingIndicator").style.display = "block";
      const res = await fetch("/changes");
      const data = await res.json();
      document.getElementById("loadingIndicator").style.display = "none";
      document.getElementById("lastChecked").textContent =
      "Última revisión: " + new Date().toLocaleString("es-ES");
      const list = document.getElementById("changesList");
      list.innerHTML = "";
      if (data.length === 0) {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = "<span>✅</span><span> Todo está fabuloso. Sin cambios detectados.</span>";
      list.appendChild(card);
      document.title = `(${data.length}) 🎟️ Cambios detectados`;
      } else {
      const notifSound = document.getElementById("notifSound");
      data.forEach(change => {
        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = `
        <h3>${change.label}</h3>
        <p><a href="${change.url}" target="_blank">${change.url}</a></p>
        <p>${change.status}</p>
        <p>🕒 ${new Date(change.timestamp).toLocaleString("es-ES")}</p>
        `;
        if (change.status.includes("Actualizado")) {
        card.style.borderColor = "#ec4899";
        card.style.backgroundColor = "#ffe4f1";
        card.classList.add("recent-change");
        showToast(`🎀 Cambio en:\n${change.url}`);
        notifSound.play().catch(() => {});
        if ("vibrate" in navigator) navigator.vibrate([120, 60, 120]);
        }
        list.appendChild(card);
      });
      }
    }
          <!-- Add at the bottom of your HTML, before </body> -->
      <div id="changeLogContainer" style="width:100%;margin-top:2rem;">
        <h2 style="text-align:center;color:#ec4899;">📝 Historial de Cambios</h2>
        <ul id="changeLog" style="list-style:none;padding:0;text-align:center;"></ul>
      </div>
      <script>
      async function updateLog() {
        const res = await fetch("/changelog");
        const log = await res.json();
        const logList = document.getElementById("changeLog");
        logList.innerHTML = "";
        if (log.length === 0) {
          logList.innerHTML = "<li style='color:#aaa;'>Sin cambios recientes.</li>";
        } else {
          log.slice().reverse().forEach(entry => {
            const li = document.createElement("li");
            li.style.marginBottom = "0.5rem";
            li.innerHTML = `<b style="color:#e11d48;">${entry.label}</b> 
              <a href="${entry.url}" target="_blank" style="color:#c026d3;">${entry.url}</a>
              <span style="color:#9d174d;">${entry.status}</span>
              <span style="color:#aaa;">${new Date(entry.timestamp).toLocaleString("es-ES")}</span>`;
            logList.appendChild(li);
          });
        }
      }
      updateLog();
      setInterval(updateLog, 15000);
      </script>
    update();
    setInterval(update, 10000);
    </script>
  </body>
  </html>
  """)



URLS = [
    #{"label": "test", "url": "https://httpbin.org/get/"},
    {"label": "Wicked", "url": "https://wickedelmusical.com/"},
    {"label": "Wicked elenco", "url": "https://wickedelmusical.com/elenco"},
    {"label": "Wicked entradas", "url": "https://tickets.wickedelmusical.com/espectaculo/wicked-el-musical/W01"},
    {"label": "Houdini", "url": "https://www.houdinielmusical.com"},
    {"label": "Los Miserables", "url": "https://miserableselmusical.es/"},
    {"label": "Los Miserables elenco", "url": "https://miserableselmusical.es/elenco"},
    {"label": "Los Miserables entradas", "url": "https://tickets.miserableselmusical.es/espectaculo/los-miserables/M01"},
    {"label": "The Book of Mormon", "url": "https://thebookofmormonelmusical.es"},
    {"label": "Mormon elenco", "url": "https://thebookofmormonelmusical.es/elenco/"},
    {"label": "Mormon entradas", "url": "https://tickets.thebookofmormonelmusical.es/espectaculo/the-book-of-mormon-el-musical/BM01"},
    {"label": "Buscando a Audrey", "url": "https://buscandoaaudrey.com"}
]
from bs4 import BeautifulSoup

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

        # Remove common dynamic elements by class/id (add more as needed)
        dynamic_selectors = [
            ".date_info", ".timestamp", "#ad", ".ads", ".cookie-banner", "#cookies", ".tracker"
        ]
        for selector in dynamic_selectors:
            for tag in soup.select(selector):
                tag.decompose()

        # Normalize whitespace and strip
        content_text = soup.get_text(separator=" ", strip=True)
        normalized_text = " ".join(content_text.split())  # remove excessive whitespace

        return hashlib.md5(normalized_text.encode("utf-8")).hexdigest()
    except Exception as e:
        return f"ERROR: {str(e)}"



def extract_normalized_date_info(url):
    """Get normalized text content from .date_info element."""
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    date_info = soup.select_one('.date_info')
    if not date_info:
        return None

    text = date_info.get_text(strip=True)
    return ' '.join(text.split()).lower()

      

@app.route("/changes")
def changes():
    global previous_states
    changes_list = []
    now = datetime.now(UTC).isoformat()

    for item in URLS:
        label = item["label"]
        url = item["url"]

        # For test URL, always mark as updated
        if "httpbin.org" in url:
            status = "¡Actualizado! 🎉"
            state = str(datetime.now())
        else:
            state = extract_normalized_date_info(url)
            if state is None:
                state = hash_url_content(url)

            last_state = previous_states.get(url)
            if last_state is None:
                status = "Primer chequeo 👀"
            elif last_state != state:
                status = "¡Actualizado! 🎉"
                send_telegram_text(url, "Cambio detectado en la web", now)
                # --- Add to log ---
                change_log.append({
                    "label": label,
                    "url": url,
                    "timestamp": now,
                    "status": status
                })
                if len(change_log) > MAX_LOG_ENTRIES:
                    change_log.pop(0)
            else:
                status = "Sin cambios ✨"

        previous_states[url] = state

        changes_list.append({
            "label": label,
            "url": url,
            "status": status,
            "timestamp": now
        })

    return jsonify(changes_list)
@app.route("/changelog")
def changelog():
    return jsonify(list(change_log))
@app.route("/urls")
def urls():
    with open("urls.json") as f:
        data = json.load(f)
    return jsonify(data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
