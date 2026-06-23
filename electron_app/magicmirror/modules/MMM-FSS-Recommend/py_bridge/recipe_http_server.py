#!/usr/bin/env python3
import sys
import json
import uuid
from flask import Flask, request, render_template_string, jsonify
import threading
import qrcode
import base64
from io import BytesIO
import socket
import logging

# Disable Flask default logging to avoid cluttering MagicMirror stdout
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
recipes_db = {}

def get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def generate_qr_base64(url):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Danh sách đi chợ: {{ recipe.recipe_name }}</title>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #121212; color: #ffffff; padding: 20px; line-height: 1.6; margin: 0; }
        h1 { font-size: 24px; color: #4facfe; margin-bottom: 5px; }
        .summary { color: #aaaaaa; font-size: 14px; margin-bottom: 20px; }
        .category { font-weight: bold; margin-top: 20px; font-size: 18px; border-bottom: 1px solid #333; padding-bottom: 5px; margin-bottom: 10px; }
        ul { list-style: none; padding: 0; margin: 0; }
        li { padding: 12px 15px; background-color: #1e1e1e; margin-bottom: 8px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; }
        .missing { border-left: 4px solid #ff4444; }
        .available { border-left: 4px solid #00C851; }
        .qty { font-weight: bold; color: #4facfe; background: rgba(79, 172, 254, 0.1); padding: 4px 8px; border-radius: 4px; font-size: 0.9em; }
        .name { flex: 1; margin-right: 10px; }
        .empty { color: #888; font-style: italic; }
    </style>
</head>
<body>
    <h1>{{ recipe.recipe_name }}</h1>
    <div class="summary">{{ recipe.summary }}</div>
    
    <div class="category">🛒 Cần mua</div>
    <ul>
        {% set has_missing = false %}
        {% for item in recipe.ingredients if item.status == 'missing' %}
            {% set has_missing = true %}
            <li class="missing"><span class="name">{{ item.name }}</span><span class="qty">Thiếu {{ item.required - item.available }}</span></li>
        {% endfor %}
        {% if not has_missing %}
            <li class="available empty"><span>(Không cần mua thêm gì)</span></li>
        {% endif %}
    </ul>

    <div class="category">✅ Đã có ở nhà</div>
    <ul>
        {% set has_available = false %}
        {% for item in recipe.ingredients if item.status == 'available' %}
            {% set has_available = true %}
            <li class="available"><span class="name">{{ item.name }}</span><span class="qty">Sẵn {{ item.available }}</span></li>
        {% endfor %}
        {% if not has_available %}
            <li class="missing empty"><span>(Chưa có nguyên liệu nào)</span></li>
        {% endif %}
    </ul>
</body>
</html>
"""

@app.route('/r/<recipe_id>')
def view_recipe(recipe_id):
    recipe = recipes_db.get(recipe_id)
    if not recipe:
        return "Recipe not found or expired", 404
    return render_template_string(HTML_TEMPLATE, recipe=recipe)

def run_server():
    app.run(host='0.0.0.0', port=8081, debug=False, use_reloader=False)

if __name__ == '__main__':
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            
            msg = json.loads(line)
            if msg.get("type") == "GENERATE_QR":
                data = msg.get("data", {})
                recipe_id = str(uuid.uuid4())[:8]
                recipes_db[recipe_id] = data
                
                url = f"http://{get_ip_address()}:8081/r/{recipe_id}"
                qr_b64 = generate_qr_base64(url)
                
                print(json.dumps({
                    "type": "QR_RESULT", 
                    "data": {"url": url, "qr_base64": qr_b64}
                }), flush=True)
        except Exception as e:
            print(json.dumps({"type": "ERROR", "message": str(e)}), flush=True)
