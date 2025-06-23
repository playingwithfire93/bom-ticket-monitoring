from flask import Flask, jsonify, render_template_string
import os
from datetime import datetime, UTC
import requests
import hashlib
import json

app = Flask(__name__)
previous_states = {}

@app.route("/")
def home():
    return render_template_string("""
    <style>
  body {
    font-family: 'Segoe UI', sans-serif;
    background: linear-gradient(to right, #fdfbfb, #ebedee);
    margin: 0;
    padding: 2rem;
      color: #1f2937;
  }

  h1 {
    font-size: 1.8rem;
    margin-bottom: 1.5rem;
  }

  .dashboard {
    max-width: 800px;
    margin: 0 auto;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }

  .last-checked {
    font-size: 0.9rem;
    color: #6b7280;
  }

  .badge {
    background-color: #10b981;
    color: white;
    padding: 0.3rem 0.7rem;
    border-radius: 0.5rem;
    font-size: 0.75rem;
  }

  .grid {
    display: grid;
    gap: 1rem;
  }

  .card {
    background: white;
    border: 1px solid #e5e7eb;
    padding: 1rem;
    border-radius: 0.75rem;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05);
    transition: transform 0.2s ease, box-shadow 0.3s ease;
  }
  .card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
}
  .card h3 {
    margin: 0 0 0.5rem 0;
    font-size: 1.1rem;
  }

  .card p {
    margin: 0.2rem 0;
    font-size: 0.9rem;
  }

  #toast {
    position: fixed;
    bottom: 1rem;
    right: 1rem;
    background-color: #ec4899;
    color: white;
    padding: 1rem 1.5rem;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    display: none;
    z-index: 9999;
    animation: fadeInUp 0.6s ease, fadeOut 0.6s ease 3.4s;
  }

  @keyframes fadeInOut {
    0% { opacity: 0; transform: translateY(20px); }
    10% { opacity: 1; transform: translateY(0); }
    90% { opacity: 1; }
    100% { opacity: 0; transform: translateY(20px); }
  }
</style>

    </head>
    <body>
      <h1>🎭 Ticket monitoring dashboard</h1>

      <div class="dashboard">
        <div class="header">
          <p id="lastChecked" class="last-checked">Last Checked: ...</p>
          <span class="badge">🔄 Auto-refreshing</span>
        </div>

        <div id="changesList" class="grid">
          <div class="card"><span>⏳</span><span>Loading updates...</span></div>
        </div>
      </div>

      <div id="toast">Cambio detectado</div>

      <!-- 🔊 Audio element for notification -->
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
        document.getElementById("loadingIndicator").style.display = "block";
const res = await fetch("/changes");
document.getElementById("loadingIndicator").style.display = "none";
        async function update() {
          const res = await fetch("/changes");
          const data = await res.json();

          document.getElementById("lastChecked").textContent =
            "Last Checked: " + new Date().toLocaleString("es-ES");

          const list = document.getElementById("changesList");
          list.innerHTML = "";

          // 🎯 Update tab title
          if (data.length > 0) {
            document.title = `(${data.length}) Cambios detectados 🎟️`;
          } else {
            document.title = "🎟️ Ticket Monitor Dashboard";
          }

          if (data.length === 0) {
            const card = document.createElement("div");
            card.className = "card";
            card.innerHTML = "<span>✅</span><span>No new changes detected.</span>";
            list.appendChild(card);
          } else {
            const notifSound = document.getElementById("notifSound");
            data.forEach(change => {
              const card = document.createElement("div");
              card.className = "card";
              card.innerHTML = `
                <h3>Cambio detectado</h3>
                <p><a href="${change.url}" target="_blank">${change.url}</a></p>
                <p>${change.timestamp}</p>
              `;
              list.appendChild(card);

              // ✅ Toast and sound
              showToast(`🔔 Cambio en:\n${change.url}`);
              notifSound.play().catch(() => {}); // prevent autoplay errors
              if ("vibrate" in navigator) {
  navigator.vibrate([100, 50, 100]);
}

            });
          }
        }

        update();
        setInterval(update, 10000);
      </script>
    </body>
    </html>
    """)


URLS = [
    {"label": "test", "url": "https://httpbin.org/get/"},
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

def hash_url_content(url):
    try:
        response = requests.get(url, timeout=10)
        content_hash = hashlib.md5(response.content).hexdigest()
        return content_hash
    except Exception as e:
        return f"ERROR: {str(e)}"
@app.route("/changes")  
def changes():
    global previous_states
    updates = []

    for item in URLS:
        url = item["url"]
        current_hash = hash_url_content(url)
        last_hash = previous_states.get(url)

        if last_hash and last_hash != current_hash:
            updates.append({
                "url": url,
                "timestamp": datetime.now(UTC).isoformat()
            })

        # This should be outside the if block
        previous_states[url] = current_hash

    return jsonify(updates)


@app.route("/urls")
def urls():
    with open("urls.json") as f:
        data = json.load(f)
    return jsonify(data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
