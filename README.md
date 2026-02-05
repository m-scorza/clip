# Clip Automator

Pipeline de automacao de clipes para campanhas de influenciadores.

Baixa videos do YouTube, encontra os melhores momentos, gera clipes editados
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

## Uso Rapido

### 1. Gerar clipes de um video

```bash
python main.py pipeline --url "https://youtube.com/watch?v=XXXXX" --clips 5
```

Opcoes:
- `--clips N` - Numero de clipes (padrao: 5)
- `--headline "TEXTO"` - Headline personalizada (auto se nao especificado)
- `--category "FAMOSOS"` - Categoria do banner
- `--campaign-id N` - Registrar clipes em uma campanha

### 2. Gerenciar campanhas

```bash
# Criar campanha
python main.py campaign --create \
    --name "Campanha Verao" \
    --influencer "FulanoTV" \
    --pay 5.0 \
    --min-views 10000

# Listar campanhas
python main.py campaign --list

# Registrar link apos postar
python main.py campaign --add-link \
    --campaign-id 1 \
    --clip-id 1 \
    --platform instagram \
    --link "https://instagram.com/reel/xxx"

# Marcar como submetido na plataforma
python main.py campaign --submit --campaign-id 1 --clip-id 1
```

## Estrutura do Projeto

```
clip/
├── main.py              # Orquestrador principal (CLI)
├── requirements.txt     # Dependencias Python
├── config/
│   └── settings.py      # Configuracoes (duracao, fontes, etc)
├── src/
│   ├── downloader.py    # Download de videos (yt-dlp)
│   ├── analyzer.py      # Analise de momentos (Whisper + heuristicas)
│   ├── editor.py        # Edicao de clipes (FFmpeg)
│   └── tracker.py       # Tracking de campanhas
└── output/
    ├── downloads/       # Videos baixados
    ├── clips/           # Clipes gerados
    └── campaigns.json   # Dados de campanhas
```

## Como Funciona

1. **Download**: Baixa o video usando yt-dlp
2. **Transcricao**: Transcreve o audio com Whisper (legendas automaticas)
3. **Analise**: Encontra melhores momentos combinando:
   - Picos de energia no audio (momentos de emocao)
   - Palavras-chave na transcricao (reacoes, frases de impacto)
   - Capitulos do YouTube (se disponiveis)
4. **Edicao**: Para cada momento selecionado:
   - Corta o trecho
   - Converte para formato vertical (9:16) com fundo blur
   - Adiciona legendas (burn-in)
   - Adiciona headline/banner
5. **Tracking**: Registra clipes em campanhas para acompanhamento

## O Que Voce Precisa Fazer Manualmente

- Postar os clipes no Instagram/TikTok
- Copiar os links de compartilhamento
- Registrar os links via CLI (`campaign --add-link`)
- Submeter na plataforma de campanha

## Configuracoes

Edite `config/settings.py` para ajustar:
- Duracao dos clipes (min/max/alvo)
- Resolucao de saida
- Tamanho e posicao das legendas
- Modelo do Whisper (tiny=rapido, large=preciso)
- Idioma da transcricao
