# RecordAI

Aplicação simples para gravar a saída de áudio padrão do sistema em um arquivo .wav usando GStreamer.

## Requisitos

- Python 3.x
- Ubuntu 24.04 (ou superior) com PipeWire ou PulseAudio
- GStreamer e plugins PulseAudio
- PyGObject (normalmente já incluso no Ubuntu)

## Instalação das dependências (Ubuntu)

```bash
sudo apt-get install python3-gi gir1.2-gst-plugins-base-1.0 gir1.2-gstreamer-1.0 \
  gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-pulseaudio
```

## Uso

Para iniciar a gravação da saída de áudio padrão do sistema:

```bash
python3 recordai_gst.py
```

A aplicação irá:
1. Detectar automaticamente o sink (saída) padrão do sistema
2. Gravar tudo que for reproduzido na saída padrão (alto-falantes, fones, bluetooth, etc.)
3. Salvar o arquivo WAV na pasta `output` com timestamp
4. Para finalizar, pressione Ctrl+C

## Notas

- Não é necessário redirecionar manualmente o áudio nas configurações do sistema
- O áudio capturado será exatamente o que você ouviria na saída padrão
- Não há dependências Python via pip; tudo é instalado via apt
- O script é compatível com PipeWire e PulseAudio

## Estrutura do projeto

- `recordai_gst.py` — Script principal de gravação
- `output/` — Pasta onde os arquivos de áudio são salvos

## Licença

MVP para gravação de áudio do sistema no Linux 