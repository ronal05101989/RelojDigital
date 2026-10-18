"""Panel web del sistema de asistencia. Ejecutar:  python app.py"""
import logging
import os
import sys
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, Response, flash, redirect, render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import calculo
import correo
import zk_sync
from db import ajuste, db, guardar_ajuste, inicializar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
inicializar()

app = Flask(__name__)
with db() as _con:
    app.secret_key = ajuste(_con, "secret_key")
app.jinja_env.globals.update(hm=calculo.hm, DIAS=calculo.DIAS)


def fecha_param(nombre, defecto):
    try:
        return date.fromisoformat(request.args.get(nombre, ""))
    except ValueError:
        return defecto


@app.before_request
def requiere_login():
    if request.endpoint not in ("login", "static") and not session.get("admin"):
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        with db() as con:
            ok = check_password_hash(ajuste(con, "admin_hash"), request.form.get("clave", ""))
        if ok:
            session["admin"] = True
            return redirect(url_for("inicio"))
        flash("Contraseña incorrecta", "error")
    return render_template("login.html")


@app.route("/salir")
def salir():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------- Inicio
@app.route("/")
def inicio():
    hoy = date.today()
    with db() as con:
        filas = calculo.detalle(con, hoy, hoy)
        ultimos = con.execute(
            "SELECT m.*, COALESCE(e.nombre, 'Desconocido') AS nombre FROM marcajes m "
            "LEFT JOIN empleados e ON e.codigo = m.codigo ORDER BY m.fecha_hora DESC LIMIT 15").fetchall()
        total = con.execute("SELECT COUNT(*) FROM empleados WHERE activo = 1").fetchone()[0]
        estado = {"ultima_sync": ajuste(con, "ultima_sync"), "ultimo_error": ajuste(con, "ultimo_error"),
                  "ip": ajuste(con, "reloj_ip")}
    cuenta = lambda *estados: sum(1 for f in filas if f["estado"] in estados)
    tarjetas = {"Empleados": total,
                "Presentes": sum(1 for f in filas if f["marcajes"]),
                "Tardanzas": sum(1 for f in filas if f["tardanza"]),
                "Faltas": cuenta("Falta"),
                "Con permiso": sum(1 for f in filas if f["es_permiso"]),
                "Por llegar": cuenta("Pendiente")}
    faltan = [f for f in filas if f["estado"] in ("Falta", "Pendiente")]
    tarde = [f for f in filas if f["tardanza"]]
    return render_template("inicio.html", hoy=hoy, tarjetas=tarjetas, faltan=faltan, tarde=tarde,
                           ultimos=ultimos, estado=estado)


@app.post("/sincronizar")
def sincronizar():
    try:
        usuarios, nuevos = zk_sync.sincronizar()
        flash(f"Reloj sincronizado: {usuarios} usuarios, {nuevos} marcajes nuevos.", "ok")
    except Exception as e:
        flash(f"No se pudo conectar al reloj: {e}", "error")
    return redirect(request.referrer or url_for("inicio"))


# ---------------------------------------------------------------- Empleados
@app.route("/empleados")
def empleados():
    buscar = request.args.get("q", "").strip()
    with db() as con:
        lista = con.execute(
            "SELECT e.*, h.nombre AS horario FROM empleados e LEFT JOIN horarios h ON h.id = e.horario_id "
            "WHERE e.codigo LIKE ? OR e.nombre LIKE ? OR e.departamento LIKE ? "
            "ORDER BY e.activo DESC, e.nombre", (f"%{buscar}%",) * 3).fetchall()
        horarios = con.execute("SELECT * FROM horarios ORDER BY nombre").fetchall()
    return render_template("empleados.html", lista=lista, horarios=horarios, q=buscar)


@app.route("/empleados/<codigo>", methods=["GET", "POST"])
def empleado(codigo):
    with db() as con:
        if request.method == "POST":
            f = request.form
            con.execute(
                "INSERT INTO empleados (codigo, nombre, departamento, horario_id, activo) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(codigo) DO UPDATE SET nombre = excluded.nombre, departamento = excluded.departamento, "
                "horario_id = excluded.horario_id, activo = excluded.activo",
                (f["codigo"].strip(), f["nombre"].strip(), f.get("departamento", "").strip(),
                 f.get("horario_id") or None, 1 if f.get("activo") else 0))
            flash("Empleado guardado.", "ok")
            return redirect(url_for("empleados"))
        emp = con.execute("SELECT * FROM empleados WHERE codigo = ?", (codigo,)).fetchone()
        horarios = con.execute("SELECT * FROM horarios ORDER BY nombre").fetchall()
    return render_template("empleado.html", emp=emp, codigo=codigo, horarios=horarios)


@app.post("/empleados/horario-masivo")
def horario_masivo():
    codigos = request.form.getlist("codigos")
    with db() as con:
        con.executemany("UPDATE empleados SET horario_id = ? WHERE codigo = ?",
                        [(request.form.get("horario_id") or None, c) for c in codigos])
    flash(f"Horario asignado a {len(codigos)} empleados.", "ok")
    return redirect(url_for("empleados"))


# ---------------------------------------------------------------- Horarios
@app.route("/horarios", methods=["GET", "POST"])
def horarios():
    with db() as con:
        if request.method == "POST":
            f = request.form
            datos = (f["nombre"].strip(), f["entrada"], f["salida"], int(f.get("tolerancia_min") or 0),
                     int(f.get("descanso_min") or 0), ",".join(f.getlist("dias")))
            if f.get("id"):
                con.execute("UPDATE horarios SET nombre=?, entrada=?, salida=?, tolerancia_min=?, descanso_min=?, "
                            "dias=? WHERE id=?", datos + (f["id"],))
            else:
                con.execute("INSERT INTO horarios (nombre, entrada, salida, tolerancia_min, descanso_min, dias) "
                            "VALUES (?, ?, ?, ?, ?, ?)", datos)
            flash("Horario guardado.", "ok")
            return redirect(url_for("horarios"))
        lista = con.execute("SELECT h.*, (SELECT COUNT(*) FROM empleados e WHERE e.horario_id = h.id) AS empleados "
                            "FROM horarios h ORDER BY nombre").fetchall()
    return render_template("horarios.html", lista=lista)


@app.post("/horarios/<int:id>/borrar")
def borrar_horario(id):
    with db() as con:
        con.execute("DELETE FROM horarios WHERE id = ?", (id,))
    flash("Horario eliminado. Sus empleados quedaron sin horario.", "ok")
    return redirect(url_for("horarios"))


# ---------------------------------------------------------------- Marcajes
@app.route("/marcajes")
def marcajes():
    desde = fecha_param("desde", date.today())
    hasta = fecha_param("hasta", desde)
    codigo = request.args.get("codigo", "")
    sql = ("SELECT m.*, COALESCE(e.nombre, 'Desconocido') AS nombre FROM marcajes m "
           "LEFT JOIN empleados e ON e.codigo = m.codigo WHERE m.fecha_hora >= ? AND m.fecha_hora < ?")
    params = [desde.isoformat(), (hasta + timedelta(days=1)).isoformat()]
    if codigo:
        sql += " AND m.codigo = ?"
        params.append(codigo)
    with db() as con:
        lista = con.execute(sql + " ORDER BY m.fecha_hora DESC LIMIT 2000", params).fetchall()
        emps = con.execute("SELECT codigo, nombre FROM empleados ORDER BY nombre").fetchall()
    return render_template("marcajes.html", lista=lista, emps=emps, desde=desde, hasta=hasta, codigo=codigo)


@app.post("/marcajes/nuevo")
def nuevo_marcaje():
    f = request.form
    try:
        momento = datetime.strptime(f"{f['fecha']} {f['hora']}", "%Y-%m-%d %H:%M")
    except ValueError:
        flash("Fecha u hora no válida.", "error")
        return redirect(url_for("marcajes"))
    with db() as con:
        con.execute("INSERT OR IGNORE INTO marcajes (codigo, fecha_hora, origen, nota) VALUES (?, ?, 'manual', ?)",
                    (f["codigo"], momento.strftime("%Y-%m-%d %H:%M:00"), f.get("nota", "").strip()))
    flash("Marcaje manual agregado.", "ok")
    return redirect(url_for("marcajes", desde=f["fecha"], codigo=f["codigo"]))


@app.post("/marcajes/<int:id>/borrar")
def borrar_marcaje(id):
    with db() as con:
        con.execute("DELETE FROM marcajes WHERE id = ?", (id,))
    flash("Marcaje eliminado.", "ok")
    return redirect(request.referrer or url_for("marcajes"))


# ---------------------------------------------------------------- Reportes
def _params_reporte():
    hoy = date.today()
    desde = fecha_param("desde", hoy.replace(day=1))
    hasta = fecha_param("hasta", hoy)
    return desde, hasta, request.args.get("codigo") or None, request.args.get("departamento") or None


@app.route("/reportes")
def reportes():
    desde, hasta, codigo, depto = _params_reporte()
    tipo = request.args.get("tipo", "resumen")
    if tipo not in calculo.REPORTES:
        tipo = "resumen"
    with db() as con:
        filas = calculo.detalle(con, desde, hasta, codigo, depto)
        emps = con.execute("SELECT codigo, nombre FROM empleados WHERE activo = 1 ORDER BY nombre").fetchall()
        deptos = [r[0] for r in con.execute("SELECT DISTINCT departamento FROM empleados "
                                            "WHERE departamento <> '' ORDER BY 1")]
    columnas, datos, total = calculo.tabla(filas, tipo)
    return render_template("reportes.html", columnas=columnas, datos=datos, total=total, tipo=tipo,
                           REPORTES=calculo.REPORTES, emps=emps, deptos=deptos,
                           desde=desde, hasta=hasta, codigo=codigo or "", depto=depto or "")


@app.route("/reportes/excel")
def reporte_excel():
    desde, hasta, codigo, depto = _params_reporte()
    tipo = "completo" if request.args.get("todos") else request.args.get("tipo", "completo")
    tipos = [tipo] if tipo in calculo.REPORTES else list(calculo.REPORTES)
    with db() as con:
        filas = calculo.detalle(con, desde, hasta, codigo, depto)
        nombre_emp = con.execute("SELECT nombre FROM empleados WHERE codigo = ?", (codigo,)).fetchone() if codigo else None
    subtitulo = " · ".join(x for x in (f"Departamento: {depto}" if depto else "",
                                       f"Empleado: {nombre_emp['nombre']}" if nombre_emp else "") if x)
    nombre = f"{tipo}_{desde:%Y%m%d}_{hasta:%Y%m%d}.xlsx"
    return Response(calculo.excel(filas, desde, hasta, tipos, subtitulo),
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename={nombre}"})


# ---------------------------------------------------------------- Permisos, licencias y feriados
@app.route("/permisos", methods=["GET", "POST"])
def permisos():
    hoy = date.today()
    if request.method == "POST":
        f = request.form
        hd, hh = f.get("hora_desde", ""), f.get("hora_hasta", "")
        if f["hasta"] < f["desde"]:
            flash("La fecha final no puede ser anterior a la inicial.", "error")
        elif bool(hd) != bool(hh) or (hd and hh <= hd):
            flash("Para un permiso por horas indica la hora de inicio y una hora de fin posterior; "
                  "déjalas vacías si es por día completo.", "error")
        else:
            with db() as con:
                con.executemany(
                    "INSERT INTO ausencias (codigo, tipo, desde, hasta, hora_desde, hora_hasta, documento, motivo) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [(c, f["tipo"].strip(), f["desde"], f["hasta"], hd, hh, f.get("documento", "").strip(),
                      f.get("motivo", "").strip()) for c in f.getlist("codigos")])
            flash(f"{f['tipo']} registrado para {len(f.getlist('codigos'))} empleado(s).", "ok")
        return redirect(url_for("permisos"))

    desde = fecha_param("desde", hoy - timedelta(days=60))
    hasta = fecha_param("hasta", hoy + timedelta(days=365))
    codigo = request.args.get("codigo", "")
    sql = ("SELECT a.*, e.nombre, e.departamento FROM ausencias a JOIN empleados e ON e.codigo = a.codigo "
           "WHERE a.desde <= ? AND a.hasta >= ?")
    params = [hasta.isoformat(), desde.isoformat()]
    if codigo:
        sql += " AND a.codigo = ?"
        params.append(codigo)
    with db() as con:
        lista = con.execute(sql + " ORDER BY a.desde DESC", params).fetchall()
        emps = con.execute("SELECT codigo, nombre, departamento FROM empleados WHERE activo = 1 "
                           "ORDER BY nombre").fetchall()
        feriados = con.execute("SELECT * FROM feriados WHERE fecha >= ? ORDER BY fecha",
                               (f"{hoy.year - 1}-01-01",)).fetchall()
    return render_template("permisos.html", lista=lista, emps=emps, feriados=feriados, hoy=hoy,
                           desde=desde, hasta=hasta, codigo=codigo, tipos=calculo.TIPOS_AUSENCIA)


@app.post("/permisos/<int:id>/borrar")
def borrar_permiso(id):
    with db() as con:
        con.execute("DELETE FROM ausencias WHERE id = ?", (id,))
    flash("Permiso eliminado.", "ok")
    return redirect(request.referrer or url_for("permisos"))


@app.post("/feriados")
def nuevo_feriado():
    with db() as con:
        con.execute("INSERT OR REPLACE INTO feriados VALUES (?, ?)",
                    (request.form["fecha"], request.form.get("descripcion", "").strip()))
    flash("Feriado guardado.", "ok")
    return redirect(url_for("permisos") + "#feriados")


@app.post("/feriados/<fecha>/borrar")
def borrar_feriado(fecha):
    with db() as con:
        con.execute("DELETE FROM feriados WHERE fecha = ?", (fecha,))
    flash("Feriado eliminado.", "ok")
    return redirect(url_for("permisos") + "#feriados")


# ---------------------------------------------------------------- Ajustes
@app.route("/ajustes", methods=["GET", "POST"])
def ajustes():
    with db() as con:
        if request.method == "POST":
            accion = request.form.get("accion")
            if accion == "reloj":
                for clave in ("reloj_ip", "reloj_puerto", "reloj_clave", "intervalo_min"):
                    guardar_ajuste(con, clave, request.form.get(clave, "").strip())
                flash("Datos del reloj guardados.", "ok")
            elif accion == "reglas":
                guardar_ajuste(con, "extra_minimo_min", int(request.form.get("extra_minimo_min") or 0))
                flash("Reglas de cálculo guardadas.", "ok")
            elif accion == "correo":
                for clave in ("correo_hora", "correo_destinos", "smtp_servidor", "smtp_puerto",
                              "smtp_seguridad", "smtp_usuario"):
                    guardar_ajuste(con, clave, request.form.get(clave, "").strip())
                if request.form.get("smtp_clave"):  # vacío = conservar la contraseña guardada
                    guardar_ajuste(con, "smtp_clave", request.form["smtp_clave"])
                guardar_ajuste(con, "correo_activo", "1" if request.form.get("correo_activo") else "0")
                flash("Configuración de correo guardada.", "ok")
            elif accion == "clave":
                if not check_password_hash(ajuste(con, "admin_hash"), request.form.get("actual", "")):
                    flash("La contraseña actual no es correcta.", "error")
                elif len(request.form.get("nueva", "")) < 6:
                    flash("La nueva contraseña debe tener al menos 6 caracteres.", "error")
                else:
                    guardar_ajuste(con, "admin_hash", generate_password_hash(request.form["nueva"]))
                    flash("Contraseña cambiada.", "ok")
            return redirect(url_for("ajustes"))
        datos = {c: ajuste(con, c) for c in ("reloj_ip", "reloj_puerto", "reloj_clave", "intervalo_min",
                                             "ultima_sync", "ultimo_error", "correo_activo", "correo_hora",
                                             "correo_destinos", "smtp_servidor", "smtp_puerto", "smtp_seguridad",
                                             "smtp_usuario", "correo_estado", "extra_minimo_min")}
        datos["hay_clave_smtp"] = bool(ajuste(con, "smtp_clave"))
        clave_por_defecto = check_password_hash(ajuste(con, "admin_hash"), "admin")
    return render_template("ajustes.html", d=datos, clave_por_defecto=clave_por_defecto)


@app.post("/ajustes/importar")
def importar_usb():
    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename:
        flash("Selecciona el archivo attlog.dat de la memoria USB.", "error")
    else:
        leidos, nuevos = zk_sync.importar_attlog(archivo.read().decode("utf-8", errors="ignore"))
        flash(f"Archivo importado: {leidos} marcajes leídos, {nuevos} nuevos.", "ok")
    return redirect(url_for("ajustes"))


@app.post("/ajustes/correo-prueba")
def correo_prueba():
    try:
        faltas, tardes = correo.enviar(destinos=request.form.get("destino") or None)
        flash(f"Correo de prueba enviado ({faltas} inasistencias, {tardes} tardanzas de hoy).", "ok")
    except Exception as e:
        flash(f"No se pudo enviar el correo: {e}", "error")
    return redirect(url_for("ajustes") + "#correo")


if __name__ == "__main__":
    puerto = int(os.environ.get("PUERTO", 5000))
    con_reloj = "--sin-reloj" not in sys.argv
    if con_reloj:
        zk_sync.iniciar_sincronizacion_automatica()
    correo.iniciar_envio_diario(zk_sync.sincronizar if con_reloj else None)
    print(f"\n  Sistema de asistencia listo: abre http://localhost:{puerto} en el navegador")
    print("  Usuario: administrador   Contraseña inicial: admin\n")
    from waitress import serve
    serve(app, host="0.0.0.0", port=puerto, threads=8)
