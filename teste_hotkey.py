from pynput import keyboard

def on_activate():
    print('Atalho Ctrl+Alt+M pressionado!')

hotkey = keyboard.HotKey(
    keyboard.HotKey.parse('<ctrl>+<alt>+m'),
    on_activate
)

def for_canonical(f):
    return lambda k: f(listener.canonical(k))

with keyboard.Listener(
    on_press=for_canonical(hotkey.press),
    on_release=for_canonical(hotkey.release)
) as listener:
    print('Aguardando Ctrl+Alt+M global...')
    listener.join() 