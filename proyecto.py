import tkinter as tk
from tkinter import Menu # Importar el widget Menu
from tkinter import ttk # Importar el widget ttk
import threading
import time
import datetime
import webbrowser
import subprocess
import psutil
import random
import tkinter.filedialog as fd
import tkinter.messagebox as mb
import tkinter.simpledialog as sd
import os
import shutil
from threading import Event
# Mapa de eventos para detener carreras por canvas
race_stop_events = {}
# Música: control global para reproducción/parada
music_lock = threading.Lock()
music_process = None
music_current = None
music_playing = False
# Alarma: control global
alarm_control = {
    "event": None,
    "thread": None,
    "end_ts": None
}

# Optional heavy imports guarded
try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MATPLOTLIB = True
except Exception:
    HAS_MATPLOTLIB = False

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
except Exception:
    HAS_REQUESTS = False

try:
    import pygame
    pygame.mixer.init()
    HAS_PYGAME = True
except Exception:
    HAS_PYGAME = False

def update_time(label_widget):
    """Función que actualiza la hora y el día de la semana en un label.

    Se ejecuta en un hilo secundario y programa las actualizaciones en
    el hilo principal de Tkinter usando el método `after` del widget.
    """
    while True:
        now = datetime.datetime.now()
        day_of_week = now.strftime("%A")
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%Y-%m-%d")
        label_text = f"{day_of_week}, {date_str} - {time_str}"

        # Programar la actualización en el hilo principal
        try:
            label_widget.after(0, label_widget.config, {"text": label_text})
        except Exception:
            # Si el widget ya no existe, salir del bucle
            break

        time.sleep(1)


def launch_browser(url):
    try:
        webbrowser.open(url)
    except Exception as e:
        mb.showerror("Error", f"No se pudo abrir el navegador:\n{e}")


def launch_browser_prompt():
    url = sd.askstring("Abrir navegador", "Introduce la URL:", initialvalue="https://www.google.com")
    if url:
        threading.Thread(target=launch_browser, args=(url,), daemon=True).start()


def run_backup_script():
    script = fd.askopenfilename(title="Selecciona script .ps1", filetypes=[("PowerShell", "*.ps1"), ("All", "*")])
    if not script:
        return

    def runner(path):
        # Intentar usar pwsh o powershell
        for exe in ("pwsh", "powershell", "pwsh.exe", "powershell.exe"):
            try:
                subprocess.run([exe, "-File", path], check=True)
                mb.showinfo("Backup", "Script ejecutado correctamente")
                return
            except FileNotFoundError:
                continue
            except subprocess.CalledProcessError as e:
                mb.showerror("Error", f"El script devolvió error:\n{e}")
                return
        mb.showerror("Error", "No se encontró PowerShell en el sistema")

    threading.Thread(target=runner, args=(script,), daemon=True).start()


def _copy_path_to_backup(path):
    """Worker: copia `path` (archivo o carpeta) dentro de ./backup del proyecto.
    Se ejecuta en un hilo de fondo.
    """
    base_dir = os.path.abspath(os.path.dirname(__file__))
    backup_dir = os.path.join(base_dir, "backup")
    try:
        os.makedirs(backup_dir, exist_ok=True)
    except Exception:
        pass

    try:
        if os.path.isfile(path):
            name = os.path.basename(path)
            dest = os.path.join(backup_dir, name)
            # si existe, añadir timestamp
            if os.path.exists(dest):
                stem, ext = os.path.splitext(name)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                dest = os.path.join(backup_dir, f"{stem}_{ts}{ext}")
            shutil.copy2(path, dest)
            root.after(0, mb.showinfo, "Backup", f"Archivo copiado en:\n{dest}")
        elif os.path.isdir(path):
            name = os.path.basename(os.path.normpath(path)) or 'folder'
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(backup_dir, f"{name}_{ts}")
            # usar copytree
            shutil.copytree(path, dest)
            root.after(0, mb.showinfo, "Backup", f"Carpeta copiada en:\n{dest}")
        else:
            root.after(0, mb.showwarning, "Backup", "La ruta seleccionada no es válida")
    except Exception as e:
        try:
            root.after(0, mb.showerror, "Backup", f"Error al copiar:\n{e}")
        except Exception:
            pass


def backup_ui():
    """Interfaz: pedir al usuario que seleccione archivo o carpeta y lanzar copia en background.
    Debe ejecutarse en el hilo principal (dialogos)."""
    # Primero intentar seleccionar un archivo
    path = fd.askopenfilename(title="Selecciona archivo para copiar (Cancelar para elegir carpeta)")
    if path:
        threading.Thread(target=_copy_path_to_backup, args=(path,), daemon=True).start()
        return
    # Si no eligió archivo, permitir elegir carpeta
    dirpath = fd.askdirectory(title="Selecciona carpeta para copiar (si cancelas, se aborta)")
    if dirpath:
        threading.Thread(target=_copy_path_to_backup, args=(dirpath,), daemon=True).start()
        return
    # si cancela ambas, informar
    try:
        mb.showinfo("Backup", "Operación cancelada")
    except Exception:
        pass


def open_resource_window():
    if not HAS_MATPLOTLIB:
        mb.showwarning("Dependencia", "matplotlib no está disponible. Instálalo con pip install matplotlib")
        return

    win = tk.Toplevel(root)
    win.title("Recursos del sistema")
    fig, axes = plt.subplots(3, 1, figsize=(6, 6))
    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.get_tk_widget().pack(fill="both", expand=True)

    xdata = list(range(30))
    cpu_data = [0]*30
    mem_data = [0]*30
    net_data = [0]*30

    line_cpu, = axes[0].plot(xdata, cpu_data, label="CPU %")
    axes[0].set_ylim(0, 100)
    line_mem, = axes[1].plot(xdata, mem_data, label="Mem %", color="orange")
    axes[1].set_ylim(0, 100)
    line_net, = axes[2].plot(xdata, net_data, label="KB/s", color="green")

    axes[0].legend(loc="upper right")
    axes[1].legend(loc="upper right")
    axes[2].legend(loc="upper right")

    prev_net = psutil.net_io_counters()

    after_id = None

    def on_close():
        nonlocal after_id
        try:
            if after_id is not None:
                win.after_cancel(after_id)
        except Exception:
            pass
        try:
            win.destroy()
        except Exception:
            pass

    win.protocol("WM_DELETE_WINDOW", on_close)

    def update_plot():
        nonlocal cpu_data, mem_data, net_data, prev_net, after_id
        # Si la ventana se cerró, terminar el bucle de actualización
        try:
            if not win.winfo_exists():
                return
        except Exception:
            return
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        cur_net = psutil.net_io_counters()
        # bytes per second -> KB/s
        sent = (cur_net.bytes_sent - prev_net.bytes_sent) / 1024.0
        recv = (cur_net.bytes_recv - prev_net.bytes_recv) / 1024.0
        prev_net = cur_net
        net_kb = (sent + recv) / 2.0

        cpu_data = cpu_data[1:]+[cpu]
        mem_data = mem_data[1:]+[mem]
        net_data = net_data[1:]+[net_kb]

        line_cpu.set_ydata(cpu_data)
        line_mem.set_ydata(mem_data)
        line_net.set_ydata(net_data)
        try:
            canvas.draw()
        except Exception:
            # Si el canvas fue destruido, salir
            return
        try:
            if win.winfo_exists():
                # guardar id para poder cancelarlo en on_close
                nonlocal after_id
                after_id = win.after(1000, update_plot)
        except Exception:
            return

    update_plot()


def open_text_editor():
    win = tk.Toplevel(root)
    win.title("Editor de texto")
    txt = tk.Text(win, wrap="word")
    txt.pack(fill="both", expand=True)

    def save():
        path = fd.asksaveasfilename(defaultextension=".txt")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(txt.get("1.0", "end-1c"))
            mb.showinfo("Guardado", "Archivo guardado")

    def open_file():
        path = fd.askopenfilename(filetypes=[("Text","*.txt;*.py;*.md"), ("All","*")])
        if path:
            if os.path.isdir(path):
                mb.showwarning("Abrir", "Selecciona un archivo, no una carpeta")
                return
            try:
                with open(path, "r", encoding="utf-8") as f:
                    txt.delete("1.0", "end")
                    txt.insert("1.0", f.read())
            except Exception as e:
                mb.showerror("Error", f"No se pudo leer el archivo:\n{e}")

    btns = tk.Frame(win)
    ttk.Button(btns, text="Abrir", command=open_file, style="Secondary.TButton").pack(side="left")
    ttk.Button(btns, text="Guardar", command=save, style="Accent.TButton").pack(side="left")
    btns.pack()


def scrape_url():
    if not HAS_REQUESTS:
        mb.showwarning("Dependencia", "requests/bs4 no están disponibles. Instálalos con pip install requests beautifulsoup4")
        return
    url = sd.askstring("Scraping", "Introduce la URL a scrapear:")
    if not url:
        return
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # eliminar scripts, styles y noscript
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        # intentar obtener título y meta description
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        meta_desc = ""
        md = soup.find("meta", attrs={"name": "description"})
        if md and md.get("content"):
            meta_desc = md.get("content").strip()

        # extraer texto visible, limpiar espacios
        raw_text = soup.get_text(separator="\n")
        # colapsar líneas en exceso y espacios
        lines = [ln.strip() for ln in raw_text.splitlines()]
        cleaned = "\n".join([ln for ln in lines if ln])

        # preparar carpeta de salida `scrapping` en el directorio del script
        base_dir = os.path.abspath(os.path.dirname(__file__))
        out_dir = os.path.join(base_dir, "scrapping")
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception:
            pass

        # construir nombre de archivo seguro
        from urllib.parse import urlparse
        parsed = urlparse(url)
        netloc = parsed.netloc or parsed.path.replace("/", "_")
        safe_netloc = "".join([c if c.isalnum() else "_" for c in netloc])[:80]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        txt_name = f"scrape_{safe_netloc}_{timestamp}.txt"
        html_name = f"scrape_{safe_netloc}_{timestamp}.html"
        txt_path = os.path.join(out_dir, txt_name)
        html_path = os.path.join(out_dir, html_name)

        # escribir archivos
        header = f"URL: {url}\nTitle: {title}\nMeta-Description: {meta_desc}\nTimestamp: {timestamp}\n\n"
        try:
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(header)
                f.write(cleaned)
        except Exception as e:
            mb.showwarning("Advertencia", f"No se pudo guardar el fichero txt:\n{e}")

        try:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(r.text)
        except Exception:
            pass

        # mostrar resultado reducido en una ventana y notificar fichero guardado
        win = tk.Toplevel(root)
        win.title(f"Scrape: {url}")
        t = tk.Text(win, wrap="word")
        t.insert("1.0", header + cleaned[:20000])
        t.pack(fill="both", expand=True)

        try:
            mb.showinfo("Guardado", f"Contenido scrapado guardado en:\n{txt_path}")
        except Exception:
            pass
    except Exception as e:
        mb.showerror("Error", f"Falló scraping:\n{e}")


def fetch_weather_xabia():
    """Consulta la API de OpenWeatherMap para obtener el tiempo en Jávea (Alicante).
    Pide al usuario la API key (se puede obtener en https://home.openweathermap.org/api_keys).
    Actualiza la etiqueta central `center_status` con temperatura y muestra un cuadro informativo.
    """
    # comprobar dependencia
    if not HAS_REQUESTS:
        mb.showwarning("Dependencia", "requests no está instalado. Instálalo con pip install requests")
        return

    # Ruta para guardar la API key de forma persistente
    cfg_dir = os.path.join(os.path.expanduser("~"), ".config", "proyecto")
    key_file = os.path.join(cfg_dir, "openweather.key")

    api_key = None
    # si existe fichero con key, usarla
    try:
        if os.path.exists(key_file):
            with open(key_file, "r", encoding="utf-8") as fk:
                k = fk.read().strip()
                if k:
                    api_key = k
    except Exception:
        api_key = None

    # si no había key persistida, pedirla y guardarla
    if not api_key:
        api_key = sd.askstring("OpenWeatherMap API", "Introduce tu API Key de OpenWeatherMap:")
        if not api_key:
            return
        try:
            os.makedirs(cfg_dir, exist_ok=True)
            with open(key_file, "w", encoding="utf-8") as fk:
                fk.write(api_key.strip())
        except Exception:
            # no crítico: continuar sin guardar
            pass

    # Usar lat/lon para Jávea (Xàbia): lat=38.789166, lon=0.163055
    lat = 38.789166
    lon = 0.163055
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric", "lang": "es"}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        temp = data.get("main", {}).get("temp")
        desc = data.get("weather", [{}])[0].get("description", "")
        humidity = data.get("main", {}).get("humidity")
        wind = data.get("wind", {}).get("speed")

        info = f"Tiempo en Jávea, Alicante:\nTemperatura: {temp} °C\nCondición: {desc}\nHumedad: {humidity}%\nViento: {wind} m/s"
        try:
            mb.showinfo("Tiempo - Jávea", info)
        except Exception:
            pass
        try:
            center_status.config(text=f"Jávea: {temp}°C, {desc}")
        except Exception:
            pass
    except requests.HTTPError as e:
        # Manejo específico para 401 (Unauthorized)
        try:
            resp = getattr(e, 'response', None)
            if resp is not None and resp.status_code == 401:
                ans = mb.askyesno("Autenticación", "La API key no es válida (401 Unauthorized).\n¿Quieres borrar la key guardada y volver a introducirla?")
                if ans:
                    try:
                        if os.path.exists(key_file):
                            os.remove(key_file)
                    except Exception:
                        pass
                    # reintentar: llamar recursivamente para pedir nueva key
                    try:
                        fetch_weather_xabia()
                    except Exception:
                        pass
                else:
                    try:
                        mb.showerror("Error", "API key inválida. Revisa tu key en OpenWeatherMap.")
                    except Exception:
                        pass
                return
        except Exception:
            pass
        try:
            mb.showerror("Error", f"Error al obtener datos: {e}")
        except Exception:
            pass
    except Exception as e:
        try:
            mb.showerror("Error", f"Falló la consulta:\n{e}")
        except Exception:
            pass


def clear_openweather_key():
    """Borra la API key guardada de OpenWeather (si existe)."""
    cfg_dir = os.path.join(os.path.expanduser("~"), ".config", "proyecto")
    key_file = os.path.join(cfg_dir, "openweather.key")
    try:
        if os.path.exists(key_file):
            os.remove(key_file)
            mb.showinfo("Key eliminada", f"Se ha eliminado: {key_file}")
        else:
            mb.showinfo("Key", "No había ninguna key guardada")
    except Exception as e:
        try:
            mb.showerror("Error", f"No se pudo borrar la key:\n{e}")
        except Exception:
            pass


def play_music_file():
    if not HAS_PYGAME:
        # si pygame no está disponible, usaremos afplay como fallback
        pass
    path = fd.askopenfilename(filetypes=[("Audio","*.mp3;*.wav;*.midi;*.mid"), ("All","*")])
    if not path:
        return

    def _play_with_pygame(p):
        global music_playing, music_current
        try:
            with music_lock:
                # detener cualquier reproducción previa
                try:
                    pygame.mixer.music.stop()
                except Exception:
                    pass
                pygame.mixer.music.load(p)
                pygame.mixer.music.play(-1)
                music_current = p
                music_playing = True
        except Exception as e:
            mb.showerror("Error", f"No se pudo reproducir con pygame:\n{e}")

    def _play_with_afplay(p):
        global music_process, music_playing, music_current
        try:
            # detener proceso anterior
            with music_lock:
                if music_process is not None:
                    try:
                        music_process.kill()
                    except Exception:
                        pass
                # iniciar afplay en background
                music_process = subprocess.Popen(["afplay", p])
                music_current = p
                music_playing = True
        except Exception as e:
            mb.showerror("Error", f"No se pudo reproducir con afplay:\n{e}")

    # arrancar en hilo para no bloquear la UI
    def runner(p):
        if HAS_PYGAME:
            _play_with_pygame(p)
        else:
            _play_with_afplay(p)

    threading.Thread(target=runner, args=(path,), daemon=True).start()


def stop_music():
    """Detiene la reproducción iniciada por `play_music_file` (pygame o afplay)."""
    global music_process, music_playing, music_current
    with music_lock:
        if HAS_PYGAME:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
        if music_process is not None:
            try:
                music_process.kill()
            except Exception:
                pass
            music_process = None
        music_playing = False
        music_current = None


def set_alarm_minutes():
    mins = sd.askinteger("Alarma", "Avisar en cuántos minutos?", minvalue=1, maxvalue=1440)
    if not mins:
        return

    # si ya hay una alarma, cancelarla antes
    try:
        if alarm_control.get("event") is not None:
            try:
                alarm_control["event"].set()
            except Exception:
                pass
    except Exception:
        pass

    ev = Event()
    end_ts = time.time() + mins * 60
    alarm_control["event"] = ev
    alarm_control["end_ts"] = end_ts

    def alarm_worker():
        try:
            while True:
                if ev.is_set():
                    # cancelada
                    try:
                        root.after(0, alarm_countdown_label.config, {"text": "Alarma cancelada"})
                    except Exception:
                        pass
                    break
                now_ts = time.time()
                remaining = int(end_ts - now_ts)
                if remaining <= 0:
                    # sonar alarma
                    try:
                        sound_path = "/System/Library/Sounds/Glass.aiff"
                        if HAS_PYGAME:
                            try:
                                s = pygame.mixer.Sound(sound_path)
                                s.play()
                            except Exception:
                                root.bell()
                        else:
                            subprocess.Popen(["afplay", sound_path])
                    except Exception:
                        try:
                            root.bell()
                        except Exception:
                            pass
                    try:
                        root.after(0, mb.showinfo, "Alarma", f"Pasaron {mins} minutos")
                    except Exception:
                        pass
                    try:
                        root.after(0, alarm_countdown_label.config, {"text": "No hay alarma programada"})
                    except Exception:
                        pass
                    break

                # actualizar etiqueta en hilo principal
                try:
                    h = remaining // 3600
                    mnt = (remaining % 3600) // 60
                    s = remaining % 60
                    text = f"Cuenta atrás: {h:02d}:{mnt:02d}:{s:02d}"
                    root.after(0, alarm_countdown_label.config, {"text": text})
                except Exception:
                    pass

                time.sleep(1)
        finally:
            # limpiar control
            try:
                alarm_control["event"] = None
                alarm_control["end_ts"] = None
            except Exception:
                pass

    t = threading.Thread(target=alarm_worker, daemon=True)
    alarm_control["thread"] = t
    t.start()


def cancel_alarm():
    """Cancela la alarma programada (si existe)."""
    try:
        ev = alarm_control.get("event")
        if ev is not None:
            try:
                ev.set()
            except Exception:
                pass
        try:
            alarm_countdown_label.config(text="Alarma cancelada")
        except Exception:
            pass
        alarm_control["event"] = None
        alarm_control["thread"] = None
        alarm_control["end_ts"] = None
    except Exception:
        pass


def open_game_race(parent_canvas=None, num_racers=4, speed_mult=1.0):
    """Ejecuta la carrera de camellos en un canvas dado.
    Si no se proporciona canvas, abre un Toplevel (compatibilidad antigua).
    num_racers: número de corredores
    speed_mult: multiplicador de velocidad (>=0.1)
    """
    if parent_canvas is None:
        win = tk.Toplevel(root)
        win.title("Carrera de camellos")
        canvas = tk.Canvas(win, width=600, height=200, bg="white")
        canvas.pack()
        # si se crea un Toplevel, asegurar limpieza cuando se cierre
        def _on_win_close():
            try:
                stop_event.set()
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass
        # provisional — stop_event aún no creado; lo conectaremos más abajo estableciendo protocolo después
    else:
        canvas = parent_canvas
        try:
            canvas.delete("all")
            canvas.config(bg="white")
        except Exception:
            # si el canvas no existe o fue destruido, no continuar
            return

    # Calcular línea de meta en función del tamaño del canvas
    try:
        finish = canvas.winfo_width() - 50
    except Exception:
        finish = 550
    if finish < 200:
        finish = 550

    camels = []
    colors = ["red", "blue", "green", "orange", "purple", "cyan", "magenta", "yellow"]
    # limitar número de corredores
    try:
        n = max(1, min(int(num_racers), 12))
    except Exception:
        n = 4
    for i in range(n):
        y = 20 + i * 30
        color = colors[i % len(colors)]
        rect = canvas.create_rectangle(10, y, 60, y + 25, fill=color)
        camels.append(rect)

    # Control para anunciar ganador una sola vez
    winner_lock = threading.Lock()
    winner = {"index": None}

    lock = threading.Lock()
    # evento para detener esta carrera
    stop_event = Event()
    race_stop_events[id(canvas)] = stop_event

    # si se creó win arriba, conectar el cierre a stop_event
    try:
        if 'win' in locals():
            win.protocol("WM_DELETE_WINDOW", _on_win_close)
    except Exception:
        pass

    def racer(item, idx):
        while True:
            if stop_event.is_set():
                return
            try:
                with lock:
                    try:
                        coords = canvas.coords(item)
                    except tk.TclError:
                        return
                    if not coords:
                        return
                    x1, y1, x2, y2 = coords
                    if x2 >= finish:
                        # Si aún no hay ganador, anunciarlo y resaltar
                        with winner_lock:
                            if winner["index"] is None:
                                winner["index"] = idx + 1
                                try:
                                    # resaltar ganador en dorado
                                    root.after(0, lambda it=item: canvas.itemconfig(it, fill="#FFD700"))
                                except Exception:
                                    pass
                                try:
                                    root.after(0, mb.showinfo, "Ganador", f"¡Camello #{winner['index']} ha ganado!")
                                except Exception:
                                    pass
                                # detener el resto de corredores
                                try:
                                    stop_event.set()
                                except Exception:
                                    pass
                        return
                    max_step = max(1, int(10 * float(speed_mult)))
                    step = random.randint(1, max_step)
                    try:
                        canvas.move(item, step, 0)
                    except tk.TclError:
                        return
            except Exception:
                return
            time.sleep(random.uniform(0.05, 0.2))

    for idx, r in enumerate(camels):
        threading.Thread(target=racer, args=(r, idx), daemon=True).start()

    # Lanzar un watcher que elimina el evento cuando la carrera termina
    def _watcher():
        try:
            while True:
                if stop_event.is_set():
                    break
                all_done = True
                with lock:
                    for item in camels:
                        try:
                            coords = canvas.coords(item)
                        except tk.TclError:
                            # canvas destroyed -> stop
                            stop_event.set()
                            all_done = True
                            break
                        if coords and coords[2] < finish:
                            all_done = False
                            break
                if all_done:
                    break
                time.sleep(0.5)
        finally:
            try:
                race_stop_events.pop(id(canvas), None)
            except Exception:
                pass

    threading.Thread(target=_watcher, daemon=True).start()


def launch_app(path):
    """Abrir una aplicación en macOS usando `open` en un hilo separado."""
    def _run():
        if not os.path.exists(path):
            # intentar con el nombre de la app si se pasó un nombre
            try:
                subprocess.run(["open", "-a", path], check=True)
                return
            except Exception as e:
                mb.showerror("Error", f"No se encontró la aplicación:\n{path}\n{e}")
                return
        try:
            subprocess.run(["open", path], check=True)
        except Exception as e:
            try:
                subprocess.run(["open", "-a", path], check=True)
            except Exception as e2:
                mb.showerror("Error", f"No se pudo abrir la aplicación:\n{e}\n{e2}")

    threading.Thread(target=_run, daemon=True).start()


# Crear la ventana principal
root = tk.Tk()
root.title("Ventana Responsive")
root.geometry("1200x700")  # Tamaño inicial (más ancho)

# Tema y paleta básica
PALETTE = {
    "bg_main": "#f5f7fa",
    "sidebar": "#eef3f8",
    "panel": "#ffffff",
    "accent": "#2b8bd6",
    "muted": "#7a8a99"
}
FONT_TITLE = ("Helvetica", 11, "bold")
FONT_NORMAL = ("Helvetica", 10)

root.configure(bg=PALETTE["bg_main"])
_style = ttk.Style(root)
try:
    _style.theme_use("clam")
except Exception:
    pass
_style.configure("Accent.TButton", background=PALETTE["accent"], foreground="white", font=FONT_NORMAL, padding=6)
_style.map("Accent.TButton", background=[('active', '#1e68b8')])
_style.configure("Secondary.TButton", background="#eef6fb", foreground=PALETTE["accent"], font=FONT_NORMAL, padding=6)
_style.map("Secondary.TButton", background=[('active', '#e0f0ff')])
_style.configure("TNotebook", background=PALETTE["bg_main"], tabposition='n')
_style.configure("TFrame", background=PALETTE["panel"]) 


# Configurar la ventana principal para que sea responsive
root.columnconfigure(0, weight=0)  # Columna izquierda, tamaño fijo
root.columnconfigure(1, weight=1)  # Columna central, tamaño variable
root.columnconfigure(2, weight=0)  # Columna derecha, tamaño fijo
root.rowconfigure(0, weight=1)  # Fila principal, tamaño variable
root.rowconfigure(1, weight=0)  # Barra de estado, tamaño fijo

# Crear el menú superior
menu_bar = Menu(root)

file_menu = Menu(menu_bar, tearoff=0)
file_menu.add_command(label="Nuevo")
file_menu.add_command(label="Abrir")
file_menu.add_separator()
file_menu.add_command(label="Salir", command=root.quit)

edit_menu = Menu(menu_bar, tearoff=0)
edit_menu.add_command(label="Copiar")
edit_menu.add_command(label="Pegar")

help_menu = Menu(menu_bar, tearoff=0)
help_menu.add_command(label="Acerca de")

menu_bar.add_cascade(label="Archivo", menu=file_menu)
menu_bar.add_cascade(label="Editar", menu=edit_menu)
menu_bar.add_cascade(label="Ayuda", menu=help_menu)

root.config(menu=menu_bar)

# Crear los frames laterales y el central
frame_izquierdo = tk.Frame(root, bg=PALETTE["sidebar"], width=220, highlightthickness=0)
frame_central = tk.Frame(root, bg=PALETTE["bg_main"])
frame_derecho = tk.Frame(root, bg=PALETTE["sidebar"], width=260, highlightthickness=0)

# Colocar los frames laterales y el central
frame_izquierdo.grid(row=0, column=0, sticky="ns")
frame_central.grid(row=0, column=1, sticky="nsew")
frame_derecho.grid(row=0, column=2, sticky="ns")

# Configurar los tamaños fijos de los frames laterales
frame_izquierdo.grid_propagate(False)
frame_derecho.grid_propagate(False)

# --- Contenido del sidebar izquierdo (secciones y botones) ---
left_title = tk.Label(frame_izquierdo, text="", bg=PALETTE["sidebar"])
left_title.pack(pady=10)

sec_acciones = tk.Label(frame_izquierdo, text="Acciones", bg=PALETTE["panel"], font=FONT_TITLE, anchor="w", padx=8)
sec_acciones.pack(fill="x", padx=8, pady=(8,2))

btn_extraer = ttk.Button(frame_izquierdo, text="Extraer datos", width=18, style="Secondary.TButton")
btn_navegar = ttk.Button(frame_izquierdo, text="Navegar", width=18, style="Secondary.TButton")
btn_buscar = ttk.Button(frame_izquierdo, text="Buscar API Google", width=18, style="Secondary.TButton")
btn_extraer.pack(pady=6, padx=8, fill='x')
btn_navegar.pack(pady=6, padx=8, fill='x')
btn_buscar.pack(pady=6, padx=8, fill='x')

sec_apps = tk.Label(frame_izquierdo, text="Aplicaciones", bg=PALETTE["panel"], font=FONT_TITLE, anchor="w", padx=8)
sec_apps.pack(fill="x", padx=8, pady=(12,6))

btn_vscode = ttk.Button(frame_izquierdo, text="Visual Code", width=18, style="Accent.TButton")
btn_app2 = ttk.Button(frame_izquierdo, text="App2", width=18, style="Secondary.TButton")
btn_app3 = ttk.Button(frame_izquierdo, text="App3", width=18, style="Secondary.TButton")
btn_vscode.pack(pady=6, padx=8, fill='x')
btn_app2.pack(pady=6, padx=8, fill='x')
btn_app3.pack(pady=6, padx=8, fill='x')

sec_batch = tk.Label(frame_izquierdo, text="Procesos batch", bg=PALETTE["panel"], font=FONT_TITLE, anchor="w", padx=8)
sec_batch.pack(fill="x", padx=8, pady=(12,6))

btn_backup = ttk.Button(frame_izquierdo, text="Copias de seguridad", width=18, style="Secondary.TButton")
btn_backup.pack(pady=6, padx=8, fill='x')
# --- Contenido del sidebar derecho (chat y lista de alumnos) ---
chat_title = tk.Label(frame_derecho, text="Chat", font=("Helvetica", 14, "bold"), bg=PALETTE["sidebar"])
chat_title.pack(pady=(8,8))

msg_label = tk.Label(frame_derecho, text="Mensaje", bg=PALETTE["sidebar"], font=FONT_NORMAL)
msg_label.pack(padx=8, anchor="w")

msg_text = tk.Text(frame_derecho, height=6, width=26, bd=0, relief="flat")
msg_text.pack(padx=8, pady=(6,8), fill="x")

send_btn = ttk.Button(frame_derecho, text="Enviar", style="Accent.TButton")
send_btn.pack(padx=8, pady=(0,12))

alumnos_label = tk.Label(frame_derecho, text="Alumnos", bg=PALETTE["sidebar"], font=FONT_TITLE)
alumnos_label.pack(padx=8, anchor="w")

# Frame con scrollbar para la lista de alumnos
alumnos_frame = tk.Frame(frame_derecho)
alumnos_frame.pack(fill="both", expand=True, padx=8, pady=6)

canvas = tk.Canvas(alumnos_frame, borderwidth=0, highlightthickness=0, bg="white")
scrollbar = tk.Scrollbar(alumnos_frame, orient="vertical", command=canvas.yview)
inner = tk.Frame(canvas, bg="white")
inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.create_window((0, 0), window=inner, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)
canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# Añadir algunos alumnos de ejemplo
for n in range(1, 6):
    a_frame = tk.Frame(inner, bg="white", bd=1, relief="groove")
    tk.Label(a_frame, text=f"Alumno {n}", font=("Helvetica", 12, "bold"), bg="white").pack(anchor="w")
    tk.Label(a_frame, text="Lorem ipsum dolor sit amet, consectetur...", bg="white", wraplength=160, justify="left").pack(anchor="w", pady=(2,6))
    a_frame.pack(fill="x", pady=4)

    

music_label = tk.Label(frame_derecho, text="Reproductor música", bg="#dcdcdc")
music_label.pack(fill="x", padx=8, pady=(6,8))

# Botones / comandos vinculados
btn_navegar.config(command=launch_browser_prompt)
# El botón de copias ahora pide un archivo o carpeta y lo copia a ./backup
btn_backup.config(command=backup_ui)
# Abrir Visual Studio Code (ruta absoluta en macOS)
btn_vscode.config(command=lambda: launch_app("/Applications/Visual Studio Code.app"))
btn_app2.config(command=open_resource_window)
btn_app3.config(command=open_game_race)
btn_extraer.config(command=scrape_url)
btn_buscar.config(command=fetch_weather_xabia)
    # refresh button removed (was duplicated per alumno)

# Los controles de alarma y reproducción de música están disponibles en la pestaña "Enlaces"

# Enviar mensaje (simulado)
def send_message():
    text = msg_text.get("1.0", "end-1c").strip()
    if not text:
        mb.showwarning("Mensaje", "El mensaje está vacío")
        return
    mb.showinfo("Mensaje", "Mensaje enviado (simulado)")
    msg_text.delete("1.0", "end")

send_btn.config(command=send_message)

# Dividir el frame central en dos partes (superior variable e inferior fija)
frame_central.rowconfigure(0, weight=1)  # Parte superior, tamaño variable
frame_central.rowconfigure(1, weight=0)  # Parte inferior, tamaño fijo
frame_central.columnconfigure(0, weight=1)  # Ocupa toda la anchura

# Crear subframes dentro del frame central
frame_superior = tk.Frame(frame_central, bg="lightyellow")
frame_inferior = tk.Frame(frame_central, bg="lightgray", height=100)

# Colocar los subframes dentro del frame central
frame_superior.grid(row=0, column=0, sticky="nsew")
frame_inferior.grid(row=1, column=0, sticky="ew")

# Fijar el tamaño de la parte inferior
frame_inferior.grid_propagate(False)

# Añadir texto informativo en la parte inferior central
info_label = tk.Label(frame_inferior, text="Panel para notas informativas y mensajes sobre la ejecución de los hilos.",
                      bg=PALETTE["panel"], anchor="w", justify="left", padx=12, font=FONT_NORMAL)
info_label.pack(fill="both", expand=True, padx=8, pady=8)

# Crear la barra de estado como contenedor (Frame)
barra_estado = tk.Frame(root, bg="lightgray")
barra_estado.grid(row=1, column=0, columnspan=3, sticky="ew")

# Notebook para las pestañas
style = ttk.Style()
style.configure("CustomNotebook.TNotebook.Tab", font=("Arial", 12, "bold"))
notebook = ttk.Notebook(frame_superior, style="CustomNotebook.TNotebook")
notebook.pack(fill="both", expand=True, padx=6, pady=6)

# Crear seis solapas con nombres definidos
tab_resultados = ttk.Frame(notebook)
tab_navegador = ttk.Frame(notebook)
tab_correos = ttk.Frame(notebook)
tab_tareas = ttk.Frame(notebook)
tab_alarmas = ttk.Frame(notebook)
tab_enlaces = ttk.Frame(notebook)

notebook.add(tab_resultados, text="Resultados", padding=8)
notebook.add(tab_navegador, text="Navegador", padding=8)
notebook.add(tab_correos, text="Correos", padding=8)
notebook.add(tab_tareas, text="Tareas", padding=8)
notebook.add(tab_alarmas, text="Alarmas", padding=8)
notebook.add(tab_enlaces, text="Enlaces", padding=8)

# --- Contenido básico de cada solapa ---
# Resultados: canvas del juego y botón para iniciar la carrera
res_top = tk.Frame(tab_resultados)
res_top.pack(fill="both", expand=True)
res_controls = tk.Frame(tab_resultados, height=40)
res_controls.pack(fill="x")
res_canvas = tk.Canvas(res_top, width=800, height=300, bg="white")
res_canvas.pack(fill="both", expand=True, padx=8, pady=8)
# Controles: iniciar, número de corredores, velocidad y detener
start_race_btn = ttk.Button(res_controls, text="Iniciar Carrera", style="Accent.TButton")
start_race_btn.pack(side="left", padx=8, pady=6)
tk.Label(res_controls, text="Corredores:").pack(side="left", padx=(10,2))
num_spin = tk.Spinbox(res_controls, from_=1, to=12, width=4)
num_spin.pack(side="left", padx=2)
tk.Label(res_controls, text="Velocidad:").pack(side="left", padx=(10,2))
speed_scale = tk.Scale(res_controls, from_=0.5, to=3.0, resolution=0.1, orient="horizontal", length=140)
speed_scale.set(1.0)
speed_scale.pack(side="left", padx=2)
stop_race_btn = ttk.Button(res_controls, text="Detener Carrera", style="Secondary.TButton")
stop_race_btn.pack(side="left", padx=8)

# Enlazar el botón para ejecutar la carrera dentro del canvas de la solapa Resultados
def _start_from_ui():
    try:
        n = int(num_spin.get())
    except Exception:
        n = 4
    try:
        sp = float(speed_scale.get())
    except Exception:
        sp = 1.0
    open_game_race(res_canvas, num_racers=n, speed_mult=sp)

def _stop_from_ui():
    ev = race_stop_events.get(id(res_canvas))
    if ev is not None:
        try:
            ev.set()
        except Exception:
            pass
    try:
        res_canvas.delete("all")
    except Exception:
        pass

start_race_btn.config(command=_start_from_ui)
stop_race_btn.config(command=_stop_from_ui)

# Navegador: entrada de URL y botón
nav_frame = tk.Frame(tab_navegador)
nav_frame.pack(fill="both", expand=True, padx=8, pady=8)
url_entry = tk.Entry(nav_frame)
url_entry.insert(0, "https://www.google.com")
url_entry.pack(fill="x", side="left", expand=True, padx=(0,8))
open_url_btn = ttk.Button(nav_frame, text="Abrir", command=lambda: threading.Thread(target=launch_browser, args=(url_entry.get(),), daemon=True).start(), style="Accent.TButton")
open_url_btn.pack(side="right")

# Correos: cuadro de chat simple (simulado)
cor_frame = tk.Frame(tab_correos)
cor_frame.pack(fill="both", expand=True, padx=8, pady=8)
cor_msg_text = tk.Text(cor_frame, height=12)
cor_msg_text.pack(fill="both", expand=True)
cor_send_btn = ttk.Button(cor_frame, text="Enviar", width=12, style="Accent.TButton")
cor_send_btn.pack(pady=(6,0))

def correos_send():
    text = cor_msg_text.get("1.0", "end-1c").strip()
    if not text:
        mb.showwarning("Mensaje", "El mensaje está vacío")
        return
    mb.showinfo("Mensaje", "Mensaje enviado (simulado)")
    cor_msg_text.delete("1.0", "end")

cor_send_btn.config(command=correos_send)

# Tareas: editor simple embebido
task_frame = tk.Frame(tab_tareas)
task_frame.pack(fill="both", expand=True, padx=8, pady=8)
task_text = tk.Text(task_frame, wrap="word")
task_text.pack(fill="both", expand=True)
task_btns = tk.Frame(tab_tareas)
task_btns.pack(fill="x")

def task_open():
    path = fd.askopenfilename(filetypes=[("Text","*.txt;*.py;*.md"), ("All","*")])
    if not path:
        return
    if os.path.isdir(path):
        mb.showwarning("Abrir", "Selecciona un archivo, no una carpeta")
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            task_text.delete("1.0", "end")
            task_text.insert("1.0", f.read())
    except Exception as e:
        mb.showerror("Error", f"No se pudo leer el archivo:\n{e}")

def task_save():
    path = fd.asksaveasfilename(defaultextension=".txt")
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(task_text.get("1.0", "end-1c"))
        mb.showinfo("Guardado", "Archivo guardado")
    except Exception as e:
        mb.showerror("Error", f"No se pudo guardar el archivo:\n{e}")

    ttk.Button(task_btns, text="Abrir", command=task_open, style="Secondary.TButton").pack(side="left", padx=4, pady=6)
    ttk.Button(task_btns, text="Guardar", command=task_save, style="Accent.TButton").pack(side="left", padx=4, pady=6)

# Alarmas: usar set_alarm_minutes (ya existente)
alarm_frame = tk.Frame(tab_alarmas)
alarm_frame.pack(fill="both", expand=True, padx=8, pady=8)
ttk.Button(alarm_frame, text="Programar alarma", command=set_alarm_minutes, style="Accent.TButton").pack(pady=8)

# Label de cuenta regresiva y botón cancelar
alarm_countdown_label = tk.Label(alarm_frame, text="No hay alarma programada", font=FONT_TITLE, bg=PALETTE["panel"], fg=PALETTE["muted"], padx=8, pady=6)
alarm_countdown_label.pack(pady=(6,8), fill="x")
ttk.Button(alarm_frame, text="Cancelar alarma", command=lambda: threading.Thread(target=lambda: cancel_alarm(), daemon=True).start(), style="Secondary.TButton").pack()

# Enlaces: botones para abrir apps y utilidades
links_frame = tk.Frame(tab_enlaces)
links_frame.pack(fill="both", expand=True, padx=8, pady=8)
ttk.Button(links_frame, text="Abrir Visual Studio Code", command=lambda: launch_app("/Applications/Visual Studio Code.app"), style="Accent.TButton").pack(fill="x", pady=4)
ttk.Button(links_frame, text="Abrir Spotify", command=lambda: launch_app("/Applications/Spotify.app"), style="Secondary.TButton").pack(fill="x", pady=4)
ttk.Button(links_frame, text="Mostrar recursos (matplotlib)", command=open_resource_window, style="Secondary.TButton").pack(fill="x", pady=4)
ttk.Button(links_frame, text="Reproducir música (archivo)", command=play_music_file, style="Secondary.TButton").pack(fill="x", pady=4)
ttk.Button(links_frame, text="Detener música", command=stop_music, style="Secondary.TButton").pack(fill="x", pady=4)
ttk.Button(links_frame, text="Borrar OpenWeather Key", command=clear_openweather_key, style="Secondary.TButton").pack(fill="x", pady=4)

# Barra de estado
# Dividir la barra de estado en 4 labels


# Usar pack para alinear los labels horizontalmente



# Secciones en la barra de estado: izquierda, centro y derecha
left_status = tk.Label(barra_estado, text="Correos sin leer 🔄", bg="#f0f0f0", anchor="w", padx=8)
center_status = tk.Label(barra_estado, text="Temperatura local: -- °C", bg="#f0f0f0", anchor="center")
label_fecha_hora = tk.Label(barra_estado, text="Cargando fecha...", font=("Helvetica", 12), bd=1, fg="blue", relief="sunken", anchor="e", padx=10)

left_status.pack(side="left", fill="x", expand=True)
center_status.pack(side="left", fill="x", expand=True)
label_fecha_hora.pack(side="right")

# Iniciar hilo para actualizar la fecha/hora
update_thread = threading.Thread(target=update_time, args=(label_fecha_hora,))
update_thread.daemon = True
update_thread.start()


# Hilo que monitoriza tráfico de red y actualiza la etiqueta central en KB/s
def network_monitor(label_widget):
    try:
        prev = psutil.net_io_counters()
    except Exception:
        return
    while True:
        time.sleep(1)
        cur = psutil.net_io_counters()
        sent = (cur.bytes_sent - prev.bytes_sent) / 1024.0
        recv = (cur.bytes_recv - prev.bytes_recv) / 1024.0
        prev = cur
        text = f"Tráfico - In: {recv:.1f} KB/s  Out: {sent:.1f} KB/s"
        try:
            label_widget.after(0, label_widget.config, {"text": text})
        except Exception:
            break


net_thread = threading.Thread(target=network_monitor, args=(center_status,))
net_thread.daemon = True
net_thread.start()

# Ejecución de la aplicación
root.mainloop()