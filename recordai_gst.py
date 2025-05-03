#!/usr/bin/env python3
import gi
import os
import sys
import signal
import subprocess
from datetime import datetime
import threading
import multiprocessing

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

Gst.init(None)

def get_output_filename(output_dir="output", prefix="gravacao"):  
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return os.path.join(output_dir, f"{prefix}_{timestamp}.wav")

def get_default_sink_monitor():
    """Descobre o monitor do sink padrão do sistema."""
    try:
        result = subprocess.run(['pactl', 'info'], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith('Default Sink:'):
                    sink = line.split(':', 1)[1].strip()
                    monitor = f"{sink}.monitor"
                    print(f"Sink padrão: {sink}")
                    print(f"Monitor do sink padrão: {monitor}")
                    return monitor
    except Exception as e:
        print(f"Erro ao buscar sink padrão: {e}")
    return 'default.monitor'

def get_default_source():
    """Descobre a fonte padrão (microfone) do sistema."""
    try:
        # Tenta em português e inglês
        result = subprocess.run(['pactl', 'info'], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith('Fonte padrão:') or line.startswith('Default Source:'):
                    source = line.split(':', 1)[1].strip()
                    print(f"Fonte padrão: {source}")
                    return source
    except Exception as e:
        print(f"Erro ao buscar fonte padrão: {e}")
    return 'default'

def build_gst_pipeline(device, filename):
    """Monta o pipeline do GStreamer para gravar uma fonte (monitor ou microfone)."""
    pipeline_str = (
        f'pulsesrc device={device} ! '
        'audioconvert ! audioresample ! wavenc ! '
        f'filesink location={filename}'
    )
    return Gst.parse_launch(pipeline_str)

def run_pipeline_thread(device, filename):
    import gi
    gi.require_version('Gst', '1.0')
    gi.require_version('GLib', '2.0')
    from gi.repository import Gst, GLib
    Gst.init(None)
    pipeline_str = (
        f'pulsesrc device={device} provide-clock=true do-timestamp=true ! '
        'audioconvert ! audioresample ! wavenc ! '
        f'filesink location={filename}'
    )
    pipeline = Gst.parse_launch(pipeline_str)
    pipeline.set_state(Gst.State.PLAYING)
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    pipeline.set_state(Gst.State.NULL)
    print(f"[Thread] Pipeline encerrado para {device}")

def main():
    output_dir = "output"
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename_out = os.path.join(output_dir, f"saida_{timestamp}.wav")
    filename_mic = os.path.join(output_dir, f"mic_{timestamp}.wav")
    os.makedirs(output_dir, exist_ok=True)

    monitor_device = get_default_sink_monitor()
    mic_device = get_default_source()
    print(f"\nArquivo de saída: {filename_out}")
    print(f"Arquivo do microfone: {filename_mic}")
    print(f"Usando monitor: {monitor_device}")
    print(f"Usando microfone: {mic_device}\n")

    t_out = threading.Thread(target=run_pipeline_thread, args=(monitor_device, filename_out))
    t_mic = threading.Thread(target=run_pipeline_thread, args=(mic_device, filename_mic))
    t_out.start()
    t_mic.start()

    print("Gravando saída de áudio do sistema E microfone simultaneamente... (Pressione Ctrl+C para parar)")
    try:
        t_out.join()
        t_mic.join()
    except KeyboardInterrupt:
        print("\nInterrompendo gravação...")
        # Threads vão encerrar ao receber KeyboardInterrupt
        pass
    print(f"Gravação da saída salva em: {filename_out}")
    print(f"Gravação do microfone salva em: {filename_mic}")

if __name__ == "__main__":
    main() 