import os
import json
import math
import datetime
from flask import Flask, request, render_template_string, jsonify, Response
from threading import Lock
from functools import wraps

app = Flask(__name__)

# --- CONFIGURAÇÃO ---
DATA_DIR = "/app/data"
DB_FILE = os.path.join(DATA_DIR, 'leads_database.json')
PER_PAGE = 10 
db_lock = Lock()

# --- SEGURANÇA (LOGIN) ---
USUARIO_ADMIN = "admin"
SENHA_ADMIN = "fullbai123"  # <--- SUA SENHA AQUI

def check_auth(username, password):
    return username == USUARIO_ADMIN and password == SENHA_ADMIN

def authenticate():
    return Response(
    'Acesso negado. Você precisa fazer login para ver os leads.', 401,
    {'WWW-Authenticate': 'Basic realm="Login Necessario"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

if not os.path.exists(DATA_DIR):
    try: os.makedirs(DATA_DIR)
    except: pass

# --- BANCO DE DADOS ---
def init_db():
    if not os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'w', encoding='utf-8') as f: json.dump([], f)
        except: pass

def load_leads():
    init_db()
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def save_lead(new_lead):
    with db_lock: 
        leads = load_leads()
        leads.insert(0, new_lead)
        try:
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(leads, f, indent=4, ensure_ascii=False)
        except: pass

# --- ROTAS ---

@app.route('/webhook/is-captura-09', methods=['GET'])
def webhook_status():
    return "Webhook ON.", 200

@app.route('/webhook/is-captura-09', methods=['POST'])
def webhook():
    try:
        raw_data = {}
        if request.is_json: raw_data = request.json
        else: raw_data = request.form.to_dict()

        print(f"RECEBIDO: {raw_data}", flush=True)
        source = raw_data.get('body', raw_data)

        # AGORA CAPTURA TUDO
        lead_data = {
            'id': len(load_leads()) + 1, 
            'nome': source.get('Nome') or source.get('nome') or source.get('name') or 'N/A',
            'email': source.get('Email') or source.get('email') or 'N/A',
            'whatsapp': source.get('Seu Whatsapp (DDD) + 9 Digitos') or source.get('whatsapp') or source.get('telephone') or 'N/A',
            
            # UTMs Completas
            'origem': source.get('utm_source', '-'),
            'midia': source.get('utm_medium', '-'),   # <-- NOVO
            'campanha': source.get('utm_campaign', '-'),
            'conteudo': source.get('utm_content', '-'), # <-- NOVO
            'termo': source.get('utm_term', '-'),
            
            'data': source.get('data_hora') or datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            'form': source.get('form_name') or source.get('form_id', '-')
        }

        save_lead(lead_data)
        return jsonify({'status': 'success', 'message': 'Lead salvo'}), 200

    except Exception as e:
        print(f"ERRO: {str(e)}", flush=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/', methods=['GET'])
@requires_auth  # <--- PROTEGE A TELA COM SENHA
def index():
    leads = load_leads()
    query = request.args.get('search', '').lower()
    if query:
        leads = [l for l in leads if query in str(l.get('nome','')).lower() or query in str(l.get('email','')).lower() or query in str(l.get('whatsapp','')).lower()]

    page = request.args.get('page', 1, type=int)
    total_leads = len(leads)
    total_pages = math.ceil(total_leads / PER_PAGE)
    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE
    leads_paginated = leads[start:end]

    return render_template_string(HTML_TEMPLATE, leads=leads_paginated, page=page, total_pages=total_pages, total_leads=total_leads, query=query, per_page=PER_PAGE)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gestão de Leads</title>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root { --primary-color: #004635; --primary-hover: #1f8659; --text-primary: #111827; --text-secondary: #4b5563; --text-muted: #6b7280; --bg-white: #ffffff; --bg-light: #f9fafb; --bg-gray: #f3f4f6; --border-color: #e5e7eb; --radius: .5rem; }
        * { margin: 0; padding: 0; box-sizing: border-box; } 
        body { font-family: "DM Sans", sans-serif; background-color: var(--bg-light); color: var(--text-primary); padding: 2rem 1rem; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { margin-bottom: 2rem; display:flex; justify-content:space-between; align-items:center; }
        .title { font-size: 1.5rem; font-weight: 700; color: var(--text-primary); }
        .toolbar { background-color: var(--bg-white); border-radius: var(--radius); padding: 1rem; margin-bottom: 1rem; display: flex; gap: 1rem; box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); }
        .search-box { position: relative; flex: 1; }
        .search-input { width: 100%; padding: .5rem 1rem .5rem 2.5rem; border: 1px solid var(--border-color); border-radius: var(--radius); font-family: inherit; }
        .search-icon { position: absolute; left: .75rem; top: 50%; transform: translateY(-50%); color: var(--text-muted); width: 16px; height: 16px; }
        .action-btn { padding: .5rem 1rem; color: #fff; border: none; border-radius: var(--radius); cursor: pointer; font-family: inherit; font-size: .875rem; transition: all .2s; text-decoration: none; display: inline-block; }
        .search-btn { background-color: var(--primary-color); }
        .clear-btn { background-color: #6c757d; }
        .refresh-btn { background-color: #9ca3af; display: flex; align-items: center; justify-content: center;}
        .table-container { background-color: var(--bg-white); border-radius: var(--radius); box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); overflow: hidden; overflow-x: auto; }
        .products-table { width: 100%; border-collapse: collapse; min-width: 1000px; }
        .products-table th { padding: .75rem 1rem; text-align: left; font-size: .75rem; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; border-bottom: 1px solid var(--border-color); background-color: var(--bg-gray); }
        .products-table td { padding: .75rem 1rem; border-bottom: 1px solid var(--border-color); color: #373737; font-size: 14px; vertical-align: middle; }
        .products-table tr:hover { background-color: var(--bg-light); }
        .lead-name { font-weight: 500; color: var(--text-primary); }
        .lead-email { color: var(--text-secondary); }
        .whatsapp-badge { display: inline-block; padding: .25rem .5rem; border-radius: 9999px; font-size: .75rem; background-color: rgba(16,185,129,.1); color: #004635; font-weight: 500; }
        
        /* COLUNAS UTM */
        .utm-block { display:flex; flex-direction:column; gap:2px; }
        .utm-line { font-size: 12px; color: #555; line-height: 1.3; }
        .utm-label { color: #999; font-size: 11px; font-weight:600; text-transform:uppercase; margin-right:4px; }
        
        .date-info { font-size: 13px; color: var(--text-muted); }
        .pagination { display: flex; justify-content: space-between; align-items: center; padding: 1rem; border-top: 1px solid var(--border-color); }
        .pagination-info { font-size: .875rem; color: var(--text-secondary); }
        .pagination-controls { display: flex; gap: .25rem; }
        .page-btn { padding: .5rem .75rem; background: 0 0; border: 1px solid var(--border-color); color: var(--text-secondary); text-decoration: none; border-radius: var(--radius); font-size: .875rem; transition: all .2s; }
        .page-btn:hover { background-color: var(--bg-gray); }
        .page-btn.active { background-color: var(--primary-color); color: #fff; border-color: var(--primary-color); }
        .page-btn.disabled { opacity: 0.5; pointer-events: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="title">Leads Capturados ({{ total_leads }})</h1>
            <div style="font-size:12px; color:#999;">🔒 Seguro</div>
        </div>

        <div class="toolbar">
            <form action="/" method="get" style="display: flex; gap: 1rem; flex: 1;">
                <div class="search-box">
                    <svg class="search-icon" fill="currentColor" viewBox="0 0 16 16"><path d="M11.742 10.344a6.5 6.5 0 10-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 001.415-1.414l-3.85-3.85a1.007 1.007 0 00-.115-.1zM12 6.5a5.5 5.5 0 11-11 0 5.5 5.5 0 0111 0z"/></svg>
                    <input type="text" name="search" class="search-input" placeholder="Buscar por Nome, Email ou Whatsapp" value="{{ query }}">
                </div>
                <button type="submit" class="action-btn search-btn">Buscar</button>
                {% if query %}
                <a href="/" class="action-btn clear-btn">Limpar</a>
                {% endif %}
            </form>
            <a href="/" class="action-btn refresh-btn" title="Atualizar">
                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
            </a>
        </div>

        <div class="table-container">
            <table class="products-table">
                <thead>
                    <tr>
                        <th>CLIENTE</th>
                        <th>CONTATO</th>
                        <th>ORIGEM / MÍDIA</th>
                        <th>CAMPANHA / CONTEÚDO</th>
                        <th>DATA</th>
                    </tr>
                </thead>
                <tbody>
                    {% for lead in leads %}
                    <tr>
                        <td>
                            <div class="lead-name">{{ lead.nome }}</div>
                            <div style="font-size:11px; color:#999;">ID: {{ lead.id }}</div>
                        </td>
                        <td>
                            <div class="lead-email">{{ lead.email }}</div>
                            <span class="whatsapp-badge">{{ lead.whatsapp }}</span>
                        </td>
                        <td>
                            <div class="utm-block">
                                <div class="utm-line"><span class="utm-label">SRC:</span> {{ lead.origem }}</div>
                                <div class="utm-line"><span class="utm-label">MED:</span> {{ lead.get('midia', '-') }}</div>
                                <div class="utm-line"><span class="utm-label">TRM:</span> {{ lead.get('termo', '-') }}</div>
                            </div>
                        </td>
                        <td>
                            <div class="utm-block">
                                <div class="utm-line"><span class="utm-label">CMP:</span> {{ lead.campanha }}</div>
                                <div class="utm-line"><span class="utm-label">CNT:</span> {{ lead.get('conteudo', '-') }}</div>
                                <div class="utm-line"><span class="utm-label">FRM:</span> {{ lead.form }}</div>
                            </div>
                        </td>
                        <td><span class="date-info">{{ lead.data }}</span></td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="5" style="text-align: center; padding: 2rem;">Nenhum lead encontrado.</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

            {% if total_pages > 1 %}
            <div class="pagination">
                <div class="pagination-info">Página {{ page }} de {{ total_pages }}</div>
                <div class="pagination-controls">
                    <a href="/?page={{ page - 1 }}&search={{ query }}" class="page-btn {% if page <= 1 %}disabled{% endif %}">&lt;</a>
                    {% for p in range(1, total_pages + 1) %}
                        {% if p == page or p == 1 or p == total_pages or (p >= page - 2 and p <= page + 2) %}
                            <a href="/?page={{ p }}&search={{ query }}" class="page-btn {% if p == page %}active{% endif %}">{{ p }}</a>
                        {% elif p == page - 3 or p == page + 3 %}
                            <span style="padding: .5rem;">...</span>
                        {% endif %}
                    {% endfor %}
                    <a href="/?page={{ page + 1 }}&search={{ query }}" class="page-btn {% if page >= total_pages %}disabled{% endif %}">&gt;</a>
                </div>
            </div>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
