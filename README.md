# RecordAI

**RecordAI** é uma aplicação gráfica para Linux que grava automaticamente a saída de áudio do sistema (tudo que toca nos alto-falantes/fones) e/ou microfone, salva os áudios em arquivos compactados `.ogg` (Opus), permite transcrever o conteúdo gravado e gerar resumos inteligentes com IA (Google Gemini). Possui interface moderna para gerenciar, reproduzir, excluir, detalhar gravações **e capturar prints de tela do monitor do mouse, com análise automática via IA**.

---

## Funcionalidades

- Grava a saída de áudio do sistema e/ou microfone, sem necessidade de redirecionamento manual.
- Interface gráfica intuitiva (Tkinter) para gerenciar gravações.
- Salva gravações em blocos organizados por data/hora.
- Reproduz, exclui, abre pastas e apaga todas as gravações facilmente.
- Transcreve automaticamente o áudio gravado para texto (Google Speech Recognition).
- Gera título, resumo e principais pontos da gravação usando IA (Google Gemini).
- **Captura prints de tela do monitor do mouse (atalho Ctrl+Alt+M), vinculando-os à gravação selecionada.**
- **Analisa prints de tela com IA (Google Gemini), exibindo resultado em markdown (com ou sem tkmarkdown).**
- Visualização detalhada de cada gravação, incluindo transcrição, análise da IA e prints capturados.
- Compatível com Ubuntu 24+ (PipeWire ou PulseAudio).

---

## Pré-requisitos

### Dependências do Sistema (Ubuntu)

Execute no terminal:

```bash
sudo apt-get update
sudo apt-get install python3-gi gir1.2-gst-plugins-base-1.0 gir1.2-gstreamer-1.0 \
  gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
  gstreamer1.0-pulseaudio python3-tk python3-pyaudio portaudio19-dev ffmpeg
```

> **Obs:** O `python3-tk` é necessário para a interface gráfica.  
> O `ffmpeg` é necessário para manipulação de áudio (conversão OGG/WAV).

### Dependências Python

Recomenda-se o uso de ambiente virtual:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> **Opcional:** Para exibir resultados de análise de prints em markdown formatado na interface, instale também:
> 
> ```bash
> pip install tkmarkdown
> ```

---

## Configuração de Variáveis de Ambiente

Para usar as funcionalidades de IA (resumo/título/pontos e análise de prints), é necessário configurar a API do Google Gemini. Crie um arquivo `.env` na raiz do projeto com o seguinte conteúdo:

```
GEMINI_API_KEY=seu_token_google_gemini
GEMINI_MODEL=gemini-pro
RECORD_BLOCK_SECONDS=240
```

- `GEMINI_API_KEY`: sua chave de API do Google Gemini (obrigatório para IA).
- `GEMINI_MODEL`: modelo Gemini a ser utilizado (ex: `gemini-pro`).
- `RECORD_BLOCK_SECONDS`: duração máxima de cada bloco de gravação (em segundos, padrão: 240).

> **Atenção:** Sem a chave da API, apenas a gravação e transcrição funcionarão.

---

## Como usar

1. **Clone o repositório:**

   ```bash
   git clone <url-do-repositorio>
   cd recordai
   ```

2. **(Opcional) Crie e ative o ambiente virtual:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instale as dependências Python:**

   ```bash
   pip install -r requirements.txt
   ```

4. **(Opcional) Instale o tkmarkdown para visualização avançada de markdown.**

5. **(Opcional) Configure o arquivo `.env` para recursos de IA.**

6. **Execute a aplicação:**

   ```bash
   python3 recordai.py
   ```

7. **Na interface:**
   - Clique em **Iniciar Gravação** para começar a gravar.
   - Clique em **Encerrar Gravação** para finalizar e salvar.
   - Use os botões para reproduzir, excluir, abrir pasta ou apagar todas as gravações.
   - Use **Transcrever** para gerar o texto do áudio.
   - Use **Aplicar IA** para gerar título, resumo e pontos principais.
   - **Selecione uma gravação e pressione Ctrl+Alt+M para capturar um print do monitor do mouse.**
   - Prints capturados aparecem na aba "Prints" dos detalhes da gravação, podendo ser analisados por IA.
   - As gravações ficam na pasta `output/`.

---

## Estrutura do Projeto

```
recordai/
├── recordai.py         # Script principal com interface gráfica
├── requirements.txt    # Dependências Python
├── output/             # Pasta onde os arquivos .ogg gravados e prints são salvos
│   └── .gitkeep        # Mantém a pasta no repositório
├── .gitignore          # Ignora arquivos de áudio, prints, .env e venv
└── README.md           # Este arquivo
```

---

## Observações Técnicas

- O programa detecta automaticamente o monitor do sink padrão do sistema via `pactl`.
- A gravação é feita via GStreamer, misturando microfone e saída do sistema (caso deseje).
- Arquivos são salvos em OGG/Opus, ideais para voz e música.
- Não é necessário configurar nada no PulseAudio/PipeWire ou usar pavucontrol.
- A transcrição utiliza Google Speech Recognition (necessita conexão com a internet).
- O resumo com IA e a análise de prints utilizam a API do Google Gemini (necessita chave e internet).
- **Captura de prints:**
  - Atalho local: Ctrl+Alt+M (funciona apenas com a janela da aplicação em foco).
  - Atalho global: Ctrl+Alt+M (funciona em todo o sistema, requer sudo e X11).
  - Prints são salvos na gravação selecionada e podem ser analisados por IA.
  - Resultado da análise é exibido em markdown (se `tkmarkdown` instalado, com formatação avançada).

---

## Observação sobre Atalhos Globais no Linux

Para que o recurso de atalho global (ex: Ctrl+Alt+M) funcione no Linux, é necessário rodar a aplicação como root, pois a biblioteca `pynput` exige permissões elevadas para capturar teclas globalmente.

**Como rodar:**

Se estiver usando ambiente virtual (venv):

```bash
sudo -E venv/bin/python recordai.py
```

Se não estiver usando venv:

```bash
sudo python3 recordai.py
```

> **Atenção:**
> - O uso de sudo é necessário apenas para o atalho global. As demais funções da aplicação funcionam normalmente sem sudo.
> - Se faltar algum pacote ao rodar como root, instale com:
>   ```bash
>   sudo pip install -r requirements.txt
>   ```
> - Em ambientes Wayland (Ubuntu 22+ padrão), atalhos globais podem não funcionar. Prefira X11 para esse recurso.

---

## Licença

Projeto livre para uso e modificação.