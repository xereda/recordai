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
import getpass
import base64
from google.genai import types
from markdown import markdown as md2html
from tkinterweb import HtmlFrame

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
        master.geometry("1120x600")
        master.resizable(False, False)
        master.configure(bg="#f7f7f7")

        # --- Estilo global para Treeview ---
        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 12))
        style.configure("Treeview.Heading", font=("Arial", 13, "bold"))

        self.is_recording = False
        self.pipeline = None
        self.loop = None
        self.filename = None
        self.thread = None
        self.output_dir = "output"

        # --- Layout ---
        self.label = tk.Label(master, text="Grave e gerencie os áudios da saída do sistema.", font=("Arial", 12, "bold"), bg="#f7f7f7")
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
        self.start_button = tk.Button(btn_frame, text="Iniciar Gravação", command=self.start_recording, width=15, height=1, bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), relief=tk.RAISED, bd=2)
        self.start_button.grid(row=0, column=0, padx=8, pady=2, ipady=2)
        self.stop_button = tk.Button(btn_frame, text="Encerrar Gravação", command=self.stop_recording, width=15, height=1, bg="#F44336", fg="white", font=("Arial", 12, "bold"), state=tk.DISABLED, relief=tk.RAISED, bd=2)
        self.stop_button.grid(row=0, column=1, padx=8, pady=2, ipady=2)
        self.refresh_button = tk.Button(btn_frame, text="Atualizar Lista", command=self.refresh_files, width=12, height=1, font=("Arial", 12), relief=tk.RAISED, bd=2)
        self.refresh_button.grid(row=0, column=2, padx=8, pady=2, ipady=2)

        # --- Tabela de arquivos ---
        self.tree = ttk.Treeview(master, columns=("datahora", "titulo", "duracao", "detalhes", "pasta"), show="headings", height=12)
        self.tree.heading("datahora", text="Data/Hora")
        self.tree.heading("titulo", text="Título")
        self.tree.heading("duracao", text="Duração")
        self.tree.heading("detalhes", text="Detalhes")
        self.tree.column("datahora", width=160)
        self.tree.column("titulo", width=260)
        self.tree.column("duracao", width=80, anchor="center")
        self.tree.column("detalhes", width=100, anchor="center")
        self.tree.column("pasta", width=0, stretch=False, minwidth=0)
        self.tree.pack(pady=4, fill='x')
        self.tree.bind('<Double-1>', self.open_file)
        self.tree.bind('<Button-1>', self.on_tree_click_detalhes)
        self.tree.bind('<ButtonRelease-1>', self.on_tree_select_anywhere)

        # --- Botões de ação (logo abaixo da grid) ---
        action_frame = tk.Frame(master, bg="#f7f7f7")
        action_frame.pack(pady=2, fill='x')
        self.play_button = tk.Button(action_frame, text="Reproduzir", command=self.play_file, width=12, height=1, font=("Arial", 12), relief=tk.RAISED, bd=2)
        self.play_button.grid(row=0, column=0, padx=6, pady=2, ipady=2)
        self.delete_button = tk.Button(action_frame, text="Excluir", command=self.delete_file, width=12, height=1, font=("Arial", 12), relief=tk.RAISED, bd=2)
        self.delete_button.grid(row=0, column=1, padx=6, pady=2, ipady=2)
        self.open_folder_button = tk.Button(action_frame, text="Abrir Pasta", command=self.open_folder, width=12, height=1, font=("Arial", 12), relief=tk.RAISED, bd=2)
        self.open_folder_button.grid(row=0, column=2, padx=6, pady=2, ipady=2)
        self.delete_all_button = tk.Button(action_frame, text="Excluir Todos", command=self.delete_all_files, width=12, height=1, font=("Arial", 12), relief=tk.RAISED, bd=2)
        self.delete_all_button.grid(row=0, column=3, padx=6, pady=2, ipady=2)
        self.transcrever_button = tk.Button(action_frame, text="Transcrever", command=self.transcrever_selecionado, width=12, height=1, font=("Arial", 12), relief=tk.RAISED, bd=2, bg="#1976D2", fg="white")
        self.transcrever_button.grid(row=0, column=4, padx=6, pady=2, ipady=2)
        self.ia_button = tk.Button(action_frame, text="Aplicar IA", command=self.aplicar_ia_selecionado, width=12, height=1, font=("Arial", 12), relief=tk.RAISED, bd=2, bg="#388E3C", fg="white")
        self.ia_button.grid(row=0, column=5, padx=6, pady=2, ipady=2)

        self.status = tk.Label(master, text="", font=("Arial", 12), bg="#f7f7f7", fg="#555")
        self.status.pack(pady=(5, 0))

        # Tooltip para o botão de iniciar gravação
        self.start_btn_tooltip = None
        self.update_start_button_state()

        # --- Tempo decorrido ---
        self.tempo_decorrido_var = tk.StringVar(value="00:00:00")
        self.tempo_decorrido_label = tk.Label(master, textvariable=self.tempo_decorrido_var, font=("Arial", 14, "bold"), bg="#f7f7f7", fg="#1976D2")
        # O tempo decorrido só aparece durante a gravação
        # Não faz pack aqui, só quando iniciar gravação

        self.refresh_files()
        # Atalho local para print: Ctrl+Alt+M
        self.master.bind('<Control-Alt-m>', lambda event: self.capturar_print_monitor_mouse())
        # Listener global (pynput)
        self._start_pynput_hotkey_listener()

    def get_output_dir_and_prefix(self):
        # Gera o timestamp no padrão AAAAMMDDHHMMSS
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        output_dir = os.path.join(self.output_dir, timestamp)
        os.makedirs(output_dir, exist_ok=True)
        try:
            ajustar_permissao_usuario(output_dir)
        except Exception as e:
            print(f"[PERMISSAO] Falha ao ajustar permissão do diretório: {e}")
        prefix = f'gravacao'
        return output_dir, prefix, timestamp

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
        self.gravacao_dir, self.prefix, self.gravacao_timestamp = self.get_output_dir_and_prefix()
        self.filename_base = os.path.join(self.gravacao_dir, f"{self.prefix}")
        self.mic_device = self.get_default_source()
        self.monitor_device = self.get_default_sink_monitor()
        self.use_mic = self.var_mic.get()
        self.use_out = self.var_out.get()
        self.current_block = 1
        self._stop_recording_flag = threading.Event()
        self._gravacao_start_time = time.time()
        self._update_tempo_decorrido()
        # Mostra o tempo decorrido
        if not self.tempo_decorrido_label.winfo_ismapped():
            self.tempo_decorrido_label.pack(pady=(0, 8))
        self.thread = threading.Thread(target=self._record_in_blocks, daemon=True)
        self.thread.start()

    def _update_tempo_decorrido(self):
        if self.is_recording and self._gravacao_start_time:
            elapsed = int(time.time() - self._gravacao_start_time)
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            self.tempo_decorrido_var.set(f"{h:02d}:{m:02d}:{s:02d}")
            self._tempo_decorrido_job = self.master.after(1000, self._update_tempo_decorrido)
        else:
            self.tempo_decorrido_var.set("00:00:00")
            if self._tempo_decorrido_job:
                self.master.after_cancel(self._tempo_decorrido_job)
                self._tempo_decorrido_job = None

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
            try:
                ajustar_permissao_usuario(filename)
            except Exception as e:
                print(f"[PERMISSAO] Falha ao ajustar permissão do bloco: {e}")
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
        # Capture o tempo ANTES de parar a gravação
        tempo_total = self.tempo_decorrido_var.get()
        self.is_recording = False
        self._stop_recording_flag.set()
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status.config(text="Gravação finalizada!", fg="#388E3C")
        self._update_tempo_decorrido()
        # Salva o tempo total de gravação
        meta_path = os.path.join(self.gravacao_dir, 'gravacao_meta.json')
        try:
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump({"duracao": tempo_total}, f, ensure_ascii=False, indent=2)
            ajustar_permissao_usuario(meta_path)
        except Exception as e:
            print(f"[META] Falha ao salvar tempo total: {e}")
        # Esconde o tempo decorrido
        if self.tempo_decorrido_label.winfo_ismapped():
            self.tempo_decorrido_label.pack_forget()
        # Aguarda 1 segundo antes de atualizar a grid
        self.master.after(1000, self.refresh_files)
        messagebox.showinfo("Gravação finalizada", f"Arquivos salvos em blocos de até {RECORD_BLOCK_SECONDS} segundos.")

    def refresh_files(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        if not os.path.exists(self.output_dir):
            return
        gravacao_dirs = [d for d in os.listdir(self.output_dir) if os.path.isdir(os.path.join(self.output_dir, d))]
        gravacao_dirs.sort(reverse=True)
        for grav_dir in gravacao_dirs:
            full_dir = os.path.join(self.output_dir, grav_dir)
            blocos = [f for f in os.listdir(full_dir) if f.endswith('.ogg')]
            blocos.sort()
            if not blocos:
                continue
            playlist_path = os.path.join(full_dir, 'playlist.m3u')
            if not os.path.exists(playlist_path):
                with open(playlist_path, 'w', encoding='utf-8') as m3u:
                    m3u.write('#EXTM3U\n')
                    for bloco in blocos:
                        m3u.write(f'{os.path.abspath(os.path.join(full_dir, bloco))}\n')
                try:
                    ajustar_permissao_usuario(playlist_path)
                except Exception as e:
                    print(f"[PERMISSAO] Falha ao ajustar permissão do playlist: {e}")
            try:
                path_primeiro_bloco = os.path.join(full_dir, blocos[0])
                dt = datetime.fromtimestamp(os.path.getmtime(path_primeiro_bloco)).strftime('%d/%m/%Y %H:%M:%S')
            except Exception:
                dt = ''
            # Lê a duração do meta.json, se existir
            meta_path = os.path.join(full_dir, 'gravacao_meta.json')
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                        duracao_str = meta.get('duracao', '?')
                except Exception:
                    duracao_str = '?'
            else:
                duracao_str = '?'
            caminho_db = os.path.join(full_dir, f"gravacao_ia.json")
            titulo = ""
            if os.path.exists(caminho_db):
                try:
                    with open(caminho_db, 'r', encoding='utf-8') as j:
                        dados_ia = json.load(j)
                        titulo = dados_ia.get('titulo', "")
                except Exception:
                    titulo = ""
            self.tree.insert('', 'end', values=(dt, titulo, duracao_str, 'detalhes', grav_dir))
        # Seleciona automaticamente a primeira linha, se houver
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])

    def get_selected_gravacao_dir(self):
        sel = self.tree.selection()
        print(f'[DEBUG] get_selected_gravacao_dir - selection: {sel}')
        if not sel:
            messagebox.showwarning("Seleção", "Selecione um registro na lista.")
            return None
        # Agora pega o nome da pasta da coluna oculta
        dt, titulo, duracao, detalhes, pasta = self.tree.item(sel[0])['values']
        print(f'[DEBUG] get_selected_gravacao_dir - pasta selecionada: {pasta}')
        gravacao_dir = os.path.join(self.output_dir, str(pasta))
        if os.path.isdir(gravacao_dir):
            print(f'[DEBUG] get_selected_gravacao_dir - encontrou diretório: {gravacao_dir}')
            return gravacao_dir
        print('[DEBUG] get_selected_gravacao_dir - não encontrou diretório correspondente')
        return None

    def play_file(self):
        print('[DEBUG] play_file chamado')
        gravacao_dir = self.get_selected_gravacao_dir()
        print(f'[DEBUG] play_file - gravacao_dir: {gravacao_dir}')
        if not gravacao_dir:
            return
        playlist_path = os.path.join(gravacao_dir, 'playlist.m3u')
        print(f'[DEBUG] play_file - playlist_path: {playlist_path}')
        if not os.path.exists(playlist_path):
            messagebox.showwarning("Reprodução", "Playlist não encontrada para esta gravação.")
            return
        path = os.path.abspath(playlist_path)
        print(f'[DEBUG] play_file - abrindo: {path}')
        if platform.system() == "Linux":
            subprocess.Popen(["xdg-open", path])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        elif platform.system() == "Windows":
            os.startfile(path)
        else:
            webbrowser.open(path)

    def delete_file(self):
        print('[DEBUG] delete_file chamado')
        gravacao_dir = self.get_selected_gravacao_dir()
        print(f'[DEBUG] delete_file - gravacao_dir: {gravacao_dir}')
        if not gravacao_dir:
            return
        import shutil
        if not os.path.exists(gravacao_dir):
            messagebox.showinfo("Excluir", "Nenhum arquivo para excluir.")
            return
        if messagebox.askyesno("Excluir", "Deseja realmente excluir toda a gravação selecionada? (Todos os arquivos dessa gravação serão removidos)"):
            try:
                shutil.rmtree(gravacao_dir)
                self.refresh_files()
                self.status.config(text="Gravação excluída com sucesso.", fg="#F44336")
            except Exception as e:
                self.status.config(text=f"Erro ao excluir gravação: {e}", fg="#F44336")
                messagebox.showerror("Erro ao excluir", f"Erro ao excluir a gravação: {e}")

    def open_file(self, event=None):
        gravacao_dir = self.get_selected_gravacao_dir()
        if not gravacao_dir:
            return
        playlist_path = os.path.join(gravacao_dir, 'playlist.m3u')
        if not os.path.exists(playlist_path):
            messagebox.showwarning("Reprodução", "Playlist não encontrada para esta gravação.")
            return
        path = os.path.abspath(playlist_path)
        if platform.system() == "Linux":
            subprocess.Popen(["xdg-open", path])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        elif platform.system() == "Windows":
            os.startfile(path)
        else:
            webbrowser.open(path)

    def open_folder(self):
        print('[DEBUG] open_folder chamado')
        gravacao_dir = self.get_selected_gravacao_dir()
        print(f'[DEBUG] open_folder - gravacao_dir: {gravacao_dir}')
        if not gravacao_dir:
            return
        folder = os.path.abspath(gravacao_dir)
        print(f'[DEBUG] open_folder - abrindo: {folder}')
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
        gravacao_dirs = [os.path.join(self.output_dir, d) for d in os.listdir(self.output_dir)]
        gravacao_dirs = [d for d in gravacao_dirs if os.path.isdir(d) or os.path.isfile(d)]
        if not gravacao_dirs:
            messagebox.showinfo("Excluir Todos", "Nenhum arquivo para excluir.")
            return
        if messagebox.askyesno("Excluir Todos", f"Deseja realmente excluir TODO o conteúdo da pasta de gravações? (Isso removerá todas as gravações)"):
            erros = 0
            for d in gravacao_dirs:
                try:
                    if os.path.isdir(d):
                        import shutil
                        shutil.rmtree(d)
                    else:
                        os.remove(d)
                except Exception:
                    erros += 1
            # Recria a pasta output se necessário
            os.makedirs(self.output_dir, exist_ok=True)
            self.refresh_files()
            if erros:
                self.status.config(text=f"Conteúdo excluído com {erros} erros.", fg="#F44336")
            else:
                self.status.config(text=f"Todo o conteúdo de gravações foi excluído.", fg="#F44336")

    def on_tree_click_detalhes(self, event):
        print('[DEBUG] on_tree_click_detalhes chamado')
        region = self.tree.identify('region', event.x, event.y)
        print(f'[DEBUG] on_tree_click_detalhes - region: {region}')
        if region != 'cell':
            return
        row_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        print(f'[DEBUG] on_tree_click_detalhes - row_id: {row_id}, col: {col}')
        if not row_id:
            return
        self.tree.selection_set(row_id)
        colunas = self.tree['columns']
        try:
            idx_detalhes = list(colunas).index('detalhes') + 1
        except ValueError:
            return
        print(f'[DEBUG] on_tree_click_detalhes - idx_detalhes: {idx_detalhes}')
        if col != f'#{idx_detalhes}':
            return
        gravacao_dir = self.get_selected_gravacao_dir()
        print(f'[DEBUG] on_tree_click_detalhes - gravacao_dir: {gravacao_dir}')
        if not gravacao_dir:
            return
        self.abrir_detalhes_gravacao(gravacao_dir)

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

    def transcrever_audio(self, gravacao_dir):
        """
        Transcreve todos os blocos .ogg de uma gravação (subpasta), junta as transcrições e salva em um único .txt.
        Mostra feedback visual do progresso na barra de status.
        """
        try:
            blocos_ogg = [f for f in os.listdir(gravacao_dir) if f.endswith('.ogg')]
            blocos_ogg.sort(key=lambda x: int(os.path.splitext(x)[0].split('_')[-1]))
            if not blocos_ogg:
                self.master.after(0, lambda: messagebox.showwarning("Transcrição", "Nenhum bloco encontrado para transcrição."))
                return
            transcricoes = []
            total_blocos = len(blocos_ogg)
            for idx, bloco_ogg in enumerate(blocos_ogg):
                self.master.after(0, lambda idx=idx, total_blocos=total_blocos: self.status.config(text=f"Transcrevendo bloco {idx+1} de {total_blocos}..."))
                caminho_ogg = os.path.join(gravacao_dir, bloco_ogg)
                nome_bloco = os.path.splitext(bloco_ogg)[0]
                caminho_wav = os.path.join(gravacao_dir, f"{nome_bloco}.wav")
                # Converte OGG para WAV
                audio = AudioSegment.from_file(caminho_ogg, format="ogg")
                audio = audio.normalize()
                audio.export(caminho_wav, format="wav")
                try:
                    ajustar_permissao_usuario(caminho_wav)
                except Exception as e:
                    print(f"[PERMISSAO] Falha ao ajustar permissão do wav: {e}")
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
            caminho_txt = os.path.join(gravacao_dir, 'gravacao.txt')
            with open(caminho_txt, 'w', encoding='utf-8') as f:
                f.write(texto_final)
            try:
                ajustar_permissao_usuario(caminho_txt)
            except Exception as e:
                print(f"[PERMISSAO] Falha ao ajustar permissão do txt: {e}")
            self.master.after(0, lambda: self.status.config(text="Transcrição finalizada com sucesso!", fg="#388E3C"))
            self.master.after(0, lambda: messagebox.showinfo("Transcrição", "Transcrição finalizada com sucesso!"))
        except Exception as e:
            print(f"[TRANSCRIÇÃO] Erro ao transcrever: {e}")
            self.master.after(0, lambda err=e: messagebox.showerror("Erro na Transcrição", f"Erro ao transcrever: {err}"))
            self.master.after(0, lambda: self.status.config(text="", fg="#555"))
        finally:
            self.master.after(0, self.finalizar_transcricao_feedback)
            self.master.after(0, lambda: self.tree.bind('<Button-1>', self.on_tree_click_detalhes))

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

    def abrir_detalhes_gravacao(self, gravacao_dir):
        import tkinter as tk
        from tkinter import ttk
        import os, json
        from datetime import datetime
        from markdown import markdown as md2html
        from tkinterweb import HtmlFrame
        files = [f for f in os.listdir(gravacao_dir) if f.endswith('.ogg')]
        files.sort()
        if not files:
            messagebox.showwarning("Detalhes", "Nenhum bloco encontrado para exibir detalhes.")
            return
        caminho_ogg = os.path.join(gravacao_dir, files[0])
        caminho_txt = os.path.join(gravacao_dir, 'gravacao.txt')
        caminho_db = os.path.join(gravacao_dir, 'gravacao_ia.json')
        data = datetime.fromtimestamp(os.path.getmtime(caminho_ogg)).strftime('%d/%m/%Y %H:%M:%S')
        if os.path.exists(caminho_txt):
            with open(caminho_txt, 'r', encoding='utf-8') as f:
                transcricao = f.read()
        else:
            transcricao = '(Nenhuma transcrição disponível)'
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
                    if isinstance(pontos_ia, list):
                        pontos_ia_lista = pontos_ia
                    else:
                        pontos_ia_lista = [str(pontos_ia)]
                except Exception:
                    pontos_ia_lista = [str(pontos_ia)]
        else:
            pontos_ia_lista = [str(pontos_ia)]
        detalhes = tk.Toplevel(self.master)
        detalhes.title(f"Detalhes da Gravação: {os.path.basename(gravacao_dir)}")
        # Maximizar multiplataforma: apenas ajusta geometry para ocupar toda a tela, mantendo barra de título
        largura = detalhes.winfo_screenwidth()
        altura = detalhes.winfo_screenheight()
        detalhes.geometry(f"{largura}x{altura}+0+0")
        detalhes.configure(bg="#f7f7f7")
        # Não usar state('zoomed') nem fullscreen
        PAD = 24
        BG_CARD = "#e3eafc"
        BG_MODAL = "#f7f7f7"
        FG_TITLE = "#222"
        # Frame principal horizontal
        main_frame = tk.Frame(detalhes, bg=BG_MODAL)
        main_frame.pack(fill='both', expand=True)
        left_frame = tk.Frame(main_frame, bg=BG_MODAL)
        left_frame.pack(side='left', fill='both', expand=True)
        right_frame = tk.Frame(main_frame, bg=BG_MODAL, width=detalhes.winfo_screenwidth()//2)
        right_frame.pack(side='right', fill='both', expand=True)
        # --- PARTE ESQUERDA: dividir em superior (info) e inferior (thumbs) ---
        left_frame.grid_rowconfigure(0, weight=3)
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)
        # Superior: info
        card_info = tk.Frame(left_frame, bg=BG_CARD, bd=0, highlightbackground="#b3c6e6", highlightthickness=1)
        card_info.grid(row=0, column=0, sticky='nsew', padx=PAD, pady=(PAD*2, 8))
        tk.Label(card_info, text=f"Data/Hora: {data}", font=("Arial", 12, "bold"), bg=BG_CARD).pack(anchor='w', padx=16, pady=(12, 2))
        tk.Label(card_info, text="Título:", font=("Arial", 11, "bold"), bg=BG_CARD).pack(anchor='w', padx=16, pady=(8, 0))
        titulo_var = tk.StringVar(value=titulo_ia)
        tk.Entry(card_info, textvariable=titulo_var, font=("Arial", 12), width=60, state='readonly').pack(anchor='w', padx=16, pady=(0, 8))
        tk.Label(card_info, text="Transcrição:", font=("Arial", 11, "bold"), bg=BG_CARD).pack(anchor='w', padx=16, pady=(8, 0))
        txt_transc = tk.Text(card_info, font=("Arial", 12), height=10, wrap='word')
        txt_transc.pack(fill='both', expand=False, padx=16, pady=(0, 8))
        txt_transc.insert('1.0', transcricao)
        txt_transc.config(state='disabled')
        tk.Label(card_info, text="Resumo:", font=("Arial", 11, "bold"), bg=BG_CARD).pack(anchor='w', padx=16, pady=(8, 0))
        txt_resumo = tk.Text(card_info, font=("Arial", 12), height=6, wrap='word')
        txt_resumo.pack(fill='both', expand=False, padx=16, pady=(0, 8))
        txt_resumo.insert('1.0', resumo_ia)
        txt_resumo.config(state='disabled')
        tk.Label(card_info, text="Principais Pontos:", font=("Arial", 11, "bold"), bg=BG_CARD).pack(anchor='w', padx=16, pady=(8, 0))
        txt_pontos = tk.Text(card_info, font=("Arial", 12), height=8, wrap='word')
        txt_pontos.pack(fill='both', expand=False, padx=16, pady=(0, 16))
        txt_pontos.insert('1.0', '\n'.join(f'- {item}' for item in pontos_ia_lista))
        txt_pontos.config(state='disabled')
        # Inferior: painel de thumbs com rolagem
        thumbs_frame = tk.Frame(left_frame, bg=BG_MODAL)
        thumbs_frame.grid(row=1, column=0, sticky='nsew', padx=PAD, pady=(0, PAD))
        tk.Label(thumbs_frame, text="Prints:", font=("Arial", 13, "bold"), bg=BG_MODAL, anchor='w').pack(anchor='w', padx=2, pady=(0, 2))
        canvas = tk.Canvas(thumbs_frame, bg=BG_MODAL, highlightthickness=0)
        scrollbar = tk.Scrollbar(thumbs_frame, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG_MODAL)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        # Suporte ao scroll do mouse
        def _on_mousewheel(event):
            if event.num == 5 or event.delta == -120:
                canvas.yview_scroll(1, "units")
            elif event.num == 4 or event.delta == 120:
                canvas.yview_scroll(-1, "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)  # Windows/macOS
        canvas.bind_all("<Button-4>", _on_mousewheel)    # Linux scroll up
        canvas.bind_all("<Button-5>", _on_mousewheel)    # Linux scroll down
        # Listar thumbs
        from glob import glob
        from PIL import Image, ImageTk
        prints = glob(os.path.join(gravacao_dir, 'print_*.png'))
        prints = sorted(prints, key=lambda x: os.path.getctime(x), reverse=True)
        self._detalhes_imgs_refs = []
        max_per_row = 3
        for idx, img_path in enumerate(prints):
            img = Image.open(img_path)
            img.thumbnail((180, 120))
            tk_img = ImageTk.PhotoImage(img)
            self._detalhes_imgs_refs.append(tk_img)
            def abrir_full(img_path=img_path):
                if not hasattr(self, '_modal_print_ref') or self._modal_print_ref is None or not self._modal_print_ref.winfo_exists():
                    self._modal_print_ref = tk.Toplevel(self.master)
                self._abrir_modal_print(img_path, reuse_modal=self._modal_print_ref)
                self._modal_print_ref.deiconify()
                self._modal_print_ref.lift()
            frame_thumb = tk.Frame(scroll_frame, bg=BG_MODAL, bd=1, relief="solid")
            btn = tk.Button(frame_thumb, image=tk_img, command=abrir_full, bg=BG_MODAL, relief="flat")
            btn.pack()
            tk.Label(frame_thumb, text=os.path.basename(img_path), font=("Arial", 9), bg=BG_MODAL).pack()
            row = idx // max_per_row
            col = idx % max_per_row
            frame_thumb.grid(row=row, column=col, padx=10, pady=10)
        if not prints:
            tk.Label(scroll_frame, text="Nenhum print capturado ainda.", font=("Arial", 12, "italic"), bg=BG_MODAL, fg="#888").pack(pady=30)
        # --- PARTE DIREITA: pergunta IA ---
        frame_pergunta = tk.Frame(right_frame, bg=BG_MODAL)
        frame_pergunta.pack(fill='x', padx=PAD, pady=(PAD*2, 10), anchor='n')
        tk.Label(frame_pergunta, text="Pergunte algo sobre esta gravação:", font=("Arial", 13, "bold"), bg=BG_MODAL).pack(anchor='w', padx=2, pady=(0, 2))
        pergunta_var = tk.StringVar()
        entry_pergunta = tk.Entry(frame_pergunta, textvariable=pergunta_var, font=("Arial", 12), width=40)
        entry_pergunta.pack(side='left', padx=(0, 8), pady=2, fill='x', expand=True)
        btn_perguntar = tk.Button(frame_pergunta, text="Perguntar", font=("Arial", 11, "bold"), bg="#388E3C", fg="white")
        btn_perguntar.pack(side='left', ipadx=10, ipady=2)
        entry_pergunta.bind('<Return>', lambda e: btn_perguntar.invoke())
        # Resposta IA (markdown)
        tk.Label(right_frame, text="Resposta da IA:", font=("Arial", 13, "bold"), bg=BG_MODAL, anchor='w').pack(anchor='w', padx=PAD, pady=(8, 0))
        card_resposta = tk.Frame(right_frame, bg=BG_CARD, bd=0, highlightbackground="#b3c6e6", highlightthickness=1)
        card_resposta.pack(fill='both', expand=True, padx=PAD, pady=(4, PAD))
        resposta_markdown = tk.StringVar(value="")
        def set_resposta_markdown(md):
            resposta_markdown.set(md)
            for widget in card_resposta.winfo_children():
                widget.destroy()
            html = md2html(md, extensions=['fenced_code', 'codehilite'])
            html = html.replace('<pre>', '<pre style="background:#f4f4f4;border:1px solid #b3c6e6;padding:8px;border-radius:6px;overflow-x:auto;font-family:monospace;font-size:13px;">')
            html = html.replace('<code>', '<code style="font-family:monospace;font-size:13px;">')
            html_frame = HtmlFrame(card_resposta, messages_enabled=False, vertical_scrollbar=True)
            html_frame.load_html(html)
            html_frame.pack(fill='both', expand=True, padx=18, pady=(12, 0))
            # Botão copiar resposta
            btn_frame_resposta = tk.Frame(card_resposta, bg=BG_CARD)
            btn_frame_resposta.pack(fill='x', padx=18, pady=(8, 10), anchor='s')
            def copiar_resposta():
                detalhes.clipboard_clear()
                detalhes.clipboard_append(md)
                btn_copiar_resp.config(text="Copiado!", bg="#a5d6a7")
                detalhes.after(2000, lambda: btn_copiar_resp.config(text="Copiar resposta", bg="#b3c6e6"))
            btn_copiar_resp = tk.Button(btn_frame_resposta, text="Copiar resposta", command=copiar_resposta, font=("Arial", 10), bg="#b3c6e6", relief=tk.RAISED)
            btn_copiar_resp.pack(side='left', padx=(0, 8), ipadx=8, ipady=2)
        set_resposta_markdown("")
        # Função para perguntar à IA e exibir resposta em markdown
        def perguntar_ia(transcricao_c=transcricao):
            pergunta = pergunta_var.get().strip()
            if not pergunta:
                set_resposta_markdown("Digite uma pergunta.")
                return
            btn_perguntar.config(state=tk.DISABLED)
            set_resposta_markdown("Consultando IA...")
            texto_base = transcricao_c
            def run_ia_pergunta():
                try:
                    import os
                    api_key = os.environ.get("GEMINI_API_KEY") or GEMINI_API_KEY
                    model = GEMINI_MODEL
                    genai.configure(api_key=api_key)
                    prompt = f"""Você receberá a transcrição de uma gravação de áudio. Use esse texto como contexto para responder a pergunta do usuário, sempre em português do Brasil. Seja objetivo e claro.\n\nTranscrição:\n{texto_base}\n\nPergunta do usuário:\n{pergunta}\n\nResponda de forma clara, objetiva e, se possível, cite trechos da transcrição que embasam sua resposta. Use markdown bem formatado."""
                    model = genai.GenerativeModel(GEMINI_MODEL)
                    response = model.generate_content(prompt)
                    resposta = response.text.strip()
                    self.master.after(0, lambda: set_resposta_markdown(resposta))
                except Exception as e:
                    msg_erro = str(e)
                    if len(msg_erro) > 400:
                        msg_erro = msg_erro[:400] + '\n... (mensagem truncada)'
                    self.master.after(0, lambda: set_resposta_markdown(f"Erro ao consultar IA: {msg_erro}"))
                finally:
                    self.master.after(0, lambda: btn_perguntar.config(state=tk.NORMAL))
            import threading
            threading.Thread(target=run_ia_pergunta, daemon=True).start()
        btn_perguntar.config(command=perguntar_ia)

    def transcrever_selecionado(self):
        print('[DEBUG] transcrever_selecionado chamado')
        gravacao_dir = self.get_selected_gravacao_dir()
        print(f'[DEBUG] transcrever_selecionado - gravacao_dir: {gravacao_dir}')
        if not gravacao_dir:
            return
        files = [f for f in os.listdir(gravacao_dir) if f.endswith('.ogg')]
        files.sort()
        print(f'[DEBUG] transcrever_selecionado - arquivos .ogg: {files}')
        if not files:
            messagebox.showwarning("Transcrição", "Nenhum bloco encontrado para transcrição.")
            return
        self.iniciar_transcricao_thread(gravacao_dir)

    def aplicar_ia_selecionado(self):
        print('[DEBUG] aplicar_ia_selecionado chamado')
        gravacao_dir = self.get_selected_gravacao_dir()
        print(f'[DEBUG] aplicar_ia_selecionado - gravacao_dir: {gravacao_dir}')
        if not gravacao_dir:
            return
        files = [f for f in os.listdir(gravacao_dir) if f.endswith('.ogg')]
        print(f'[DEBUG] aplicar_ia_selecionado - arquivos .ogg: {files}')
        if not files:
            messagebox.showwarning("IA", "Nenhum bloco encontrado para aplicar IA.")
            return
        self.status.config(text="Processando IA...", fg="#1976D2")
        self.ia_button.config(state=tk.DISABLED)
        t = threading.Thread(target=self.processar_ia_gemini, args=(gravacao_dir,), daemon=True)
        t.start()

    def processar_ia_gemini(self, gravacao_dir):
        try:
            caminho_txt = os.path.join(gravacao_dir, 'gravacao.txt')
            caminho_db = os.path.join(gravacao_dir, 'gravacao_ia.json')
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
            try:
                ajustar_permissao_usuario(caminho_db)
            except Exception as e:
                print(f"[PERMISSAO] Falha ao ajustar permissão do json: {e}")
            # Atualiza a grid e modal
            self.atualizar_titulo_grid(gravacao_dir, titulo)
            self.master.after(0, lambda: messagebox.showinfo("IA", "Resumo, título e pontos principais gerados com sucesso!"))
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Erro IA", f"Erro ao processar IA: {e}"))
        finally:
            self.master.after(0, lambda: self.ia_button.config(state=tk.NORMAL))
            self.master.after(0, lambda: self.status.config(text="", fg="#555"))
            self.master.after(0, lambda: self.tree.bind('<Button-1>', self.on_tree_click_detalhes))

    def atualizar_titulo_grid(self, gravacao_dir, titulo):
        # Atualiza o título na grid para a linha correspondente ao diretório da gravação
        # Busca a data/hora do primeiro bloco da gravação
        files = [f for f in os.listdir(gravacao_dir) if f.endswith('.ogg')]
        files.sort()
        if not files:
            return
        path = os.path.join(gravacao_dir, files[0])
        dt = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%d/%m/%Y %H:%M:%S')
        for row in self.tree.get_children():
            values = self.tree.item(row)['values']
            if values[0] == dt:
                self.tree.set(row, 'titulo', titulo)
                break

    def on_tree_select_anywhere(self, event):
        # Seleciona a linha clicada independentemente da coluna
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self.tree.selection_set(row_id)

    def capturar_print_monitor_mouse(self):
        import pyautogui
        from screeninfo import get_monitors
        from datetime import datetime
        import os
        try:
            x, y = pyautogui.position()
            for m in get_monitors():
                if m.x <= x < m.x + m.width and m.y <= y < m.y + m.height:
                    region = (m.x, m.y, m.width, m.height)
                    break
            else:
                print('[PRINT] Não foi possível identificar o monitor do mouse.')
                self.status.config(text="Não foi possível identificar o monitor do mouse.", fg="#F44336")
                return
            img = pyautogui.screenshot(region=region)
            grav_dir = self.get_selected_gravacao_dir()
            if grav_dir and os.path.isdir(grav_dir):
                ts = datetime.now().strftime('%H-%M-%S')
                path = os.path.join(grav_dir, f'print_{ts}.png')
                img.save(path)
                print(f'[PRINT] Print salvo: {path}')
                self._ultimo_print_path = path
                try:
                    ajustar_permissao_usuario(path)
                except Exception as e:
                    print(f"[PERMISSAO] Não foi possível ajustar permissões do arquivo: {e}")
                self.status.config(text="Print de tela capturado com sucesso!", fg="#388E3C")
                # Iniciar análise IA em background, sem depender de interface de modal
                def analisar_ia_em_bg():
                    import threading
                    def run_ia():
                        try:
                            self.status.config(text="Análise IA em andamento...", fg="#1976D2")
                            api_key = os.environ.get("GEMINI_API_KEY") or GEMINI_API_KEY
                            model = GEMINI_MODEL
                            genai.configure(api_key=api_key)
                            with open(path, 'rb') as f:
                                img_bytes = f.read()
                            prompt = """Analise esta imagem e forneça uma análise detalhada em português do Brasil, incluindo:\n\n1. Um resumo conciso do conteúdo visual\n2. Se houver código de programação, desafio de código, questão de prova ou questionário:\n   - Extraia o código ou a questão exatamente como aparece\n   - Explique o que está sendo proposto/resolvido\n   - Identifique a linguagem de programação (se aplicável)\n   - Gere uma resposta objetiva para a questão/código/desafio, se possível, e inclua como um tópico final chamado 'Resposta Objetiva'\n3. Se houver texto ou mensagens de erro:\n   - Transcreva o texto exatamente como aparece\n   - Explique o significado ou contexto\n\nRetorne a resposta EXCLUSIVAMENTE em markdown bem formatado, com títulos, listas, blocos de código e destaques conforme apropriado. Não inclua explicações fora do markdown.\n\nExemplo de estrutura sugerida:\n\n# Resumo\n...\n\n# Código ou Questão Detectada\n```python\n...\n```\n\n## Explicação\n...\n\n## Resposta Objetiva\n...\n\n# Texto Detectado\n...\n\n# Mensagens de Erro\n...\n\nSe algum item não existir, omita a seção correspondente."""
                            model = genai.GenerativeModel(GEMINI_MODEL)
                            response = model.generate_content(
                                [
                                    {"text": prompt},
                                    {"inline_data": {"mime_type": "image/png", "data": img_bytes}},
                                ],
                                generation_config={
                                    "temperature": 0.1,
                                    "top_p": 0.8,
                                    "top_k": 40,
                                    "max_output_tokens": 2048,
                                },
                            )
                            resposta = response.text.strip()
                            resposta_limpa = re.sub(r"^```[a-zA-Z]*\n?|```$", "", resposta, flags=re.MULTILINE).strip()
                            md_path = path.replace('.png', '.md')
                            with open(md_path, 'w', encoding='utf-8') as f:
                                f.write(resposta_limpa)
                            try:
                                ajustar_permissao_usuario(md_path)
                            except Exception:
                                pass
                            self.status.config(text="Análise IA concluída!", fg="#388E3C")
                        except Exception as e:
                            print(f'[IA][BG] Erro ao analisar print automaticamente: {e}')
                            msg = str(e)
                            if len(msg) > 120:
                                msg = msg[:120] + '...'
                            self.status.config(text=f"Erro na análise IA: {msg}", fg="#F44336")
                    threading.Thread(target=run_ia, daemon=True).start()
                self.master.after(300, analisar_ia_em_bg)
            else:
                print('[PRINT] Nenhuma gravação selecionada na grid para salvar o print.')
                self.status.config(text="Nenhuma gravação selecionada para salvar o print.", fg="#F44336")
        except Exception as e:
            print(f'[PRINT] Erro ao capturar print: {e}')
            self.status.config(text=f"Erro ao capturar print: {e}", fg="#F44336")

    def _start_pynput_hotkey_listener(self):
        try:
            from pynput import keyboard
        except ImportError:
            print('[HOTKEY] pynput não instalado. Atalho global não funcionará.')
            return
        def on_activate():
            print('[HOTKEY] Ctrl+Alt+M pressionado (global)!')
            self.master.after(0, self.capturar_print_monitor_mouse)
        hotkey = keyboard.HotKey(
            keyboard.HotKey.parse('<ctrl>+<alt>+m'),
            on_activate
        )
        def listen():
            with keyboard.Listener(
                on_press=hotkey.press,
                on_release=hotkey.release
            ) as listener:
                print('Aguardando Ctrl+Alt+M global...')
                listener.join()
        import threading
        t = threading.Thread(target=listen, daemon=True)
        t.start()

    def _abrir_modal_print(self, img_path, reuse_modal=None):
        import tkinter as tk
        from PIL import Image, ImageTk
        import os
        from markdown import markdown as md2html
        from tkinterweb import HtmlFrame

        BG_MODAL = "#f7f7f7"
        BG_CARD = "#e3eafc"
        PAD = 24

        if reuse_modal and reuse_modal.winfo_exists():
            modal = reuse_modal
            for widget in modal.winfo_children():
                widget.destroy()
        else:
            modal = tk.Toplevel(self.master)
        modal.title(f"Print: {os.path.basename(img_path)}")
        largura = modal.winfo_screenwidth()
        altura = modal.winfo_screenheight()
        modal.geometry(f"{largura}x{altura}+0+0")
        modal.configure(bg=BG_MODAL)

        # Frame principal dividido em duas colunas
        main_frame = tk.Frame(modal, bg=BG_MODAL)
        main_frame.pack(fill='both', expand=True)
        main_frame.pack_propagate(False)

        # Lado esquerdo (imagem + análise IA)
        left_frame = tk.Frame(main_frame, bg=BG_MODAL, width=largura//2, height=altura)
        left_frame.pack(side='left', fill='both', expand=True)
        left_frame.pack_propagate(False)

        # Lado direito (placeholder)
        right_frame = tk.Frame(main_frame, bg=BG_MODAL, width=largura//2, height=altura)
        right_frame.pack(side='right', fill='both', expand=True)
        right_frame.pack_propagate(False)

        # TOPO ESQUERDO: imagem do print
        img_frame = tk.Frame(left_frame, bg=BG_MODAL)
        img_frame.pack(fill='x', padx=PAD, pady=(PAD*2, 8), anchor='n')
        img = Image.open(img_path)
        max_w = largura//2 - 2*PAD
        max_h = int(altura * 0.35)
        img.thumbnail((max_w, max_h))
        tk_img = ImageTk.PhotoImage(img)
        lbl_img = tk.Label(img_frame, image=tk_img, bg=BG_MODAL)
        lbl_img.image = tk_img
        lbl_img.pack(anchor='center')
        tk.Label(img_frame, text=os.path.basename(img_path), font=("Arial", 12, "bold"), bg=BG_MODAL).pack(anchor='center', pady=(4, 0))

        # ABAIXO DA IMAGEM: análise IA (markdown)
        analise_frame = tk.Frame(left_frame, bg=BG_CARD, bd=0, highlightbackground="#b3c6e6", highlightthickness=1)
        analise_frame.pack(fill='both', expand=True, padx=PAD, pady=(0, PAD))
        tk.Label(analise_frame, text="Análise do Print (IA)", font=("Arial", 13, "bold"), bg=BG_CARD).pack(anchor='w', padx=16, pady=(12, 2))
        md_path = img_path.replace('.png', '.md')
        resposta_ia = ""
        if os.path.exists(md_path):
            with open(md_path, 'r', encoding='utf-8') as f:
                resposta_ia = f.read()
        if resposta_ia:
            html = md2html(resposta_ia, extensions=['fenced_code', 'codehilite'])
            html = html.replace('<pre>', '<pre style="background:#f4f4f4;border:1px solid #b3c6e6;padding:8px;border-radius:6px;overflow-x:auto;font-family:monospace;font-size:13px;">')
            html = html.replace('<code>', '<code style="font-family:monospace;font-size:13px;">')
            html_frame = HtmlFrame(analise_frame, messages_enabled=False, vertical_scrollbar=True)
            html_frame.load_html(html)
            html_frame.pack(fill='both', expand=True, padx=18, pady=(0, 8))
        else:
            tk.Label(analise_frame, text="Nenhuma análise IA disponível para este print.", font=("Arial", 11, "italic"), bg=BG_CARD, fg="#888").pack(anchor='w', padx=16, pady=(0, 8))

        # DIREITA: apenas texto placeholder
        placeholder = tk.Label(right_frame, text="Área reservada para interação com IA", font=("Arial", 16, "italic"), bg=BG_MODAL, fg="#888")
        placeholder.pack(expand=True)

def ajustar_permissao_usuario(path):
    try:
        user = os.getenv("SUDO_USER") or getpass.getuser()
        if user and user != "root":
            import pwd
            uid = pwd.getpwnam(user).pw_uid
            gid = pwd.getpwnam(user).pw_gid
            os.chown(path, uid, gid)
    except Exception as e:
        print(f"[PERMISSAO] Não foi possível ajustar permissões do arquivo: {e}")

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