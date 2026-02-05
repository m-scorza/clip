#!/usr/bin/env python3
"""
Clip Automator - Pipeline de automação de clipes para campanhas de influenciadores.

Uso:
    python main.py pipeline --url URL [--clips N] [--headline TEXTO] [--category CAT]
    python main.py campaign --create --name NOME --influencer NOME [--pay VALOR] [--min-views N]
    python main.py campaign --list [--id N]
    python main.py campaign --add-link --campaign-id N --clip-id N --platform PLAT --link URL
    python main.py campaign --submit --campaign-id N --clip-id N

Exemplos:
    # Gerar 5 clipes de um vídeo do YouTube
    python main.py pipeline --url "https://youtube.com/watch?v=XXXXX" --clips 5

    # Criar uma campanha
    python main.py campaign --create --name "Campanha Verão" --influencer "FulanoTV" --pay 5.0

    # Registrar link de postagem
    python main.py campaign --add-link --campaign-id 1 --clip-id 1 --platform instagram --link "https://instagram.com/reel/xxx"
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
    print("\n[3/4] Encontrando melhores momentos...")
    moments = find_best_moments(
        video_info=video_info,
        transcript=transcript,
        audio_energy=energy,
        num_clips=num_clips,
        min_duration=MIN_CLIP_DURATION_SECONDS,
        max_duration=MAX_CLIP_DURATION_SECONDS,
        target_duration=TARGET_CLIP_DURATION_SECONDS,
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
        if not clip_headline and moment.text:
            # Gera headline automática a partir do texto
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
                category=category,
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

    args = parser.parse_args()

    if args.command == "pipeline":
        run_pipeline(args)
    elif args.command == "campaign":
        run_campaign(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
