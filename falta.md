## Qué falta — 3 cosas concretas

1. **Desplegar el worker que lea la casilla real y mande al webhook** (Fase 4). Sin esto no llega ningún reporte DMARC real a la app, aunque todo el resto ya esté listo.
2. **Configurar `SMTP_*` en `.env`** (Fase 6) para que las alertas (`send_alert_email`) manden correo — hoy se guardan en la base pero nunca se notifican.
3. **Programar `jobs/recheck_domains.py` como Cron Job en Railway** (Fase 5) — el código de vigilancia DNS periódica ya existe, pero no corre solo, hay que agendarlo.


## Notas sobre configuración (dudas ya resueltas)

* `DMARC_REPORTS_MAILBOX` y `DMARC_WEBHOOK_SECRET` son para la app Flask (a qué casilla apunta el `rua=`, y qué secreto exige el webhook) — no son credenciales de acceso a la casilla.

* Las credenciales IMAP de la casilla (host/usuario/password) van en `config/parsedmarc.ini` (sección `[imap]`), no en `.env` — ver `config/parsedmarc.ini.example`.
* `SMTP_*` es para mandar los correos de alerta, no para recibir reportes — son cosas independientes.
