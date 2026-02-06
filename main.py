#!/usr/bin/env python3
"""
Clip Automator - Pipeline de automação de clipes para campanhas de influenciadores.

Uso:
    python main.py chat                    # Modo conversacional (prompt-driven)
    python main.py pipeline --url URL      # Pipeline YouTube
    python main.py twitch --username CANAL # Pipeline Twitch
    python main.py research --influencer X # Pesquisa competitiva
    python main.py templates               # Listar templates de edição
    python main.py campaign --create ...   # Gerenciar campanhas

Exemplos:
    # Modo conversacional (recomendado)
    python main.py chat

    # Gerar 5 clipes de um vídeo do YouTube
    python main.py pipeline --url "https://youtube.com/watch?v=XXXXX" --clips 5

    # Buscar clipes populares da Twitch
    python main.py twitch --username "gaules" --clips 10 --min-views 5000

    # Pesquisar o que funciona para um influenciador
    python main.py research --influencer "FulanoTV"
"""

import argparse
import os
import sys

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import (
    CLIPS_DIR,
    DOWNLOAD_DIR,
    MAX_CLIP_DURATION_SECONDS,
    MIN_CLIP_DURATION_SECONDS,
    NUM_CLIPS_TO_GENERATE,
    TARGET_CLIP_DURATION_SECONDS,
    USE_CLAUDE_FOR_ANALYSIS,
    WHISPER_LANGUAGE,
    WHISPER_MODEL,
)
from src.downloader import download_video, extract_audio
from src.analyzer import (
    analyze_audio_energy,
    find_best_moments,
    transcribe_video,
)
from src.editor import process_clip
from src.tracker import (
    add_clip_to_campaign,
    create_campaign,
    get_campaign_summary,
    mark_submitted,
    update_clip_link,
)


def run_pipeline(args):
    """Executa o pipeline completo: download -> análise -> corte -> edição."""
    url = args.url
    num_clips = args.clips or NUM_CLIPS_TO_GENERATE
    headline = args.headline
    category = args.category or "FAMOSOS"
    campaign_id = args.campaign_id

    print("=" * 60)
    print("CLIP AUTOMATOR - Pipeline de Clipes")
    print("=" * 60)

    # Etapa 1: Download
    print("\n[1/4] Baixando vídeo...")
    video_info = download_video(url, DOWNLOAD_DIR)
    video_path = video_info["path"]
    print(f"  Título: {video_info['title']}")
    print(f"  Duração: {video_info['duration'] // 60}min {video_info['duration'] % 60}s")
    print(f"  Canal: {video_info['channel']}")

    # Etapa 2: Transcrição e análise de áudio
    print("\n[2/4] Analisando vídeo...")
    audio_path = extract_audio(video_path)

    print("  Transcrevendo áudio...")
    transcript = transcribe_video(audio_path, model=WHISPER_MODEL, language=WHISPER_LANGUAGE)

    print("  Analisando energia do áudio...")
    energy = analyze_audio_energy(audio_path)

    # Etapa 3: Encontrar melhores momentos
    use_claude = getattr(args, 'smart', False) or USE_CLAUDE_FOR_ANALYSIS
    if use_claude:
        print("\n[3/4] Encontrando melhores momentos (Claude AI)...")
    else:
        print("\n[3/4] Encontrando melhores momentos...")
    moments = find_best_moments(
        video_info=video_info,
        transcript=transcript,
        audio_energy=energy,
        num_clips=num_clips,
        min_duration=MIN_CLIP_DURATION_SECONDS,
        max_duration=MAX_CLIP_DURATION_SECONDS,
        target_duration=TARGET_CLIP_DURATION_SECONDS,
        use_claude=use_claude,
    )

    print(f"  {len(moments)} momentos encontrados:")
    for i, m in enumerate(moments):
        mins = int(m.start // 60)
        secs = int(m.start % 60)
        print(f"    #{i+1}: {mins}:{secs:02d} - score={m.score:.2f} ({m.reason})")
        if m.text:
            preview = m.text[:80] + "..." if len(m.text) > 80 else m.text
            print(f"         \"{preview}\"")

    # Etapa 4: Gerar clipes
    print("\n[4/4] Gerando clipes editados...")
    video_id = video_info["id"]
    output_dir = os.path.join(CLIPS_DIR, video_id)
    generated_clips = []

    for i, moment in enumerate(moments):
        clip_name = f"clip_{i+1:02d}"
        print(f"\n  Processando clip #{i+1}/{len(moments)}:")

        clip_headline = headline
        # Se a Claude já gerou headline, usa ela
        if not clip_headline and hasattr(moment, 'headline') and moment.headline:
            clip_headline = moment.headline
        elif not clip_headline and moment.text:
            if use_claude:
                try:
                    from src.claude_ai import generate_headline
                    clip_headline = generate_headline(
                        clip_text=moment.text,
                        video_title=video_info.get("title", ""),
                    )
                except Exception:
                    clip_headline = _auto_headline(moment.text)
            else:
                clip_headline = _auto_headline(moment.text)

        try:
            clip_path = process_clip(
                video_path=video_path,
                start=moment.start,
                end=moment.end,
                output_dir=output_dir,
                clip_name=clip_name,
                transcript_segments=transcript.get("segments", []),
                headline_text=clip_headline,
                category=getattr(moment, 'category', category),
            )
            generated_clips.append({
                "path": clip_path,
                "moment": moment,
                "headline": clip_headline,
            })

            # Registra na campanha se especificada
            if campaign_id:
                add_clip_to_campaign(
                    campaign_id=campaign_id,
                    clip_path=clip_path,
                    source_video_url=url,
                    clip_start=moment.start,
                    clip_end=moment.end,
                )

        except Exception as e:
            print(f"  ERRO no clip #{i+1}: {e}")
            continue

    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"Clipes gerados: {len(generated_clips)}/{len(moments)}")
    print(f"Diretório: {output_dir}")
    print()

    for i, clip in enumerate(generated_clips):
        print(f"  #{i+1}: {clip['path']}")
        if clip["headline"]:
            print(f"       Headline: {clip['headline']}")

    print()
    print("PRÓXIMOS PASSOS (manual):")
    print("  1. Revise os clipes gerados")
    print("  2. Poste nos Instagram/TikTok")
    print("  3. Registre os links:")
    print(f"     python main.py campaign --add-link --campaign-id ID --clip-id ID --platform instagram --link URL")
    print("  4. Submeta na plataforma da campanha:")
    print(f"     python main.py campaign --submit --campaign-id ID --clip-id ID")
    print()

    return generated_clips


def run_campaign(args):
    """Gerencia campanhas."""
    if args.create:
        create_campaign(
            name=args.name,
            influencer=args.influencer,
            platform_url=args.platform_url or "",
            pay_per_1k_views=args.pay or 0.0,
            min_views=args.min_views or 10000,
        )
    elif args.list:
        print(get_campaign_summary(args.id))
    elif args.add_link:
        update_clip_link(
            campaign_id=args.campaign_id,
            clip_id=args.clip_id,
            platform=args.platform,
            link=args.link,
        )
    elif args.submit:
        mark_submitted(
            campaign_id=args.campaign_id,
            clip_id=args.clip_id,
        )
    else:
        print("Use --create, --list, --add-link ou --submit")


def _auto_headline(text: str, max_length: int = 60) -> str:
    """Gera headline automática a partir do texto transcrito."""
    text = text.strip().upper()

    # Pega a primeira frase completa
    for sep in [".", "!", "?"]:
        if sep in text:
            text = text[: text.index(sep) + 1]
            break

    if len(text) > max_length:
        text = text[: max_length - 3] + "..."

    return text


def main():
    parser = argparse.ArgumentParser(
        description="Clip Automator - Automação de clipes para campanhas"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Pipeline
    pipe_parser = subparsers.add_parser("pipeline", help="Executar pipeline de clipes")
    pipe_parser.add_argument("--url", required=True, help="URL do vídeo do YouTube")
    pipe_parser.add_argument("--clips", type=int, help="Número de clipes para gerar")
    pipe_parser.add_argument("--headline", help="Texto da headline (auto se não especificado)")
    pipe_parser.add_argument("--category", help="Categoria do banner (ex: FAMOSOS)")
    pipe_parser.add_argument("--campaign-id", type=int, help="ID da campanha para registrar")
    pipe_parser.add_argument("--smart", action="store_true", help="Usar Claude AI para análise inteligente (requer ANTHROPIC_API_KEY)")

    # Campaign
    camp_parser = subparsers.add_parser("campaign", help="Gerenciar campanhas")
    camp_parser.add_argument("--create", action="store_true", help="Criar nova campanha")
    camp_parser.add_argument("--list", action="store_true", help="Listar campanhas")
    camp_parser.add_argument("--add-link", action="store_true", help="Adicionar link de post")
    camp_parser.add_argument("--submit", action="store_true", help="Marcar como submetido")
    camp_parser.add_argument("--name", help="Nome da campanha")
    camp_parser.add_argument("--influencer", help="Nome do influenciador")
    camp_parser.add_argument("--platform-url", help="URL da plataforma")
    camp_parser.add_argument("--pay", type=float, help="Pagamento por 1k views")
    camp_parser.add_argument("--min-views", type=int, help="Views mínimas")
    camp_parser.add_argument("--id", type=int, help="ID da campanha para filtrar")
    camp_parser.add_argument("--campaign-id", type=int, help="ID da campanha")
    camp_parser.add_argument("--clip-id", type=int, help="ID do clipe")
    camp_parser.add_argument("--platform", help="Plataforma (instagram, tiktok)")
    camp_parser.add_argument("--link", help="Link do post")

    # Chat (modo conversacional)
    subparsers.add_parser("chat", help="Modo conversacional (prompt-driven)")

    # Twitch
    twitch_parser = subparsers.add_parser("twitch", help="Buscar clipes da Twitch")
    twitch_parser.add_argument("--username", required=True, help="Nome do canal na Twitch")
    twitch_parser.add_argument("--clips", type=int, default=10, help="Número de clipes")
    twitch_parser.add_argument("--min-views", type=int, default=1000, help="Views mínimas")
    twitch_parser.add_argument("--period-days", type=int, default=30, help="Período em dias")
    twitch_parser.add_argument("--edit", action="store_true", help="Editar clipes para mobile")
    twitch_parser.add_argument("--template", default="clean", help="Template de edição")
    twitch_parser.add_argument("--campaign-id", type=int, help="ID da campanha")

    # Research
    research_parser = subparsers.add_parser("research", help="Pesquisa competitiva")
    research_parser.add_argument("--influencer", required=True, help="Nome do influenciador")

    # Templates
    subparsers.add_parser("templates", help="Listar templates de edição")

    args = parser.parse_args()

    if args.command == "pipeline":
        run_pipeline(args)
    elif args.command == "campaign":
        run_campaign(args)
    elif args.command == "chat":
        from src.chat import start_chat
        start_chat()
    elif args.command == "twitch":
        run_twitch(args)
    elif args.command == "research":
        run_research(args)
    elif args.command == "templates":
        run_templates()
    else:
        parser.print_help()


def run_twitch(args):
    """Busca e edita clipes da Twitch."""
    client_id = os.environ.get("TWITCH_CLIENT_ID")
    client_secret = os.environ.get("TWITCH_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Configure as variáveis de ambiente:")
        print("  export TWITCH_CLIENT_ID='seu_client_id'")
        print("  export TWITCH_CLIENT_SECRET='seu_client_secret'")
        print("\nObtenha em: https://dev.twitch.tv/console/apps (gratuito)")
        return

    from src.twitch import search_and_download_best_clips
    from src.editor import process_clip
    from src.templates import apply_template

    clips = search_and_download_best_clips(
        username=args.username,
        client_id=client_id,
        client_secret=client_secret,
        max_clips=args.clips,
        min_views=args.min_views,
        period_days=args.period_days,
    )

    if not clips:
        print("Nenhum clipe encontrado.")
        return

    if args.edit:
        print(f"\nEditando {len(clips)} clipes com template '{args.template}'...")
        output_dir = os.path.join(CLIPS_DIR, f"twitch_{args.username}")
        os.makedirs(output_dir, exist_ok=True)

        for i, clip in enumerate(clips):
            clip_name = f"twitch_clip_{i+1:02d}"
            try:
                # Converte para vertical
                output_path = os.path.join(output_dir, f"{clip_name}.mp4")
                process_clip(
                    video_path=clip["path"],
                    start=0,
                    end=clip["duration"],
                    output_dir=output_dir,
                    clip_name=clip_name,
                    headline_text=clip["title"].upper()[:60],
                    add_subs=False,  # Twitch clips geralmente são curtos
                )

                # Aplica template se não for o padrão
                if args.template != "clean":
                    template_path = os.path.join(output_dir, f"{clip_name}_styled.mp4")
                    apply_template(output_path, template_path, args.template)
                    os.rename(template_path, output_path)

                print(f"  Editado: {output_path}")

                if args.campaign_id:
                    from src.tracker import add_clip_to_campaign
                    add_clip_to_campaign(
                        campaign_id=args.campaign_id,
                        clip_path=output_path,
                        source_video_url=clip["url"],
                        clip_start=0,
                        clip_end=clip["duration"],
                    )
            except Exception as e:
                print(f"  Erro no clip {i+1}: {e}")

    print("\nPronto! Revise os clipes e poste nas redes sociais.")


def run_research(args):
    """Executa pesquisa competitiva."""
    from src.research import (
        research_clips_about,
        research_youtube_shorts,
        generate_research_report,
    )

    influencer = args.influencer
    print(f"Pesquisando '{influencer}'... isso pode levar alguns minutos.\n")

    youtube_data = research_youtube_shorts(influencer)
    competitor_data = research_clips_about(influencer)

    report = generate_research_report(
        influencer_name=influencer,
        youtube_data=youtube_data,
        competitor_data=competitor_data,
        output_path=f"output/research_{influencer.lower().replace(' ', '_')}.txt",
    )
    print(report)


def run_templates():
    """Lista templates de edição."""
    from src.templates import list_templates
    templates = list_templates()
    print("Templates de edição disponíveis:\n")
    for t in templates:
        print(f"  {t['name']:15s}  {t['description']}")
    print("\nUse --template NOME para aplicar no pipeline.")


if __name__ == "__main__":
    main()
