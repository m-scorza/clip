#!/usr/bin/env python3
"""
Interface web do Clip Automator.
Roda no GitHub Codespaces com URL pública.

Uso:
    python web/app.py
    # Acesse http://localhost:5000 (ou a URL do Codespace)
"""

import json
import os
import sys
import threading
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "static"),
)

# Estado global de jobs em andamento
jobs = {}
job_counter = 0


# --- Páginas ---

@app.route("/")
def index():
    return render_template("index.html")


# --- API endpoints ---

@app.route("/api/smart", methods=["GET"])
def get_smart_status():
    """Retorna status do Claude AI (ligado/desligado)."""
    from config.settings import USE_CLAUDE_FOR_ANALYSIS
    # Recarrega o módulo para pegar valor atualizado
    import importlib
    import config.settings as settings_mod
    importlib.reload(settings_mod)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    return jsonify({
        "enabled": settings_mod.USE_CLAUDE_FOR_ANALYSIS,
        "api_key_set": bool(api_key),
        "api_key_preview": f"{api_key[:12]}..." if api_key else "",
    })


@app.route("/api/smart", methods=["POST"])
def toggle_smart():
    """Liga/desliga Claude AI."""
    import re
    data = request.json or {}
    enable = data.get("enabled", False)

    settings_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "settings.py")
    with open(settings_path, "r") as f:
        content = f.read()

    value = "True" if enable else "False"
    content = re.sub(r'USE_CLAUDE_FOR_ANALYSIS = \w+', f'USE_CLAUDE_FOR_ANALYSIS = {value}', content)

    with open(settings_path, "w") as f:
        f.write(content)

    return jsonify({"enabled": enable, "message": f"Claude AI {'LIGADO' if enable else 'DESLIGADO'}"})


@app.route("/api/costs", methods=["GET"])
def get_costs():
    """Retorna dados de custo da API."""
    from src.cost_audit import _load_audit
    data = _load_audit()

    # Agrega por operação
    by_operation = {}
    for c in data.get("calls", []):
        op = c["operation"]
        if op not in by_operation:
            by_operation[op] = {"count": 0, "brl": 0.0}
        by_operation[op]["count"] += 1
        by_operation[op]["brl"] += c["cost_brl"]

    return jsonify({
        "total_calls": len(data.get("calls", [])),
        "total_usd": data.get("total_usd", 0),
        "total_brl": data.get("total_brl", 0),
        "by_operation": by_operation,
        "recent": data.get("calls", [])[-10:],
    })


@app.route("/api/costs/roi", methods=["POST"])
def calculate_roi():
    """Calcula ROI."""
    data = request.json or {}
    revenue = data.get("revenue", 0)
    from src.cost_audit import _load_audit
    audit = _load_audit()
    cost = audit.get("total_brl", 0)
    profit = revenue - cost
    roi = ((revenue - cost) / cost * 100) if cost > 0 else 0
    return jsonify({
        "revenue": revenue,
        "cost": cost,
        "profit": profit,
        "roi_percent": roi,
        "worth_it": profit > 0,
    })


@app.route("/api/campaigns", methods=["GET"])
def list_campaigns():
    """Lista todas as campanhas."""
    from src.tracker import load_campaigns
    return jsonify(load_campaigns())


@app.route("/api/campaigns", methods=["POST"])
def create_campaign_api():
    """Cria uma campanha."""
    data = request.json or {}
    from src.tracker import create_campaign
    campaign = create_campaign(
        name=data.get("name", "Nova Campanha"),
        influencer=data.get("influencer", ""),
        pay_per_1k_views=data.get("pay", 0),
        min_views=data.get("min_views", 10000),
    )
    return jsonify(campaign)


@app.route("/api/campaigns/<int:campaign_id>/link", methods=["POST"])
def add_link_api(campaign_id):
    """Adiciona link a um clipe."""
    data = request.json or {}
    from src.tracker import update_clip_link
    update_clip_link(
        campaign_id=campaign_id,
        clip_id=data["clip_id"],
        platform=data["platform"],
        link=data["link"],
    )
    return jsonify({"status": "ok"})


@app.route("/api/templates", methods=["GET"])
def list_templates_api():
    """Lista templates de edição."""
    from src.templates import list_templates
    return jsonify(list_templates())


@app.route("/api/pipeline", methods=["POST"])
def start_pipeline():
    """Inicia pipeline em background, retorna job_id."""
    global job_counter
    data = request.json or {}

    url = data.get("url")
    if not url:
        return jsonify({"error": "Campo 'url' é obrigatório"}), 400

    job_counter += 1
    job_id = job_counter
    jobs[job_id] = {
        "id": job_id,
        "status": "running",
        "type": "pipeline",
        "logs": [],
        "result": None,
        "error": None,
    }

    def run_job():
        try:
            jobs[job_id]["logs"].append("Iniciando pipeline...")

            class Args:
                pass
            args = Args()
            args.url = url
            args.clips = data.get("clips", 5)
            args.headline = data.get("headline")
            args.category = data.get("category", "FAMOSOS")
            args.campaign_id = data.get("campaign_id")
            args.smart = data.get("smart", False)

            from main import run_pipeline
            clips = run_pipeline(args)

            jobs[job_id]["result"] = {
                "clips_count": len(clips),
                "clips": [{"path": c["path"], "headline": c.get("headline")} for c in clips],
            }
            jobs[job_id]["status"] = "done"
            jobs[job_id]["logs"].append(f"Concluído! {len(clips)} clipes gerados.")
        except Exception as e:
            jobs[job_id]["error"] = str(e)
            jobs[job_id]["status"] = "error"
            jobs[job_id]["logs"].append(f"ERRO: {e}")

    thread = threading.Thread(target=run_job, daemon=True)
    thread.start()

    return jsonify({"job_id": job_id, "status": "running"})


@app.route("/api/research", methods=["POST"])
def start_research():
    """Inicia pesquisa em background."""
    global job_counter
    data = request.json or {}
    influencer = data.get("influencer")
    if not influencer:
        return jsonify({"error": "Campo 'influencer' é obrigatório"}), 400

    job_counter += 1
    job_id = job_counter
    jobs[job_id] = {"id": job_id, "status": "running", "type": "research", "logs": [], "result": None, "error": None}

    def run_job():
        try:
            from src.research import research_clips_about, research_youtube_shorts, generate_research_report
            jobs[job_id]["logs"].append(f"Pesquisando '{influencer}'...")

            yt = research_youtube_shorts(influencer)
            jobs[job_id]["logs"].append(f"YouTube: {len(yt)} vídeos encontrados")

            comp = research_clips_about(influencer)
            jobs[job_id]["logs"].append(f"Clipes de terceiros: {len(comp)} encontrados")

            report = generate_research_report(influencer_name=influencer, youtube_data=yt, competitor_data=comp)
            jobs[job_id]["result"] = {"report": report, "youtube_count": len(yt), "competitor_count": len(comp)}
            jobs[job_id]["status"] = "done"
        except Exception as e:
            jobs[job_id]["error"] = str(e)
            jobs[job_id]["status"] = "error"

    threading.Thread(target=run_job, daemon=True).start()
    return jsonify({"job_id": job_id, "status": "running"})


@app.route("/api/jobs/<int:job_id>", methods=["GET"])
def get_job(job_id):
    """Retorna status de um job."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job não encontrado"}), 404
    return jsonify(job)


@app.route("/api/env", methods=["POST"])
def set_env():
    """Define variáveis de ambiente (para configurar API keys na interface)."""
    data = request.json or {}
    for key, value in data.items():
        if key in ("ANTHROPIC_API_KEY", "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET"):
            os.environ[key] = value
    return jsonify({"status": "ok", "keys_set": list(data.keys())})


# --- Servir arquivos de output ---

@app.route("/output/<path:filename>")
def serve_output(filename):
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
    return send_from_directory(output_dir, filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n{'='*50}")
    print(f"  Clip Automator Web")
    print(f"  http://localhost:{port}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=True)
