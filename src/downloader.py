"""
Módulo de download de vídeos do YouTube usando yt-dlp.
"""

import os
import json
import subprocess
import sys


def download_video(url: str, output_dir: str = "output/downloads") -> dict:
    """
    Baixa um vídeo do YouTube e retorna informações sobre ele.

    Args:
        url: URL do vídeo do YouTube
        output_dir: Diretório de saída

    Returns:
        Dict com path do arquivo, título, duração, etc.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Primeiro, pega as informações do vídeo sem baixar
    info = get_video_info(url)
    if not info:
        raise RuntimeError(f"Não foi possível obter informações do vídeo: {url}")

    video_id = info["id"]
    output_template = os.path.join(output_dir, f"{video_id}.%(ext)s")

    cmd = [
        sys.executable, "-m", "yt_dlp",
        url,
        "-o", output_template,
        "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--quiet",
        "--progress",
    ]

    print(f"Baixando: {info.get('title', url)}...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Erro no download: {result.stderr}")

    # Encontra o arquivo baixado
    video_path = os.path.join(output_dir, f"{video_id}.mp4")
    if not os.path.exists(video_path):
        # Tenta encontrar qualquer arquivo com o ID
        for f in os.listdir(output_dir):
            if f.startswith(video_id):
                video_path = os.path.join(output_dir, f)
                break

    if not os.path.exists(video_path):
        raise RuntimeError(f"Arquivo não encontrado após download: {video_path}")

    print(f"Download concluído: {video_path}")

    return {
        "path": video_path,
        "id": video_id,
        "title": info.get("title", ""),
        "duration": info.get("duration", 0),
        "channel": info.get("channel", ""),
        "description": info.get("description", ""),
        "chapters": info.get("chapters", []),
    }


def get_video_info(url: str) -> dict | None:
    """
    Obtém metadados do vídeo sem baixar.
    """
    cmd = [
        sys.executable, "-m", "yt_dlp",
        url,
        "--dump-json",
        "--no-download",
        "--no-playlist",
        "--quiet",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Erro ao obter info: {result.stderr}")
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def extract_audio(video_path: str, output_path: str = None) -> str:
    """
    Extrai o áudio de um vídeo para análise.

    Args:
        video_path: Caminho do vídeo
        output_path: Caminho de saída (opcional)

    Returns:
        Caminho do arquivo de áudio
    """
    if output_path is None:
        base = os.path.splitext(video_path)[0]
        output_path = f"{base}_audio.wav"

    if os.path.exists(output_path):
        return output_path

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vn",  # sem vídeo
        "-acodec", "pcm_s16le",
        "-ar", "16000",  # 16kHz para Whisper
        "-ac", "1",  # mono
        "-y",  # sobrescrever
        "-loglevel", "error",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Erro ao extrair áudio: {result.stderr}")

    return output_path
