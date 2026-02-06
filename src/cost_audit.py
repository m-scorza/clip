"""
Sistema de auditoria de custos da API Claude.

Registra cada chamada à API com:
- Tokens usados (input + output)
- Custo estimado em USD e BRL
- Qual função chamou
- Para qual vídeo/influenciador
- Timestamp

Permite ver:
- Custo total acumulado
- Custo por vídeo
- Custo por tipo de operação (análise, headline, estratégia)
- Se está compensando financeiramente
"""

import json
import os
from datetime import datetime


AUDIT_FILE = "output/api_costs.json"

# Preços por 1M de tokens (USD) - atualizado fev/2026
# Fonte: https://docs.anthropic.com/en/docs/about-claude/pricing
PRICING = {
    "claude-haiku-4-5-20251001": {
        "input_per_1m": 1.00,   # US$1.00 / 1M input tokens
        "output_per_1m": 5.00,  # US$5.00 / 1M output tokens
        "name": "Haiku 4.5",
    },
    "claude-sonnet-4-5-20250929": {
        "input_per_1m": 3.00,   # US$3.00 / 1M input tokens
        "output_per_1m": 15.00, # US$15.00 / 1M output tokens
        "name": "Sonnet 4.5",
    },
}

# Taxa de câmbio aproximada USD -> BRL
USD_TO_BRL = 5.80


def _load_audit() -> dict:
    """Carrega dados de auditoria."""
    if os.path.exists(AUDIT_FILE):
        with open(AUDIT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"calls": [], "total_usd": 0.0, "total_brl": 0.0}


def _save_audit(data: dict):
    """Salva dados de auditoria."""
    os.makedirs(os.path.dirname(AUDIT_FILE), exist_ok=True)
    with open(AUDIT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def record_api_call(
    operation: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    video_id: str = "",
    video_title: str = "",
    influencer: str = "",
    details: str = "",
) -> dict:
    """
    Registra uma chamada à API com custos.

    Args:
        operation: Tipo de operação (find_moments, headline, analyze, strategy)
        model: ID do modelo usado
        input_tokens: Tokens de input consumidos
        output_tokens: Tokens de output consumidos
        video_id: ID do vídeo (se aplicável)
        video_title: Título do vídeo
        influencer: Nome do influenciador
        details: Detalhes extras

    Returns:
        Dict com custos calculados
    """
    pricing = PRICING.get(model, PRICING["claude-haiku-4-5-20251001"])

    cost_input_usd = (input_tokens / 1_000_000) * pricing["input_per_1m"]
    cost_output_usd = (output_tokens / 1_000_000) * pricing["output_per_1m"]
    cost_total_usd = cost_input_usd + cost_output_usd
    cost_total_brl = cost_total_usd * USD_TO_BRL

    entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation,
        "model": model,
        "model_name": pricing["name"],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost_total_usd, 6),
        "cost_brl": round(cost_total_brl, 4),
        "video_id": video_id,
        "video_title": video_title,
        "influencer": influencer,
        "details": details,
    }

    data = _load_audit()
    data["calls"].append(entry)
    data["total_usd"] = round(sum(c["cost_usd"] for c in data["calls"]), 6)
    data["total_brl"] = round(sum(c["cost_brl"] for c in data["calls"]), 4)
    _save_audit(data)

    return entry


def get_cost_report(detailed: bool = False) -> str:
    """
    Gera relatório de custos.

    Args:
        detailed: Se True, mostra cada chamada individual

    Returns:
        Relatório em texto
    """
    data = _load_audit()
    calls = data.get("calls", [])

    if not calls:
        return "Nenhuma chamada de API registrada ainda."

    lines = [
        "=" * 65,
        "AUDITORIA DE CUSTOS - API Claude",
        "=" * 65,
        "",
        f"  Total de chamadas:  {len(calls)}",
        f"  Custo total (USD):  US${data['total_usd']:.4f}",
        f"  Custo total (BRL):  R${data['total_brl']:.2f}",
        "",
    ]

    # Custo por operação
    by_operation = {}
    for c in calls:
        op = c["operation"]
        if op not in by_operation:
            by_operation[op] = {"count": 0, "usd": 0.0, "brl": 0.0, "tokens_in": 0, "tokens_out": 0}
        by_operation[op]["count"] += 1
        by_operation[op]["usd"] += c["cost_usd"]
        by_operation[op]["brl"] += c["cost_brl"]
        by_operation[op]["tokens_in"] += c["input_tokens"]
        by_operation[op]["tokens_out"] += c["output_tokens"]

    lines.append("  POR OPERACAO:")
    for op, stats in sorted(by_operation.items(), key=lambda x: x[1]["brl"], reverse=True):
        lines.append(f"    {op:20s}  {stats['count']:3d}x  R${stats['brl']:.2f}  ({stats['tokens_in']:,} in / {stats['tokens_out']:,} out)")

    # Custo por vídeo
    by_video = {}
    for c in calls:
        vid = c.get("video_id") or c.get("video_title") or "sem_video"
        if vid not in by_video:
            by_video[vid] = {"count": 0, "usd": 0.0, "brl": 0.0, "title": c.get("video_title", vid)}
        by_video[vid]["count"] += 1
        by_video[vid]["usd"] += c["cost_usd"]
        by_video[vid]["brl"] += c["cost_brl"]

    if len(by_video) > 1 or "sem_video" not in by_video:
        lines.append("")
        lines.append("  POR VIDEO:")
        for vid, stats in sorted(by_video.items(), key=lambda x: x[1]["brl"], reverse=True):
            title = stats["title"][:40]
            lines.append(f"    {title:42s}  {stats['count']:2d}x  R${stats['brl']:.2f}")

    # Custo médio
    if calls:
        avg_brl = data["total_brl"] / len(calls)
        lines.append("")
        lines.append(f"  Custo medio por chamada:  R${avg_brl:.4f}")

        videos_count = len([v for v in by_video if v != "sem_video"])
        if videos_count > 0:
            avg_per_video = data["total_brl"] / videos_count
            lines.append(f"  Custo medio por video:   R${avg_per_video:.2f}")

    # Chamadas detalhadas
    if detailed:
        lines.append("")
        lines.append("-" * 65)
        lines.append("  DETALHAMENTO (ultimas 20 chamadas):")
        lines.append("-" * 65)
        for c in calls[-20:]:
            ts = c["timestamp"][:19].replace("T", " ")
            lines.append(
                f"  {ts}  {c['operation']:15s}  "
                f"{c['input_tokens']:6,}in {c['output_tokens']:5,}out  "
                f"R${c['cost_brl']:.4f}  {c.get('video_title', '')[:25]}"
            )

    lines.append("")
    lines.append("=" * 65)
    return "\n".join(lines)


def get_roi_analysis(total_revenue_brl: float = 0.0) -> str:
    """
    Analisa se o uso da API está compensando financeiramente.

    Args:
        total_revenue_brl: Receita total das campanhas (em BRL)

    Returns:
        Análise de ROI
    """
    data = _load_audit()
    total_cost = data.get("total_brl", 0)

    lines = [
        "=" * 50,
        "ANALISE DE ROI - Claude API",
        "=" * 50,
        "",
        f"  Gasto total com API:   R${total_cost:.2f}",
        f"  Receita informada:     R${total_revenue_brl:.2f}",
    ]

    if total_revenue_brl > 0:
        profit = total_revenue_brl - total_cost
        roi_pct = ((total_revenue_brl - total_cost) / total_cost * 100) if total_cost > 0 else float('inf')
        lines.append(f"  Lucro liquido:         R${profit:.2f}")
        lines.append(f"  ROI:                   {roi_pct:.0f}%")
        lines.append("")
        if profit > 0:
            lines.append("  VEREDICTO: API esta compensando!")
        else:
            lines.append("  VEREDICTO: API NAO esta compensando.")
            lines.append("  Considere desligar com: python main.py smart --off")
    else:
        lines.append("")
        lines.append("  Informe a receita para calcular ROI:")
        lines.append("  python main.py costs --revenue 150.00")

    lines.append("")
    lines.append("=" * 50)
    return "\n".join(lines)


def reset_audit():
    """Reseta todos os dados de auditoria."""
    _save_audit({"calls": [], "total_usd": 0.0, "total_brl": 0.0})
    print("Dados de auditoria resetados.")
