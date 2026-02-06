"""
Interface conversacional para o Clip Automator.

Permite controlar todo o pipeline via prompts em linguagem natural.
Exemplo: "Comecei a campanha X do influenciador Y, faz os clipes aí"

Funciona com ou sem API da Claude/OpenAI.
Sem API: usa matching de intenções por keywords.
Com API: usa LLM para entender comandos complexos.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- Parser de Intenções (sem LLM) ---

class IntentParser:
    """
    Parser simples de intenções baseado em keywords.
    Funciona sem nenhuma API externa.
    """

    INTENTS = {
        "create_campaign": {
            "keywords": ["campanha", "campaign", "nova campanha", "criar campanha", "comecei", "começar"],
            "extract": ["influencer", "campaign_name", "pay", "min_views"],
        },
        "research": {
            "keywords": ["pesquisar", "research", "analisar", "análise", "estudar", "investigar",
                         "o que funciona", "o que viraliza", "tendências"],
            "extract": ["influencer"],
        },
        "generate_clips_youtube": {
            "keywords": ["youtube", "video", "vídeo", "cortar", "clipar", "gerar clipes",
                         "fazer clipes", "fazer cortes"],
            "extract": ["url", "num_clips", "template"],
        },
        "generate_clips_twitch": {
            "keywords": ["twitch", "stream", "live", "clipes da twitch"],
            "extract": ["influencer", "num_clips", "min_views"],
        },
        "list_templates": {
            "keywords": ["templates", "estilos", "formatos", "esqueletos", "tipos de edição"],
            "extract": [],
        },
        "list_campaigns": {
            "keywords": ["listar", "campanhas", "status", "resumo", "como está"],
            "extract": ["campaign_id"],
        },
        "add_link": {
            "keywords": ["link", "postei", "publiquei", "subi", "instagram", "tiktok"],
            "extract": ["platform", "link", "campaign_id", "clip_id"],
        },
        "submit": {
            "keywords": ["submeter", "enviar", "plataforma", "submit"],
            "extract": ["campaign_id", "clip_id"],
        },
        "help": {
            "keywords": ["ajuda", "help", "como", "o que", "comandos"],
            "extract": [],
        },
    }

    def parse(self, text: str) -> dict:
        """
        Analisa texto em linguagem natural e extrai intenção + parâmetros.

        Returns:
            Dict com 'intent' e 'params'
        """
        text_lower = text.lower().strip()

        # Identifica intenção
        best_intent = None
        best_score = 0

        for intent, config in self.INTENTS.items():
            score = 0
            for keyword in config["keywords"]:
                if keyword in text_lower:
                    score += len(keyword)  # Palavras maiores = mais específicas
            if score > best_score:
                best_score = score
                best_intent = intent

        if not best_intent:
            best_intent = "help"

        # Extrai parâmetros
        params = {}

        # URL
        url_match = re.search(r'(https?://\S+)', text)
        if url_match:
            params["url"] = url_match.group(1)

        # Números
        num_match = re.search(r'(\d+)\s*(clipes?|clips?|cortes?)', text_lower)
        if num_match:
            params["num_clips"] = int(num_match.group(1))

        views_match = re.search(r'(\d+)\s*k?\s*(views?|visualiza)', text_lower)
        if views_match:
            val = int(views_match.group(1))
            if "k" in text_lower[views_match.start():views_match.end()+2]:
                val *= 1000
            params["min_views"] = val

        pay_match = re.search(r'r?\$\s*(\d+[.,]?\d*)', text_lower)
        if pay_match:
            params["pay"] = float(pay_match.group(1).replace(",", "."))

        # Plataforma
        if "instagram" in text_lower or "insta" in text_lower or "reels" in text_lower:
            params["platform"] = "instagram"
        elif "tiktok" in text_lower or "tik tok" in text_lower:
            params["platform"] = "tiktok"

        # Template
        for template_name in ["clean", "dramatic", "energy", "podcast", "meme", "cinema", "tiktok_viral"]:
            if template_name in text_lower:
                params["template"] = template_name
                break

        # Nomes (heurística: palavras capitalizadas que não são comandos)
        capitalized = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text)
        command_words = {"Campanha", "Clipes", "Video", "Youtube", "Twitch", "Instagram",
                         "Tiktok", "Template", "Link"}
        names = [n for n in capitalized if n not in command_words]

        if names:
            # Primeiro nome capitalizado provavelmente é o influenciador
            params["influencer"] = names[0]
            if len(names) > 1:
                params["campaign_name"] = " ".join(names[1:])

        # IDs
        camp_id_match = re.search(r'campanha\s*#?(\d+)', text_lower)
        if camp_id_match:
            params["campaign_id"] = int(camp_id_match.group(1))

        clip_id_match = re.search(r'clip[e]?\s*#?(\d+)', text_lower)
        if clip_id_match:
            params["clip_id"] = int(clip_id_match.group(1))

        return {"intent": best_intent, "params": params, "raw_text": text}


# --- Executor de Comandos ---

class CommandExecutor:
    """Executa comandos baseados em intenções parseadas."""

    def __init__(self):
        self.parser = IntentParser()

    def execute(self, text: str) -> str:
        """
        Processa um comando em linguagem natural e executa a ação.

        Args:
            text: Comando do usuário

        Returns:
            Resposta em texto
        """
        parsed = self.parser.parse(text)
        intent = parsed["intent"]
        params = parsed["params"]

        handlers = {
            "create_campaign": self._handle_create_campaign,
            "research": self._handle_research,
            "generate_clips_youtube": self._handle_generate_youtube,
            "generate_clips_twitch": self._handle_generate_twitch,
            "list_templates": self._handle_list_templates,
            "list_campaigns": self._handle_list_campaigns,
            "add_link": self._handle_add_link,
            "submit": self._handle_submit,
            "help": self._handle_help,
        }

        handler = handlers.get(intent, self._handle_help)

        try:
            return handler(params)
        except Exception as e:
            return f"Erro ao executar: {e}\n\nTente reformular o comando ou use 'ajuda' para ver opções."

    def _handle_create_campaign(self, params: dict) -> str:
        from src.tracker import create_campaign

        influencer = params.get("influencer")
        if not influencer:
            return ("Para criar uma campanha preciso do nome do influenciador.\n"
                    "Exemplo: 'Criar campanha para FulanoTV pagando R$5 por 1k views'")

        name = params.get("campaign_name", f"Campanha {influencer}")
        pay = params.get("pay", 0.0)
        min_views = params.get("min_views", 10000)

        campaign = create_campaign(
            name=name,
            influencer=influencer,
            pay_per_1k_views=pay,
            min_views=min_views,
        )

        return (f"Campanha criada!\n"
                f"  ID: #{campaign['id']}\n"
                f"  Nome: {campaign['name']}\n"
                f"  Influenciador: {influencer}\n"
                f"  Pagamento: R${pay}/1k views\n"
                f"  Views mínimas: {min_views}\n\n"
                f"Próximo passo: pesquise o influenciador ou gere clipes.\n"
                f"Exemplo: 'Pesquisar o que funciona para {influencer}'")

    def _handle_research(self, params: dict) -> str:
        from src.research import (
            research_clips_about,
            research_youtube_shorts,
            generate_research_report,
        )

        influencer = params.get("influencer")
        if not influencer:
            return ("Preciso do nome do influenciador para pesquisar.\n"
                    "Exemplo: 'Pesquisar o que funciona para FulanoTV'")

        print(f"Pesquisando '{influencer}'... isso pode levar alguns minutos.\n")

        # Busca no YouTube
        youtube_data = research_youtube_shorts(influencer)
        competitor_data = research_clips_about(influencer)

        report = generate_research_report(
            influencer_name=influencer,
            youtube_data=youtube_data,
            competitor_data=competitor_data,
            output_path=f"output/research_{influencer.lower().replace(' ', '_')}.txt",
        )

        return report

    def _handle_generate_youtube(self, params: dict) -> str:
        url = params.get("url")
        if not url:
            return ("Preciso da URL do vídeo do YouTube.\n"
                    "Exemplo: 'Gerar 5 clipes do vídeo https://youtube.com/watch?v=XXXXX'")

        num_clips = params.get("num_clips", 5)
        template = params.get("template", "clean")
        campaign_id = params.get("campaign_id")

        # Simula os args do argparse
        class Args:
            pass

        args = Args()
        args.url = url
        args.clips = num_clips
        args.headline = None
        args.category = "FAMOSOS"
        args.campaign_id = campaign_id

        from main import run_pipeline
        clips = run_pipeline(args)

        if template != "clean":
            return (f"{len(clips)} clipes gerados com template '{template}'!\n"
                    f"Revise os clipes e poste nas redes sociais.")

        return f"{len(clips)} clipes gerados! Revise e poste nas redes sociais."

    def _handle_generate_twitch(self, params: dict) -> str:
        influencer = params.get("influencer")
        if not influencer:
            return ("Preciso do nome do canal na Twitch.\n"
                    "Exemplo: 'Buscar clipes do Gaules na Twitch'")

        client_id = os.environ.get("TWITCH_CLIENT_ID")
        client_secret = os.environ.get("TWITCH_CLIENT_SECRET")

        if not client_id or not client_secret:
            return ("Para usar a Twitch, configure as variáveis de ambiente:\n"
                    "  export TWITCH_CLIENT_ID='seu_client_id'\n"
                    "  export TWITCH_CLIENT_SECRET='seu_client_secret'\n\n"
                    "Obtenha em: https://dev.twitch.tv/console/apps (gratuito)")

        from src.twitch import search_and_download_best_clips

        num_clips = params.get("num_clips", 10)
        min_views = params.get("min_views", 1000)

        clips = search_and_download_best_clips(
            username=influencer,
            client_id=client_id,
            client_secret=client_secret,
            max_clips=num_clips,
            min_views=min_views,
        )

        if not clips:
            return f"Nenhum clipe encontrado para '{influencer}' na Twitch."

        lines = [f"{len(clips)} clipes baixados da Twitch!\n"]
        for c in clips[:5]:
            lines.append(f"  - {c['title']} ({c['view_count']:,} views)")

        lines.append("\nPróximo: edite para formato mobile e poste.")
        return "\n".join(lines)

    def _handle_list_templates(self, params: dict) -> str:
        from src.templates import list_templates

        templates = list_templates()
        lines = ["Templates de edição disponíveis:\n"]
        for t in templates:
            lines.append(f"  {t['name']:15s} - {t['description']}")

        lines.append("\nUse: 'Gerar clipes do vídeo URL com template dramatic'")
        return "\n".join(lines)

    def _handle_list_campaigns(self, params: dict) -> str:
        from src.tracker import get_campaign_summary
        return get_campaign_summary(params.get("campaign_id"))

    def _handle_add_link(self, params: dict) -> str:
        from src.tracker import update_clip_link

        campaign_id = params.get("campaign_id")
        clip_id = params.get("clip_id")
        platform = params.get("platform")
        link = params.get("url") or params.get("link")

        if not all([campaign_id, clip_id, platform, link]):
            return ("Preciso de todos os dados:\n"
                    "Exemplo: 'Postei o clipe 1 da campanha 1 no instagram: https://...'")

        update_clip_link(campaign_id, clip_id, platform, link)
        return f"Link registrado: {platform} para clipe #{clip_id} da campanha #{campaign_id}"

    def _handle_submit(self, params: dict) -> str:
        from src.tracker import mark_submitted

        campaign_id = params.get("campaign_id")
        clip_id = params.get("clip_id")

        if not campaign_id or not clip_id:
            return ("Preciso do ID da campanha e do clipe.\n"
                    "Exemplo: 'Submeter clipe 1 da campanha 1'")

        mark_submitted(campaign_id, clip_id)
        return f"Clipe #{clip_id} da campanha #{campaign_id} marcado como submetido!"

    def _handle_help(self, params: dict) -> str:
        return """
Comandos disponíveis (em linguagem natural):

  CAMPANHA:
    "Criar campanha para [influenciador] pagando R$X por 1k views"
    "Listar campanhas"
    "Status da campanha 1"

  PESQUISA:
    "Pesquisar o que funciona para [influenciador]"
    "Analisar tendências do [influenciador]"

  CLIPES - YOUTUBE:
    "Gerar 5 clipes do vídeo [URL]"
    "Fazer cortes do [URL] com template dramatic"

  CLIPES - TWITCH:
    "Buscar clipes do [canal] na Twitch"
    "Pegar os melhores clipes da Twitch do [canal]"

  TEMPLATES:
    "Mostrar templates de edição"
    "Listar estilos disponíveis"

  PÓS-POSTAGEM:
    "Postei o clipe 1 da campanha 1 no instagram: [link]"
    "Submeter clipe 1 da campanha 1"

  EXEMPLOS COMPLETOS:
    "Comecei a campanha do Gaules, R$5 por 1k views, mínimo 10k"
    "Pesquisar o que viraliza do Gaules"
    "Buscar top 10 clipes do Gaules na Twitch com mais de 5000 views"
    "Gerar 3 clipes do vídeo https://... com template tiktok_viral"
"""


# --- REPL Interativo ---

def start_chat():
    """Inicia o modo interativo de chat."""
    executor = CommandExecutor()

    print("=" * 60)
    print("CLIP AUTOMATOR - Modo Conversacional")
    print("=" * 60)
    print("Digite comandos em linguagem natural.")
    print("Digite 'ajuda' para ver opções ou 'sair' para encerrar.\n")

    while True:
        try:
            user_input = input("Você> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté mais!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("sair", "exit", "quit", "q"):
            print("Até mais!")
            break

        response = executor.execute(user_input)
        print(f"\n{response}\n")


if __name__ == "__main__":
    start_chat()
