# Qué hace la app hoy

**1. Checker puntual** (`/`, `/check`, `/api/check/<domain>`): audita cualquier dominio contra SPF, DMARC, DKIM, MX, DNSSEC, MTA-STS, TLS-RPT, BIMI y NS. Muestra un resumen con IA, cards de "riesgos y qué hacer" con severidad y acción concreta, y no guarda nada — es 100% bajo demanda.

**2. Monitoreo continuo** (`/monitoreo/...`): permite registrar un dominio, genera las instrucciones exactas de DNS para DMARC/TLS-RPT/SPF (con detección de proveedor por MX y generador de política interactivo), verifica en vivo si ya se publicó el cambio, y deja un dashboard con historial de reportes y alertas — persistido en Postgres.

---

## Qué falta — 3 cosas concretas

1. **Desplegar el worker que lea la casilla real y mande al webhook** (Fase 4). Sin esto no llega ningún reporte DMARC real a la app, aunque todo el resto ya esté listo.
2. **Configurar `SMTP_*` en `.env`** (Fase 6) para que las alertas (`send_alert_email`) manden correo — hoy se guardan en la base pero nunca se notifican.
3. **Programar `jobs/recheck_domains.py` como Cron Job en Railway** (Fase 5) — el código de vigilancia DNS periódica ya existe, pero no corre solo, hay que agendarlo.

## Estado por fase

| Fase | Qué es | Estado |
|---|---|---|
| 0 | Casilla de correo + MX + TXT de verificación externa (RFC 7489 §7.1) | ⚠️ Parcial — la casilla (`programadorphp2017@gmail.com`) ya recibe correo, pero el TXT de autorización (`_report._dmarc.gmail.com`) no está publicado; `checkdmarc` lo marca como warning en cada dominio que se registra |
| 1 | Persistencia (modelos + base de datos) | ✅ Hecho — migrado a Postgres |
| 2 | Alta de dominios + instrucciones de DNS | ✅ Hecho |
| 3 | Ingesta de reportes (webhook) | ✅ Código hecho y probado con payload simulado — falta que lleguen reportes reales |
| 4 | Worker de parsedmarc real en Railway | ❌ Pendiente/incierto — nunca se confirmó qué es ese otro repo ni si manda al webhook |
| 5 | Cron de vigilancia DNS (`jobs/recheck_domains.py`) | ✅ Código hecho — falta configurarlo como Cron Job en Railway |
| 6 | Notificaciones por email (`send_alert_email`) | ❌ Pendiente — `SMTP_*` no está configurado |
| 7 | UI del dashboard | ✅ Hecho |
| 8 | Prueba end-to-end con reportes reales | ❌ Bloqueada por las fases 0 y 4 |

## Notas sobre configuración (dudas ya resueltas)

* `DMARC_REPORTS_MAILBOX` y `DMARC_WEBHOOK_SECRET` son para la app Flask (a qué casilla apunta el `rua=`, y qué secreto exige el webhook) — no son credenciales de acceso a la casilla.
* Las credenciales IMAP de la casilla (host/usuario/password) van en `config/parsedmarc.ini` (sección `[imap]`), no en `.env` — ver `config/parsedmarc.ini.example`.
* `SMTP_*` es para mandar los correos de alerta, no para recibir reportes — son cosas independientes.
