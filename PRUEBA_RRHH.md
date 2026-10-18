# Versión de prueba RRHH — DATATECH

1. Extraiga TODO el ZIP en una carpeta NUEVA. No lo ejecute dentro del ZIP.
2. Instale Python con Add python.exe to PATH.
3. Ejecute demo.bat para datos ficticios, o iniciar.bat para un sistema limpio.
4. Abra http://localhost:5000. Contraseña inicial: admin.
5. Si hay otra copia abierta en puerto 5000, ciérrela primero.

## Funciones verificadas
- Permisos, licencias, vacaciones por empleado o selección múltiple.
- Reportes por rango, persona y departamento: resumen, entradas/salidas,
  inasistencias, tardanzas, extras, permisos. Visualización y Excel.
- Alertas diarias por correo: configuración SMTP, activación y envío de prueba.
- Turnos 07:00–16:00, 08:00–18:00 y 07:00–13:00, lunes a viernes.
- Conexión ZKTeco y carga USB attlog.dat.
- Login con logo DATATECH y contacto 829-712-8706.

## Configuración requerida
Asigne a cada empleado su horario y departamento. Confirme con RRHH tolerancia,
descanso y mínimo de extras. Se precargan 10 minutos de tolerancia, descanso
60 minutos en turnos largos y 0 en el corto; son editables.
Las extras se calculan por tiempo trabajado por encima de la jornada neta,
no representan autorización de pago ni recargos monetarios.
Los turnos anteriores y asignaciones existentes se conservan.

## Correo y reloj
La prueba local valida SMTP mediante simulación, SIN enviar correos.
Debe configurar y probar la cuenta institucional y la conectividad con su
reloj en su PC. El proveedor debe permitir autenticación SMTP con contraseña.
El envío diario requiere PC encendida, programa abierto y hora local correcta.

## Datos
Este ZIP no contiene bases de datos existentes ni credenciales.
Se crean al iniciar. Para usar sus datos reales, haga respaldo y copie
asistencia.db a la nueva carpeta con ambos sistemas cerrados.
No reemplace su base con demo.db. demo.bat regenera sus datos ficticios.

## Validación realizada
Pruebas automáticas con SQLite temporal: acceso, pantallas, alta de empleado,
marcajes, vacaciones, cálculo de faltas/tardanzas/extras, exclusión de fin
 de semana, filtros y archivos Excel, SMTP simulado.
No se verificó conexión física ZKTeco ni entrega real de correo.
