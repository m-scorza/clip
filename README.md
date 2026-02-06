# Clip Automator

Pipeline de automacao de clipes para campanhas de influenciadores.

Baixa videos do YouTube e Twitch, encontra os melhores momentos, gera clipes editados
(vertical 9:16, com legendas e headline) prontos para postar no Instagram/TikTok.

## Requisitos

- Python 3.10+
- FFmpeg instalado no sistema
- Conexao com a internet

```bash
# Instalar FFmpeg (Ubuntu/Debian)
sudo apt install ffmpeg

# Instalar dependencias Python
pip install -r requirements.txt
```

## Modo Conversacional (Recomendado)

O jeito mais facil de usar. Aceita comandos em linguagem natural:

```bash
python main.py chat
```

Exemplos de comandos:
```
Voce> Criar campanha para Gaules pagando R$5 por 1k views
Voce> Pesquisar o que funciona para Gaules
Voce> Buscar top 10 clipes do Gaules na Twitch
Voce> Gerar 5 clipes do video https://youtube.com/watch?v=XXX
Voce> Mostrar templates de edicao
Voce> Postei o clipe 1 da campanha 1 no instagram: https://...
```

## Uso via CLI

### 1. Clipes do YouTube

```bash
python main.py pipeline --url "https://youtube.com/watch?v=XXX" --clips 5 --template dramatic
```

### 2. Clipes da Twitch

```bash
# Buscar clipes mais populares de um canal
python main.py twitch --username "gaules" --clips 10 --min-views 5000

# Buscar e ja editar para mobile
python main.py twitch --username "gaules" --clips 5 --edit --template tiktok_viral
```

Requer credenciais da Twitch (gratuito):
```bash
export TWITCH_CLIENT_ID='seu_client_id'
export TWITCH_CLIENT_SECRET='seu_client_secret'
# Obtenha em: https://dev.twitch.tv/console/apps
```

### 3. Pesquisa Competitiva

```bash
python main.py research --influencer "FulanoTV"
```

Analisa:
- Shorts/clips do influenciador que deram certo
- Clipes de outros canais sobre o influenciador
- Padroes de duracao, titulo, views
- Recomendacoes de estrategia

### 4. Templates de Edicao

```bash
python main.py templates
```

Templates disponiveis:
- `clean` - Limpo, legendas centralizadas
- `dramatic` - Zoom progressivo, vinheta escura
- `energy` - Cores vibrantes, contraste alto
- `podcast` - Foco no audio, legendas grandes
- `meme` - Texto impacto estilo zoeira
- `cinema` - Letterbox, color grading quente
- `tiktok_viral` - Legenda palavra-por-palavra, cores neon

### 5. Gerenciar Campanhas

```bash
# Criar campanha
python main.py campaign --create --name "Campanha X" --influencer "Fulano" --pay 5.0

# Listar campanhas
python main.py campaign --list

# Registrar link de post
python main.py campaign --add-link --campaign-id 1 --clip-id 1 --platform instagram --link "URL"

# Marcar como submetido
python main.py campaign --submit --campaign-id 1 --clip-id 1
```

## N8N (Orquestracao Visual)

Para quem quer orquestrar o pipeline visualmente com N8N:

```bash
cd n8n
docker-compose up -d
```

Acesse http://localhost:5678 (admin/changeme).
Importe o workflow de `n8n/workflows/clip_pipeline.json`.

O N8N chama a Worker API (porta 8000) que executa os scripts Python.

## Estrutura do Projeto

```
clip/
├── main.py                  # CLI principal
├── requirements.txt         # Dependencias Python
├── config/
│   └── settings.py          # Configuracoes
├── src/
│   ├── downloader.py        # Download YouTube (yt-dlp)
│   ├── analyzer.py          # Analise de momentos (Whisper + heuristicas)
│   ├── editor.py            # Edicao de clipes (FFmpeg)
│   ├── twitch.py            # Integracao Twitch API
│   ├── templates.py         # Templates/esqueletos de edicao
│   ├── research.py          # Pesquisa competitiva
│   ├── tracker.py           # Tracking de campanhas
│   └── chat.py              # Interface conversacional
├── n8n/
│   ├── docker-compose.yml   # Setup N8N + Worker
│   ├── Dockerfile.worker    # Container do worker Python
│   ├── worker_api.py        # API HTTP para o N8N
│   └── workflows/           # Workflows N8N exportados
└── output/
    ├── downloads/           # Videos baixados
    ├── clips/               # Clipes gerados
    └── campaigns.json       # Dados de campanhas
```

## O Que e Automatico vs Manual

| Etapa | Status |
|-------|--------|
| Download do video (YouTube/Twitch) | Automatico |
| Encontrar melhores momentos | Automatico |
| Transcricao e legendas | Automatico |
| Edicao (vertical, headline, template) | Automatico |
| Pesquisa competitiva | Automatico |
| **Postar no Instagram/TikTok** | **Manual** |
| **Copiar link e registrar** | **Semi-manual (CLI)** |
| **Submeter na plataforma** | **Manual** |

## Configuracoes

Edite `config/settings.py` para ajustar:
- Duracao dos clipes (min/max/alvo)
- Resolucao de saida
- Tamanho e posicao das legendas
- Modelo do Whisper (tiny=rapido, large=preciso)
- Idioma da transcricao
