"""
Módulo de edição de clipes usando FFmpeg.

Funcionalidades:
- Corte de trechos do vídeo
- Redimensionamento para formato vertical (9:16)
- Adição de legendas (burn-in)
- Adição de headline/banner
"""

import json
import os
import subprocess

from config.settings import (
    FONT_COLOR,
    FONT_SIZE,
    HEADLINE_BG_COLOR,
    HEADLINE_FONT_SIZE,
    HEADLINE_TEXT_COLOR,
    OUTLINE_COLOR,
    OUTLINE_WIDTH,
    OUTPUT_FPS,
    OUTPUT_HEIGHT,
    OUTPUT_WIDTH,
    SUBTITLE_POSITION,
)


def cut_clip(
    video_path: str,
    start: float,
    end: float,
    output_path: str,
) -> str:
    """
    Corta um trecho do vídeo.

    Args:
        video_path: Caminho do vídeo original
        start: Tempo de início em segundos
        end: Tempo de fim em segundos
        output_path: Caminho de saída

    Returns:
        Caminho do clipe cortado
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    duration = end - start
    cmd = [
        "ffmpeg",
        "-ss", str(start),
        "-i", video_path,
        "-t", str(duration),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-preset", "fast",
        "-crf", "23",
        "-y",
        "-loglevel", "error",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Erro ao cortar clipe: {result.stderr}")

    return output_path


def make_vertical(input_path: str, output_path: str) -> str:
    """
    Converte vídeo horizontal para formato vertical (9:16) para Reels/TikTok.
    Centraliza o conteúdo e adiciona blur nas bordas.

    Args:
        input_path: Caminho do vídeo horizontal
        output_path: Caminho de saída

    Returns:
        Caminho do vídeo vertical
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Filtro complexo: fundo blurred + vídeo centralizado em cima
    filter_complex = (
        # Cria fundo blurred (escala o vídeo para preencher o frame vertical e aplica blur)
        f"[0:v]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},boxblur=20:20[bg];"
        # Escala o vídeo original para caber na largura mantendo aspect ratio
        f"[0:v]scale={OUTPUT_WIDTH}:-2:force_original_aspect_ratio=decrease[fg];"
        # Sobrepõe o vídeo centralizado sobre o fundo
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[out]"
    )

    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-r", str(OUTPUT_FPS),
        "-preset", "fast",
        "-crf", "23",
        "-y",
        "-loglevel", "error",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Erro ao converter para vertical: {result.stderr}")

    return output_path


def generate_subtitle_file(
    transcript_segments: list[dict],
    clip_start: float,
    clip_end: float,
    output_path: str,
) -> str:
    """
    Gera arquivo SRT de legendas a partir da transcrição.

    Args:
        transcript_segments: Segmentos da transcrição Whisper
        clip_start: Início do clipe (para ajustar timestamps)
        clip_end: Fim do clipe
        output_path: Caminho do arquivo SRT

    Returns:
        Caminho do arquivo SRT
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    srt_entries = []
    index = 1

    for seg in transcript_segments:
        seg_start = seg.get("start", 0)
        seg_end = seg.get("end", 0)
        text = seg.get("text", "").strip()

        if not text:
            continue

        # Só inclui segmentos dentro do intervalo do clipe
        if seg_end < clip_start or seg_start > clip_end:
            continue

        # Ajusta timestamps relativos ao início do clipe
        adjusted_start = max(0, seg_start - clip_start)
        adjusted_end = max(0, seg_end - clip_start)

        # Divide texto longo em linhas menores (max ~40 chars por linha)
        lines = _wrap_text(text, max_chars=40)
        formatted_text = "\n".join(lines)

        srt_entries.append(
            f"{index}\n"
            f"{_format_srt_time(adjusted_start)} --> {_format_srt_time(adjusted_end)}\n"
            f"{formatted_text}\n"
        )
        index += 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_entries))

    return output_path


def add_subtitles(
    video_path: str,
    srt_path: str,
    output_path: str,
) -> str:
    """
    Adiciona legendas ao vídeo (burn-in / hardcoded).

    Args:
        video_path: Caminho do vídeo
        srt_path: Caminho do arquivo SRT
        output_path: Caminho de saída

    Returns:
        Caminho do vídeo com legendas
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Posição da legenda
    if SUBTITLE_POSITION == "center":
        y_pos = "(h-text_h)/2+h/4"
    elif SUBTITLE_POSITION == "top":
        y_pos = "h/6"
    else:  # bottom
        y_pos = "h-text_h-60"

    # Escapa o caminho do SRT para FFmpeg (: e \ precisam ser escapados)
    escaped_srt = srt_path.replace("\\", "\\\\").replace(":", "\\:")

    subtitle_filter = (
        f"subtitles='{escaped_srt}'"
        f":force_style='FontSize={FONT_SIZE},"
        f"PrimaryColour=&H00FFFFFF,"  # white
        f"OutlineColour=&H00000000,"  # black outline
        f"Outline={OUTLINE_WIDTH},"
        f"Alignment=10,"
        f"MarginV=200'"
    )

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", subtitle_filter,
        "-c:v", "libx264",
        "-c:a", "copy",
        "-preset", "fast",
        "-crf", "23",
        "-y",
        "-loglevel", "error",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Erro ao adicionar legendas: {result.stderr}")

    return output_path


def add_headline(
    video_path: str,
    headline_text: str,
    output_path: str,
    category: str = "FAMOSOS",
) -> str:
    """
    Adiciona headline/banner no topo do vídeo (como no screenshot do Instagram).

    Args:
        video_path: Caminho do vídeo
        headline_text: Texto da headline
        output_path: Caminho de saída
        category: Tag de categoria (ex: "FAMOSOS")

    Returns:
        Caminho do vídeo com headline
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Escapa aspas simples no texto
    headline_text = headline_text.replace("'", "'\\''")
    category = category.replace("'", "'\\''")

    # Filtro complexo: banner preto semi-transparente + texto
    filter_complex = (
        # Banner de fundo
        f"drawbox=x=0:y=ih*0.65:w=iw:h=ih*0.25:color=black@0.7:t=fill,"
        # Tag de categoria (canto superior esquerdo do banner)
        f"drawtext=text='{category}'"
        f":fontsize={int(HEADLINE_FONT_SIZE * 0.6)}"
        f":fontcolor=white:bordercolor=black:borderw=2"
        f":x=30:y=ih*0.65+10"
        f":box=1:boxcolor=black@0.8:boxborderw=8,"
        # Texto principal da headline
        f"drawtext=text='{headline_text}'"
        f":fontsize={HEADLINE_FONT_SIZE}"
        f":fontcolor=white:bordercolor=black:borderw=2"
        f":x=(w-text_w)/2:y=ih*0.70"
        f":line_spacing=10"
    )

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", filter_complex,
        "-c:v", "libx264",
        "-c:a", "copy",
        "-preset", "fast",
        "-crf", "23",
        "-y",
        "-loglevel", "error",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Erro ao adicionar headline: {result.stderr}")

    return output_path


def process_clip(
    video_path: str,
    start: float,
    end: float,
    output_dir: str,
    clip_name: str,
    transcript_segments: list[dict] | None = None,
    headline_text: str | None = None,
    category: str = "FAMOSOS",
    make_vertical_format: bool = True,
    add_subs: bool = True,
    add_head: bool = True,
) -> str:
    """
    Pipeline completo de processamento de um clipe.

    1. Corta o trecho
    2. Converte para vertical (9:16)
    3. Adiciona legendas
    4. Adiciona headline

    Args:
        video_path: Vídeo original
        start: Início em segundos
        end: Fim em segundos
        output_dir: Diretório de saída
        clip_name: Nome base do clipe
        transcript_segments: Segmentos de transcrição (para legendas)
        headline_text: Texto da headline (se None, não adiciona)
        category: Categoria para o banner
        make_vertical_format: Se deve converter para 9:16
        add_subs: Se deve adicionar legendas
        add_head: Se deve adicionar headline

    Returns:
        Caminho do clipe final
    """
    os.makedirs(output_dir, exist_ok=True)

    # Etapa 1: Corta
    cut_path = os.path.join(output_dir, f"{clip_name}_raw.mp4")
    print(f"  Cortando {start:.1f}s - {end:.1f}s...")
    cut_clip(video_path, start, end, cut_path)

    current_path = cut_path

    # Etapa 2: Vertical
    if make_vertical_format:
        vert_path = os.path.join(output_dir, f"{clip_name}_vertical.mp4")
        print(f"  Convertendo para formato vertical...")
        make_vertical(current_path, vert_path)
        current_path = vert_path

    # Etapa 3: Legendas
    if add_subs and transcript_segments:
        srt_path = os.path.join(output_dir, f"{clip_name}.srt")
        generate_subtitle_file(transcript_segments, start, end, srt_path)

        sub_path = os.path.join(output_dir, f"{clip_name}_sub.mp4")
        print(f"  Adicionando legendas...")
        try:
            add_subtitles(current_path, srt_path, sub_path)
            current_path = sub_path
        except RuntimeError as e:
            print(f"  AVISO: Não foi possível adicionar legendas: {e}")

    # Etapa 4: Headline
    if add_head and headline_text:
        head_path = os.path.join(output_dir, f"{clip_name}_final.mp4")
        print(f"  Adicionando headline...")
        try:
            add_headline(current_path, headline_text, head_path, category)
            current_path = head_path
        except RuntimeError as e:
            print(f"  AVISO: Não foi possível adicionar headline: {e}")

    # Renomeia para o nome final se não for o último passo
    final_path = os.path.join(output_dir, f"{clip_name}.mp4")
    if current_path != final_path:
        os.rename(current_path, final_path)

    # Limpa arquivos intermediários
    for suffix in ["_raw.mp4", "_vertical.mp4", "_sub.mp4", "_final.mp4"]:
        intermediate = os.path.join(output_dir, f"{clip_name}{suffix}")
        if os.path.exists(intermediate) and intermediate != final_path:
            os.remove(intermediate)

    print(f"  Clipe pronto: {final_path}")
    return final_path


def _wrap_text(text: str, max_chars: int = 40) -> list[str]:
    """Quebra texto em linhas de no máximo max_chars caracteres."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        if current_line and len(current_line) + len(word) + 1 > max_chars:
            lines.append(current_line)
            current_line = word
        else:
            current_line = f"{current_line} {word}".strip()

    if current_line:
        lines.append(current_line)

    return lines if lines else [""]


def _format_srt_time(seconds: float) -> str:
    """Converte segundos para formato SRT (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
