"""
Sistema de templates de edição (esqueletos de edits).

Templates definem "receitas" de edição reutilizáveis, como:
- Zoom dramático em momentos de reação
- Transição com flash branco
- Efeito de shake/tremor
- Câmera lenta em momentos de impacto
- Texto animado (pop-in)
- Barra de progresso
- Split screen

Cada template é um conjunto de filtros FFmpeg encadeados.
"""

import json
import os
import subprocess
from dataclasses import dataclass, field


@dataclass
class EditTemplate:
    """Define um template de edição reutilizável."""
    name: str
    description: str
    # Filtros de vídeo FFmpeg (vf ou filter_complex)
    video_filters: list[str] = field(default_factory=list)
    # Filtros de áudio
    audio_filters: list[str] = field(default_factory=list)
    # Overlay de imagem/texto
    overlays: list[dict] = field(default_factory=list)
    # Configurações específicas
    config: dict = field(default_factory=dict)


# --- Templates Pré-definidos ---

TEMPLATES = {
    "clean": EditTemplate(
        name="clean",
        description="Limpo: vertical 9:16, legendas centralizadas, headline no topo",
        video_filters=[],
        config={"subtitle_position": "center", "headline_position": "top"},
    ),

    "dramatic": EditTemplate(
        name="dramatic",
        description="Dramatico: zoom leve progressivo, vinheta escura nas bordas, legendas bold",
        video_filters=[
            # Zoom lento de 1.0x para 1.05x ao longo do clipe
            "zoompan=z='min(zoom+0.0002,1.05)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}",
            # Vinheta escura
            "vignette=PI/4",
        ],
        config={
            "subtitle_style": "FontSize=52,Bold=1,Outline=4",
            "color_grading": "eq=contrast=1.1:brightness=0.02:saturation=1.2",
        },
    ),

    "energy": EditTemplate(
        name="energy",
        description="Energia: cores vibrantes, cortes rapidos, flash nas transicoes",
        video_filters=[
            # Saturação alta + contraste
            "eq=contrast=1.15:saturation=1.4:brightness=0.03",
            # Sharpen para mais definição
            "unsharp=5:5:1.0:5:5:0.0",
        ],
        config={
            "subtitle_style": "FontSize=56,Bold=1,Outline=3,PrimaryColour=&H0000FFFF",
            "transition": "flash",
        },
    ),

    "podcast": EditTemplate(
        name="podcast",
        description="Podcast: foco no audio, legendas grandes estilo karaoke, fundo minimalista",
        video_filters=[
            # Leve blur no fundo para focar na conversa
            "gblur=sigma=0.5",
        ],
        config={
            "subtitle_position": "center",
            "subtitle_style": "FontSize=60,Bold=1,Outline=4,PrimaryColour=&H00FFFFFF",
            "headline_position": "bottom",
        },
    ),

    "meme": EditTemplate(
        name="meme",
        description="Meme: texto impacto (branco com borda preta), estilo zoeira",
        video_filters=[],
        config={
            "subtitle_style": "FontSize=64,Bold=1,Outline=5,FontName=Impact",
            "headline_style": "impact",
        },
    ),

    "cinema": EditTemplate(
        name="cinema",
        description="Cinema: barras pretas (letterbox), color grading quente, fonte elegante",
        video_filters=[
            # Color grading cinematográfico (tons quentes)
            "colorbalance=rs=0.05:gs=-0.02:bs=-0.05:rm=0.03:gm=0.0:bm=-0.03",
            # Leve grain para look de filme
            "noise=alls=3:allf=t",
        ],
        config={
            "letterbox": True,
            "letterbox_ratio": 0.1,  # 10% de barra em cima e embaixo
            "subtitle_style": "FontSize=44,Italic=1,Outline=2",
        },
    ),

    "tiktok_viral": EditTemplate(
        name="tiktok_viral",
        description="TikTok Viral: legendas palavra-por-palavra, cores neon, ritmo rapido",
        video_filters=[
            # Contraste alto
            "eq=contrast=1.2:saturation=1.3",
        ],
        config={
            "subtitle_mode": "word_by_word",  # Legenda aparece palavra por palavra
            "subtitle_style": "FontSize=58,Bold=1,Outline=3,PrimaryColour=&H0000FF00",
            "highlight_color": "&H000000FF",  # Vermelho para palavra atual
        },
    ),
}


def list_templates() -> list[dict]:
    """Lista todos os templates disponíveis."""
    return [
        {"name": t.name, "description": t.description}
        for t in TEMPLATES.values()
    ]


def get_template(name: str) -> EditTemplate:
    """Obtém um template pelo nome."""
    if name not in TEMPLATES:
        available = ", ".join(TEMPLATES.keys())
        raise ValueError(f"Template '{name}' não encontrado. Disponíveis: {available}")
    return TEMPLATES[name]


def apply_template(
    input_path: str,
    output_path: str,
    template_name: str,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> str:
    """
    Aplica um template de edição a um vídeo.

    Args:
        input_path: Vídeo de entrada
        output_path: Vídeo de saída
        template_name: Nome do template
        width: Largura de saída
        height: Altura de saída
        fps: FPS de saída

    Returns:
        Caminho do vídeo com template aplicado
    """
    template = get_template(template_name)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Monta os filtros de vídeo
    vf_parts = []

    # Filtros do template (com substituição de variáveis)
    for vf in template.video_filters:
        vf = vf.format(width=width, height=height, fps=fps)
        vf_parts.append(vf)

    # Color grading se configurado
    color_grading = template.config.get("color_grading")
    if color_grading:
        vf_parts.append(color_grading)

    # Letterbox se configurado
    if template.config.get("letterbox"):
        ratio = template.config.get("letterbox_ratio", 0.1)
        bar_h = int(height * ratio)
        vf_parts.append(
            f"drawbox=x=0:y=0:w={width}:h={bar_h}:color=black:t=fill,"
            f"drawbox=x=0:y={height - bar_h}:w={width}:h={bar_h}:color=black:t=fill"
        )

    # Monta comando FFmpeg
    cmd = ["ffmpeg", "-i", input_path]

    if vf_parts:
        cmd.extend(["-vf", ",".join(vf_parts)])

    # Filtros de áudio
    if template.audio_filters:
        cmd.extend(["-af", ",".join(template.audio_filters)])

    cmd.extend([
        "-c:v", "libx264",
        "-c:a", "aac",
        "-preset", "fast",
        "-crf", "23",
        "-y",
        "-loglevel", "error",
        output_path,
    ])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Erro ao aplicar template '{template_name}': {result.stderr}")

    return output_path


def save_custom_template(
    name: str,
    description: str,
    video_filters: list[str] = None,
    audio_filters: list[str] = None,
    config: dict = None,
    templates_file: str = "config/custom_templates.json",
):
    """
    Salva um template customizado em arquivo JSON.

    Permite que o usuário crie seus próprios esqueletos de edição.
    """
    os.makedirs(os.path.dirname(templates_file), exist_ok=True)

    # Carrega templates existentes
    existing = {}
    if os.path.exists(templates_file):
        with open(templates_file, "r") as f:
            existing = json.load(f)

    existing[name] = {
        "name": name,
        "description": description,
        "video_filters": video_filters or [],
        "audio_filters": audio_filters or [],
        "config": config or {},
    }

    with open(templates_file, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    # Registra no dict global
    TEMPLATES[name] = EditTemplate(
        name=name,
        description=description,
        video_filters=video_filters or [],
        audio_filters=audio_filters or [],
        config=config or {},
    )

    print(f"Template '{name}' salvo com sucesso.")


def load_custom_templates(templates_file: str = "config/custom_templates.json"):
    """Carrega templates customizados do arquivo JSON."""
    if not os.path.exists(templates_file):
        return

    with open(templates_file, "r") as f:
        data = json.load(f)

    for name, tpl in data.items():
        TEMPLATES[name] = EditTemplate(
            name=tpl["name"],
            description=tpl["description"],
            video_filters=tpl.get("video_filters", []),
            audio_filters=tpl.get("audio_filters", []),
            config=tpl.get("config", {}),
        )
