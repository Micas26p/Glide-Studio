# Glide Studio — revisão da Etapa 5

Data: 09/09/2026. Trabalho local na branch `main`, sem publicação no GitHub.

**Resultado:** correções aplicadas e executável atualizado. Os testes abaixo
passaram, mas o gate integral de liberação permanece parcialmente verificado:
a importação pelo navegador foi bloqueada pelo controle de permissões; não houve
validação de uma fila longa completa na janela WebView. Este relatório não é uma
afirmação de ausência de bugs.

## A. Estado inicial e final

- Inicial: não havia suíte automatizada versionada. A análise estática encontrou
  quatro referências a uma variável inexistente na montagem final. O render de
  teste `0b960c8a9bd0` reproduziu `name 'subtitles' is not defined`.
- Os sete primeiros testes produziram nove falhas de asserção e um erro,
  considerando os casos de estrutura JSON inválida separadamente.
- Final: 18 testes passam; Python compila, JavaScript passa em `node --check`,
  Ruff não encontra nomes indefinidos ou erros de sintaxe nos módulos principais,
  e `pip check` passa nos ambientes Python 3.11 de build e Python 3.14 local.
- Render H.264 concluído e decodificado integralmente; exportação vertical
  corrigida, inspecionada visualmente e decodificada integralmente.
- PyInstaller recompilado após a última alteração de produção. O smoke test do
  executável terminou com código 0 e 14 respostas HTTP 200; YuNet ativo.

As alterações já presentes em `frontend/index.html`, `glide_render_plan.py`,
`music_history.json` e a remoção de `desktop_smoke_ok.json` foram preservadas.
Os servidores e testes usaram raízes de dados isoladas em `scratch/` ou no
diretório temporário do sistema. As mídias documentais foram lidas para produzir
cópias curtas de teste; os originais não foram alterados.

## B. Correções principais

| Prioridade | Defeito | Correção / evidência |
|---|---|---|
| P1 | Montagem final falhava sem cache de áudio | Caminho SRT mantido no Job; render de 24 s concluído |
| P1 | Fila antiga em formato de lista era ignorada | Leitura compatível com lista e objeto; teste de reabertura |
| P1 | Primário corrompido substituía backup recuperável | Validar o primário antes de atualizar `.bak`; teste de falha |
| P1 | Reenvio interrompido destruía upload anterior | Gravação temporária e substituição atômica; injeção de erro de leitura |
| P1 | Reenvios contavam duas vezes e nomes iguais colidiam | Contagem por caminho relativo e aliases protegidos; dois testes |
| P1 | Disparos simultâneos podiam criar mais de um worker | Lock de ciclo de vida; 20 chamadas concorrentes iniciam um worker |
| P1 | Job cancelado podia voltar à fase de lançamento | Estado terminal rejeitado com 409; teste |
| P1 | Roteiros desapareciam do snapshot do projeto | Preservar `script_guides`; gravação e leitura testadas |
| P1 | Áudio silencioso gerava parâmetros infinitos | Fallback de loudnorm e relatório JSON finito; teste |
| P1 | Modo vertical de preservação também recortava a imagem | Primeiro plano inteiro com fundo desfocado; frame final inspecionado |
| P1 | FFmpeg do dual export não participava do cancelamento | Usar executor monitorado; cancelamento propagado, fallback CPU preservado |
| P1 | Iniciadores encerravam qualquer processo na porta 8787 | Removido `taskkill`; versão web reaproveita apenas servidor local compatível |
| P2 | JSON estruturalmente inválido causava erro interno | Resposta 400 antes de criar diretórios e Job |
| P2 | Upload vazio era aceito | Rejeição antes de publicar o arquivo |
| P2 | Versão web tentava instalar dependências toda vez | Arranque com `.venv` existente; reparação orientada pelo instalador |
| P2 | Build falhava com espaço no caminho do Python | Aspas no executável e expansão correta de errorlevel |
| P2 | Interface anunciava remoção mesmo com erro no servidor | Aguardar resposta; manter projeto e mostrar erro se falhar |
| P2 | Escape contornava proteção do importador ocupado | Usar a função de fechamento que respeita operação ativa |
| P2 | Teclado escapava dos modais | Foco inicial, ciclo Tab/Shift+Tab e retorno ao controle de origem |

Foi observado um `PermissionError` transitório ao publicar um diretório de cache
na versão inicial. A publicação agora repete somente esse tipo de falha, com
limite de quatro tentativas e espera total de 0,3 s; erros persistentes continuam
visíveis. As duas condições foram testadas por injeção. Não é possível atribuir
com certeza a ocorrência original ao antivírus ou ao indexador do Windows.

## C. Limpeza e estrutura

- Upload legado reutiliza o mesmo caminho de gravação protegido do upload em etapas.
- Novo `web_app.py` concentra o arranque web offline e espera o backend responder
  antes de abrir o navegador.
- `requirements-dev.txt` separa ferramentas de verificação das dependências de uso.
- Sem reescrita do diretor, filtro visual, modelos ou formatos de projeto.

## D. Medições

30 requisições por rota, descartando uma chamada de aquecimento. Mesma máquina,
servidores isolados antes/depois; medições informativas, sem controle de toda a
carga externa do computador.

| Rota | Mediana antes | Mediana depois | p95 antes | p95 depois |
|---|---:|---:|---:|---:|
| `/api/health` | 12,18 ms | 7,96 ms | 23,74 ms | 10,32 ms |
| `/api/config` | 6,21 ms | 6,14 ms | 9,78 ms | 7,68 ms |
| `/api/queue/projects` | 6,78 ms | 6,71 ms | 9,86 ms | 8,96 ms |

Não houve regressão observada nessas rotas. As diferenças não sustentam uma
alegação geral de aceleração. O render completo levou 79,296 s; a versão inicial
falhava antes de produzir o arquivo, portanto não existe comparação válida de
velocidade de render antes/depois. Não foi feito benchmark de longa duração.

## E. Interface e automação

- Novo modo vertical Automático protege textos e CTA já incorporados ao vídeo.
  A opção Full-Bleed permanece disponível e avisa sobre o corte de elementos.
  Escolhas explícitas dos presets existentes são mantidas.
- O modo de preservação ocupa o centro do quadro vertical com a composição
  horizontal completa. Isso evita cortes; não equivale a uma nova composição
  editorial independente para Shorts.
- Rejeição de todas as mídias pelo filtro agora tem orientação específica,
  em vez de atribuir o problema genericamente a arquivos inválidos.
- Interface observada em tema claro, dimensão normal e 1080×680: estado vazio,
  controles desabilitados, configuração, rolagem do modal, foco, Tab, Shift+Tab,
  Escape e persistência do nome Unicode após recarregamento.
- Console consultado nesses percursos: nenhum erro ou aviso retornado.

## F. Cenários de mídia

1. **Cenário técnico de 24 s:** dois vídeos sintéticos, imagem, áudio, música e
   SRT Unicode; upload em etapas, direção, filtro visual, reuso, textos, CTA,
   efeitos sonoros, masterização e montagem final. O filtro rejeitou parte dos
   padrões; a opção existente de render curto foi usada para testar a montagem
   com o material restante. Isso não comprova a qualidade editorial em acervos
   variados.
2. **Resultado horizontal:** H.264, 1280×720, aproximadamente 24,02 s, AAC presente,
   1.578.370 bytes. Pico medido após decodificação: −6,8 dBFS; média: −15,2 dBFS.
   Frame com texto e CTA inspecionado; FFmpeg decodificou todo o arquivo.
3. **Resultado vertical:** 1080×1920, H.264/AAC. O primeiro frame inspecionado
   revelou corte do texto; após a correção, o texto e CTA aparecem inteiros.
   A versão corrigida foi decodificada sem erros.
4. **Codecs:** amostras reais de dois segundos exportadas pelos argumentos do
   motor: HEVC por NVENC e H.264 por libx264 com aceleração indisponível. FFprobe
   confirmou os codecs. O fallback de HEVC para H.264 CPU é política preexistente.
5. **Mídia documental:** cópias curtas de dois vídeos, foto e narração locais.
   O filtro rejeitou toda a amostra. A inspeção mostrou apresentadora fixa em um
   vídeo e uma vinheta com logo em outro. O filtro foi preservado; esse cenário
   não produziu um segundo render completo.

## G. Verificações e evidências

Comandos principais, a partir da raiz do projeto:

```powershell
.\.venv-build311\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-build311\Scripts\python.exe -m ruff check --select F821,F822,F823,E9 *.py
.\.venv-build311\Scripts\python.exe -m PyInstaller --noconfirm --distpath scratch\qa_package --workpath scratch\qa_build GlideUltra.spec
```

Evidências locais mantidas:

- `scratch/qa_baseline_tests.log`: falhas reproduzidas antes das correções.
- `scratch/qa_final_tests.log`: 18 testes aprovados, incluindo FFmpeg real cancelado.
- `scratch/qa_demo/0b960c8a9bd0_status.json`: falha inicial de montagem.
- `scratch/qa_demo/3c20ae0d8a85_status.json` e `_probe.json`: render completo e metadados.
- `scratch/qa_after/exports/render_20260909_151735_3c20ae0d8a85/`: MP4s e relatórios do motor.
- `scratch/qa_demo/output_frame.png`, `shorts_frame.png` e `shorts_fixed_frame.png`: inspeção antes/depois.
- `scratch/qa_latency.json`: amostras agregadas de latência.
- `scratch/qa_codec/codec_smoke.json`: argumentos de exportação e codecs confirmados.
- `scratch/qa_packaging_verified.log`: build final.
- `scratch/qa_desktop_smoke.json`: 14 recursos HTTP 200 e YuNet ativo.

O build avisou sobre `pycparser.lextab`, `pycparser.yacctab` e `tzdata` ausentes.
O parser C instalado foi executado com sucesso; o app utiliza relógio local,
sem depender de fusos nomeados por ZoneInfo. O smoke do pacote passou. Isso não
substitui uma prova de todos os caminhos opcionais de CFFI ou fusos horários.

## H. Regressões descobertas durante a própria validação

O corte vertical e a perda do roteiro no snapshot foram encontrados em passes
posteriores ao primeiro render corrigido. Ambos foram corrigidos e retestados.
O teste de interrupção de upload verificou os bytes anteriores preservados;
o teste de concorrência verificou um único lançamento. A suíte final permanece
inteiramente aprovada.

## I. Limitações e gate de liberação

| Item | Estado |
|---|---|
| Build de produção e smoke empacotado | Verificado |
| Testes automatizados relevantes | 18 aprovados |
| Pipeline principal pela API, até MP4 | Verificado com cenário técnico |
| Save/reopen | Fila antiga, backup, roteiro e nome na UI verificados |
| Output horizontal e vertical | Decodificação e frames verificados |
| Entradas inválidas e falhas principais | JSON, vazio, leitura/gravação, falta de FFmpeg e cancelamento verificados |
| Logs dos fluxos aprovados | Sem erro crítico observado; falhas injetadas separadas |
| Benchmark sem regressão | Somente as três rotas medidas |
| Revisão visual e interação | Parcial; controles e modais citados acima |
| Dados do usuário | Raízes de teste isoladas; originais não editados |
| Instalação em Windows limpo / sessão nativa completa | Não verificado |
| Importação de arquivo pela interface e fila longa E2E | Não concluído |
| GPU OOM real, disco cheio, crash do sistema, todos os DPIs | Não provocado |

O controle de navegador recusou a importação em `http://127.0.0.1:8795/`,
informando permissão negada. O passo não foi repetido por outro meio. Os uploads
de teste pela API que geraram os cenários acima já tinham sido executados antes
dessa recusa. Não há alegação de validação integral do fluxo humano.

## J. Entrega, reversão e prioridades seguintes

`Glide Studio.exe` na raiz foi substituído pelo pacote que passou no smoke.
SHA-256: `B468D8CE6642F71B8D460715D8D761692E7E917F5BCAA3AB9E2BD2682AAA5C29`.
A cópia de segurança está em `scratch/Glide Studio.before-etapa5.exe`.
As mudanças de código permanecem locais e não foram enviadas ao GitHub.

Backlog por valor/risco:

1. **P1 — validação pendente:** executar importação, fila com vários projetos,
   pausa/retomada, fechamento e reabertura na janela nativa. Impacto: regressões
   de integração nesses percursos ainda podem existir. Contorno: testar uma
   cópia da fila antes de um lote extenso.
2. **P2 — calibração do filtro:** corpus rotulado com fotografias documentais,
   apresentadores e vinhetas; medir falsos positivos. Os motivos apresentados
   ainda podem classificar uma cena como slide mesmo quando o elemento poluente
   é outro. Não afrouxar proteção sem evidência.
3. **P2 — Shorts editorial:** composição própria de textos/CTA sobre vídeo vertical
   limpo. Hoje o Automático preserva a composição pronta com fundo desfocado;
   Full-Bleed pode cortar elementos por escolha explícita.
4. **P2 — endurance e empacotamento:** benchmark com vídeos longos e fila extensa,
   memória/processos/cache, instalação limpa e matriz NVIDIA/AMD/Intel/CPU.
5. **P3 — evolução estrutural:** extrair gradualmente upload, fila e exportação de
   `app.py`, mantendo a nova suíte. Reescrita ampla não foi recomendada nesta revisão.
