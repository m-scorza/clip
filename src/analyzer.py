"""
Módulo de análise de vídeo para encontrar os melhores momentos.

Usa combinação de:
- Análise de energia do áudio (momentos de maior volume/emoção)
- Transcrição + heurísticas (risadas, reações, frases de impacto)
- Capítulos do YouTube (se disponíveis)
"""

import json
import os
import struct
import subprocess
import wave
from dataclasses import dataclass


@dataclass
class Moment:
    """Representa um momento interessante no vídeo."""
    start: float  # segundos
    end: float    # segundos
    score: float  # 0-1, quanto maior melhor
    reason: str   # por que esse momento foi selecionado
    text: str     # transcrição do trecho (se disponível)


def transcribe_video(audio_path: str, model: str = "base", language: str = "pt") -> dict:
    """
    Transcreve o áudio usando Whisper.

    Args:
        audio_path: Caminho do arquivo de áudio WAV
        model: Modelo do Whisper (tiny, base, small, medium, large)
        language: Idioma

    Returns:
        Dict com segments (lista de segmentos com timestamps e texto)
    """
    try:
        import whisper_timestamped as whisper
    except ImportError:
        try:
            import whisper
        except ImportError:
            print("AVISO: Whisper não instalado. Instalando...")
            subprocess.run(
                ["pip", "install", "openai-whisper"],
                capture_output=True,
            )
            import whisper

    print(f"Transcrevendo áudio com modelo '{model}'...")
    model_obj = whisper.load_model(model)

    # whisper_timestamped dá timestamps por palavra
    try:
        result = whisper.transcribe(model_obj, audio_path, language=language)
    except TypeError:
        # fallback para whisper normal (sem timestamps por palavra)
        result = model_obj.transcribe(audio_path, language=language)

    print(f"Transcrição concluída: {len(result.get('segments', []))} segmentos")
    return result


def analyze_audio_energy(audio_path: str, window_seconds: float = 2.0) -> list[dict]:
    """
    Analisa a energia do áudio para encontrar picos de volume.

    Args:
        audio_path: Caminho do arquivo WAV
        window_seconds: Tamanho da janela de análise em segundos

    Returns:
        Lista de dicts com {time, energy} normalizados
    """
    with wave.open(audio_path, "r") as wf:
        sample_rate = wf.getframerate()
        n_channels = wf.getnchannels()
        n_frames = wf.getnframes()
        sample_width = wf.getsampwidth()
        raw_data = wf.readframes(n_frames)

    # Converte para valores numéricos
    if sample_width == 2:
        fmt = f"<{n_frames * n_channels}h"
        samples = list(struct.unpack(fmt, raw_data))
    else:
        raise ValueError(f"Sample width {sample_width} não suportado")

    # Se estéreo, pega média dos canais
    if n_channels == 2:
        samples = [(samples[i] + samples[i + 1]) / 2 for i in range(0, len(samples), 2)]

    window_size = int(sample_rate * window_seconds)
    energy_data = []

    for i in range(0, len(samples) - window_size, window_size // 2):
        window = samples[i : i + window_size]
        # RMS energy
        energy = (sum(s * s for s in window) / len(window)) ** 0.5
        time = i / sample_rate
        energy_data.append({"time": time, "energy": energy})

    # Normaliza
    if energy_data:
        max_energy = max(d["energy"] for d in energy_data)
        if max_energy > 0:
            for d in energy_data:
                d["energy"] = d["energy"] / max_energy

    return energy_data


def find_best_moments(
    video_info: dict,
    transcript: dict | None = None,
    audio_energy: list[dict] | None = None,
    num_clips: int = 5,
    min_duration: float = 30.0,
    max_duration: float = 90.0,
    target_duration: float = 60.0,
) -> list[Moment]:
    """
    Encontra os melhores momentos para clipes.

    Combina várias sinais:
    1. Picos de energia no áudio
    2. Palavras-chave na transcrição (reações, risadas, frases impactantes)
    3. Capítulos do YouTube (tendem a ser inícios de tópicos)

    Args:
        video_info: Metadados do vídeo (do downloader)
        transcript: Resultado da transcrição Whisper
        audio_energy: Dados de energia do áudio
        num_clips: Número de clipes para gerar
        min_duration: Duração mínima do clipe em segundos
        max_duration: Duração máxima do clipe em segundos
        target_duration: Duração alvo do clipe

    Returns:
        Lista de Moments ordenados por score
    """
    video_duration = video_info.get("duration", 0)
    candidates = []

    # --- Sinal 1: Picos de energia no áudio ---
    if audio_energy:
        high_energy_regions = _find_high_energy_regions(
            audio_energy, threshold=0.6, min_gap=10.0
        )
        for region in high_energy_regions:
            start = max(0, region["start"] - 5)  # 5s antes do pico
            end = min(video_duration, start + target_duration)
            candidates.append(Moment(
                start=start,
                end=end,
                score=region["peak_energy"] * 0.4,
                reason="audio_peak",
                text="",
            ))

    # --- Sinal 2: Análise da transcrição ---
    if transcript and "segments" in transcript:
        segments = transcript["segments"]
        text_moments = _analyze_transcript_for_moments(
            segments, target_duration, video_duration
        )
        candidates.extend(text_moments)

    # --- Sinal 3: Capítulos do YouTube ---
    chapters = video_info.get("chapters", [])
    if chapters:
        for chapter in chapters:
            start = chapter.get("start_time", 0)
            end = min(
                chapter.get("end_time", start + target_duration),
                start + max_duration,
            )
            if end - start < min_duration:
                end = min(video_duration, start + target_duration)
            candidates.append(Moment(
                start=start,
                end=end,
                score=0.3,
                reason="chapter",
                text=chapter.get("title", ""),
            ))

    # --- Combina e deduplica ---
    if not candidates:
        # Fallback: divide o vídeo em segmentos iguais
        segment_length = video_duration / max(num_clips, 1)
        for i in range(num_clips):
            start = i * segment_length
            end = min(start + target_duration, video_duration)
            candidates.append(Moment(
                start=start,
                end=end,
                score=0.1,
                reason="fallback_uniform",
                text="",
            ))

    # Remove sobreposições e seleciona os melhores
    candidates.sort(key=lambda m: m.score, reverse=True)
    selected = _remove_overlapping(candidates, min_gap=15.0)

    # Ajusta durações
    for moment in selected:
        duration = moment.end - moment.start
        if duration < min_duration:
            moment.end = min(video_duration, moment.start + min_duration)
        elif duration > max_duration:
            moment.end = moment.start + max_duration

    # Enriquece com texto da transcrição
    if transcript and "segments" in transcript:
        for moment in selected:
            moment.text = _get_text_for_timerange(
                transcript["segments"], moment.start, moment.end
            )

    return selected[:num_clips]


def _find_high_energy_regions(
    energy_data: list[dict], threshold: float = 0.6, min_gap: float = 10.0
) -> list[dict]:
    """Encontra regiões de alta energia no áudio."""
    regions = []
    current_region = None

    for point in energy_data:
        if point["energy"] >= threshold:
            if current_region is None:
                current_region = {
                    "start": point["time"],
                    "end": point["time"],
                    "peak_energy": point["energy"],
                }
            else:
                current_region["end"] = point["time"]
                current_region["peak_energy"] = max(
                    current_region["peak_energy"], point["energy"]
                )
        else:
            if current_region is not None:
                regions.append(current_region)
                current_region = None

    if current_region:
        regions.append(current_region)

    # Merge regiões próximas
    merged = []
    for region in regions:
        if merged and region["start"] - merged[-1]["end"] < min_gap:
            merged[-1]["end"] = region["end"]
            merged[-1]["peak_energy"] = max(
                merged[-1]["peak_energy"], region["peak_energy"]
            )
        else:
            merged.append(region)

    return merged


# Palavras que indicam momentos interessantes em português
REACTION_KEYWORDS = [
    "nossa", "caramba", "meu deus", "sério", "não acredito",
    "inacreditável", "absurdo", "impressionante", "incrível",
    "que loucura", "mentira", "jura", "gente", "socorro",
    "polêmica", "bomba", "exclusivo", "revelação", "verdade",
    "nunca contei", "segredo", "primeira vez", "ninguém sabe",
]


def _analyze_transcript_for_moments(
    segments: list[dict],
    target_duration: float,
    video_duration: float,
) -> list[Moment]:
    """Analisa transcrição para encontrar momentos com conteúdo interessante."""
    moments = []

    for i, seg in enumerate(segments):
        text = seg.get("text", "").lower().strip()
        start = seg.get("start", 0)

        # Pontua baseado em palavras-chave
        score = 0.0
        matched_keywords = []
        for keyword in REACTION_KEYWORDS:
            if keyword in text:
                score += 0.15
                matched_keywords.append(keyword)

        # Perguntas tendem a ser bons inícios de trechos
        if "?" in text:
            score += 0.1

        # Frases curtas e enfáticas (exclamações)
        if "!" in text and len(text) < 100:
            score += 0.1

        if score > 0.1:
            clip_start = max(0, start - 3)
            clip_end = min(video_duration, clip_start + target_duration)
            reason = f"keywords: {', '.join(matched_keywords)}" if matched_keywords else "emphasis"
            moments.append(Moment(
                start=clip_start,
                end=clip_end,
                score=min(score, 1.0),
                reason=reason,
                text=text,
            ))

    return moments


def _remove_overlapping(moments: list[Moment], min_gap: float = 15.0) -> list[Moment]:
    """Remove momentos que se sobrepõem, mantendo os de maior score."""
    selected = []
    for moment in moments:
        overlaps = False
        for existing in selected:
            if (moment.start < existing.end + min_gap and
                    moment.end > existing.start - min_gap):
                overlaps = True
                break
        if not overlaps:
            selected.append(moment)
    return selected


def _get_text_for_timerange(
    segments: list[dict], start: float, end: float
) -> str:
    """Extrai texto da transcrição para um intervalo de tempo."""
    texts = []
    for seg in segments:
        seg_start = seg.get("start", 0)
        seg_end = seg.get("end", 0)
        if seg_start >= start and seg_end <= end:
            texts.append(seg.get("text", "").strip())
    return " ".join(texts)
