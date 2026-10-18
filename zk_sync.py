"""Descarga de usuarios y marcajes desde el reloj ZKTeco (por red o archivo USB)."""
import logging
import threading
import time
from datetime import datetime

from db import ajuste, db, guardar_ajuste

log = logging.getLogger("reloj")
_candado = threading.Lock()  # evita dos sincronizaciones a la vez


def _guardar(usuarios, registros, origen):
    """usuarios: [(codigo, nombre)], registros: [(codigo, datetime)]. Devuelve nuevos marcajes."""
    nuevos = 0
    with db() as con:
        for codigo, nombre in usuarios:
            con.execute(
                "INSERT OR IGNORE INTO empleados (codigo, nombre, horario_id) "
                "VALUES (?, ?, (SELECT MIN(id) FROM horarios))",
                (codigo, nombre or f"Empleado {codigo}"))
        for codigo, momento in registros:
            cur = con.execute(
                "INSERT OR IGNORE INTO marcajes (codigo, fecha_hora, origen) VALUES (?, ?, ?)",
                (codigo, momento.strftime("%Y-%m-%d %H:%M:%S"), origen))
            nuevos += cur.rowcount
    return nuevos


def sincronizar():
    """Conecta al reloj por red, descarga todo y guarda lo nuevo. Devuelve (usuarios, nuevos)."""
    from zk import ZK  # pyzk

    with db() as con:
        ip = ajuste(con, "reloj_ip")
        puerto = int(ajuste(con, "reloj_puerto", "4370") or 4370)
        clave = int(ajuste(con, "reloj_clave", "0") or 0)

    with _candado:
        conexion = None
        try:
            zk = ZK(ip, port=puerto, timeout=15, password=clave, force_udp=False, ommit_ping=True)
            conexion = zk.connect()
            conexion.disable_device()  # bloquea el reloj unos segundos mientras se lee
            usuarios = [(str(u.user_id), (u.name or "").strip()) for u in conexion.get_users()]
            registros = [(str(r.user_id), r.timestamp) for r in conexion.get_attendance()]
        except Exception as e:
            with db() as con:
                guardar_ajuste(con, "ultimo_error",
                               f"{datetime.now():%d/%m/%Y %H:%M} - No se pudo conectar a {ip}:{puerto}: {e}")
            raise
        finally:
            if conexion:
                try:
                    conexion.enable_device()
                    conexion.disconnect()
                except Exception:
                    pass

        nuevos = _guardar(usuarios, registros, "reloj")
        with db() as con:
            guardar_ajuste(con, "ultima_sync",
                           f"{datetime.now():%d/%m/%Y %H:%M} - {len(registros)} marcajes leídos, {nuevos} nuevos")
            guardar_ajuste(con, "ultimo_error", "")
        return len(usuarios), nuevos


def importar_attlog(texto):
    """Importa el archivo *_attlog.dat que el reloj guarda en la memoria USB.

    Cada línea es: <ID usuario> TAB <AAAA-MM-DD HH:MM:SS> TAB <estado> ...
    """
    registros = []
    for linea in texto.splitlines():
        partes = linea.strip().split("\t")
        if len(partes) < 2:
            continue
        try:
            registros.append((partes[0].strip(), datetime.strptime(partes[1].strip(), "%Y-%m-%d %H:%M:%S")))
        except ValueError:
            continue
    usuarios = sorted({(codigo, "") for codigo, _ in registros})
    return len(registros), _guardar(usuarios, registros, "usb")


def iniciar_sincronizacion_automatica():
    """Hilo en segundo plano que descarga el reloj cada N minutos."""
    def bucle():
        while True:
            try:
                usuarios, nuevos = sincronizar()
                log.info("Sincronizado: %s usuarios, %s marcajes nuevos", usuarios, nuevos)
            except Exception as e:
                log.warning("Error al sincronizar con el reloj: %s", e)
            with db() as con:
                minutos = max(1, int(ajuste(con, "intervalo_min", "5") or 5))
            time.sleep(minutos * 60)

    threading.Thread(target=bucle, daemon=True, name="sync-reloj").start()
