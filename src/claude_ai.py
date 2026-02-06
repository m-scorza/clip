"""
Módulo de análise inteligente usando a API da Claude (Anthropic).

Funcionalidades:
- Análise da transcrição para encontrar momentos virais
- Geração de headlines otimizadas para engajamento
- Sugestão de categoria e estilo de edição
- Análise de por que certos clipes funcionam

Custo aproximado: ~R$0.05-0.15 por vídeo analisado (modelo Haiku).
"""

import json
import os


def _get_client():
    """Cria cliente da API Anthropic."""
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "Pacote 'anthropic' não instalado.\n"
            "Instale com: pip install anthropic"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY não configurada.\n"
            "Configure com: export ANTHROPIC_API_KEY='sua_chave'\n"
            "Obtenha em: https://console.anthropic.com/settings/keys"
        )

    return anthropic.Anthropic(api_key=api_key)


def find_viral_moments(
    transcript_text: str,
    segments: list[dict],
    video_title: str = "",
    video_duration: float = 0,
    num_clips: int = 5,
    min_duration: float = 30,
    max_duration: float = 90,
    target_duration: float = 60,
    influencer_name: str = "",
    model: str = "claude-haiku-4-5-20251001",
) -> list[dict]:
    """
    Usa Claude para analisar a transcrição e encontrar os melhores momentos para clipes virais.

    Muito mais inteligente que as heurísticas de keywords porque:
    - Entende contexto e narrativa
    - Identifica setup + punchline (não só a reação)
    - Encontra momentos controversos/polêmicos que geram engajamento
    - Sugere onde cortar para manter tensão

    Args:
        transcript_text: Texto completo da transcrição
        segments: Segmentos com timestamps [{start, end, text}, ...]
        video_title: Título do vídeo original
        video_duration: Duração total em segundos
        num_clips: Quantos momentos encontrar
        min_duration: Duração mínima do clipe
        max_duration: Duração máxima do clipe
        target_duration: Duração alvo
        influencer_name: Nome do influenciador (para contexto)
        model: Modelo da Claude a usar

    Returns:
        Lista de dicts com {start, end, score, reason, headline, category}
    """
    client = _get_client()

    # Monta a transcrição com timestamps para referência
    timestamped_text = _format_transcript_with_timestamps(segments)

    # Trunca se muito longo (limite de tokens)
    if len(timestamped_text) > 80000:
        timestamped_text = timestamped_text[:80000] + "\n[... transcrição truncada ...]"

    prompt = f"""Você é um especialista em conteúdo viral para TikTok e Instagram Reels.

Analise esta transcrição de um vídeo e encontre os {num_clips} melhores momentos para criar clipes curtos virais.

VÍDEO: {video_title}
{f'INFLUENCIADOR: {influencer_name}' if influencer_name else ''}
DURAÇÃO TOTAL: {video_duration:.0f} segundos

TRANSCRIÇÃO COM TIMESTAMPS:
{timestamped_text}

CRITÉRIOS PARA MOMENTOS VIRAIS (em ordem de importância):
1. POLÊMICA/CONTROVÉRSIA - Opiniões fortes, revelações, discordâncias
2. EMOÇÃO INTENSA - Raiva, surpresa, riso, choque, indignação
3. FRASES DE IMPACTO - Citações memoráveis que as pessoas vão querer compartilhar
4. STORYTELLING - Histórias com setup claro + clímax (o clipe precisa ter começo-meio-fim)
5. CURIOSIDADE - Algo que faz o espectador querer saber mais (bom para retenção)

REGRAS:
- Cada clipe deve ter entre {min_duration:.0f}s e {max_duration:.0f}s (ideal: {target_duration:.0f}s)
- O clipe precisa fazer sentido sozinho (sem contexto do vídeo completo)
- Comece o clipe ANTES do momento de impacto (inclua o setup)
- Os clipes NÃO devem se sobrepor (mínimo 15s de gap entre eles)
- Gere uma headline curta e impactante para cada clipe (max 60 caracteres, CAPS)

Responda APENAS com JSON válido no formato:
[
  {{
    "start": 125.0,
    "end": 185.0,
    "score": 0.95,
    "reason": "Explicação curta de por que este momento é viral",
    "headline": "HEADLINE IMPACTANTE AQUI",
    "category": "POLÊMICA"
  }}
]

Ordene por score (maior primeiro). Score de 0.0 a 1.0."""

    print("  Analisando transcrição com Claude AI...")

    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    # Extrai JSON da resposta
    try:
        # Tenta parsear direto
        moments = json.loads(response_text)
    except json.JSONDecodeError:
        # Tenta encontrar JSON dentro da resposta
        import re
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if json_match:
            moments = json.loads(json_match.group())
        else:
            print(f"  AVISO: Não foi possível parsear resposta da Claude.")
            return []

    # Valida e limpa
    validated = []
    for m in moments:
        start = float(m.get("start", 0))
        end = float(m.get("end", start + target_duration))

        # Garante duração dentro dos limites
        duration = end - start
        if duration < min_duration:
            end = start + min_duration
        elif duration > max_duration:
            end = start + max_duration

        # Garante que não ultrapassa o vídeo
        if video_duration > 0:
            end = min(end, video_duration)
            start = min(start, video_duration - min_duration)
            start = max(0, start)

        validated.append({
            "start": start,
            "end": end,
            "score": float(m.get("score", 0.5)),
            "reason": m.get("reason", "claude_analysis"),
            "headline": m.get("headline", ""),
            "category": m.get("category", "FAMOSOS"),
        })

    print(f"  Claude encontrou {len(validated)} momentos virais.")
    return validated[:num_clips]


def generate_headline(
    clip_text: str,
    video_title: str = "",
    influencer_name: str = "",
    style: str = "polêmico",
    model: str = "claude-haiku-4-5-20251001",
) -> str:
    """
    Gera uma headline otimizada para engajamento.

    Args:
        clip_text: Texto transcrito do clipe
        video_title: Título do vídeo original
        influencer_name: Nome do influenciador
        style: Estilo da headline (polêmico, informativo, engraçado, chocante)
        model: Modelo da Claude

    Returns:
        Headline em texto (max 60 chars, CAPS)
    """
    client = _get_client()

    prompt = f"""Crie UMA headline curta e impactante para um Reel/TikTok.

TRECHO DO VÍDEO: "{clip_text[:500]}"
{f'VÍDEO ORIGINAL: {video_title}' if video_title else ''}
{f'INFLUENCIADOR: {influencer_name}' if influencer_name else ''}
ESTILO: {style}

REGRAS:
- Máximo 60 caracteres
- TUDO EM MAIÚSCULAS
- Deve gerar curiosidade ou indignação (clickbait inteligente)
- Não pode ser mentira, mas pode ser provocativo
- Não use emojis

Responda APENAS com a headline, nada mais."""

    message = client.messages.create(
        model=model,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )

    headline = message.content[0].text.strip().strip('"').strip("'")

    # Garante limite de caracteres
    if len(headline) > 60:
        headline = headline[:57] + "..."

    return headline.upper()


def analyze_why_clip_works(
    clip_text: str,
    view_count: int = 0,
    platform: str = "tiktok",
    model: str = "claude-haiku-4-5-20251001",
) -> dict:
    """
    Analisa por que um clipe existente funcionou (para aprendizado).
    Útil para alimentar o sistema de ML futuro.

    Args:
        clip_text: Texto/descrição do clipe
        view_count: Número de views
        platform: Plataforma (tiktok, instagram)

    Returns:
        Dict com análise {factors, score_breakdown, recommendations}
    """
    client = _get_client()

    prompt = f"""Analise este clipe viral de {platform} e explique POR QUE ele funcionou.

CONTEÚDO: "{clip_text[:1000]}"
VIEWS: {view_count:,}

Responda em JSON:
{{
  "factors": ["fator1", "fator2", "fator3"],
  "hook_quality": 0.0-1.0,
  "emotional_impact": 0.0-1.0,
  "shareability": 0.0-1.0,
  "controversy_level": 0.0-1.0,
  "ideal_duration_seconds": 45,
  "best_template": "dramatic|energy|podcast|meme|cinema|tiktok_viral",
  "recommendations": ["dica1", "dica2"]
}}"""

    message = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        import re
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            return json.loads(json_match.group())
        return {"factors": ["parse_error"], "recommendations": [response_text]}


def suggest_clips_strategy(
    influencer_name: str,
    research_data: dict = None,
    model: str = "claude-haiku-4-5-20251001",
) -> str:
    """
    Gera uma estratégia completa de clipes para um influenciador.

    Args:
        influencer_name: Nome do influenciador
        research_data: Dados da pesquisa competitiva (opcional)

    Returns:
        Estratégia em texto
    """
    client = _get_client()

    context = ""
    if research_data:
        context = f"\nDADOS DA PESQUISA:\n{json.dumps(research_data, ensure_ascii=False)[:3000]}"

    prompt = f"""Você é um estrategista de conteúdo viral. Crie uma estratégia de clipes para o influenciador "{influencer_name}".

{context}

Responda com:
1. TIPO DE CONTEÚDO que mais viraliza para esse perfil
2. DURAÇÃO IDEAL dos clipes
3. MELHOR TEMPLATE de edição (dramatic, energy, podcast, meme, cinema, tiktok_viral)
4. HORÁRIOS ideais de postagem
5. HEADLINES que funcionam (3 exemplos)
6. HASHTAGS sugeridas (5-10)
7. ESTRATÉGIA de crescimento (primeiro mês)

Seja direto e prático. Foque em ações concretas."""

    message = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def _format_transcript_with_timestamps(segments: list[dict]) -> str:
    """Formata transcrição com timestamps para a Claude analisar."""
    lines = []
    for seg in segments:
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        text = seg.get("text", "").strip()
        if text:
            mins = int(start // 60)
            secs = int(start % 60)
            lines.append(f"[{mins}:{secs:02d}] {text}")
    return "\n".join(lines)
