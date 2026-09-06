# Glide Studio — Estúdio Local de Produção e Montagem de Vídeo

O **Glide Studio** é uma plataforma local completa de edição, montagem inteligente e produção audiovisual automatizada, projetada para operar **100% offline e localmente** no Windows, sem dependências de nuvem e com total privacidade.

---

## Como Usar em Outro Computador (Instalação 1-Clique)

Não é necessário pedir a nenhum agente de IA nem digitar comandos complexos no terminal. O projeto já inclui instalador e iniciador automatizados para qualquer máquina Windows 10/11.

### Passo a Passo:

1. **Baixar o Projeto do GitHub**:
   - Acesse [github.com/Micas26p/Glide-Studio](https://github.com/Micas26p/Glide-Studio)
   - Clique no botão verde **Code** $\rightarrow$ **Download ZIP** (ou clone via `git clone https://github.com/Micas26p/Glide-Studio.git`)
   - Extraia a pasta em qualquer local do seu computador (ex: Documentos ou Área de Trabalho).

2. **Instalar Tudo Automaticamente**:
   - Abra a pasta e dê 2 cliques no arquivo:
     ```
     instalar.bat
     ```
   - O instalador automático fará todo o trabalho:
     - **Python 3**: Detecta se já existe; se não existir, baixa e instala o Python 3.11 oficial silenciosamente.
     - **Motor FFmpeg**: Detecta se já existe no sistema; se não existir, baixa os binários portáteis oficiais do `ffmpeg.exe` e `ffprobe.exe` diretamente para a pasta do projeto.
     - **Ambiente Isolado (`.venv`)**: Cria o ambiente virtual e instala todas as dependências (FastAPI, OpenCV, NumPy, PyWebView, etc.).
     - **Modelos e Ativos**: Todos os modelos neurais (detector facial YuNet ONNX), trilhas sonoras e fontes já vêm embutidos na pasta `assets/`.

3. **Iniciar o Sistema**:
   - Após a instalação (ou no dia a dia), basta dar 2 cliques em:
     ```
     iniciar.bat
     ```
   - O Glide Studio abrirá instantaneamente em uma janela desktop nativa.
   - *(Opcional)* Se preferir usar no navegador web (Chrome, Edge), utilize `Iniciar_Versao_Web.bat`.

---

## Principais Inovações & Recursos Nativos

- **Auto B-Roll Pacing Slicer**: Fatiamento rítmico dinâmico de tomadas longas (3.5s–5.0s) com cortes alternados e *Punch-In* sutil (1.12x).
- **Sincronia Editorial Magnética de Fala**: Ajuste milimétrico de pontos de corte da timeline sincronizados a fins de frases e pausas de respiração (via SRT ou detecção vocal).
- **Dual Export 9:16 (Shorts / Reels / TikTok)**: Exportação simultânea em formato vertical inteligente com tracking e enquadramento dinâmico facial via YuNet ONNX local.
- **Reuso Cinematográfico Mutante**: Algoritmo matemático coprimo anti-colisão para repetir mídias em vídeos longos com variações angulares e espelhamento horizontal anti-Content-ID seguro.
- **Filtro Visual Anti-Poluição Nativo**:
  - **Salvaguarda de Fotos Históricas**: Preserva fotografias documentais monocromáticas (P&B e Sépia) sem falso descarte por saturação.
  - **Auto-Crop Limpo (`clean_roi`)**: Resgata fotos de acervo com legendas de rodapé ou barras superiores em vez de descartá-las.
  - **Trim de Vinhetas (`clean_trim`)**: Elimina automaticamente vinhetas iniciais ou créditos finais de clipes externos, preservando o trecho limpo.
  - **Radar de Logos nos 4 Cantos**: Identifica e descarta marcas d'água e logos de emissoras de TV (*station bugs*) nos 4 cantos extremos.
- **Calibração Realista de Progresso**: Feedback contínuo de renderização por amostragem temporal sem travamentos em 95%.

---

## Estrutura do Projeto

```text
Glide-Studio/
├── instalar.bat              # Instalador automático 1-clique (baixa Python, FFmpeg e libs)
├── iniciar.bat               # Atalho principal para abrir a aplicação desktop
├── Iniciar_Versao_Web.bat    # Atalho alternativo para abrir no navegador web
├── build_desktop_windows.bat # Compilador para gerar Glide Studio.exe standalone
├── app.py                    # Motor backend principal (FastAPI, OpenCV, FFmpeg)
├── desktop_app.py            # Invólucro desktop com janela nativa (PyWebView)
├── requirements.txt          # Dependências Python do projeto
├── GlideUltra.spec           # Especificação do PyInstaller para build
├── assets/                   # Modelos neurais (YuNet ONNX), áudios, efeitos e fontes
└── frontend/                 # Interface gráfica moderna (HTML5, CSS3, JS)
```

---

## Requisitos Mínimos do Sistema

- **Sistema Operacional**: Windows 10 ou Windows 11 (64-bit).
- **Processador**: Intel Core i3 / AMD Ryzen 3 ou superior.
- **Memória RAM**: 4 GB (recomendado 8 GB ou mais).
- **Espaço em Disco**: ~500 MB livres.
- **Conexão de Internet**: Apenas necessária na primeira execução do `instalar.bat` para baixar os pacotes; após instalado, o sistema opera **100% offline**.
