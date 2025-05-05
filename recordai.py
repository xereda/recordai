#!/usr/bin/env python3
import gi
import os
from datetime import datetime
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import sys
import platform
import webbrowser
from pydub import AudioSegment, silence
import speech_recognition as sr
import google.generativeai as genai
from dotenv import load_dotenv
import json
import re
import tempfile
import time
from collections import defaultdict

if sys.version_info < (3, 6):
    print("Python 3.6+ é necessário.")
    sys.exit(1)

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

Gst.init(None)

# Carrega variáveis do .env
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL')
RECORD_BLOCK_SECONDS = int(os.getenv('RECORD_BLOCK_SECONDS', '240'))
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class RecorderGUI:
    def __init__(self, master):
        self.master = master
        master.title("RecordAI - Gravação de Áudio do Sistema")
        master.geometry("1120x520")
        master.resizable(False, False)
        master.configure(bg="#f7f7f7")

        self.is_recording = False
        self.pipeline = None
        self.loop = None
        self.filename = None
        self.thread = None
        self.output_dir = "output"

        # --- Layout ---
        self.label = tk.Label(master, text="Grave e gerencie os áudios da saída do sistema.", font=("Arial", 13, "bold"), bg="#f7f7f7")
        self.label.pack(pady=(18, 10), fill='x')

        # --- Switches de captação ---
        switch_frame = tk.Frame(master, bg="#f7f7f7")
        switch_frame.pack(pady=(0, 10), fill='x')
        self.var_mic = tk.BooleanVar(value=True)
        self.var_out = tk.BooleanVar(value=True)
        self.check_mic = tk.Checkbutton(switch_frame, text="Gravar microfone (entrada)", variable=self.var_mic, bg="#f7f7f7", font=("Arial", 12, "bold"), padx=10, pady=4, command=self.update_start_button_state)
        self.check_mic.pack(side=tk.LEFT, padx=10)
        self.check_out = tk.Checkbutton(switch_frame, text="Gravar saída do sistema", variable=self.var_out, bg="#f7f7f7", font=("Arial", 12, "bold"), padx=10, pady=4, command=self.update_start_button_state)
        self.check_out.pack(side=tk.LEFT, padx=10)

        # --- Botões principais ---
        btn_frame = tk.Frame(master, bg="#f7f7f7")
        btn_frame.pack(pady=(0, 8), fill='x')
        self.start_button = tk.Button(btn_frame, text="Iniciar Gravação", command=self.start_recording, width=15, height=1, bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), relief=tk.RAISED, bd=2)
        self.start_button.grid(row=0, column=0, padx=8, pady=2, ipady=2)
        self.stop_button = tk.Button(btn_frame, text="Encerrar Gravação", command=self.stop_recording, width=15, height=1, bg="#F44336", fg="white", font=("Arial", 11, "bold"), state=tk.DISABLED, relief=tk.RAISED, bd=2)
        self.stop_button.grid(row=0, column=1, padx=8, pady=2, ipady=2)
        self.refresh_button = tk.Button(btn_frame, text="Atualizar Lista", command=self.refresh_files, width=12, height=1, font=("Arial", 10), relief=tk.RAISED, bd=2)
        self.refresh_button.grid(row=0, column=2, padx=8, pady=2, ipady=2)

        # --- Tabela de arquivos ---
        self.tree = ttk.Treeview(master, columns=("titulo", "arquivo", "duracao", "datahora", "detalhes"), show="headings", height=12)
        self.tree.heading("titulo", text="Título")
        self.tree.heading("arquivo", text="Arquivo")
        self.tree.heading("duracao", text="Duração")
        self.tree.heading("datahora", text="Data/Hora")
        self.tree.heading("detalhes", text="Detalhes")
        self.tree.column("titulo", width=260)
        self.tree.column("arquivo", width=320)
        self.tree.column("duracao", width=80, anchor="center")
        self.tree.column("datahora", width=160)
        self.tree.column("detalhes", width=100, anchor="center")
        self.tree.pack(pady=10, fill='x', expand=True)
        self.tree.bind('<Double-1>', self.open_file)
        self.tree.bind('<Button-1>', self.on_tree_click_detalhes)

        # --- Botões de ação ---
        action_frame = tk.Frame(master, bg="#f7f7f7")
        action_frame.pack(pady=(5, 10), fill='x')
        self.play_button = tk.Button(action_frame, text="Reproduzir", command=self.play_file, width=12, height=1, font=("Arial", 10), relief=tk.RAISED, bd=2)
        self.play_button.grid(row=0, column=0, padx=6, pady=2, ipady=2)
        self.delete_button = tk.Button(action_frame, text="Excluir", command=self.delete_file, width=12, height=1, font=("Arial", 10), relief=tk.RAISED, bd=2)
        self.delete_button.grid(row=0, column=1, padx=6, pady=2, ipady=2)
        self.open_folder_button = tk.Button(action_frame, text="Abrir Pasta", command=self.open_folder, width=12, height=1, font=("Arial", 10), relief=tk.RAISED, bd=2)
        self.open_folder_button.grid(row=0, column=2, padx=6, pady=2, ipady=2)
        self.delete_all_button = tk.Button(action_frame, text="Excluir Todos", command=self.delete_all_files, width=12, height=1, font=("Arial", 10), relief=tk.RAISED, bd=2)
        self.delete_all_button.grid(row=0, column=3, padx=6, pady=2, ipady=2)
        self.transcrever_button = tk.Button(action_frame, text="Transcrever", command=self.transcrever_selecionado, width=12, height=1, font=("Arial", 10), relief=tk.RAISED, bd=2, bg="#1976D2", fg="white")
        self.transcrever_button.grid(row=0, column=4, padx=6, pady=2, ipady=2)
        self.ia_button = tk.Button(action_frame, text="Aplicar IA", command=self.aplicar_ia_selecionado, width=12, height=1, font=("Arial", 10), relief=tk.RAISED, bd=2, bg="#388E3C", fg="white")
        self.ia_button.grid(row=0, column=5, padx=6, pady=2, ipady=2)

        self.status = tk.Label(master, text="", font=("Arial", 11), bg="#f7f7f7", fg="#555")
        self.status.pack(pady=(5, 0))

        # Tooltip para o botão de iniciar gravação
        self.start_btn_tooltip = None
        self.update_start_button_state()

        self.refresh_files()

    def get_output_filename(self, prefix="gravacao"):  
        os.makedirs(self.output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return os.path.join(self.output_dir, f"{prefix}_{timestamp}.ogg")

    def get_default_source(self):
        try:
            result = subprocess.run(['pactl', 'info'], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.startswith('Fonte padrão:') or line.startswith('Default Source:'):
                        return line.split(':', 1)[1].strip()
        except Exception as e:
            print(f"Erro ao buscar fonte padrão: {e}")
        return 'default'

    def get_default_sink_monitor(self):
        try:
            result = subprocess.run(['pactl', 'info'], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.startswith('Sink padrão:') or line.startswith('Default Sink:'):
                        return line.split(':', 1)[1].strip() + '.monitor'
        except Exception as e:
            print(f"Erro ao buscar sink padrão: {e}")
        return 'default.monitor'

    def build_gst_pipeline_mix(self, mic_device, monitor_device, filename, use_mic=True, use_out=True):
        elements = []
        elements.append('audiomixer name=mix ! audioconvert ! audioresample ! opusenc bitrate=32000 ! oggmux ! filesink location={}'.format(filename))
        if use_mic:
            elements.append('pulsesrc device={} provide-clock=true do-timestamp=true ! audioconvert ! audioresample ! mix.'.format(mic_device))
        if use_out:
            elements.append('pulsesrc device={} provide-clock=true do-timestamp=true ! audioconvert ! audioresample ! mix.'.format(monitor_device))
        pipeline_str = ' '.join(elements)
        return Gst.parse_launch(pipeline_str)

    def update_start_button_state(self):
        use_mic = self.var_mic.get()
        use_out = self.var_out.get()
        if not use_mic and not use_out:
            self.start_button.config(state=tk.DISABLED)
            self.add_start_btn_tooltip("Selecione pelo menos uma fonte para gravar (microfone ou saída do sistema)")
        else:
            self.start_button.config(state=tk.NORMAL)
            self.remove_start_btn_tooltip()

    def add_start_btn_tooltip(self, text):
        if self.start_btn_tooltip:
            return
        def show_tooltip(event):
            x = self.start_button.winfo_rootx() + self.start_button.winfo_width() // 2
            y = self.start_button.winfo_rooty() + self.start_button.winfo_height() + 8
            self.start_btn_tooltip = tw = tk.Toplevel(self.start_button)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            label = tk.Label(tw, text=text, background="#ffffe0", relief=tk.SOLID, borderwidth=1, font=("Arial", 10))
            label.pack(ipadx=6, ipady=2)
        def hide_tooltip(event):
            if self.start_btn_tooltip:
                self.start_btn_tooltip.destroy()
                self.start_btn_tooltip = None
        self.start_button.bind("<Enter>", show_tooltip)
        self.start_button.bind("<Leave>", hide_tooltip)

    def remove_start_btn_tooltip(self):
        self.start_button.unbind("<Enter>")
        self.start_button.unbind("<Leave>")
        if self.start_btn_tooltip:
            self.start_btn_tooltip.destroy()
            self.start_btn_tooltip = None

    def start_recording(self):
        if self.is_recording:
            return
        self.is_recording = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status.config(text="Gravando... (clique em Encerrar para finalizar)", fg="#1976D2")
        self.filename_base = self.get_output_filename().replace('.ogg', '')
        self.mic_device = self.get_default_source()
        self.monitor_device = self.get_default_sink_monitor()
        self.use_mic = self.var_mic.get()
        self.use_out = self.var_out.get()
        self.current_block = 1
        self._stop_recording_flag = threading.Event()
        self.thread = threading.Thread(target=self._record_in_blocks, daemon=True)
        self.thread.start()

    def _record_in_blocks(self):
        while not self._stop_recording_flag.is_set():
            filename = f"{self.filename_base}_{self.current_block:02d}.ogg"
            pipeline = self.build_gst_pipeline_mix(self.mic_device, self.monitor_device, filename, self.use_mic, self.use_out)
            loop = GLib.MainLoop()
            pipeline.set_state(Gst.State.PLAYING)
            print(f"[DEBUG] Iniciando bloco {self.current_block}: {filename}")
            t = threading.Thread(target=lambda: self._wait_and_stop_block(loop, pipeline), daemon=True)
            t.start()
            try:
                loop.run()
            except Exception as e:
                print(f"Erro durante a gravação do bloco: {e}")
            pipeline.set_state(Gst.State.NULL)
            self.current_block += 1
        print("[DEBUG] Gravação encerrada.")

    def _wait_and_stop_block(self, loop, pipeline):
        # Espera RECORD_BLOCK_SECONDS ou até o flag de parada
        for _ in range(RECORD_BLOCK_SECONDS):
            if self._stop_recording_flag.is_set():
                break
            time.sleep(1)
        loop.quit()
        pipeline.set_state(Gst.State.NULL)

    def stop_recording(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self._stop_recording_flag.set()
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status.config(text="Gravação finalizada!", fg="#388E3C")
        self.refresh_files()
        messagebox.showinfo("Gravação finalizada", f"Arquivos salvos em blocos de até {RECORD_BLOCK_SECONDS} segundos.")

    def refresh_files(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        if not os.path.exists(self.output_dir):
            return
        files = [f for f in os.listdir(self.output_dir) if f.endswith('.ogg')]
        files.sort()
        # Agrupa arquivos por prefixo base
        gravacoes = defaultdict(list)
        for f in files:
            nome_base = os.path.splitext(f)[0]
            m = re.match(r'(.+_\d{8}_\d{6})_\d{2}$', nome_base)
            if m:
                prefixo_base = m.group(1)
            else:
                prefixo_base = nome_base
            gravacoes[prefixo_base].append(f)
        # Exibe um registro por gravação
        for prefixo_base, blocos in sorted(gravacoes.items(), reverse=True):
            # Soma duração dos blocos
            duracao_total = 0
            dt = ''
            for idx, f in enumerate(sorted(blocos)):
                path = os.path.join(self.output_dir, f)
                try:
                    audio = AudioSegment.from_file(path)
                    duracao_total += int(audio.duration_seconds)
                    if idx == 0:
                        dt = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%d/%m/%Y %H:%M:%S')
                except Exception:
                    pass
            minutos = duracao_total // 60
            segundos = duracao_total % 60
            duracao_str = f"{minutos:02d}:{segundos:02d}"
            caminho_db = os.path.join(self.output_dir, f"{os.path.basename(prefixo_base)}_ia.json")
            titulo = ""
            if os.path.exists(caminho_db):
                try:
                    with open(caminho_db, 'r', encoding='utf-8') as j:
                        dados_ia = json.load(j)
                        titulo = dados_ia.get('titulo', "")
                except Exception:
                    titulo = ""
            self.tree.insert('', 'end', values=(titulo, os.path.basename(prefixo_base), duracao_str, dt, 'detalhes'))

    def get_selected_prefixo_base(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Seleção", "Selecione um registro na lista.")
            return None
        return self.tree.item(sel[0])['values'][1]

    def play_file(self):
        prefixo_base = self.get_selected_prefixo_base()
        if not prefixo_base:
            return
        # Busca um dos arquivos .ogg para passar para play_file
        files = [f for f in os.listdir(self.output_dir) if f.startswith(prefixo_base + '_') and f.endswith('.ogg')]
        if not files:
            messagebox.showwarning("Reprodução", "Nenhum bloco encontrado para reproduzir.")
            return
        f = files[0]
        path = os.path.abspath(os.path.join(self.output_dir, f))
        if platform.system() == "Linux":
            subprocess.Popen(["xdg-open", path])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        elif platform.system() == "Windows":
            os.startfile(path)
        else:
            webbrowser.open(path)

    def delete_file(self):
        prefixo_base = self.get_selected_prefixo_base()
        if not prefixo_base:
            return
        # Busca todos os arquivos .ogg para excluir
        files = [f for f in os.listdir(self.output_dir) if f.startswith(prefixo_base + '_') and f.endswith('.ogg')]
        if not files:
            messagebox.showinfo("Excluir Todos", "Nenhum arquivo para excluir.")
            return
        if messagebox.askyesno("Excluir Todos", f"Deseja realmente excluir TODOS os arquivos de áudio? ({len(files)} arquivos)"):
            erros = 0
            for f in files:
                try:
                    os.remove(os.path.join(self.output_dir, f))
                except Exception:
                    erros += 1
            self.refresh_files()
            if erros:
                self.status.config(text=f"{len(files)-erros} arquivos excluídos, {erros} erros.", fg="#F44336")
            else:
                self.status.config(text=f"Todos os arquivos excluídos.", fg="#F44336")

    def open_file(self, event=None):
        prefixo_base = self.get_selected_prefixo_base()
        if not prefixo_base:
            return
        # Busca um dos arquivos .ogg para passar para open_file
        files = [f for f in os.listdir(self.output_dir) if f.startswith(prefixo_base + '_') and f.endswith('.ogg')]
        if not files:
            messagebox.showwarning("Reprodução", "Nenhum bloco encontrado para abrir.")
            return
        f = files[0]
        path = os.path.abspath(os.path.join(self.output_dir, f))
        self.play_file()

    def open_folder(self):
        folder = os.path.abspath(self.output_dir)
        if platform.system() == "Linux":
            subprocess.Popen(["xdg-open", folder])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", folder])
        elif platform.system() == "Windows":
            os.startfile(folder)
        else:
            webbrowser.open(folder)

    def delete_all_files(self):
        if not os.path.exists(self.output_dir):
            messagebox.showinfo("Excluir Todos", "Nenhum arquivo para excluir.")
            return
        files = [f for f in os.listdir(self.output_dir) if f.endswith('.ogg')]
        if not files:
            messagebox.showinfo("Excluir Todos", "Nenhum arquivo para excluir.")
            return
        if messagebox.askyesno("Excluir Todos", f"Deseja realmente excluir TODOS os arquivos de áudio? ({len(files)} arquivos)"):
            erros = 0
            for f in files:
                try:
                    os.remove(os.path.join(self.output_dir, f))
                except Exception:
                    erros += 1
            self.refresh_files()
            if erros:
                self.status.config(text=f"{len(files)-erros} arquivos excluídos, {erros} erros.", fg="#F44336")
            else:
                self.status.config(text=f"Todos os arquivos excluídos.", fg="#F44336")

    def on_tree_click_detalhes(self, event):
        region = self.tree.identify('region', event.x, event.y)
        if region != 'cell':
            return
        row_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not row_id:
            return
        # Descobre dinamicamente o índice da coluna 'detalhes'
        colunas = self.tree['columns']
        try:
            idx_detalhes = list(colunas).index('detalhes') + 1  # +1 porque Treeview começa em 1
        except ValueError:
            return
        if col != f'#{idx_detalhes}':
            return
        values = self.tree.item(row_id)['values']
        if not values:
            return
        arquivo = values[1]
        self.abrir_detalhes_gravacao(arquivo)

    def on_tree_motion(self, event):
        row_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if col in ('#3', '#4') and row_id:
            self.tree.config(cursor='hand2')
        else:
            self.tree.config(cursor='')

    def iniciar_transcricao_thread(self, arquivo):
        # Desabilita botões e mostra status
        self.status.config(text="Transcrevendo...", fg="#1976D2")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)
        self.play_button.config(state=tk.DISABLED)
        self.delete_button.config(state=tk.DISABLED)
        self.open_folder_button.config(state=tk.DISABLED)
        self.delete_all_button.config(state=tk.DISABLED)
        self.refresh_button.config(state=tk.DISABLED)
        # Desabilita o clique na treeview
        self.tree.unbind('<Button-1>')
        t = threading.Thread(target=self.transcrever_audio, args=(arquivo,), daemon=True)
        t.start()

    def transcrever_audio(self, arquivo):
        """
        Transcreve todos os blocos .ogg de uma mesma gravação (mesmo prefixo base), junta as transcrições e salva em um único .txt.
        Mostra feedback visual do progresso na barra de status.
        """
        import re
        try:
            # Identifica o prefixo base da gravação usando regex
            nome_base = os.path.splitext(arquivo)[0]
            m = re.match(r'(.+_\d{8}_\d{6})_\d{2}$', nome_base)
            if m:
                prefixo_base = m.group(1)
            else:
                prefixo_base = nome_base
            # Busca todos os blocos .ogg da mesma gravação
            blocos_ogg = [f for f in os.listdir(self.output_dir) if f.startswith(os.path.basename(prefixo_base) + '_') and f.endswith('.ogg')]
            # Ordena os blocos pelo sufixo numérico
            blocos_ogg.sort(key=lambda x: int(os.path.splitext(x)[0].split('_')[-1]))
            if not blocos_ogg:
                self.master.after(0, lambda: messagebox.showwarning("Transcrição", "Nenhum bloco encontrado para transcrição."))
                return
            transcricoes = []
            total_blocos = len(blocos_ogg)
            for idx, bloco_ogg in enumerate(blocos_ogg):
                self.master.after(0, lambda idx=idx, total_blocos=total_blocos: self.status.config(text=f"Transcrevendo bloco {idx+1} de {total_blocos}..."))
                caminho_ogg = os.path.join(self.output_dir, bloco_ogg)
                nome_bloco = os.path.splitext(bloco_ogg)[0]
                caminho_wav = os.path.join(self.output_dir, f"{nome_bloco}.wav")
                # Converte OGG para WAV
                audio = AudioSegment.from_file(caminho_ogg, format="ogg")
                audio = audio.normalize()
                audio.export(caminho_wav, format="wav")
                recognizer = sr.Recognizer()
                try:
                    with sr.AudioFile(caminho_wav) as source:
                        audio_data = recognizer.record(source)
                        texto = recognizer.recognize_google(audio_data, language='pt-BR')
                        transcricoes.append(texto)
                except sr.UnknownValueError:
                    transcricoes.append(f'[Bloco {idx+1}: não foi possível entender o áudio]')
                except Exception as e:
                    transcricoes.append(f'[Bloco {idx+1}: erro ao transcrever: {e}]')
                # Remove arquivo temporário
                if os.path.exists(caminho_wav):
                    try:
                        os.remove(caminho_wav)
                    except Exception:
                        pass
            # Junta as transcrições
            texto_final = '\n'.join(transcricoes)
            caminho_txt = os.path.join(self.output_dir, f"{os.path.basename(prefixo_base)}.txt")
            with open(caminho_txt, 'w', encoding='utf-8') as f:
                f.write(texto_final)
            self.master.after(0, lambda: self.status.config(text="Transcrição finalizada com sucesso!", fg="#388E3C"))
            self.master.after(0, lambda: messagebox.showinfo("Transcrição", "Transcrição finalizada com sucesso!"))
        except Exception as e:
            self.master.after(0, lambda: self.status.config(text="", fg="#555"))
            self.master.after(0, lambda: messagebox.showerror("Erro na Transcrição", f"Erro ao transcrever: {e}"))
        finally:
            self.master.after(0, self.finalizar_transcricao_feedback)

    def finalizar_transcricao_feedback(self):
        self.status.config(text="", fg="#555")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.NORMAL)
        self.play_button.config(state=tk.NORMAL)
        self.delete_button.config(state=tk.NORMAL)
        self.open_folder_button.config(state=tk.NORMAL)
        self.delete_all_button.config(state=tk.NORMAL)
        self.refresh_button.config(state=tk.NORMAL)
        # Reabilita o clique na treeview
        self.tree.bind('<Button-1>', self.on_tree_click_detalhes)
        self.refresh_files()

    def abrir_detalhes_gravacao(self, arquivo):
        # arquivo agora é o prefixo base
        prefixo_base = arquivo
        # Busca o primeiro bloco para pegar data e transcrição
        files = [f for f in os.listdir(self.output_dir) if f.startswith(prefixo_base + '_') and f.endswith('.ogg')]
        files.sort()
        if not files:
            messagebox.showwarning("Detalhes", "Nenhum bloco encontrado para exibir detalhes.")
            return
        nome_base = prefixo_base
        caminho_ogg = os.path.join(self.output_dir, files[0])
        caminho_txt = os.path.join(self.output_dir, f"{os.path.basename(prefixo_base)}.txt")
        caminho_db = os.path.join(self.output_dir, f"{os.path.basename(prefixo_base)}_ia.json")
        data = datetime.fromtimestamp(os.path.getmtime(caminho_ogg)).strftime('%d/%m/%Y %H:%M:%S')
        # Lê a transcrição se existir
        if os.path.exists(caminho_txt):
            with open(caminho_txt, 'r', encoding='utf-8') as f:
                transcricao = f.read()
        else:
            transcricao = '(Nenhuma transcrição disponível)'
        # Lê IA se existir
        titulo_ia = '(A ser determinado por IA)'
        resumo_ia = '(A ser gerado por IA)'
        pontos_ia = '(A ser gerado por IA)'
        if os.path.exists(caminho_db):
            with open(caminho_db, 'r', encoding='utf-8') as f:
                try:
                    dados_ia = json.load(f)
                    titulo_ia = dados_ia.get('titulo', titulo_ia)
                    resumo_ia = dados_ia.get('resumo', resumo_ia)
                    pontos_ia = dados_ia.get('pontos', pontos_ia)
                    # Garante que pontos_ia seja uma lista
                    if isinstance(pontos_ia, list):
                        pontos_ia_lista = pontos_ia
                    else:
                        pontos_ia_lista = [str(pontos_ia)]
                except Exception:
                    pontos_ia_lista = [str(pontos_ia)]
        else:
            pontos_ia_lista = [str(pontos_ia)]
        # Cria a janela de detalhes
        detalhes = tk.Toplevel(self.master)
        detalhes.title(f"Detalhes da Gravação: {prefixo_base}")
        detalhes.geometry("780x650")  # 30% maior que 600x500
        detalhes.configure(bg="#f7f7f7")
        # Data
        tk.Label(detalhes, text=f"Data/Hora: {data}", font=("Arial", 11, "bold"), bg="#f7f7f7").pack(anchor='w', padx=16, pady=(16, 4))
        # Título (IA)
        tk.Label(detalhes, text="Título:", font=("Arial", 11, "bold"), bg="#f7f7f7").pack(anchor='w', padx=16, pady=(8, 0))
        self.titulo_var = tk.StringVar(value=titulo_ia)
        tk.Entry(detalhes, textvariable=self.titulo_var, font=("Arial", 11), width=60, state='readonly').pack(anchor='w', padx=16, pady=(0, 8))
        # Transcrição
        tk.Label(detalhes, text="Transcrição:", font=("Arial", 11, "bold"), bg="#f7f7f7").pack(anchor='w', padx=16, pady=(8, 0))
        txt_transc = tk.Text(detalhes, font=("Arial", 10), height=10, wrap='word')
        txt_transc.pack(fill='both', expand=False, padx=16, pady=(0, 8))
        txt_transc.insert('1.0', transcricao)
        txt_transc.config(state='disabled')
        # Resumo (IA) como textarea
        tk.Label(detalhes, text="Resumo:", font=("Arial", 11, "bold"), bg="#f7f7f7").pack(anchor='w', padx=16, pady=(8, 0))
        txt_resumo = tk.Text(detalhes, font=("Arial", 10), height=6, wrap='word')
        txt_resumo.pack(fill='both', expand=False, padx=16, pady=(0, 8))
        txt_resumo.insert('1.0', resumo_ia)
        txt_resumo.config(state='disabled')
        # Principais pontos (IA) como lista
        tk.Label(detalhes, text="Principais Pontos:", font=("Arial", 11, "bold"), bg="#f7f7f7").pack(anchor='w', padx=16, pady=(8, 0))
        txt_pontos = tk.Text(detalhes, font=("Arial", 10), height=8, wrap='word')
        txt_pontos.pack(fill='both', expand=False, padx=16, pady=(0, 16))
        txt_pontos.insert('1.0', '\n'.join(f'- {item}' for item in pontos_ia_lista))
        txt_pontos.config(state='disabled')

    def transcrever_selecionado(self):
        prefixo_base = self.get_selected_prefixo_base()
        if not prefixo_base:
            return
        # Busca um dos arquivos .ogg para passar para transcrever_audio
        files = [f for f in os.listdir(self.output_dir) if f.startswith(prefixo_base + '_') and f.endswith('.ogg')]
        if not files:
            messagebox.showwarning("Transcrição", "Nenhum bloco encontrado para transcrição.")
            return
        self.iniciar_transcricao_thread(files[0])

    def aplicar_ia_selecionado(self):
        prefixo_base = self.get_selected_prefixo_base()
        if not prefixo_base:
            return
        files = [f for f in os.listdir(self.output_dir) if f.startswith(prefixo_base + '_') and f.endswith('.ogg')]
        if not files:
            messagebox.showwarning("IA", "Nenhum bloco encontrado para aplicar IA.")
            return
        self.status.config(text="Processando IA...", fg="#1976D2")
        self.ia_button.config(state=tk.DISABLED)
        t = threading.Thread(target=self.processar_ia_gemini, args=(files[0],), daemon=True)
        t.start()

    def processar_ia_gemini(self, arquivo):
        import re
        try:
            nome_base = os.path.splitext(arquivo)[0]
            m = re.match(r'(.+_\d{8}_\d{6})_\d{2}$', nome_base)
            if m:
                prefixo_base = m.group(1)
            else:
                prefixo_base = nome_base
            caminho_txt = os.path.join(self.output_dir, f"{os.path.basename(prefixo_base)}.txt")
            caminho_db = os.path.join(self.output_dir, f"{os.path.basename(prefixo_base)}_ia.json")
            # Lê a transcrição
            if not os.path.exists(caminho_txt):
                self.master.after(0, lambda: messagebox.showwarning("IA", "Transcrição não encontrada para esta gravação."))
                return
            with open(caminho_txt, 'r', encoding='utf-8') as f:
                transcricao = f.read()
            # Monta o prompt pedindo JSON puro, sem markdown
            prompt = (
                "Você receberá a transcrição de uma reunião em português do Brasil. "
                "Gere um título objetivo para a reunião, um resumo de até 5 linhas e elenque os principais pontos discutidos (em tópicos).\n"
                "Retorne a resposta exclusivamente no seguinte formato JSON, sem comentários, sem blocos de código markdown (como ```json), sem texto extra antes ou depois, apenas o JSON puro:\n"
                '{\n  "titulo": "...",\n  "resumo": "...",\n  "pontos": [\n    "...",\n    "..."\n  ]\n}\n'
                "Transcrição:\n" + transcricao
            )
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = model.generate_content(prompt)
            resposta = response.text.strip()
            # Limpa blocos de markdown se vierem
            resposta_limpa = re.sub(r"^```[a-zA-Z]*\n?|```$", "", resposta, flags=re.MULTILINE).strip()
            # Tenta fazer o parser do JSON retornado
            try:
                dados_ia = json.loads(resposta_limpa)
                titulo = dados_ia.get('titulo', '')
                resumo = dados_ia.get('resumo', '')
                pontos = dados_ia.get('pontos', [])
                if isinstance(pontos, list):
                    pontos_str = '\n'.join(pontos)
                else:
                    pontos_str = str(pontos)
            except Exception as e:
                self.master.after(0, lambda: messagebox.showerror("Erro IA", f"A resposta da IA não está em formato JSON válido.\n\nResposta:\n{resposta}"))
                return
            # Salva no banco de dados json
            with open(caminho_db, 'w', encoding='utf-8') as f:
                json.dump({"titulo": titulo, "resumo": resumo, "pontos": pontos}, f, ensure_ascii=False, indent=2)
            # Atualiza a grid e modal
            self.master.after(0, lambda: self.atualizar_titulo_grid(os.path.basename(prefixo_base), titulo))
            self.master.after(0, lambda: messagebox.showinfo("IA", "Resumo, título e pontos principais gerados com sucesso!"))
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Erro IA", f"Erro ao processar IA: {e}"))
        finally:
            self.master.after(0, lambda: self.ia_button.config(state=tk.NORMAL))
            self.master.after(0, lambda: self.status.config(text="", fg="#555"))

    def atualizar_titulo_grid(self, arquivo, titulo):
        # Atualiza o título na grid para a linha correspondente ao arquivo
        for row in self.tree.get_children():
            values = self.tree.item(row)['values']
            if values[1] == arquivo:
                self.tree.set(row, 'titulo', titulo)
                break

def dividir_audio_em_blocos(caminho_wav, duracao_bloco_seg=240, min_silencio_ms=700, silencio_thresh_db=-40):
    """
    Divide um arquivo .wav em blocos de até 'duracao_bloco_seg' segundos, cortando preferencialmente nos silêncios.
    Se o áudio for menor ou igual ao limite, retorna um único bloco.
    Adiciona logs para depuração.
    """
    audio = AudioSegment.from_wav(caminho_wav)
    duracao_total = len(audio) / 1000  # em segundos
    blocos = []
    print(f"[DEBUG] Duração total do áudio: {duracao_total:.2f} segundos")
    if duracao_total <= duracao_bloco_seg:
        bloco_path = os.path.join(tempfile.gettempdir(), f"bloco_{os.path.basename(caminho_wav)}_0.wav")
        audio.export(bloco_path, format="wav")
        print(f"[DEBUG] Bloco único: início=0.00s, fim={duracao_total:.2f}s, duração={duracao_total:.2f}s, sem cortes")
        blocos.append(bloco_path)
        print(f"[DEBUG] Total de blocos gerados: 1")
        return blocos
    inicio = 0
    bloco_idx = 0
    while inicio < len(audio):
        fim = min(inicio + duracao_bloco_seg * 1000, len(audio))
        segmento = audio[inicio:fim]
        # Tenta encontrar silêncio próximo ao final do bloco
        sil = silence.detect_silence(segmento, min_silence_len=min_silencio_ms, silence_thresh=silencio_thresh_db)
        corte = None
        for s in reversed(sil):
            # Procura silêncio nos últimos 30 segundos do bloco
            if s[1] > len(segmento) - 30000:
                corte = s[1]
                break
        if corte:
            bloco = segmento[:corte]
            proximo_inicio = inicio + corte
            motivo = f"corte por silêncio em {corte/1000:.2f}s do bloco"
        else:
            bloco = segmento
            proximo_inicio = fim
            motivo = "corte por tempo máximo"
        bloco_path = os.path.join(tempfile.gettempdir(), f"bloco_{os.path.basename(caminho_wav)}_{bloco_idx}.wav")
        bloco.export(bloco_path, format="wav")
        print(f"[DEBUG] Bloco {bloco_idx+1}: início={inicio/1000:.2f}s, fim={proximo_inicio/1000:.2f}s, duração={(proximo_inicio-inicio)/1000:.2f}s, {motivo}")
        blocos.append(bloco_path)
        inicio = proximo_inicio
        bloco_idx += 1
    print(f"[DEBUG] Total de blocos gerados: {len(blocos)}")
    return blocos

def main():
    output_dir = "output"
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename_mic = os.path.join(output_dir, f"mic_{timestamp}.wav")
    os.makedirs(output_dir, exist_ok=True)
    mic_device = get_default_source()
    run_pipeline(mic_device, filename_mic)

if __name__ == "__main__":
    root = tk.Tk()
    app = RecorderGUI(root)
    root.mainloop() 