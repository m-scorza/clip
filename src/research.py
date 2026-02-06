"""
Módulo de pesquisa e análise competitiva.

Analisa o ecossistema de clipes de um influenciador:
- Busca clipes existentes no TikTok/Instagram (via hashtags e keywords)
- Analisa quais tipos de clipe performam melhor
- Identifica padrões de sucesso (duração, estilo, horário)
- Gera relatório de insights para guiar a criação

Usa yt-dlp para buscar no YouTube e Twitch API para clipes.
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ContentInsight:
    """Insight sobre o que funciona para um influenciador."""
    metric: str         # ex: "duração média dos virais"
    value: str          # ex: "45 segundos"
    confidence: float   # 0-1
    source: str         # de onde veio o dado
    recommendation: str # o que fazer com isso


def research_youtube_shorts(
    channel_name: str,
    max_results: int = 20,
) -> list[dict]:
    """
    Busca Shorts/vídeos curtos de um canal no YouTube.
    Analisa quais performaram melhor para entender o que funciona.

    Args:
        channel_name: Nome do canal
        max_results: Máximo de resultados

    Returns:
        Lista de vídeos com métricas
    """
    # Busca vídeos curtos do canal
    search_query = f"{channel_name} shorts"
    cmd = [
        sys.executable, "-m", "yt_dlp",
        f"ytsearch{max_results}:{search_query}",
        "--dump-json",
        "--no-download",
        "--flat-playlist",
        "--quiet",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Erro na busca: {result.stderr}")
        return []

    videos = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            info = json.loads(line)
            videos.append({
                "id": info.get("id", ""),
                "title": info.get("title", ""),
                "view_count": info.get("view_count", 0),
                "duration": info.get("duration", 0),
                "url": info.get("url", info.get("webpage_url", "")),
            })
        except json.JSONDecodeError:
            continue

    # Ordena por views
    videos.sort(key=lambda v: v.get("view_count", 0) or 0, reverse=True)
    return videos


def research_clips_about(
    influencer_name: str,
    max_results: int = 30,
) -> list[dict]:
    """
    Busca clipes/cortes já existentes sobre um influenciador.
    Isso mostra o que outros clippers já fizeram e o que deu certo.

    Args:
        influencer_name: Nome do influenciador
        max_results: Máximo de resultados

    Returns:
        Lista de vídeos encontrados com métricas
    """
    search_queries = [
        f"{influencer_name} cortes",
        f"{influencer_name} melhores momentos",
        f"{influencer_name} clips",
    ]

    all_videos = []
    seen_ids = set()

    for query in search_queries:
        cmd = [
            sys.executable, "-m", "yt_dlp",
            f"ytsearch{max_results}:{query}",
            "--dump-json",
            "--no-download",
            "--flat-playlist",
            "--quiet",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            continue

        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                info = json.loads(line)
                vid_id = info.get("id", "")
                if vid_id in seen_ids:
                    continue
                seen_ids.add(vid_id)

                all_videos.append({
                    "id": vid_id,
                    "title": info.get("title", ""),
                    "channel": info.get("channel", info.get("uploader", "")),
                    "view_count": info.get("view_count", 0),
                    "duration": info.get("duration", 0),
                    "url": info.get("url", info.get("webpage_url", "")),
                    "upload_date": info.get("upload_date", ""),
                })
            except json.JSONDecodeError:
                continue

    all_videos.sort(key=lambda v: v.get("view_count", 0) or 0, reverse=True)
    return all_videos


def analyze_patterns(videos: list[dict]) -> list[ContentInsight]:
    """
    Analisa padrões nos vídeos que funcionam.

    Identifica:
    - Duração ideal
    - Palavras-chave nos títulos dos virais
    - Padrões de engajamento

    Args:
        videos: Lista de vídeos com métricas

    Returns:
        Lista de insights
    """
    if not videos:
        return [ContentInsight(
            metric="dados",
            value="insuficientes",
            confidence=0,
            source="research",
            recommendation="Tente com outro nome ou aguarde mais dados",
        )]

    insights = []

    # Filtra vídeos com dados de views
    with_views = [v for v in videos if v.get("view_count")]

    if with_views:
        # --- Duração ideal ---
        # Pega top 25% por views e analisa duração
        top_count = max(1, len(with_views) // 4)
        top_videos = sorted(with_views, key=lambda v: v["view_count"], reverse=True)[:top_count]
        avg_duration = sum(v.get("duration", 0) or 0 for v in top_videos) / len(top_videos)

        insights.append(ContentInsight(
            metric="Duração ideal dos clipes",
            value=f"{avg_duration:.0f} segundos",
            confidence=min(0.9, len(top_videos) / 10),
            source=f"Top {top_count} vídeos por views",
            recommendation=f"Faça clipes entre {max(15, avg_duration-15):.0f}s e {avg_duration+15:.0f}s",
        ))

        # --- Views médias ---
        avg_views = sum(v["view_count"] for v in with_views) / len(with_views)
        max_views = max(v["view_count"] for v in with_views)

        insights.append(ContentInsight(
            metric="Views médias dos clipes",
            value=f"{avg_views:,.0f}",
            confidence=0.8,
            source=f"{len(with_views)} vídeos analisados",
            recommendation=f"Potencial de até {max_views:,} views no melhor caso",
        ))

    # --- Palavras-chave populares ---
    title_words = {}
    for v in videos:
        title = v.get("title", "").lower()
        for word in title.split():
            if len(word) > 3:  # ignora palavras curtas
                title_words[word] = title_words.get(word, 0) + 1

    # Top palavras (excluindo comuns)
    common_words = {"para", "como", "mais", "muito", "sobre", "essa", "esse", "isso",
                    "aqui", "está", "estão", "será", "pode", "quando", "onde", "qual",
                    "with", "this", "that", "from", "have", "been", "were", "what"}
    top_words = sorted(
        [(w, c) for w, c in title_words.items() if w not in common_words and c > 1],
        key=lambda x: x[1],
        reverse=True,
    )[:10]

    if top_words:
        words_str = ", ".join(f'"{w}" ({c}x)' for w, c in top_words[:5])
        insights.append(ContentInsight(
            metric="Palavras-chave mais usadas em títulos",
            value=words_str,
            confidence=0.6,
            source="Análise de títulos",
            recommendation="Use essas palavras nas headlines dos clipes",
        ))

    return insights


def generate_research_report(
    influencer_name: str,
    youtube_data: list[dict] = None,
    twitch_data: list[dict] = None,
    competitor_data: list[dict] = None,
    output_path: str = None,
) -> str:
    """
    Gera relatório completo de pesquisa sobre um influenciador.

    Args:
        influencer_name: Nome do influenciador
        youtube_data: Dados do YouTube
        twitch_data: Dados da Twitch
        competitor_data: Dados de clipes de concorrentes
        output_path: Caminho para salvar o relatório

    Returns:
        Relatório em texto
    """
    lines = [
        f"{'='*70}",
        f"RELATÓRIO DE PESQUISA - {influencer_name.upper()}",
        f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        f"{'='*70}",
    ]

    # YouTube
    if youtube_data:
        lines.append(f"\n--- YOUTUBE ({len(youtube_data)} vídeos) ---")
        insights = analyze_patterns(youtube_data)
        for insight in insights:
            lines.append(f"\n  {insight.metric}: {insight.value}")
            lines.append(f"  Fonte: {insight.source}")
            lines.append(f"  Recomendação: {insight.recommendation}")

        lines.append(f"\n  Top 5 vídeos:")
        for v in youtube_data[:5]:
            views = v.get('view_count', 0)
            views_str = f"{views:,}" if views else "N/A"
            dur = v.get('duration', 0) or 0
            lines.append(f"    - {v.get('title', 'N/A')} ({views_str} views, {dur}s)")

    # Twitch
    if twitch_data:
        lines.append(f"\n--- TWITCH ({len(twitch_data)} clipes) ---")
        insights = analyze_patterns(twitch_data)
        for insight in insights:
            lines.append(f"\n  {insight.metric}: {insight.value}")
            lines.append(f"  Recomendação: {insight.recommendation}")

        lines.append(f"\n  Top 5 clipes:")
        for v in twitch_data[:5]:
            views = v.get('view_count', 0)
            lines.append(f"    - {v.get('title', 'N/A')} ({views:,} views)")

    # Concorrentes
    if competitor_data:
        lines.append(f"\n--- CLIPES DE OUTROS CANAIS ({len(competitor_data)} encontrados) ---")
        insights = analyze_patterns(competitor_data)
        for insight in insights:
            lines.append(f"\n  {insight.metric}: {insight.value}")
            lines.append(f"  Recomendação: {insight.recommendation}")

        lines.append(f"\n  Top 5 clipes de concorrentes:")
        for v in competitor_data[:5]:
            views = v.get('view_count', 0)
            views_str = f"{views:,}" if views else "N/A"
            lines.append(f"    - [{v.get('channel', 'N/A')}] {v.get('title', 'N/A')} ({views_str} views)")

    # Recomendações finais
    lines.append(f"\n{'='*70}")
    lines.append("RECOMENDAÇÕES FINAIS")
    lines.append(f"{'='*70}")

    all_data = (youtube_data or []) + (twitch_data or []) + (competitor_data or [])
    if all_data:
        all_insights = analyze_patterns(all_data)
        for insight in all_insights:
            lines.append(f"  → {insight.recommendation}")

    report = "\n".join(lines)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Relatório salvo em: {output_path}")

    return report
