# Análise das referências de Eduardo

Análise antes da cópia. Todos os seis áudios são estéreo, 48.000 Hz. M4A: AAC LC, 128 kb/s. WAV: PCM 16 bits. Nenhum apresentou amostra próxima de escala máxima pelo critério `abs(x) >= 1 - 1/32768`. Os números de silêncio usam janelas de 20 ms abaixo de -45 dBFS, portanto são aproximados.

| Perfil / versão | Duração (s) | Bytes | Pico (dBFS) | RMS (dBFS) | Silêncio inicial / final (s) |
|---|---:|---:|---:|---:|---:|
| neutro M4A | 37,87 | 617420 | -3,30 | -24,52 | 0,78 / 0,01 |
| neutro WAV tratado | 40,42 | 7760684 | -3,80 | -25,27 | 4,40 / 2,00 |
| calmo M4A | 32,04 | 523084 | -4,17 | -22,94 | 0,42 / 0,06 |
| calmo WAV tratado | 34,54 | 6631724 | -4,69 | -23,75 | 4,00 / 1,62 |
| animado M4A | 36,89 | 601496 | -3,10 | -21,20 | 0,12 / 0,17 |
| animado WAV tratado | 38,74 | 7438124 | -3,59 | -21,87 | 5,88 / 1,20 |

Nomes exatos: `audio base do eduardo (PERFIL).m4a` e `audio base do eduardo (PERFIL) (sem ruido).wav`, com PERFIL igual a neutro, calmo ou animado. O texto `roteiro base do eduardo.txt` tem 526 bytes e foi copiado como `roteiro_referencia.txt`.

Após alinhamento por correlação e reamostragem apenas para análise a 8 kHz, as correlações M4A/WAV foram 0,9952 (neutro), 0,9753 (calmo) e 0,9818 (animado). Ganhos ajustados: -0,53, -0,73 e -0,64 dB; RMS residual relativo: 9,8%, 22,1% e 19,0%. Há diferenças de duração, bordas e processamento entre versões. A correlação em banda limitada não mede integralmente o timbre, nem garante ausência de artefatos de redução de ruído. Não foi realizada avaliação auditiva; não se afirma qualidade perceptual definitiva.

Seleção inicial: os três WAVs tratados. Não há clipping nem evidência numérica forte de degradação generalizada. O problema aparente é o silêncio inicial longo, especialmente no animado, incompatível com aproveitar os primeiros 6 segundos de fala do condicionamento do modelo. Nas cópias de inferência foram retirados somente os silêncios externos, mantendo 200 ms de margem. Nenhuma fala foi intencionalmente cortada, nenhum filtro foi aplicado. Cópias completas e byte a byte ficam em `tts/voices/eduardo/originais/`.

| Perfil final | Duração (s) | Pico (dBFS) | RMS (dBFS) | Corte início / fim (s) |
|---|---:|---:|---:|---:|
| neutro | 34,42 | -3,80 | -24,58 | 4,20 / 1,80 |
| calmo | 29,32 | -4,69 | -23,04 | 3,80 / 1,42 |
| animado | 32,06 | -3,59 | -21,05 | 5,68 / 1,00 |

As referências finais continuam estéreo, 48 kHz, PCM 16 bits. A biblioteca faz mono/reamostragem internamente. JSONs registram hashes SHA256, medidas e critérios. Uma verificação posterior confirmou SHA256 idêntico dos sete arquivos externos, sem alteração dos originais.
