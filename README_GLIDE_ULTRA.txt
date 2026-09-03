GLIDE ULTRA LOCAL STUDIO v1.14.0
================================

Glide Ultra e um editor local Windows para montar videos com clipes, narracao,
musica automatica, SRT, CTA oficial e render FFmpeg em segundo plano.

INICIALIZADORES OFICIAIS
------------------------
1. Glide Studio.exe
   Inicia o backend local invisivel e abre a interface em modo app.

2. Iniciar_Versao_Web.bat
   Fallback web local. Mantem os mesmos recursos da versao desktop.

NOVIDADES DA v1.14.0 (VERSAO DEFINITIVA COMERCIAL)
--------------------------------------------------
- Exportacao Dual Automatica: Gera simultaneamente o Master 16:9 Full HD e a
  versao vertical 9:16 (_Shorts_9x16.mp4) para YouTube Shorts, TikTok e Reels.
- Extracao Inteligente de Miniaturas HD: Seleciona e exporta automaticamente
  as 3 melhores thumbnails HD do video (_thumb_1.jpg, _thumb_2.jpg, _thumb_3.jpg).
- Remocao Inteligente de Silencio: Corta pausas mortas na narracao mantendo o
  ritmo fluido e dinamico do audio.
- Nova Barra Lateral Colapsavel: Reducao para 72px com botao vetorial SVG,
  animacao suave de rotacao e centralizacao de icones.
- Botoes de Acao e Fila Reformulados: O botao Renderizar Fila agora tem estado
  inativo em alto contraste e gradiente esmeralda ativo.
- Biblioteca Musical em Chips: Segmented control dark pro para generos (Cinematic
  e Ambiente) e faixas de amostra em chips elegantes individuais.
- Normalizacao Universal de Idiomas de CTA: Suporte automatico tanto para siglas
  quanto para nomes completos (portugues, german, english, etc.).
- Atalho Escape: Fechamento instantaneo de qualquer modal ou dialogo aberto.

NOVIDADES DA v1.13.7
--------------------
- Modo Eficiente acelerado sem remover recursos: clipes intermediarios rapidos
  e composicao final unica de CTA + SRT.
- O encoder Eficiente usa mais nucleos com prioridade equilibrada, mantendo o
  computador utilizavel durante o render.
- Turbo/Eficiente agora e uma escolha global aplicada a toda a fila.
- Estimativa comparativa antes do render e contador de tempo restante no modal.

- Turbo Producao agora suspende somente durante o render os filtros visuais
  mais caros: zoom, Quality Boost e transicoes. O ducking profissional e as
  enfases editoriais do SRT permanecem automaticos.
- Resolucao, ratio, bitrate, narracao, musica, ducking, CTA, SRT animado,
  FX do SRT, intro e recuperacao continuam preservados.
- O Turbo testa o NVENC de verdade e usa preset p1 quando a GPU funciona.
  Sem NVENC funcional, usa H.264 CPU ultrafast com a resolucao e o bitrate
  definidos pelo projeto.
- CTA e SRT sao compostos em uma unica passagem visual final, com fallback
  automatico para o fluxo compativel se a composicao unificada falhar.
- Preflight, modal, fila, logs e relatorio mostram encoder, codec, recursos
  suspensos e passagens evitadas pelo Turbo.

NOVIDADES DA v1.13.5
--------------------
- Turbo agora fica preso ao preset de cada projeto, inclusive durante render
  em fila, usando snapshots congelados antes da exportacao.
- A fila ganhou Pausar fila/Retomar fila: o projeto atual termina e os
  proximos ficam pendentes ate continuar.
- Parar render cancela imediatamente o FFmpeg atual, marca o projeto como
  Cancelado e nao tenta recuperacao automatica.
- Status e logs mostram o modo efetivo do render: Turbo ou Eficiente.

NOVIDADES DA v1.13.4
--------------------
- MP4/MOV/M4V agora podem ser importados como narracao ou musica de fundo
  quando escolhidos pelos botoes Audios ou Musicas de fundo.
- O mesmo MP4 continua entrando como video quando importado por Videos, Misto
  ou pasta, evitando mistura acidental entre clipes e narracao.
- Turbo agora e enviado no payload real de render, aparece no preflight/log e
  remove os limites extras de filtros FFmpeg no backend.

NOVIDADES DA v1.13.3
--------------------
- Novo seletor Render no topo: Eficiente ou Turbo, salvo por projeto/job.
- Eficiente mantem o comportamento recente mais estavel e leve para continuar
  usando o PC durante o render.
- Turbo volta ao comportamento mais rapido e pesado: prioridade normal no
  Windows e sem os limites extras de filtros FFmpeg aplicados no modo
  Eficiente.

NOVIDADES DA v1.13.2
--------------------
- Corrigido bug visual da seta de recolher/expandir o painel lateral. A seta
  agora e desenhada por CSS seguro, evitando caracteres quebrados por encoding.

NOVIDADES DA v1.13.1
--------------------
- Protecao extra contra clipes invalidos: arquivos muito leves com tela preta,
  sem duracao ou sem frames visiveis sao ignorados automaticamente no render
  final, preservando os clipes saudaveis da timeline.
- Musica de fundo ficou mais audivel: preset Imersivo agora usa base -22 dB,
  ducking menos agressivo e teto musical maior nas pausas, mantendo a voz
  protegida.

NOVIDADES DA v1.13.0
--------------------
- Polimento final de performance: troca de projetos mais leve, timeline mais
  fluida para arrastar clipes e menos recalculos visuais desnecessarios.
- Render em modo Equilibrado por padrao, usando FFmpeg com prioridade mais
  baixa no Windows e limite de threads para manter o PC mais responsivo.
- Thumbnails, previews e modal de render foram suavizados para reduzir travas
  na versao desktop e na versao web.

NOVIDADES DA v1.12.5
--------------------
- Efeitos sonoros automaticos removidos das transicoes visuais.
- Sound design agora foca no SRT animado, com offsets recalibrados por estilo
  de texto e previews limpos sem FX de transicao.

NOVIDADES DA v1.12.4
--------------------
- Fila de projetos agora pode ser reordenada por arrastar e soltar, preservando
  midias, nomes, presets, status e backups de cada projeto.
- A nova ordem e salva no JSON interno e usada na proxima renderizacao da fila.

NOVIDADES DA v1.12.3
--------------------
- Sound design automatico recalibrado: efeitos mais presentes, normalizacao de
  assets, corte de silencio inicial e melhor sincronizacao com transicoes/SRT.
- O efeito de texto agora segue a variacao real da animacao renderizada
  (pop, slide, zoom, glitch, typewriter etc.), evitando sons fora do tempo.

NOVIDADES DA v1.12.2
--------------------
- Destino final do MP4 configuravel: Downloads do Windows, pasta definida pelo
  usuario ou download automatico pelo navegador.
- O render tecnico continua isolado internamente, mas o arquivo final aparece
  no destino escolhido para facilitar encontrar, enviar e organizar os videos.

NOVIDADES DA v1.12.1
--------------------
- Auto-Fix inteligente com plano explicavel antes do render.
- Tom musical automatico por projeto, ducking profissional, enfases no SRT e
  recuperacao de render com fallback de clipe/codec/GPU.
- Backup da fila: botoes Salvar backup e Importar backup preservam nomes de
  canais, presets, status e referencias dos projetos sem apagar a fila atual.
- Renderizar fila agora faz uma triagem rapida e processa somente projetos com
  videos, narracao, SRT e CTA prontos, ignorando os incompletos.

NOVIDADES DA v1.11.5
--------------------
- Fila mais segura para canais/projetos: nomes editaveis e persistentes,
  presets carregados ao abrir o editor e SRT/intro/estilo isolados por projeto.
- Novo botao Limpar todos na fila: limpa midias, jobs e renders antigos de
  todos os projetos sem apagar nomes nem presets individuais.
- Modos de interface simplificados para Simples e Avancado.

NOVIDADES DA v1.11.4
--------------------
- Intro de abertura otimizada: menos filtros e pintura em tela cheia, animacao
  mais curta, chime atrasado para idle e menor custo no carregamento do editor.

NOVIDADES DA v1.11.3
--------------------
- Abertura premium do editor com revelacao animada da logo, varredura luminosa,
  pulso visual e chime leve de entrada. Se o navegador bloquear autoplay, o som
  toca no primeiro clique/tecla sem atrapalhar o carregamento.

NOVIDADES DA v1.11.2
--------------------
- Efeitos sonoros automaticos mais imersivos, com maior presenca, ducking menos agressivo e previews mais audiveis.

NOVIDADES DA v1.11.1
--------------------
- Timeline com drag/drop refeito para projetos grandes: arraste mais fluido, placeholder visual e menos travamentos.

NOVIDADES DA v1.11.0
--------------------
1. Fila de projetos
   Cada card da fila guarda videos, narracao, SRT, CTA, musica, presets,
   nome final e status proprios. A importacao sempre afeta apenas o projeto
   selecionado.

2. Render sequencial
   O botao Renderizar fila processa um projeto por vez. Se um falhar, o app
   marca erro, pula para o proximo e permite tentar novamente depois.

3. Importacao em massa
   Use Importar lote para selecionar uma pasta com subpastas de projetos. O
   Glide cria cards separados e tenta detectar videos, narracao, SRT e musicas.

4. Producao e revisao
   A fila organiza a revisao em lote dentro dos modos Simples e Avancado. A galeria mostra os
   renders recentes, seus lotes, tamanhos e pastas de saida.

5. Amostra rapida
   A opcao Amostra 30s renderiza um trecho curto com os mesmos presets do job
   ativo para validar CTA, legenda, musica e efeitos antes do video completo.

NOVIDADES DA v1.10.3
--------------------
1. Plano de render
   Cada exportacao agora salva render_plan.json com entradas, politicas,
   opcoes, preflight e duracoes principais. Isso facilita auditoria e debug.

1.1. Polimento visual final
   Icone do app refeito em alta definicao com pacote ICO multi-tamanho, e tema
   claro refinado para estados ativos, contrastes e destaques mais nitidos.

2. Preflight real no backend
   Antes de copiar os arquivos, o app valida CTA, videos, narracao, SRT,
   biblioteca musical, Quality Boost e Sound FX. Erros bloqueiam o render com
   mensagem clara.

3. Configuracoes em JSON
   Presets de exportacao, fluxos rapidos, UI e sound design ficam em
   assets/config para reduzir regras espalhadas no codigo.

4. CTAs simplificados
   A logica antiga de CTA gerada/improvisada foi removida. O editor usa apenas
   CTAs oficiais em assets/cta/source: pt, en, es, fr, ru, de, it e pl.
   O audio original de cada CTA e preservado quando existir.

5. Cache aquecido
   O app prepara previews de CTA em segundo plano para reduzir travamentos na
   primeira abertura dos paineis.

6. Modo Simples / Avancado
   O modo Simples mostra o fluxo essencial. O modo Avancado revela ajustes
   finos de SRT, musica, intro, preflight e parametros tecnicos.

7. Historico musical
   O app registra as musicas usadas em music_history.json e tenta evitar repetir
   as mesmas faixas logo no render seguinte, mantendo Cinematic e Ambiente
   separados.

8. Mapa de sound design
   Quando Sound FX automatico esta ativo, cada render salva
   sound_design_map.json com o efeito, tempo, volume e motivo de uso.

9. Limpeza de instrucoes antigas
   Endpoints legados continuam apenas por compatibilidade. A interface principal
   usa create-render-job, upload-file, launch-render, preflight e status.

FLUXO RECOMENDADO
-----------------
1. Abra Glide Ultra.exe.
2. Importe videos e a narracao.
3. Escolha CTA.
4. Opcionalmente adicione SRT e ajuste legenda/CTA no modo Avancado.
5. Escolha FAST 720p ou STANDARD 1080p.
6. Clique em Renderizar MP4.

BIBLIOTECAS LOCAIS
------------------
- Cinematic: Music/Cinematic
- Ambiente: Music/Ambient e Yt music 1/2/3.MP3
- Efeitos: Music/Efeitos de video

Quando nenhuma musica manual e importada, o app escolhe musicas da biblioteca
ativa automaticamente. Se voce importar musicas de fundo, a biblioteca automatica
fica pausada naquele render.


