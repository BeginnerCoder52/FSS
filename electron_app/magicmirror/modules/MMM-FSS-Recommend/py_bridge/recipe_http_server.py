#!/usr/bin/env python3
"""Lightweight Flask HTTP server serving recipe pages for QR code scanning.

Routes:
  POST /api/recipe  — Accept recipe JSON, return {"id": "...", "url": "..."}
  GET  /r/<id>      — Render recipe as a dark-themed HTML page

Run standalone:  python3 recipe_http_server.py [--port 8081]
Or import:       recipe_http_server.start_server(port=8081)
"""
import sys, json, os, uuid, threading, logging

logging.basicConfig(level=logging.INFO, format="[RecipeHTTP] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

try:
    from flask import Flask, request, jsonify, render_template_string
except ImportError:
    print("ERROR: flask not installed. Run: pip install flask", file=sys.stderr)
    sys.exit(1)

app = Flask(__name__)

STORAGE: dict[str, dict] = {}
HOSTNAME = os.uname().nodename if hasattr(os, 'uname') else "fss-rpi"

RECIPE_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ recipe_name }} - FSS Recipe</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #1a1a2e; color: #e0e0e0; padding: 1.2rem; line-height: 1.6;
    max-width: 720px; margin: 0 auto;
  }
  h1 { font-size: 1.6rem; color: #fff; margin-bottom: 0.3rem; }
  .meta { color: #888; font-size: 0.85rem; margin-bottom: 1rem; }
  .meta span { margin-right: 1rem; }
  h2 { font-size: 1.1rem; color: #ffd700; margin: 1rem 0 0.4rem; }
  ul { padding-left: 1.2rem; margin-bottom: 0.6rem; }
  li { margin-bottom: 0.25rem; }
  .cook-step { margin-bottom: 0.5rem; padding-left: 0.5rem; border-left: 2px solid #ffd700; }
  .section { background: #16213e; border-radius: 8px; padding: 0.8rem; margin-bottom: 0.8rem; }
  .tag { display: inline-block; background: #0f3460; color: #e0e0e0; padding: 0.15rem 0.6rem;
         border-radius: 12px; font-size: 0.75rem; margin: 0.15rem; }
  hr { border: none; border-top: 1px solid #333; margin: 1rem 0; }
  .footer { text-align: center; color: #555; font-size: 0.7rem; margin-top: 1rem; }
  @media print { body { background: #fff; color: #000; }
    .section { background: #f5f5f5; } h2 { color: #b8860b; }
  }
</style>
</head>
<body>
  <h1>{{ recipe_name }}</h1>
  <div class="meta">
    {% if serving %}<span>🍽 {{ serving }}</span>{% endif %}
    {% if times %}<span>⏱ {{ times }}</span>{% endif %}
    {% if difficulty %}<span>📊 {{ difficulty }}</span>{% endif %}
  </div>

  {% if original_ingredients %}
  <div class="section">
    <h2>🧂 Nguyên liệu</h2>
    <ul>
    {% for item in original_ingredients %}
      <li>{{ item }}</li>
    {% endfor %}
    </ul>
  </div>
  {% endif %}

  {% if original_spices %}
  <div class="section">
    <h2>🌿 Gia vị</h2>
    <div>
    {% for spice in original_spices %}
      <span class="tag">{{ spice }}</span>
    {% endfor %}
    </div>
  </div>
  {% endif %}

  {% if process %}
  <div class="section">
    <h2>📋 Sơ chế</h2>
    {% for step in process %}
    <div class="cook-step">{{ step }}</div>
    {% endfor %}
  </div>
  {% endif %}

  {% if cook %}
  <div class="section">
    <h2>🍳 Cách nấu</h2>
    {% for step in cook %}
    <div class="cook-step">{{ step }}</div>
    {% endfor %}
  </div>
  {% endif %}

  {% if usage %}
  <div class="section">
    <h2>🍽 Cách dùng</h2>
    {% for step in usage %}
    <div class="cook-step">{{ step }}</div>
    {% endfor %}
  </div>
  {% endif %}

  {% if tips %}
  <div class="section">
    <h2>💡 Mẹo</h2>
    <div>{{ tips }}</div>
  </div>
  {% endif %}

  <hr>
  <div class="footer">FSS — Fridge Supervisor System</div>
</body>
</html>"""


@app.route("/api/recipe", methods=["POST"])
def api_create_recipe():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    recipe_id = str(uuid.uuid4())[:8]
    STORAGE[recipe_id] = data
    url = f"http://{HOSTNAME}.local:8081/r/{recipe_id}"
    logger.info(f"Stored recipe {recipe_id}: {data.get('recipe_name', 'unknown')}")
    return jsonify({"id": recipe_id, "url": url})


@app.route("/r/<recipe_id>")
def view_recipe(recipe_id):
    data = STORAGE.get(recipe_id)
    if not data:
        return "<h1>Recipe not found</h1><p>This recipe may have expired.</p>", 404
    return render_template_string(RECIPE_TEMPLATE, **data)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "recipes": len(STORAGE)})


def start_server(port: int = 8081, debug: bool = False):
    logger.info(f"Starting recipe HTTP server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
    start_server(port=port)
