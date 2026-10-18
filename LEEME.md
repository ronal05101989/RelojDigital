# Control de asistencia con reloj ZKTeco

Programa para llevar la asistencia de los empleados. Descarga automáticamente los marcajes
de huella del reloj ZKTeco por la red y los muestra en un panel web con reportes en Excel.

## Instalación (una sola vez)

1. Instala Python desde https://www.python.org/downloads/ y marca la casilla **"Add python.exe to PATH"**.
2. Haz doble clic en **`iniciar.bat`**. La primera vez descarga lo necesario (1-2 minutos).
3. Se abre el navegador en http://localhost:5000. La contraseña inicial es **admin** (cámbiala en Ajustes).

Para probar sin el reloj, con 100 empleados y un mes de datos ficticios, usa **`demo.bat`**.

## Configurar el reloj

1. En el reloj: **Menú → Comunicación → Ethernet** y anota la **IP** (ej.: 192.168.1.201).
2. En el programa: **Ajustes** → escribe la IP, puerto `4370` y la clave de comunicación (normalmente `0`).
3. Pulsa **"Probar conexión y descargar ahora"**. Los empleados registrados en el reloj aparecen solos.
4. En **Horarios** crea los turnos y en **Empleados** asígnalos (puedes marcar varios a la vez).

La PC donde corre el programa debe estar en la misma red que el reloj y encendida en horario laboral.
El programa descarga el reloj cada 5 minutos (se puede cambiar). Desde otras PCs de la oficina se puede
entrar con `http://IP-DE-ESTA-PC:5000`.

## Cómo calcula

| Concepto | Regla |
|---|---|
| Entrada / salida | Primer y último marcaje del día |
| Tardanza | Si marca después de *entrada + tolerancia*; cuenta los minutos desde la hora de entrada |
| Falta | Día laborable de su horario sin ningún marcaje ni permiso de día completo |
| Permiso por horas | Si cubre la hora de entrada, la tardanza se mide desde que termina el permiso |
| Feriado | Nadie tiene falta; quien trabaja suma todo como horas extra |
| Sin marcaje de salida | Solo marcó una vez (o dos veces seguidas en menos de 5 min) |
| Horas trabajadas | Salida − entrada − descanso (el descanso se descuenta si estuvo 6 h o más) |
| Horas extra | Trabajado por encima de la jornada, solo si pasa del mínimo (30 min por defecto, en Ajustes); en días libres todo cuenta como extra |

Los olvidos se corrigen en **Marcajes → Agregar marcaje manual** (queda registrado con su motivo).

## Permisos, licencias, vacaciones y feriados

En **Permisos** se registran por día completo o por horas, para uno o varios empleados a la vez, con
n.° de documento y motivo. Abajo en la misma pantalla se cargan los feriados.

## Reportes

En **Reportes** se filtra por rango de fechas, departamento y persona, y se elige el tipo:
Resumen por empleado, Entradas y salidas, Inasistencias, Tardanzas, Horas extra, Permisos y licencias.
Cada uno se descarga en Excel, o todos juntos en un Excel con una hoja por tipo.

## Alerta diaria por correo

En **Ajustes → Alerta diaria por correo**: activa el envío, elige la hora (ej. 10:00), los correos de destino
y los datos de la cuenta que envía.

- Office 365 / Outlook institucional: `smtp.office365.com`, puerto 587, STARTTLS. Sistemas debe habilitar
  "SMTP autenticado" en esa cuenta.
- Gmail / Google Workspace: `smtp.gmail.com`, puerto 587, STARTTLS, con una "contraseña de aplicación".

Usa "Enviar prueba" para verificar. El correo lleva las tablas de inasistencias, tardanzas y permisos del día
y el Excel adjunto. Se recomienda una cuenta exclusiva para esto (la contraseña queda guardada en `asistencia.db`).

## Limitaciones conocidas

- Turnos nocturnos que cruzan la medianoche (ej. 22:00–06:00) no se calculan bien todavía.
- La PC debe estar encendida a la hora del correo; si estaba apagada, se envía al encenderla ese mismo día.
- Fotos al marcar: las toma el propio reloj solo si el modelo tiene cámara; este programa no las descarga.

## Respaldo

Todos los datos están en el archivo `asistencia.db`. Cópialo a otro lugar de vez en cuando.
