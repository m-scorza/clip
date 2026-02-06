"""
API HTTP simples para o N8N chamar os scripts do pipeline.

Cada endpoint corresponde a uma etapa do pipeline.
O N8N chama esses endpoints via HTTP Request nodes.

Roda na porta 8000 dentro do Docker.
"""

import json
import os
import sys
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, "/app")


class WorkerHandler(BaseHTTPRequestHandler):
    """Handler HTTP para os endpoints do worker."""

    def do_POST(self):
        """Processa requisições POST."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._respond(400, {"error": "JSON inválido"})
            return

        routes = {
            "/pipeline/download": self._handle_download,
            "/pipeline/analyze": self._handle_analyze,
            "/pipeline/generate": self._handle_generate,
            "/pipeline/full": self._handle_full_pipeline,
            "/twitch/clips": self._handle_twitch_clips,
            "/research": self._handle_research,
            "/campaign/create": self._handle_create_campaign,
            "/campaign/list": self._handle_list_campaigns,
            "/campaign/add-link": self._handle_add_link,
            "/health": self._handle_health,
        }

        handler = routes.get(self.path)
        if not handler:
            self._respond(404, {"error": f"Rota não encontrada: {self.path}"})
            return

        try:
            result = handler(data)
            self._respond(200, result)
        except Exception as e:
            self._respond(500, {
                "error": str(e),
                "traceback": traceback.format_exc(),
            })

    def do_GET(self):
        """Health check."""
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        else:
            self._respond(404, {"error": "Use POST"})

    def _respond(self, status: int, data: dict):
        """Envia resposta JSON."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode())

    # --- Handlers ---

    def _handle_health(self, data: dict) -> dict:
        return {"status": "ok", "service": "clip-automator-worker"}

    def _handle_download(self, data: dict) -> dict:
        from src.downloader import download_video
        url = data.get("url")
        if not url:
            raise ValueError("Campo 'url' é obrigatório")
        info = download_video(url)
        return {"video_path": info["path"], "info": info}

    def _handle_analyze(self, data: dict) -> dict:
        from src.downloader import extract_audio
        from src.analyzer import transcribe_video, analyze_audio_energy, find_best_moments

        video_path = data.get("video_path")
        if not video_path:
            raise ValueError("Campo 'video_path' é obrigatório")

        audio_path = extract_audio(video_path)
        transcript = transcribe_video(audio_path)
        energy = analyze_audio_energy(audio_path)

        video_info = {"duration": data.get("duration", 0), "chapters": []}
        moments = find_best_moments(
            video_info=video_info,
            transcript=transcript,
            audio_energy=energy,
            num_clips=data.get("num_clips", 5),
        )

        return {
            "moments": [
                {
                    "start": m.start,
                    "end": m.end,
                    "score": m.score,
                    "reason": m.reason,
                    "text": m.text,
                }
                for m in moments
            ],
            "transcript_segments": transcript.get("segments", []),
        }

    def _handle_generate(self, data: dict) -> dict:
        from src.editor import process_clip

        video_path = data.get("video_path")
        moments = data.get("moments", [])
        output_dir = data.get("output_dir", "output/clips")

        clips = []
        for i, moment in enumerate(moments):
            clip_path = process_clip(
                video_path=video_path,
                start=moment["start"],
                end=moment["end"],
                output_dir=output_dir,
                clip_name=f"clip_{i+1:02d}",
                headline_text=moment.get("headline"),
            )
            clips.append(clip_path)

        return {"clips": clips}

    def _handle_full_pipeline(self, data: dict) -> dict:
        """Pipeline completo em uma chamada."""
        url = data.get("url")
        if not url:
            raise ValueError("Campo 'url' é obrigatório")

        # Simula args
        class Args:
            pass
        args = Args()
        args.url = url
        args.clips = data.get("num_clips", 5)
        args.headline = data.get("headline")
        args.category = data.get("category", "FAMOSOS")
        args.campaign_id = data.get("campaign_id")

        from main import run_pipeline
        clips = run_pipeline(args)

        return {
            "clips_generated": len(clips),
            "clips": [{"path": c["path"], "headline": c.get("headline")} for c in clips],
        }

    def _handle_twitch_clips(self, data: dict) -> dict:
        from src.twitch import search_and_download_best_clips

        username = data.get("username")
        client_id = data.get("client_id") or os.environ.get("TWITCH_CLIENT_ID")
        client_secret = data.get("client_secret") or os.environ.get("TWITCH_CLIENT_SECRET")

        if not all([username, client_id, client_secret]):
            raise ValueError("Campos 'username', TWITCH_CLIENT_ID e TWITCH_CLIENT_SECRET são obrigatórios")

        clips = search_and_download_best_clips(
            username=username,
            client_id=client_id,
            client_secret=client_secret,
            max_clips=data.get("max_clips", 10),
            min_views=data.get("min_views", 1000),
        )

        return {"clips": clips}

    def _handle_research(self, data: dict) -> dict:
        from src.research import research_clips_about, research_youtube_shorts, generate_research_report

        influencer = data.get("influencer")
        if not influencer:
            raise ValueError("Campo 'influencer' é obrigatório")

        youtube_data = research_youtube_shorts(influencer)
        competitor_data = research_clips_about(influencer)

        report = generate_research_report(
            influencer_name=influencer,
            youtube_data=youtube_data,
            competitor_data=competitor_data,
        )

        return {"report": report, "youtube_count": len(youtube_data), "competitor_count": len(competitor_data)}

    def _handle_create_campaign(self, data: dict) -> dict:
        from src.tracker import create_campaign
        campaign = create_campaign(
            name=data.get("name", "Nova Campanha"),
            influencer=data.get("influencer", ""),
            pay_per_1k_views=data.get("pay", 0),
            min_views=data.get("min_views", 10000),
        )
        return campaign

    def _handle_list_campaigns(self, data: dict) -> dict:
        from src.tracker import load_campaigns
        return load_campaigns()

    def _handle_add_link(self, data: dict) -> dict:
        from src.tracker import update_clip_link
        update_clip_link(
            campaign_id=data["campaign_id"],
            clip_id=data["clip_id"],
            platform=data["platform"],
            link=data["link"],
        )
        return {"status": "ok"}


def main():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), WorkerHandler)
    print(f"Worker API rodando na porta {port}")
    print("Endpoints disponíveis:")
    print("  POST /pipeline/full     - Pipeline completo")
    print("  POST /pipeline/download - Download de vídeo")
    print("  POST /pipeline/analyze  - Análise de momentos")
    print("  POST /pipeline/generate - Gerar clipes")
    print("  POST /twitch/clips      - Buscar clipes Twitch")
    print("  POST /research          - Pesquisa de influenciador")
    print("  POST /campaign/create   - Criar campanha")
    print("  POST /campaign/list     - Listar campanhas")
    print("  POST /campaign/add-link - Adicionar link")
    print("  GET  /health            - Health check")
    server.serve_forever()


if __name__ == "__main__":
    main()
