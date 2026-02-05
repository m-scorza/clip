"""
Configurações do pipeline de automação de clipes.
Edite este arquivo para personalizar o comportamento.
"""

# --- Download ---
DOWNLOAD_DIR = "output/downloads"
MAX_VIDEO_DURATION_MINUTES = 180  # Ignorar vídeos maiores que isso

# --- Clipes ---
CLIPS_DIR = "output/clips"
MIN_CLIP_DURATION_SECONDS = 30
MAX_CLIP_DURATION_SECONDS = 90
TARGET_CLIP_DURATION_SECONDS = 60
NUM_CLIPS_TO_GENERATE = 5  # Quantos clipes gerar por vídeo

# --- Formato de Saída (Reels/TikTok) ---
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
OUTPUT_FPS = 30

# --- Legendas ---
FONT_SIZE = 48
FONT_COLOR = "white"
OUTLINE_COLOR = "black"
OUTLINE_WIDTH = 3
SUBTITLE_POSITION = "center"  # "center", "bottom", "top"

# --- Headline ---
HEADLINE_FONT_SIZE = 56
HEADLINE_BG_COLOR = "black@0.7"
HEADLINE_TEXT_COLOR = "white"
HEADLINE_POSITION = "top"  # Posição da headline no vídeo

# --- Análise de Momentos ---
# Métodos para encontrar melhores momentos (combinados)
USE_AUDIO_PEAKS = True       # Picos de volume/energia no áudio
USE_TRANSCRIPT_ANALYSIS = True  # Análise do conteúdo falado
ENERGY_THRESHOLD = 0.7      # Limiar de energia (0-1) para considerar "momento alto"

# --- Whisper ---
WHISPER_MODEL = "base"  # tiny, base, small, medium, large
WHISPER_LANGUAGE = "pt"  # Português

# --- Claude API (opcional, para análise mais inteligente) ---
# Defina a variável de ambiente ANTHROPIC_API_KEY se quiser usar
USE_CLAUDE_FOR_ANALYSIS = False  # True = usa Claude para encontrar momentos, False = só heurísticas
