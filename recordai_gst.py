#!/usr/bin/env python3
import gi
import os
import sys
import signal
import subprocess
from datetime import datetime

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

def build_gst_pipeline(monitor_device, filename):
    """Monta o pipeline do GStreamer para gravar o monitor."""
    pipeline_str = (
        f'pulsesrc device={monitor_device} ! '
        'audioconvert ! audioresample ! wavenc ! '
        f'filesink location={filename}'
    )
    return Gst.parse_launch(pipeline_str)

def main():
    output_dir = "output"
    filename = get_output_filename(output_dir)
    monitor_device = get_default_sink_monitor()
    print(f"\nArquivo de saída: {filename}")
    print(f"Usando monitor: {monitor_device}\n")

    pipeline = build_gst_pipeline(monitor_device, filename)
    loop = GLib.MainLoop()

    def stop_recording(*args):
        print("\nGravação interrompida! Salvando arquivo...")
        pipeline.set_state(Gst.State.NULL)
        loop.quit()
        print(f"Gravação salva em: {filename}")

    signal.signal(signal.SIGINT, stop_recording)
    signal.signal(signal.SIGTERM, stop_recording)

    print("Gravando saída de áudio do sistema (saída padrão)... (Pressione Ctrl+C para parar)")
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except Exception as e:
        print(f"Erro durante a gravação: {e}")
        pipeline.set_state(Gst.State.NULL)

if __name__ == "__main__":
    main() 