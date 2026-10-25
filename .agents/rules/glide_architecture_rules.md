---
description: Regras arquiteturais críticas para pipeline de vídeo, concorrência de hardware e pacing editorial no Glide Studio.
globs: ["app.py", "glide_core/**", "glide_director*.py"]
---

# Regras de Engenharia Arquitetural — Glide Studio

1. **Precedência do Pipeline Unificado (Single-Pass First):**
   - Em qualquer função de processamento de chunk ou exportação que suporte modo direto/fused, a verificação de planos (`if "plans" in chunk_info: return render_single_chunk_fused(...)`) deve ser a PRIMEIRA instrução. Nunca execute loops de concatenação legados ou métodos de caminho relativo (`.relative_to()`) antes desse desvio.

2. **Dimensionamento Dinâmico de Gates de Hardware:**
   - Gates de limitação de codificador físico (ex: `NVENC_GATE`) não podem ter valores de corte fixos estáticos que bloqueiem a concorrência em máquinas potentes ou em testes unitários. Valide a memória de vídeo livre (`gpu_free_vram_mb()`) e o perfil de hardware (`is_laptop`, `gpu_ram_gb`) para autorizar slots adicionais.

3. **Conservação de Massa Temporal no Auto-Diretor:**
   - Ao ajustar o ritmo visual via `SpeechVelocityPacer` ou análise WPM, a duração total alocada às tomadas deve somar exatamente o tempo de locução. Qualquer aceleração no gancho (hook) deve ser elasticamente compensada com desaceleração no desenvolvimento para garantir que cada asset seja utilizado de forma estritamente única (`max_asset_usage = 1`).
