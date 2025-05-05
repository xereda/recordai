# RecordAI

**RecordAI** é uma aplicação gráfica para Linux que grava automaticamente a saída de áudio do sistema (tudo que toca nos alto-falantes/fones) em arquivos compactados `.ogg` (codec Opus), utilizando GStreamer e PipeWire/PulseAudio. Possui interface moderna para gerenciar, reproduzir e excluir gravações.

## Funcionalidades

- Grava a saída de áudio do sistema (sem necessidade de redirecionamento manual)
- Interface gráfica intuitiva (Tkinter)
- Lista, reproduz, exclui e abre gravações facilmente
- Gravação em OGG/Opus (alta qualidade e arquivos pequenos)
- Compatível com Ubuntu 24+ (PipeWire ou PulseAudio)
- Não requer dependências Python via pip

## Instalação das dependências (Ubuntu)

Execute no terminal:

```bash
sudo apt-get update
sudo apt-get install python3-gi gir1.2-gst-plugins-base-1.0 gir1.2-gstreamer-1.0 \
  gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
  gstreamer1.0-pulseaudio python3-tk
```

> **Obs:** O `python3-tk` é necessário para a interface gráfica.

## Como usar

1. **Clone o repositório** (se ainda não fez):

   ```bash
   git clone <url-do-repositorio>
   cd recordai
   ```

2. **Execute a aplicação:**

   ```bash
   python3 recordai.py
   ```

3. **Na interface:**
   - Clique em **Iniciar Gravação** para começar a gravar tudo que toca no sistema.
   - Clique em **Encerrar Gravação** para finalizar e salvar o arquivo.
   - Use os botões para reproduzir, excluir, abrir a pasta ou apagar todas as gravações.
   - As gravações ficam na pasta `output/`.

## Estrutura do projeto

```
recordai/
├── recordai.py         # Script principal com interface gráfica
├── output/             # Pasta onde os arquivos .ogg gravados são salvos
│   └── .gitkeep        # Mantém a pasta no repositório
├── .gitignore          # Ignora arquivos de áudio e outros artefatos
└── README.md           # Este arquivo
```

## Observações técnicas

- O programa detecta automaticamente o monitor do sink padrão do sistema via `pactl`.
- A gravação é feita via GStreamer, misturando microfone e saída do sistema (caso deseje).
- Arquivos são salvos em OGG/Opus, ideais para voz e música.
- Não é necessário configurar nada no PulseAudio/PipeWire ou usar pavucontrol.

## Licença

Projeto MVP para gravação de áudio do sistema no Linux. Licença livre para uso e modificação. 