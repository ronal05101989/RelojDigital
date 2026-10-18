"""Base de datos SQLite del sistema de asistencia."""
import os
import secrets
import sqlite3
from contextlib import contextmanager

from werkzeug.security import generate_password_hash

CARPETA = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(CARPETA, os.environ.get("ASISTENCIA_DB", "asistencia.db"))

ESQUEMA = """
CREATE TABLE IF NOT EXISTS horarios (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre         TEXT NOT NULL,
    entrada        TEXT NOT NULL,              -- HH:MM
    salida         TEXT NOT NULL,              -- HH:MM
    tolerancia_min INTEGER NOT NULL DEFAULT 10,
    descanso_min   INTEGER NOT NULL DEFAULT 60,
    dias           TEXT NOT NULL DEFAULT '0,1,2,3,4'  -- 0=lunes ... 6=domingo
);
CREATE TABLE IF NOT EXISTS empleados (
    codigo       TEXT PRIMARY KEY,             -- ID del usuario en el reloj
    nombre       TEXT NOT NULL,
    departamento TEXT NOT NULL DEFAULT '',
    horario_id   INTEGER REFERENCES horarios(id) ON DELETE SET NULL,
    activo       INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS marcajes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo     TEXT NOT NULL,
    fecha_hora TEXT NOT NULL,                  -- YYYY-MM-DD HH:MM:SS
    origen     TEXT NOT NULL DEFAULT 'reloj',  -- reloj | usb | manual
    nota       TEXT NOT NULL DEFAULT '',
    UNIQUE (codigo, fecha_hora)
);
CREATE INDEX IF NOT EXISTS ix_marcajes_fecha ON marcajes (fecha_hora);
CREATE TABLE IF NOT EXISTS ausencias (            -- permisos, licencias, vacaciones...
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo      TEXT NOT NULL REFERENCES empleados(codigo) ON DELETE CASCADE,
    tipo        TEXT NOT NULL,
    desde       TEXT NOT NULL,                 -- YYYY-MM-DD
    hasta       TEXT NOT NULL,                 -- YYYY-MM-DD
    hora_desde  TEXT NOT NULL DEFAULT '',      -- vacías = día completo
    hora_hasta  TEXT NOT NULL DEFAULT '',
    documento   TEXT NOT NULL DEFAULT '',      -- n.° de resolución, memo, certificado...
    motivo      TEXT NOT NULL DEFAULT '',
    registrado  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS ix_ausencias_fechas ON ausencias (desde, hasta);
CREATE TABLE IF NOT EXISTS feriados (
    fecha       TEXT PRIMARY KEY,              -- YYYY-MM-DD
    descripcion TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS ajustes (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""

AJUSTES_INICIALES = {
    "reloj_ip": "192.168.1.201",
    "reloj_puerto": "4370",
    "reloj_clave": "0",
    "intervalo_min": "5",
    "ultima_sync": "",
    "ultimo_error": "",
    "extra_minimo_min": "30",
    "correo_activo": "0",
    "correo_hora": "10:00",
    "correo_destinos": "",
    "smtp_servidor": "smtp.office365.com",
    "smtp_puerto": "587",
    "smtp_seguridad": "starttls",
    "smtp_usuario": "",
    "smtp_clave": "",
    "ultimo_correo": "",
    "correo_estado": "",
}


@contextmanager
def db():
    """Abre una conexión, confirma los cambios al salir y la cierra."""
    con = sqlite3.connect(RUTA_DB, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def inicializar():
    with db() as con:
        con.executescript(ESQUEMA)
        for clave, valor in AJUSTES_INICIALES.items():
            con.execute("INSERT OR IGNORE INTO ajustes VALUES (?, ?)", (clave, valor))
        con.execute("INSERT OR IGNORE INTO ajustes VALUES ('admin_hash', ?)",
                    (generate_password_hash("admin"),))
        con.execute("INSERT OR IGNORE INTO ajustes VALUES ('secret_key', ?)",
                    (secrets.token_hex(32),))
        if not con.execute("SELECT 1 FROM horarios").fetchone():
            con.execute("INSERT INTO horarios (nombre, entrada, salida) "
                        "VALUES ('General', '08:00', '17:00')")

        for nombre, entrada, salida, descanso in (
            ("07:00 a 16:00", "07:00", "16:00", 60),
            ("08:00 a 18:00", "08:00", "18:00", 60),
            ("07:00 a 13:00", "07:00", "13:00", 0),
        ):
            if not con.execute("SELECT 1 FROM horarios WHERE entrada=? AND salida=? AND dias='0,1,2,3,4'",
                               (entrada, salida)).fetchone():
                con.execute("INSERT INTO horarios (nombre, entrada, salida, descanso_min, dias) VALUES (?, ?, ?, ?, '0,1,2,3,4')",
                            (nombre, entrada, salida, descanso))


def ajuste(con, clave, defecto=""):
    fila = con.execute("SELECT valor FROM ajustes WHERE clave = ?", (clave,)).fetchone()
    return fila["valor"] if fila else defecto


def guardar_ajuste(con, clave, valor):
    con.execute("INSERT INTO ajustes VALUES (?, ?) "
                "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor", (clave, str(valor)))
