# IA Voz

Integração local de síntese de voz em português brasileiro com Chatterbox. A raiz do projeto é `IA_de_Voz`.

## Chatterbox TTS

### Experimento de tutorial natural

Execute `.\.venv\Scripts\python.exe -u test_tutorial_natural.py` para comparar uma única referência masculina brasileira (`eduardo/calmo.wav`). São três testes curtos: padrão (expressividade 0,5, CFG 0,5, temperatura 0,8), suave (0,4 / 0,35 / 0,75) e suave com a abertura falada “Vamos começar.”. O roteiro principal e a semente são iguais. O terceiro teste mantém a abertura audível para avaliar o início da instrução seguinte, sem cortar palavras por tempo fixo. Isso é uma experiência de condicionamento durante a geração, não treinamento; não garante melhora. Os WAVs ficam em `outputs/audio/tutorial_*.wav`, com parâmetros em JSON e cópias completas em `experimento_tutorial/`.

O carregador possui uma alternativa para o erro 1455 de memória virtual do Windows: lê os tensores F32 do checkpoint em partes, sem alterar os pesos. Ainda é necessário haver memória suficiente para o modelo e a geração.

### Interface local

Execute `iniciar_interface.bat` ou `.\.venv\Scripts\python.exe interface.py` na raiz e abra **http://127.0.0.1:8765**. Mantenha o terminal aberto durante o uso. A interface permite escrever até 300 caracteres, comparar seis referências gravadas, ajustar expressividade, acompanhar a geração, ouvir, buscar uma posição no áudio e baixar os WAVs. Os áudios anteriores permanecem no histórico.

Brisa, Campo e Aurora são nomes de apresentação das referências, não modelos diferentes. Brisa usa a amostra oficial PT-BR; Campo e Aurora usam outras amostras de português da demonstração oficial. O motor é sempre o Chatterbox PT-BR V3. Os botões de comparação reproduzem o mesmo roteiro de tutorial, sintetizado localmente com cada referência. O roteiro fica em `tts/voices/tutorial.txt` e os exemplos completos em `tts/voices/tutorial_brisa.wav`, `tutorial_campo.wav` e `tutorial_aurora.wav`. As referências originais são preservadas para as novas gerações.

Para recriar os exemplos após alterar o roteiro, execute `.\.venv\Scripts\python.exe tools/gerar_exemplos_tutorial.py`. O utilitário divide o texto em trechos seguros, reaproveita o modelo, guarda partes para retomar uma execução interrompida e junta cada voz em um WAV completo. As partes e seus relatórios ficam em `outputs/audio/voice_examples/`.

O progresso acompanha os tokens realmente produzidos. A porcentagem e o tempo restante são estimativas baseadas no tamanho do texto e nas gerações anteriores; carregamento e finalização podem demorar mais. A duração exata aparece depois de salvar o WAV. Apenas uma geração ocorre por vez e o modelo é reutilizado enquanto o servidor estiver aberto.

As referências extras podem ser preparadas com `.\.venv\Scripts\python.exe tools/prepare_ui_voices.py`. A interface usa somente bibliotecas já instaladas e o servidor escuta apenas em `127.0.0.1`.

Windows, Python 3.12 e ambiente isolado `.venv`. A instalação usa o código da demonstração oficial [ResembleAI/Chatterbox-Multilingual-TTS-pt-br](https://huggingface.co/spaces/ResembleAI/Chatterbox-Multilingual-TTS-pt-br), revisão `9e515821e826e207cd617a0fdd0223899ed108ea`, e os pesos [ResembleAI/Chatterbox-Multilingual-pt-br](https://huggingface.co/ResembleAI/Chatterbox-Multilingual-pt-br), do V3 Single Language Pack. O idioma interno é `pt`.

```powershell
.\.venv\Scripts\Activate.ps1
python test_chatterbox.py
```

Também é possível executar sem ativar: `.\.venv\Scripts\python.exe test_chatterbox.py`.

O teste gera `outputs/audio/teste_chatterbox.wav` e um relatório JSON com duração, sample rate, dispositivo e tempos. Modelos ficam em `models/pt-br-v3`, com revisões registradas em `provenance.json`. A primeira execução baixa os pesos; as seguintes reutilizam os arquivos locais.

```python
from tts import ChatterboxTTS, gerar_audio

gerar_audio("Olá! Este é um teste de voz em português brasileiro.", "teste.wav")

tts = ChatterboxTTS()  # reutilize esta instância entre gerações
tts.generate("Olá! Este é um teste do IA Voz.", "outputs/audio/teste.wav")
tts.generate("Teste com minha voz.", "outputs/audio/minha_voz.wav",
             reference_audio="tts/voices/minha_voz.wav")
```

As referências ficam em `tts/voices/`. O perfil padrão do motor é `eduardo/neutro.wav`. A interface continua selecionando explicitamente suas próprias referências. A inferência e a gravação de WAV são locais.

## Vozes de Eduardo

Os perfis `neutro`, `calmo` e `animado` usam, respectivamente, `tts/voices/eduardo/neutro.wav`, `calmo.wav` e `animado.wav`. O perfil padrão é `neutro`. Os caminhos de `VOICE_PROFILES` são relativos ao projeto e resolvidos a partir da raiz, independentemente do diretório de execução.

Na seção **Escolha a voz**, os três perfis aparecem entre Brisa e Campo, como **Eduardo · Neutro**, **Eduardo · Calmo** e **Eduardo · Animado**. Eduardo Calmo inicia selecionado na interface, com expressividade natural (0,5). Os botões de reprodução usam os três testes já gerados em `outputs/audio/`, e selecionar um perfil usa a respectiva referência nas novas gerações.

```python
from tts import ChatterboxTTS, VOICE_PROFILES, validate_reference_audio

tts = ChatterboxTTS()
tts.generate(text="Olá. Este é um teste.", output_path="outputs/audio/teste.wav")
tts.generate(text="Agora, clique no botão Salvar para concluir a operação.",
             voice="neutro", output_path="outputs/audio/teste_neutro.wav")
tts.generate(text="Olá. Este é um teste.", voice="calmo", output_path="outputs/audio/calmo.wav")
tts.generate(text="Olá. Este é um teste.", voice="animado", output_path="outputs/audio/animado.wav")
for profile, path in VOICE_PROFILES.items():
    validate_reference_audio(path, profile)
```

A integração instalada é `ia-voz-chatterbox-ptbr==0.1.0`, código oficial PT-BR V3 disponibilizado em `vendor/chatterbox`. A API real é `generate(text, audio_prompt_path=None, exaggeration=0.5, cfg_weight=0.5, temperature=0.8, language_id="en")`. O motor fornece `language_id="pt"` e o WAV escolhido em `audio_prompt_path`, mantendo os parâmetros padrão.

A biblioteca carrega a referência em mono a 24 kHz e reamostra para 16 kHz internamente. Usa os primeiros 6 segundos para tokens de fala, os primeiros 10 segundos para o decodificador e a referência completa para o encoder de locutor. Por isso, os WAVs de inferência preservam toda a fala e removem apenas silêncio das bordas, com 200 ms de margem. Não recebem filtros, normalização, compressão ou equalização. Cópias completas ficam em `tts/voices/eduardo/originais/`; as gravações externas permanecem intactas.

O relatório de todos os arquivos, comparação M4A/WAV e hashes está em `docs/voices/eduardo/source_analysis.json`. `import_manifest.json` registra a origem e os cortes de silêncio, e `roteiro_referencia.txt` preserva o roteiro da gravação. A correlação alta entre versões não garante ausência de artefatos perceptuais; uma comparação auditiva continua necessária.

Execute o teste real com `.\.venv\Scripts\python.exe -u test_vozes_eduardo.py`. Ele reutiliza uma instância do modelo e gera `outputs/audio/teste_neutro.wav`, `teste_calmo.wav` e `teste_animado.wav`, com exatamente o mesmo texto, as mesmas divisões em frases e as mesmas sementes por trecho. A divisão evita o limite interno de 1.000 tokens de fala por chamada; os trechos são unidos com pausas iguais de 250 ms. Os JSONs registram texto, referência, parâmetros, duração e validação dos WAVs. Partes validadas podem ser reaproveitadas após interrupção.

Os utilitários `tools/analisar_referencias_eduardo.py PASTA` e `tools/importar_vozes_eduardo.py PASTA` usam a pasta externa apenas como argumento da importação. O importador exige análise prévia e recusa sobrescrever referências existentes. Para análise de M4A, foi acrescentado apenas `imageio-ffmpeg==0.6.0` ao ambiente; ele fornece um FFmpeg local, sem reinstalar o motor.

CUDA é selecionada automaticamente quando `torch.cuda.is_available()` é verdadeiro; caso contrário usamos CPU. Verifique com:

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print('CUDA:', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

Nesta máquina foi detectada Intel UHD Graphics 620, sem NVIDIA. Foi instalada a variante CPU do PyTorch. Em uma futura máquina NVIDIA, instale a variante CUDA compatível com o driver conforme o [seletor oficial do PyTorch](https://pytorch.org/get-started/locally/), mantendo torch e torchaudio compatíveis com a implementação.

Teste real concluído: PyTorch `2.8.0+cpu`, WAV mono PCM 16 bits, 24.000 Hz, duração de 11,52 segundos e 553.004 bytes. A geração levou aproximadamente 8min43s nesta CPU; a primeira execução completa, incluindo download e carregamento, levou cerca de 14min24s. Os tempos variam conforme a máquina. O teste verificou amostras finitas e áudio não silencioso.

Para reproduzir a instalação CPU em um ambiente novo:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe tools/prepare_chatterbox.py
.\.venv\Scripts\python.exe -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements-tts.txt
```

As versões fixadas seguem a implementação oficial PT-BR V3, cuja API e pesos diferem do pacote genérico. Não é necessário Gradio para a integração local.

`requirements-tts-lock.txt` registra todas as versões efetivamente instaladas. Para reproduzir exatamente este ambiente CPU, prepare primeiro o código com `tools/prepare_chatterbox.py` e instale o lock usando `pip install -r requirements-tts-lock.txt --extra-index-url https://download.pytorch.org/whl/cpu` dentro do `.venv`.

FFmpeg não foi encontrado no PATH na análise inicial. Ele não é necessário para este primeiro WAV. Para montar vídeos depois, instale-o seguindo [FFmpeg Downloads](https://ffmpeg.org/download.html), adicione seu diretório `bin` ao PATH e confirme com `ffmpeg -version`.
