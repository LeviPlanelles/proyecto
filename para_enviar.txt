#!/usr/bin/env python3
import argparse
import socket
import sys
import threading


DEFAULT_PORT = 5050
ENCODING = "utf-8"


def _receiver_loop(rfile) -> None:
    while True:
        try:
            line = rfile.readline()
        except Exception:
            break
        if not line:
            break
        # Imprime mensajes entrantes en tiempo real
        sys.stdout.write(line)
        sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="Cliente de chat TCP")
    parser.add_argument("--host", help="IP/host del servidor (ej: 192.168.1.10)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Puerto (por defecto {DEFAULT_PORT})")
    parser.add_argument("--name", help="Tu nombre en el chat")
    args = parser.parse_args()

    host = args.host or input("IP del servidor: ").strip()
    if not host:
        print("Host vacío. Abortando.")
        return 2

    name = args.name or input("Tu nombre: ").strip()
    if not name:
        name = "Anon"

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, args.port))

    rfile = sock.makefile("r", encoding=ENCODING, newline="\n")
    wfile = sock.makefile("w", encoding=ENCODING, newline="\n")

    # Handshake simple con el servidor
    first = rfile.readline()
    if first and first.strip() == "NAME?":
        wfile.write(f"NAME {name}\n")
        wfile.flush()
    else:
        # Si el servidor no pide nombre, lo mandamos igualmente.
        wfile.write(f"NAME {name}\n")
        wfile.flush()
        if first:
            sys.stdout.write(first)
            sys.stdout.flush()

    t = threading.Thread(target=_receiver_loop, args=(rfile,), daemon=True)
    t.start()

    print("Conectado. Escribe mensajes y pulsa Enter. /quit para salir.")

    try:
        for line in sys.stdin:
            msg = line.rstrip("\n")
            wfile.write(msg + "\n")
            wfile.flush()
            if msg.lower() in {"/quit", "/exit"}:
                break
    except KeyboardInterrupt:
        try:
            wfile.write("/quit\n")
            wfile.flush()
        except Exception:
            pass
    finally:
        try:
            sock.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
