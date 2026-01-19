#!/usr/bin/env python3
import socket
import threading
from dataclasses import dataclass

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5050
ENCODING = "utf-8"

@dataclass
class ClientConn:
    sock: socket.socket
    addr: tuple
    name: str
    wfile: any

class ChatServer:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, on_log=None):
        self.host = host
        self.port = port
        self.on_log = on_log if on_log else print
        self.clients = {}
        self.clients_lock = threading.Lock()
        self.server_sock = None
        self.running = False
        self.thread = None

    def log(self, message):
        """Envía el mensaje al callback configurado (GUI o print)"""
        self.on_log(message)

    def broadcast(self, message: str, exclude: socket.socket | None = None) -> None:
        """Envía mensaje a todos los clientes conectados"""
        line = message.rstrip("\n") + "\n"
        with self.clients_lock:
            items = list(self.clients.items())
        
        # Log local si no está excluido el propio servidor (opcional, pero útil ver lo que se envía)
        # self.log(f"BRD: {message}") 

        for sock, client in items:
            if exclude is not None and sock is exclude:
                continue
            try:
                client.wfile.write(line)
                client.wfile.flush()
            except Exception:
                pass

    def send_server_message(self, text: str):
        """Mensaje desde el servidor (admin)"""
        msg = f"[ADMIN] {text}"
        self.log(msg)
        self.broadcast(msg)

    def _handle_client(self, conn: socket.socket, addr: tuple) -> None:
        try:
            rfile = conn.makefile("r", encoding=ENCODING, newline="\n")
            wfile = conn.makefile("w", encoding=ENCODING, newline="\n")

            name = None
            
            # Protocolo simple: pedir nombre
            try:
                wfile.write("NAME?\n")
                wfile.flush()
            except Exception:
                return

            try:
                raw_name = rfile.readline()
            except Exception:
                raw_name = None

            if not raw_name:
                return

            raw_name = raw_name.strip()
            # Compatibilidad si el cliente manda "NAME Pepe"
            if raw_name.upper().startswith("NAME "):
                raw_name = raw_name[5:].strip()

            name = raw_name or f"{addr[0]}:{addr[1]}"

            with self.clients_lock:
                self.clients[conn] = ClientConn(sock=conn, addr=addr, name=name, wfile=wfile)

            msg_join = f"* {name} se ha unido al chat *"
            self.log(msg_join)
            self.broadcast(msg_join)

            while self.running:
                try:
                    line = rfile.readline()
                except Exception:
                    break
                
                if not line: 
                    break

                msg = line.strip()
                if not msg:
                    continue

                if msg.lower() in {"/quit", "/exit"}:
                    break
                
                # Mostrar en servidor y reenviar a otros
                full_msg = f"[{name}] {msg}"
                self.log(full_msg)
                self.broadcast(full_msg)

        except Exception as e:
            self.log(f"Error gestionando cliente {addr}: {e}")
        finally:
            with self.clients_lock:
                self.clients.pop(conn, None)
            try:
                conn.close()
            except Exception:
                pass
            
            if name:
                msg_left = f"* {name} ha salido del chat *"
                self.log(msg_left)
                self.broadcast(msg_left)

    def start_background(self):
        """Inicia el servidor en un hilo secundario"""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_server_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Detiene el servidor"""
        self.running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
        self.log("Servidor detenido.")

    def _run_server_loop(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_sock.bind((self.host, self.port))
            self.server_sock.listen(100)
            self.server_sock.settimeout(1.0) # Timeout para permitir verificar self.running
            self.log(f"Servidor escuchando en {self.host}:{self.port}")
            
            while self.running:
                try:
                    conn, addr = self.server_sock.accept()
                    t = threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True)
                    t.start()
                except TimeoutError:
                    continue
                except OSError:
                    break
                except Exception as e:
                    self.log(f"Error aceptando conexión: {e}")
                    
        except Exception as e:
            self.log(f"Error fatal en servidor: {e}")
        finally:
            self.running = False
            try:
                self.server_sock.close()
            except Exception:
                pass

if __name__ == "__main__":
    # Modo standalone para pruebas
    import sys
    try:
        srv = ChatServer(port=5050)
        srv.start_background()
        print("Presiona Ctrl+C para salir.")
        while True:
            cmd = sys.stdin.readline()
            if not cmd: break
            if cmd.strip():
                srv.send_server_message(cmd.strip())
    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()
