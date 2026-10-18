"""Alerta diaria por correo con las inasistencias y tardanzas del día."""
import logging
import smtplib
import threading
import time
from datetime import date, datetime
from email.message import EmailMessage
from html import escape

import calculo
from db import ajuste, db, guardar_ajuste

log = logging.getLogger("correo")


def _tabla_html(titulo, columnas, datos, vacio):
    if not datos:
        return f"<h3>{titulo}</h3><p style='color:#1e7a3c'>{vacio}</p>"
    cab = "".join(f"<th style='text-align:left;padding:5px 8px;background:#1f4e78;color:#fff'>{escape(c)}</th>"
                  for c in columnas)
    filas = "".join("<tr>" + "".join(f"<td style='padding:5px 8px;border-bottom:1px solid #ddd'>{escape(str(v))}</td>"
                                     for v in fila) + "</tr>" for fila in datos)
    return (f"<h3>{titulo} ({len(datos)})</h3>"
            f"<table style='border-collapse:collapse;font:14px Segoe UI,Arial'><tr>{cab}</tr>{filas}</table>")


def enviar(dia=None, destinos=None):
    """Envía el reporte del día. Devuelve (inasistencias, tardanzas)."""
    dia = dia or date.today()
    with db() as con:
        cfg = {c: ajuste(con, c) for c in ("smtp_servidor", "smtp_puerto", "smtp_seguridad", "smtp_usuario",
                                           "smtp_clave", "correo_destinos")}
        filas = calculo.detalle(con, dia, dia)
    destinos = [d.strip() for d in (destinos or cfg["correo_destinos"]).replace(";", ",").split(",") if d.strip()]
    if not destinos:
        raise ValueError("No hay correos de destino configurados.")

    faltas = calculo.filtrar(filas, "inasistencias")
    tardes = calculo.filtrar(filas, "tardanzas")
    permisos = calculo.filtrar(filas, "permisos")

    cuerpo = (
        f"<div style='font:14px Segoe UI,Arial;color:#1d2733'>"
        f"<h2 style='color:#1f4e78'>Asistencia del {calculo.DIAS[dia.weekday()]} {dia:%d/%m/%Y}</h2>"
        f"<p>Reporte generado a las {datetime.now():%H:%M}. "
        f"Inasistencias: <b>{len(faltas)}</b> · Tardanzas: <b>{len(tardes)}</b> · "
        f"Con permiso o licencia: <b>{len(permisos)}</b></p>"
        + _tabla_html("Inasistencias", ["Código", "Nombre", "Departamento", "Debía entrar"],
                      [(f["codigo"], f["nombre"], f["departamento"], f["h_entrada"]) for f in faltas],
                      "Sin inasistencias.")
        + _tabla_html("Tardanzas", ["Código", "Nombre", "Departamento", "Debía entrar", "Marcó", "Minutos tarde"],
                      [(f["codigo"], f["nombre"], f["departamento"], f["h_entrada"], f["entrada"], f["tardanza"])
                       for f in tardes], "Nadie llegó tarde.")
        + _tabla_html("Con permiso o licencia", ["Código", "Nombre", "Departamento", "Permiso"],
                      [(f["codigo"], f["nombre"], f["departamento"], f["ausencia"]) for f in permisos],
                      "Nadie tiene permiso hoy.")
        + "<p style='color:#66717f;font-size:12px'>Las faltas solo cuentan a quienes ya pasaron su hora de entrada "
          "y tolerancia. Mensaje automático del sistema de control de asistencia.</p></div>")

    msg = EmailMessage()
    msg["Subject"] = f"Asistencia {dia:%d/%m/%Y}: {len(faltas)} inasistencias, {len(tardes)} tardanzas"
    msg["From"] = cfg["smtp_usuario"]
    msg["To"] = ", ".join(destinos)
    msg.set_content("Abra este correo en un programa que muestre HTML o revise el Excel adjunto.")
    msg.add_alternative(cuerpo, subtype="html")
    msg.add_attachment(calculo.excel(filas, dia, dia, ["inasistencias", "tardanzas", "permisos"]),
                       maintype="application", subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       filename=f"asistencia_{dia:%Y%m%d}.xlsx")

    puerto = int(cfg["smtp_puerto"] or 587)
    if cfg["smtp_seguridad"] == "ssl":
        servidor = smtplib.SMTP_SSL(cfg["smtp_servidor"], puerto, timeout=30)
    else:
        servidor = smtplib.SMTP(cfg["smtp_servidor"], puerto, timeout=30)
        if cfg["smtp_seguridad"] == "starttls":
            servidor.starttls()
    with servidor:
        if cfg["smtp_usuario"]:
            servidor.login(cfg["smtp_usuario"], cfg["smtp_clave"])
        servidor.send_message(msg)
    return len(faltas), len(tardes)


def iniciar_envio_diario(sincronizar_antes=None):
    """Revisa cada minuto si llegó la hora de enviar la alerta del día (una vez al día)."""
    def bucle():
        while True:
            espera = 60
            try:
                with db() as con:
                    activo = ajuste(con, "correo_activo") == "1"
                    hora = ajuste(con, "correo_hora", "10:00")
                    enviado = ajuste(con, "ultimo_correo")
                hoy = date.today()
                if activo and datetime.now().strftime("%H:%M") >= hora and enviado != hoy.isoformat():
                    if sincronizar_antes:
                        try:
                            sincronizar_antes()
                        except Exception as e:
                            log.warning("No se pudo descargar el reloj antes del correo: %s", e)
                    faltas, tardes = enviar(hoy)
                    with db() as con:
                        guardar_ajuste(con, "ultimo_correo", hoy.isoformat())
                        guardar_ajuste(con, "correo_estado", f"Enviado el {datetime.now():%d/%m/%Y %H:%M}: "
                                                             f"{faltas} inasistencias, {tardes} tardanzas")
            except Exception as e:
                log.warning("Error al enviar el correo diario: %s", e)
                with db() as con:
                    guardar_ajuste(con, "correo_estado", f"ERROR {datetime.now():%d/%m/%Y %H:%M}: {e}")
                espera = 15 * 60  # reintenta en 15 minutos
            time.sleep(espera)

    threading.Thread(target=bucle, daemon=True, name="correo-diario").start()
