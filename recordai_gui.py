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

if sys.version_info < (3, 6):
    print("Python 3.6+ é necessário.")
    sys.exit(1)

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

Gst.init(None)

class RecorderGUI:
    def __init__(self, master):
        self.master = master
        master.title("RecordAI - Gravação de Áudio do Sistema")
        master.geometry("600x400")
        master.resizable(False, False)
        master.configure(bg="#f7f7f7")

        self.is_recording = False
        self.pipeline = None
        self.loop = None
        self.filename = None
        self.thread = None
        self.output_dir = "output"

        # --- Layout ---
        self.label = tk.Label(master, text="Grave e gerencie os áudios da saída do sistema.", font=("Arial", 12), bg="#f7f7f7")
        self.label.pack(pady=(15, 5))

        btn_frame = tk.Frame(master, bg="#f7f7f7")
        btn_frame.pack(pady=5)
        self.start_button = tk.Button(btn_frame, text="Iniciar Gravação", command=self.start_recording, width=18, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.start_button.grid(row=0, column=0, padx=5)
        self.stop_button = tk.Button(btn_frame, text="Encerrar Gravação", command=self.stop_recording, width=18, bg="#F44336", fg="white", font=("Arial", 10, "bold"), state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5)
        self.refresh_button = tk.Button(btn_frame, text="Atualizar Lista", command=self.refresh_files, width=15, font=("Arial", 10))
        self.refresh_button.grid(row=0, column=2, padx=5)

        # --- Tabela de arquivos ---
        self.tree = ttk.Treeview(master, columns=("#1", "#2"), show="headings", height=10)
        self.tree.heading("#1", text="Arquivo")
        self.tree.heading("#2", text="Data/Hora")
        self.tree.column("#1", width=320)
        self.tree.column("#2", width=180)
        self.tree.pack(pady=10)
        self.tree.bind('<Double-1>', self.open_file)

        # --- Botões de ação ---
        action_frame = tk.Frame(master, bg="#f7f7f7")
        action_frame.pack(pady=5)
        self.play_button = tk.Button(action_frame, text="Reproduzir", command=self.play_file, width=15, font=("Arial", 10))
        self.play_button.grid(row=0, column=0, padx=5)
        self.delete_button = tk.Button(action_frame, text="Excluir", command=self.delete_file, width=15, font=("Arial", 10))
        self.delete_button.grid(row=0, column=1, padx=5)
        self.open_folder_button = tk.Button(action_frame, text="Abrir Pasta", command=self.open_folder, width=15, font=("Arial", 10))
        self.open_folder_button.grid(row=0, column=2, padx=5)
        self.delete_all_button = tk.Button(action_frame, text="Excluir Todos", command=self.delete_all_files, width=15, font=("Arial", 10))
        self.delete_all_button.grid(row=0, column=3, padx=5)

        self.status = tk.Label(master, text="", font=("Arial", 10), bg="#f7f7f7", fg="#555")
        self.status.pack(pady=(5, 0))

        self.refresh_files()

    def get_output_filename(self, prefix="gravacao"):  
        os.makedirs(self.output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return os.path.join(self.output_dir, f"{prefix}_{timestamp}.ogg")

    def get_default_sink_monitor(self):
        try:
            result = subprocess.run(['pactl', 'info'], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.startswith('Default Sink:'):
                        sink = line.split(':', 1)[1].strip()
                        monitor = f"{sink}.monitor"
                        return monitor
        except Exception as e:
            print(f"Erro ao buscar sink padrão: {e}")
        return 'default.monitor'

    def build_gst_pipeline(self, monitor_device, filename):
        pipeline_str = (
            f'pulsesrc device={monitor_device} ! '
            'audioconvert ! audioresample ! opusenc bitrate=32000 ! oggmux ! '
            f'filesink location={filename}'
        )
        return Gst.parse_launch(pipeline_str)

    def start_recording(self):
        if self.is_recording:
            return
        self.is_recording = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status.config(text="Gravando... (clique em Encerrar para finalizar)", fg="#1976D2")
        self.filename = self.get_output_filename()
        monitor_device = self.get_default_sink_monitor()
        self.pipeline = self.build_gst_pipeline(monitor_device, self.filename)
        self.loop = GLib.MainLoop()
        self.thread = threading.Thread(target=self._run_gst_loop, daemon=True)
        self.thread.start()

    def _run_gst_loop(self):
        self.pipeline.set_state(Gst.State.PLAYING)
        try:
            self.loop.run()
        except Exception as e:
            print(f"Erro durante a gravação: {e}")
            self.pipeline.set_state(Gst.State.NULL)

    def stop_recording(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status.config(text="Gravação finalizada!", fg="#388E3C")
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        if self.loop:
            self.loop.quit()
        self.refresh_files()
        messagebox.showinfo("Gravação finalizada", f"Arquivo salvo em:\n{self.filename}")

    def refresh_files(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        if not os.path.exists(self.output_dir):
            return
        files = [f for f in os.listdir(self.output_dir) if f.endswith('.ogg')]
        files.sort(reverse=True)
        for f in files:
            path = os.path.join(self.output_dir, f)
            dt = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%d/%m/%Y %H:%M:%S')
            self.tree.insert('', 'end', values=(f, dt))

    def get_selected_file(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Seleção", "Selecione um arquivo na lista.")
            return None
        return self.tree.item(sel[0])['values'][0]

    def play_file(self):
        f = self.get_selected_file()
        if not f:
            return
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
        f = self.get_selected_file()
        if not f:
            return
        path = os.path.join(self.output_dir, f)
        if messagebox.askyesno("Excluir", f"Deseja realmente excluir o arquivo?\n{f}"):
            try:
                os.remove(path)
                self.refresh_files()
                self.status.config(text=f"Arquivo '{f}' excluído.", fg="#F44336")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao excluir: {e}")

    def open_file(self, event=None):
        f = self.get_selected_file()
        if not f:
            return
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

if __name__ == "__main__":
    root = tk.Tk()
    app = RecorderGUI(root)
    root.mainloop() 