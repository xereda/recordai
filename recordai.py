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
        master.geometry("800x520")
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
        self.label.pack(pady=(18, 10))

        # --- Switches de captação ---
        switch_frame = tk.Frame(master, bg="#f7f7f7")
        switch_frame.pack(pady=(0, 10))
        self.var_mic = tk.BooleanVar(value=True)
        self.var_out = tk.BooleanVar(value=True)
        self.check_mic = tk.Checkbutton(switch_frame, text="Gravar microfone (entrada)", variable=self.var_mic, bg="#f7f7f7", font=("Arial", 12, "bold"), padx=10, pady=4, command=self.update_start_button_state)
        self.check_mic.pack(side=tk.LEFT, padx=10)
        self.check_out = tk.Checkbutton(switch_frame, text="Gravar saída do sistema", variable=self.var_out, bg="#f7f7f7", font=("Arial", 12, "bold"), padx=10, pady=4, command=self.update_start_button_state)
        self.check_out.pack(side=tk.LEFT, padx=10)

        # --- Botões principais ---
        btn_frame = tk.Frame(master, bg="#f7f7f7")
        btn_frame.pack(pady=(0, 8))
        self.start_button = tk.Button(btn_frame, text="Iniciar Gravação", command=self.start_recording, width=15, height=1, bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), relief=tk.RAISED, bd=2)
        self.start_button.grid(row=0, column=0, padx=8, pady=2, ipady=2)
        self.stop_button = tk.Button(btn_frame, text="Encerrar Gravação", command=self.stop_recording, width=15, height=1, bg="#F44336", fg="white", font=("Arial", 11, "bold"), state=tk.DISABLED, relief=tk.RAISED, bd=2)
        self.stop_button.grid(row=0, column=1, padx=8, pady=2, ipady=2)
        self.refresh_button = tk.Button(btn_frame, text="Atualizar Lista", command=self.refresh_files, width=12, height=1, font=("Arial", 10), relief=tk.RAISED, bd=2)
        self.refresh_button.grid(row=0, column=2, padx=8, pady=2, ipady=2)

        # --- Tabela de arquivos ---
        self.tree = ttk.Treeview(master, columns=("#1", "#2", "#3", "#4"), show="headings", height=12)
        self.tree.heading("#1", text="Arquivo")
        self.tree.heading("#2", text="Data/Hora")
        self.tree.heading("#3", text="")
        self.tree.heading("#4", text="")
        self.tree.column("#1", width=320)
        self.tree.column("#2", width=160)
        self.tree.column("#3", width=110, anchor="center")
        self.tree.column("#4", width=110, anchor="center")
        self.tree.pack(pady=10)
        self.tree.bind('<Double-1>', self.open_file)
        self.tree.bind('<Button-1>', self.on_tree_click)

        # --- Botões de ação ---
        action_frame = tk.Frame(master, bg="#f7f7f7")
        action_frame.pack(pady=(5, 10))
        self.play_button = tk.Button(action_frame, text="Reproduzir", command=self.play_file, width=12, height=1, font=("Arial", 10), relief=tk.RAISED, bd=2)
        self.play_button.grid(row=0, column=0, padx=6, pady=2, ipady=2)
        self.delete_button = tk.Button(action_frame, text="Excluir", command=self.delete_file, width=12, height=1, font=("Arial", 10), relief=tk.RAISED, bd=2)
        self.delete_button.grid(row=0, column=1, padx=6, pady=2, ipady=2)
        self.open_folder_button = tk.Button(action_frame, text="Abrir Pasta", command=self.open_folder, width=12, height=1, font=("Arial", 10), relief=tk.RAISED, bd=2)
        self.open_folder_button.grid(row=0, column=2, padx=6, pady=2, ipady=2)
        self.delete_all_button = tk.Button(action_frame, text="Excluir Todos", command=self.delete_all_files, width=12, height=1, font=("Arial", 10), relief=tk.RAISED, bd=2)
        self.delete_all_button.grid(row=0, column=3, padx=6, pady=2, ipady=2)

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
        self.filename = self.get_output_filename()
        mic_device = self.get_default_source()
        monitor_device = self.get_default_sink_monitor()
        use_mic = self.var_mic.get()
        use_out = self.var_out.get()
        if not use_mic and not use_out:
            self.status.config(text="Selecione pelo menos uma fonte para gravar.", fg="#F44336")
            self.update_start_button_state()
            return
            self.is_recording = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            return
        self.pipeline = self.build_gst_pipeline_mix(mic_device, monitor_device, self.filename, use_mic, use_out)
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
        for idx, f in enumerate(files):
            path = os.path.join(self.output_dir, f)
            dt = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%d/%m/%Y %H:%M:%S')
            self.tree.insert('', 'end', values=(f, dt, '[Transcrever]', '[Aplicar IA]'))
        self.add_action_buttons()

    def add_action_buttons(self):
        # Remove botões antigos
        if hasattr(self, 'action_buttons'):
            for btn in self.action_buttons:
                btn.destroy()
        self.action_buttons = []
        for i, item in enumerate(self.tree.get_children()):
            bbox3 = self.tree.bbox(item, column='#3')
            bbox4 = self.tree.bbox(item, column='#4')
            if not bbox3 or not bbox4:
                self.tree.update_idletasks()
                bbox3 = self.tree.bbox(item, column='#3')
                bbox4 = self.tree.bbox(item, column='#4')
            if bbox3:
                btn1 = tk.Button(self.tree, text="Transcrever", width=10, height=1, font=("Arial", 9), command=lambda iid=item: self.transcrever_arquivo(iid))
                btn1.place(x=bbox3[0]+self.tree.winfo_x(), y=bbox3[1]+self.tree.winfo_y(), width=bbox3[2], height=bbox3[3])
                self.action_buttons.append(btn1)
            if bbox4:
                btn2 = tk.Button(self.tree, text="Aplicar IA", width=10, height=1, font=("Arial", 9), command=lambda iid=item: self.aplicar_ia_arquivo(iid))
                btn2.place(x=bbox4[0]+self.tree.winfo_x(), y=bbox4[1]+self.tree.winfo_y(), width=bbox4[2], height=bbox4[3])
                self.action_buttons.append(btn2)

    def transcrever_arquivo(self, iid):
        values = self.tree.item(iid)['values']
        if values:
            print(f"[AÇÃO] Transcrever: {values[0]}")

    def aplicar_ia_arquivo(self, iid):
        values = self.tree.item(iid)['values']
        if values:
            print(f"[AÇÃO] Aplicar IA: {values[0]}")

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

    def on_tree_click(self, event):
        region = self.tree.identify('region', event.x, event.y)
        if region != 'cell':
            return
        row_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not row_id or col not in ('#3', '#4'):
            return
        values = self.tree.item(row_id)['values']
        if not values:
            return
        arquivo = values[0]
        idx = self.tree.index(row_id)
        if col == '#3':
            print(f"[AÇÃO] Transcrever: {arquivo} (id: {idx})")
        elif col == '#4':
            print(f"[AÇÃO] Aplicar IA: {arquivo} (id: {idx})")

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