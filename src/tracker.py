"""
Módulo de tracking de campanhas e clipes postados.
Salva dados localmente em JSON para acompanhamento.
"""

import json
import os
from datetime import datetime


TRACKER_FILE = "output/campaigns.json"


def load_campaigns() -> dict:
    """Carrega dados de campanhas do arquivo JSON."""
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"campaigns": []}


def save_campaigns(data: dict):
    """Salva dados de campanhas no arquivo JSON."""
    os.makedirs(os.path.dirname(TRACKER_FILE), exist_ok=True)
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def create_campaign(
    name: str,
    influencer: str,
    platform_url: str = "",
    pay_per_1k_views: float = 0.0,
    min_views: int = 10000,
) -> dict:
    """
    Registra uma nova campanha.

    Args:
        name: Nome da campanha
        influencer: Nome do influenciador
        platform_url: URL da plataforma de campanha
        pay_per_1k_views: Pagamento por 1000 views
        min_views: Mínimo de views para remuneração
    """
    data = load_campaigns()

    campaign = {
        "id": len(data["campaigns"]) + 1,
        "name": name,
        "influencer": influencer,
        "platform_url": platform_url,
        "pay_per_1k_views": pay_per_1k_views,
        "min_views": min_views,
        "created_at": datetime.now().isoformat(),
        "clips": [],
        "status": "active",
    }

    data["campaigns"].append(campaign)
    save_campaigns(data)
    print(f"Campanha '{name}' criada com ID {campaign['id']}")
    return campaign


def add_clip_to_campaign(
    campaign_id: int,
    clip_path: str,
    source_video_url: str,
    clip_start: float,
    clip_end: float,
    posted_links: dict | None = None,
) -> dict:
    """
    Registra um clipe em uma campanha.

    Args:
        campaign_id: ID da campanha
        clip_path: Caminho do arquivo do clipe
        source_video_url: URL do vídeo original
        clip_start: Início do clipe no vídeo original
        clip_end: Fim do clipe no vídeo original
        posted_links: Dict com links de postagem {platform: url}
    """
    data = load_campaigns()

    campaign = None
    for c in data["campaigns"]:
        if c["id"] == campaign_id:
            campaign = c
            break

    if not campaign:
        raise ValueError(f"Campanha {campaign_id} não encontrada")

    clip = {
        "id": len(campaign["clips"]) + 1,
        "clip_path": clip_path,
        "source_video_url": source_video_url,
        "clip_start": clip_start,
        "clip_end": clip_end,
        "created_at": datetime.now().isoformat(),
        "posted_links": posted_links or {},
        "submitted_to_platform": False,
        "views": {},
    }

    campaign["clips"].append(clip)
    save_campaigns(data)
    return clip


def update_clip_link(
    campaign_id: int,
    clip_id: int,
    platform: str,
    link: str,
):
    """
    Atualiza o link de postagem de um clipe.

    Args:
        campaign_id: ID da campanha
        clip_id: ID do clipe
        platform: Nome da plataforma (instagram, tiktok)
        link: URL do post
    """
    data = load_campaigns()

    for campaign in data["campaigns"]:
        if campaign["id"] == campaign_id:
            for clip in campaign["clips"]:
                if clip["id"] == clip_id:
                    clip["posted_links"][platform] = link
                    save_campaigns(data)
                    print(f"Link atualizado: {platform} = {link}")
                    return

    raise ValueError(f"Campanha {campaign_id} / Clip {clip_id} não encontrado")


def mark_submitted(campaign_id: int, clip_id: int):
    """Marca um clipe como submetido na plataforma de campanha."""
    data = load_campaigns()

    for campaign in data["campaigns"]:
        if campaign["id"] == campaign_id:
            for clip in campaign["clips"]:
                if clip["id"] == clip_id:
                    clip["submitted_to_platform"] = True
                    clip["submitted_at"] = datetime.now().isoformat()
                    save_campaigns(data)
                    print(f"Clip {clip_id} marcado como submetido")
                    return

    raise ValueError(f"Campanha {campaign_id} / Clip {clip_id} não encontrado")


def get_campaign_summary(campaign_id: int = None) -> str:
    """Retorna resumo de campanhas."""
    data = load_campaigns()

    lines = []
    for campaign in data["campaigns"]:
        if campaign_id and campaign["id"] != campaign_id:
            continue

        lines.append(f"\n{'='*60}")
        lines.append(f"Campanha #{campaign['id']}: {campaign['name']}")
        lines.append(f"Influenciador: {campaign['influencer']}")
        lines.append(f"Status: {campaign['status']}")
        lines.append(f"Pagamento: R${campaign['pay_per_1k_views']}/1k views")
        lines.append(f"Views mínimas: {campaign['min_views']}")
        lines.append(f"Total de clipes: {len(campaign['clips'])}")

        for clip in campaign["clips"]:
            status = "Submetido" if clip.get("submitted_to_platform") else "Pendente"
            links = clip.get("posted_links", {})
            links_str = ", ".join(f"{k}: {v}" for k, v in links.items()) if links else "Nenhum"
            lines.append(f"  Clip #{clip['id']}: {status} | Links: {links_str}")

        lines.append(f"{'='*60}")

    return "\n".join(lines) if lines else "Nenhuma campanha encontrada."
