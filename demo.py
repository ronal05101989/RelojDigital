"""Crea 100 empleados y 30 días de marcajes ficticios para probar el sistema sin el reloj.

Uso:  python demo.py      (crea demo.db aparte; no toca los datos reales)
"""
import os
import random
from datetime import date, datetime, timedelta

import db

db.RUTA_DB = os.path.join(db.CARPETA, "demo.db")
if os.path.exists(db.RUTA_DB):
    os.remove(db.RUTA_DB)
db.inicializar()

NOMBRES = ["Ana", "Luis", "María", "José", "Carmen", "Jorge", "Lucía", "Carlos", "Rosa", "Pedro",
           "Elena", "Miguel", "Sofía", "Juan", "Patricia", "Diego", "Laura", "Andrés", "Gabriela", "Raúl"]
APELLIDOS = ["García", "Rodríguez", "López", "Martínez", "Pérez", "Gómez", "Sánchez", "Díaz", "Torres",
             "Ramírez", "Flores", "Vargas", "Castro", "Rojas", "Mendoza", "Herrera", "Ruiz", "Morales"]
DEPTOS = ["Producción", "Producción", "Producción", "Almacén", "Ventas", "Administración", "Mantenimiento"]

random.seed(7)
with db.db() as con:
    con.execute("INSERT INTO horarios (nombre, entrada, salida, tolerancia_min, descanso_min, dias) "
                "VALUES ('Turno tarde', '14:00', '22:00', 5, 30, '0,1,2,3,4,5')")
    turno_tarde = con.execute("SELECT MAX(id) FROM horarios").fetchone()[0]
    for i in range(1, 101):
        nombre = f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)} {random.choice(APELLIDOS)}"
        con.execute("INSERT INTO empleados (codigo, nombre, departamento, horario_id) VALUES (?, ?, ?, ?)",
                    (str(i), nombre, random.choice(DEPTOS), turno_tarde if i > 80 else 1))

    hoy, ahora = date.today(), datetime.now()
    for i in range(1, 101):
        entrada_h, salida_h, dias = (14, 22, range(6)) if i > 80 else (8, 17, range(5))
        impuntual = random.random() < 0.15  # algunos llegan tarde seguido
        for atras in range(30, -1, -1):
            d = hoy - timedelta(days=atras)
            if d.weekday() not in dias or random.random() < 0.04:  # 4 % de faltas
                continue
            retraso = random.randint(5, 40) if random.random() < (0.35 if impuntual else 0.06) else random.randint(-15, 4)
            ent = datetime.combine(d, datetime.min.time()) + timedelta(hours=entrada_h, minutes=retraso)
            sal = datetime.combine(d, datetime.min.time()) + timedelta(
                hours=salida_h, minutes=random.choice([random.randint(-5, 10)] * 5 + [random.randint(30, 150)]))
            for momento in ([ent] if random.random() < 0.03 else [ent, sal]):  # 3 % olvida marcar salida
                if momento <= ahora:
                    con.execute("INSERT OR IGNORE INTO marcajes (codigo, fecha_hora) VALUES (?, ?)",
                                (str(i), momento.strftime("%Y-%m-%d %H:%M:%S")))

    # Algunos permisos, licencias y un feriado
    lunes = hoy - timedelta(days=hoy.weekday())
    con.executemany(
        "INSERT INTO ausencias (codigo, tipo, desde, hasta, hora_desde, hora_hasta, documento, motivo) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [("3", "Vacaciones", str(lunes - timedelta(days=14)), str(lunes - timedelta(days=3)), "", "", "Memo 045-2026", ""),
         ("12", "Licencia médica", str(lunes - timedelta(days=7)), str(lunes + timedelta(days=4)), "", "", "CITT 778812", "Reposo"),
         ("25", "Permiso por salud", str(lunes - timedelta(days=6)), str(lunes - timedelta(days=6)), "08:00", "10:30", "", "Cita médica"),
         ("40", "Comisión de servicio", str(lunes - timedelta(days=10)), str(lunes - timedelta(days=9)), "", "", "Oficio 112", "Viaje a sede regional")])
    con.execute("INSERT INTO feriados VALUES (?, 'Feriado de prueba')", (str(lunes - timedelta(days=5)),))
    # Quien está de vacaciones o licencia, o en feriado, no marca
    con.execute("DELETE FROM marcajes WHERE substr(fecha_hora, 1, 10) IN (SELECT fecha FROM feriados)")
    con.execute("DELETE FROM marcajes WHERE EXISTS (SELECT 1 FROM ausencias a WHERE a.codigo = marcajes.codigo "
                "AND a.hora_desde = '' AND substr(marcajes.fecha_hora, 1, 10) BETWEEN a.desde AND a.hasta)")
    # El del permiso por horas llega cuando termina su cita
    con.execute("UPDATE marcajes SET fecha_hora = substr(fecha_hora, 1, 10) || ' 10:52:00' WHERE codigo = '25' "
                "AND substr(fecha_hora, 1, 10) = ? AND substr(fecha_hora, 12, 2) < '12'", (str(lunes - timedelta(days=6)),))

print("Listo: demo.db con 100 empleados y 30 días de marcajes.")
