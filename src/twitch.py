"""
Módulo de integração com Twitch.

Vantagem da Twitch: clipes já existem com contagem de views,
então podemos buscar os clipes mais populares diretamente.

Usa a API da Twitch (Helix) para:
- Buscar clipes populares de um canal
- Baixar clipes para edição
- Ordenar por views (já temos o sinal de "o que funciona")
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class TwitchClip:
    """Representa um clipe da Twitch."""
    id: str
    url: str
    title: str
    view_count: int
    duration: float
    created_at: str
    creator_name: str
    thumbnail_url: str
    video_url: str  # URL direta para download


# --- Autenticação ---

def get_twitch_token(client_id: str, client_secret: str) -> str:
    """
    Obtém token de acesso da API Twitch (Client Credentials).

    Para obter client_id e client_secret:
    1. Vá em https://dev.twitch.tv/console/apps
    2. Registre uma aplicação
    3. Copie Client ID e gere um Client Secret
    É gratuito.
    """
    url = "https://id.twitch.tv/oauth2/token"
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }).encode()

    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        return result["access_token"]


def _twitch_api_get(endpoint: str, params: dict, client_id: str, token: str) -> dict:
    """Faz uma requisição GET para a API Helix da Twitch."""
    query = urllib.parse.urlencode(params)
    url = f"https://api.twitch.tv/helix/{endpoint}?{query}"

    req = urllib.request.Request(url, headers={
        "Client-ID": client_id,
        "Authorization": f"Bearer {token}",
    })

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


# --- Busca de Clipes ---

def get_broadcaster_id(username: str, client_id: str, token: str) -> str | None:
    """Obtém o ID do broadcaster pelo username."""
    result = _twitch_api_get("users", {"login": username}, client_id, token)
    data = result.get("data", [])
    if data:
        return data[0]["id"]
    return None


def get_top_clips(
    username: str,
    client_id: str,
    token: str,
    period_days: int = 30,
    max_clips: int = 20,
    min_views: int = 1000,
) -> list[TwitchClip]:
    """
    Busca os clipes mais populares de um canal na Twitch.

    Args:
        username: Nome de usuário do canal
        client_id: Client ID da Twitch
        token: Token de acesso
        period_days: Período em dias para buscar clipes
        max_clips: Máximo de clipes para retornar
        min_views: Mínimo de views para filtrar

    Returns:
        Lista de TwitchClip ordenados por views (desc)
    """
    broadcaster_id = get_broadcaster_id(username, client_id, token)
    if not broadcaster_id:
        raise ValueError(f"Canal '{username}' não encontrado na Twitch")

    started_at = (datetime.utcnow() - timedelta(days=period_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ended_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "broadcaster_id": broadcaster_id,
        "started_at": started_at,
        "ended_at": ended_at,
        "first": min(max_clips, 100),  # API max é 100
    }

    result = _twitch_api_get("clips", params, client_id, token)

    clips = []
    for item in result.get("data", []):
        view_count = item.get("view_count", 0)
        if view_count < min_views:
            continue

        # Monta a URL de download do clipe
        # O thumbnail_url contém o padrão para construir a URL do vídeo
        thumb = item.get("thumbnail_url", "")
        video_url = _clip_thumbnail_to_video_url(thumb)

        clips.append(TwitchClip(
            id=item["id"],
            url=item["url"],
            title=item.get("title", ""),
            view_count=view_count,
            duration=item.get("duration", 0),
            created_at=item.get("created_at", ""),
            creator_name=item.get("creator_name", ""),
            thumbnail_url=thumb,
            video_url=video_url,
        ))

    # Ordena por views (maior primeiro)
    clips.sort(key=lambda c: c.view_count, reverse=True)
    return clips[:max_clips]


def _clip_thumbnail_to_video_url(thumbnail_url: str) -> str:
    """
    Converte URL do thumbnail do clipe para URL do vídeo.
    Padrão: https://clips-media-assets2.twitch.tv/xxxxx-preview-480x272.jpg
    Vídeo:  https://clips-media-assets2.twitch.tv/xxxxx.mp4
    """
    if "-preview-" in thumbnail_url:
        base = thumbnail_url.split("-preview-")[0]
        return f"{base}.mp4"
    return thumbnail_url


def download_clip(clip: TwitchClip, output_dir: str = "output/downloads") -> str:
    """
    Baixa um clipe da Twitch.

    Args:
        clip: TwitchClip para baixar
        output_dir: Diretório de saída

    Returns:
        Caminho do arquivo baixado
    """
    os.makedirs(output_dir, exist_ok=True)

    # Limpa o título para usar como nome de arquivo
    safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in clip.title)
    safe_title = safe_title[:50].strip()
    output_path = os.path.join(output_dir, f"twitch_{clip.id}_{safe_title}.mp4")

    if os.path.exists(output_path):
        print(f"  Clipe já baixado: {output_path}")
        return output_path

    print(f"  Baixando clipe: {clip.title} ({clip.view_count} views)...")

    # Tenta com yt-dlp primeiro (mais confiável)
    cmd = [
        sys.executable, "-m", "yt_dlp",
        clip.url,
        "-o", output_path,
        "--quiet",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0 and os.path.exists(output_path):
        return output_path

    # Fallback: download direto da URL do vídeo
    try:
        urllib.request.urlretrieve(clip.video_url, output_path)
        return output_path
    except Exception as e:
        raise RuntimeError(f"Erro ao baixar clipe {clip.id}: {e}")


def search_and_download_best_clips(
    username: str,
    client_id: str,
    client_secret: str,
    output_dir: str = "output/downloads",
    max_clips: int = 10,
    min_views: int = 1000,
    period_days: int = 30,
) -> list[dict]:
    """
    Pipeline completo: busca e baixa os melhores clipes de um canal.

    Args:
        username: Nome do canal na Twitch
        client_id: Client ID
        client_secret: Client Secret
        output_dir: Diretório de saída
        max_clips: Máximo de clipes
        min_views: Mínimo de views
        period_days: Período de busca

    Returns:
        Lista de dicts com info do clipe e caminho do arquivo
    """
    print(f"Buscando clipes populares de '{username}' na Twitch...")

    token = get_twitch_token(client_id, client_secret)
    clips = get_top_clips(
        username=username,
        client_id=client_id,
        token=token,
        period_days=period_days,
        max_clips=max_clips,
        min_views=min_views,
    )

    if not clips:
        print("  Nenhum clipe encontrado com os critérios especificados.")
        return []

    print(f"  {len(clips)} clipes encontrados. Top 5:")
    for i, clip in enumerate(clips[:5]):
        print(f"    #{i+1}: {clip.title} ({clip.view_count} views, {clip.duration:.0f}s)")

    downloaded = []
    for clip in clips:
        try:
            path = download_clip(clip, output_dir)
            downloaded.append({
                "path": path,
                "id": clip.id,
                "title": clip.title,
                "url": clip.url,
                "view_count": clip.view_count,
                "duration": clip.duration,
                "source": "twitch",
            })
        except Exception as e:
            print(f"  Erro ao baixar {clip.id}: {e}")

    print(f"\n  {len(downloaded)} clipes baixados com sucesso.")
    return downloaded
