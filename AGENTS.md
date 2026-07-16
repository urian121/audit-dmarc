# Agente: Backend de Validación de Autenticación de Correo

## Reglas de comunicación

* Responder siempre en español.
* Respuestas directas y concisas, sin rodeos.

## Reglas de código

* Cada función o método lleva un comentario de una línea (docstring) explicando qué hace.
* No dejar que `app.py` acumule lógica de negocio: la validación/consulta de dominios va en `services/`, los helpers puros (sin dependencias de Flask ni de checkdmarc/dkimpy) van en `utils/`. `app.py` sólo define rutas y arma la respuesta.
* **Nunca editar, agregar ni eliminar datos de la base de datos (filas, columnas, tablas) sin autorización explícita del usuario** — ni en local ni en producción. Incluye migraciones, `INSERT`/`UPDATE`/`DELETE` manuales, y scripts de limpieza. Preguntar primero y esperar confirmación antes de tocar la base real.

## Reglas de frontend

* Evitar JavaScript "puro"/manual para la interactividad de la UI (fetch + manipulación de DOM a mano).
* Usar [htmx](https://htmx.org/) para peticiones AJAX, swapping parcial del DOM, indicadores de carga y validación. Documentación: [htmx.org/docs](https://htmx.org/docs/)
* El servidor responde con fragmentos HTML renderizados (Jinja2, en `templates/partials/`) a las rutas que consume htmx — no JSON. El JSON queda para la API pública (`/api/...`).
* Si hace falta lógica puntual en el cliente, preferir `hx-on:`/`hx-*` declarativos antes que añadir un archivo `.js` nuevo.
* Todo botón/link estilizado como botón (`bg-[#ef5184] ... text-zinc-950`) lleva un ícono SVG inline junto al texto — sin librerías de íconos externas, `stroke="currentColor"` para heredar el color.
* Las 5 páginas completas cargan [Pace.js](https://github.com/CodeByZach/pace) para la barra de progreso de navegación (elegido sobre NProgress por ser automático, sin código propio para iniciar/terminar la barra). `window.paceOptions` se define **antes** de cargar `pace.min.js`, con timings más rápidos que el default (`initialRate: 0.3` en vez de `0.03`, que es el que más se nota en páginas rápidas) — los defaults de Pace están pensados para páginas más pesadas que las de esta app.

## Arquitectura

* `app.py` — sólo rutas Flask, delega a `services/`.
* `services/checkdmarc_service.py` — corre `checkdmarc` + DKIM (`dkimpy`) + arma las instrucciones de DNS para el monitoreo.
* `services/card_builder.py` — convierte el resultado crudo en "cards" (ok/warn/fail) y en los riesgos priorizados que se muestran arriba de ellas.
* `services/monitoring_service.py`, `services/reports_service.py`, `services/notifications.py` — alta/estado de dominios monitoreados, ingesta de reportes DMARC, envío de alertas por correo.
* `utils/` — helpers puros, sin dependencias de Flask/checkdmarc (`domain_validation.py`, `formatting.py`, `dmarc_builder.py`).
* `models/` — `db = SQLAlchemy()` + modelos en `monitoring.py` y `user.py`. Persistencia en **Postgres** (ver sección propia abajo).
* `jobs/recheck_domains.py` — vigilancia DNS periódica (pensado como Railway Cron, no servicio de larga duración).

## Checker de un dominio (`/`, `POST /check`, `GET /api/check/<domain>`)

* DKIM: `checkdmarc` no lo reporta, así que se prueba una lista de selectores comunes contra `<selector>._domainkey.<domain>` con `dkimpy`, más un selector opcional vía `?selector=`.
* Ausencia vs. falla: para MTA-STS/TLS-RPT/BIMI (`SOFT_ABSENCE_KEYS` en `card_builder.py`), que el registro no exista es ADVERTENCIA, no FALLA — son protocolos opcionales, a diferencia de SPF/DMARC. La pista para distinguir "no existe" de "existe pero mal" es el texto "does not exist" en el error de checkdmarc.
* Los timeouts de DNS se clasifican como `na` (N/D) en todas las tarjetas, nunca como FALLA — no son evidencia de mala configuración, y no afectan el `score`.
* Warnings de `checkdmarc` en inglés se traducen (`translate_warnings()` en `utils/formatting.py`) sólo para los patrones ya identificados; lo no reconocido se muestra crudo. Confirmar el texto exacto antes de agregar un patrón nuevo (puede variar entre versiones de checkdmarc).
* Al agregar nuevos tags/mecanismos DMARC o SPF a traducir, extender los diccionarios de `card_builder.py` (`DMARC_POLICY_LABELS`, `SPF_MECHANISM_LABELS`, etc.) — no hardcodear strings sueltos en la plantilla.
* No se muestra todo lo que trae `checkdmarc`: sin tarjeta de SOA (no es de autenticación de correo), y MX filtra warnings de PTR/DNS-inverso (ruido del proveedor de correo, no corregible por el dueño del dominio).
* **Proveedor de DNS detectado** (`detect_dns_providers()`, `KNOWN_DNS_PROVIDERS` en `card_builder.py`): la tarjeta de Nameservers muestra qué proveedor de DNS usa el dominio (Cloudflare, Route 53, GoDaddy, etc.), por coincidencia de texto contra los hostnames de NS que ya trae `checkdmarc` — no hace ninguna consulta nueva. Mismo patrón que `detect_mail_provider()` (SPF/MX), pero acá no hay riesgo de sugerir nada que rompa algo — es sólo informativo, así que se muestra siempre que haya match, sin advertencias.
* "Riesgos y qué hacer" (`build_risks()`): grid con sólo los protocolos en fail/warn, severidad (Alta/Media/Baja) y una acción concreta — no repite la explicación de la tarjeta de abajo. Sólo TLS-RPT muestra un registro DNS de ejemplo (casilla ficticia, sin botón de copiar a propósito). No se hace lo mismo con SPF (un valor genérico podría rechazar correo legítimo), DKIM (lo publica el proveedor de correo) ni BIMI/MTA-STS (necesitan más que un TXT) — y nunca se sugiere la casilla real de monitoreo acá, porque este checker no tiene relación de registro con el dominio.
* Resumen con IA (`services/ai_summary.py`) es 100% opcional: sin `OPENAI_PROJECT_API_KEY`, o si la llamada falla/tarda, no se muestra y el resto de la auditoría sigue funcionando igual. Sólo conectado en el flujo HTML, nunca en `/api/check/<domain>`.
* `build_summary()`: una advertencia pesa la mitad que un ok en el `score`; una falla no suma nada.

## Monitoreo continuo de DMARC

A diferencia del checker (auditoría puntual, sin guardar nada), esto vigila dominios registrados a lo largo del tiempo. Dos mecanismos:

* **Vigilancia DNS** (`jobs/recheck_domains.py`): reutiliza `run_check()`, compara contra el último `DomainSnapshot`, genera `Alert` si cambió la política DMARC, el SPF, o los selectores DKIM encontrados.
* **Vigilancia de tráfico real** (`services/reports_service.py`): ingiere reportes DMARC agregados vía [parsedmarc](https://github.com/domainaware/parsedmarc) (webhook), compara remitentes reales contra el SPF declarado (heurística por texto de organización del ASN, no CIDR exacto) y genera `Alert` tipo `unknown_sender`.
* `Alert.kind_label` (property en `models/monitoring.py`, dict `KIND_LABELS`): traduce el `kind` interno (`unknown_sender`, `policy_changed`, etc.) a un texto legible para el dashboard (`dashboard.html` usa `alert.kind_label`, no `alert.kind`, para lo que se muestra) — el valor crudo (`alert.kind`) se sigue usando para la clase de color del badge, sin traducir. Si se agrega un `kind` nuevo, sumarlo a `KIND_LABELS` — si no, se muestra el valor crudo en inglés como fallback.
* **Comparación de remitente en `detect_unknown_senders()`**: no basta un solo substring — un nombre de organización de ASN corto (ej. "Zoho") suele aparecer dentro del hostname del target de SPF ("sender.zohobooks.com"), pero uno largo/descriptivo (ej. "Google (Including Gmail and Google Workspace)") no es substring literal de "_spf.google.com" ni al revés, aunque sea el mismo proveedor — causaba falsos positivos reales (confirmado con reportes reales de producción). Por eso se comparan dos formas a la vez: substring directo (cubre nombres cortos) **y** la palabra clave del dominio base del target (`checkdmarc.get_base_domain()`) contra las palabras sueltas del nombre de organización (cubre nombres largos). Si se vuelve a ver un falso positivo/negativo, agregar el caso a los dos test manuales antes de tocar la lógica.
* **Consultas DNS de la pantalla de instrucciones en paralelo** (`build_extra_dns_instructions()`, `build_dns_screen_data()` en `checkdmarc_service.py`): son ~5 consultas independientes (DMARC, SPF, TLS-RPT, BIMI, MTA-STS), cada una con su propio timeout de 5s — corridas una tras otra podían sumar hasta ~20-25s en el peor caso. Se paralelizaron con `ThreadPoolExecutor` (son I/O de red, no CPU) — el tiempo total queda acotado por la más lenta, no por la suma. `app.py` usa `build_dns_screen_data()` (no las funciones sueltas) en los dos lugares donde se necesitan juntas.

Piezas clave:

* Rutas en `app.py`: `GET/POST /monitoreo`, `GET /monitoreo/lista`, `GET /monitoreo/<token>`, `GET /monitoreo/<token>/dns`, `POST /monitoreo/<token>/toggle`, `POST /monitoreo/<token>/verificar-dns`, `POST /monitoreo/dns/preview`, `POST /webhooks/dmarc-aggregate/<secret>`. El secreto del webhook va en la URL, no en un header (no está confirmado que parsedmarc permita headers custom); si no matchea `DMARC_WEBHOOK_SECRET`, responde 404 (no 401) para no delatar que la ruta existe. URLs en español a propósito (`/monitoreo`), excepto el webhook.
* **Activar/desactivar** (`MonitoredDomain.is_active`): pausar en vez de eliminar — reversible, y evita perder historial por error. Inactivo = se salta la vigilancia DNS y se ignoran los reportes entrantes, pero se conserva el historial.
* **Verificación de DNS** (`dns_verified`/`dns_verified_at` para DMARC, `tls_rpt_verified`/`tls_rpt_verified_at` para TLS-RPT): botón "Verificar" (htmx) en cada card que confirma en vivo si el `rua=` publicado ya incluye la casilla de monitoreo; se guarda en la base, no se reconsulta sola en cada visita. SPF no tiene botón de verificar — nunca le sugerimos un valor a publicar (ver más abajo), así que no hay nada específico que confirmar más allá de lo que la card ya muestra en cada carga.
* **Generador de política DMARC** (`utils/dmarc_builder.build_dmarc_value()`): controles p/sp/pct/adkim/aspf en la pantalla de instrucciones DNS, recalculados en vivo vía htmx. Es sólo una vista previa — deliberadamente no se persiste la política elegida. Default de `pct` (`build_dmarc_dns_instructions()`): **25%** sólo cuando el dominio no tiene ningún registro DMARC todavía (arranque gradual sugerido para cuando más adelante se suba `p` a cuarentena/rechazo — a `p=none` no le afecta, pct sólo aplica con enforcement); si ya existe un registro, se respeta el valor real publicado (100% si no trae `pct=` explícito, como implica la RFC), nunca se le inventa un 25%. `adkim`/`aspf` (`build_dmarc_value()`) siempre se muestran en el `Valor` generado (`adkim=r; aspf=r;` por default), a diferencia de `sp`/`pct` que se omiten cuando están en su default — decisión explícita del usuario, para que la relajación de alineación quede siempre visible aunque sea la opción por defecto. Mismo criterio que `pct=25`: si el dominio no tiene ningún registro DMARC todavía, `ruf=` se sugiere igual a `rua=` (misma casilla, para también recibir reportes de fallos individuales); si ya existe un registro (con o sin `ruf=` propio), se respeta tal cual, nunca se le agrega uno de más. La opción "Igual que p" de `sp` (sin tag `sp=`) se mantiene a propósito, aunque hoy con `p=none` se vea idéntica a "Ninguno" (`sp=none` explícito) — se diferencian en cuanto `p` deja de ser `none`: "Igual que p" sigue subiendo con `p` a futuro, "Ninguno" deja los subdominios sin protección para siempre.
* **Instrucciones de DNS** (`build_dmarc_dns_instructions()`): si el dominio ya tiene DMARC, agrega la casilla de monitoreo a su `rua=` existente; si no tiene ninguno, sugiere uno nuevo en `p=none` (nunca bloquea correo).
* **Otros protocolos en la pantalla de DNS** (`build_extra_dns_instructions()`): además de DMARC, la pantalla muestra TLS-RPT (valor real sugerido, mismo criterio que DMARC — nunca bloquea correo, seguro de auto-generar con la casilla de monitoreo), SPF, y BIMI/MTA-STS (sólo lectura + instrucciones, porque ninguno se resuelve con un TXT solo: BIMI necesita un logo hospedado, MTA-STS un archivo de política en una URL aparte). DKIM y DNSSEC son sólo texto instructivo, sin consulta a DNS — DKIM porque lo publica el proveedor de correo, DNSSEC porque no es un registro TXT (se activa en el panel del proveedor de DNS/registrador). Los botones de copiar de esta pantalla usan las macros `copy_icon_button()`/`copy_text_button()` en `registered.html` — no repetir el SVG a mano si se agrega otro campo copiable.
* **SPF con detección de proveedor** (`detect_mail_provider()`, `KNOWN_MX_PROVIDERS` en `checkdmarc_service.py`): si el dominio no tiene SPF, nunca se sugiere un valor final (podría rechazar correo legítimo si no conocemos todos los remitentes) — pero sí se muestran los hostnames MX reales (siempre, como ayuda visual para identificar el proveedor, igual que un `nslookup -type=MX` o MXToolbox) y, si alguno matchea un proveedor conocido (Google/Microsoft/Zoho/etc., heurística por texto, no oficial), se agrega un `include:` de partida. Si no matchea ninguno, se muestran los mismos hostnames con una nota de "no lo reconocimos, búscalo tú" — nunca se oculta la lista sólo porque no matcheó nada. En ambos casos se agrega la nota de sumar herramientas de marketing/transaccionales y servidores propios antes de publicar.
* `send_alert_email()`: el webhook sólo crea la `Alert` en la base; el envío del correo se centraliza en el cron de `jobs/recheck_domains.py`, para no bloquear la respuesta del webhook con una llamada SMTP.

## Login (Flask-Login)

* `models/user.py` (`User`, con `UserMixin`): sólo `email` + `password_hash` (hash con `werkzeug.security`, ya viene con Flask — no se instaló ninguna librería nueva para esto) + `created_at`. `services/auth_service.py`: `register_user()`/`authenticate()`.
* `MonitoredDomain.user_id` (FK a `users.id`, **nullable**): cada dominio pertenece a quien lo registró (`register_domain()` ahora exige `user_id`); `list_domains(user_id)` filtra por dueño. Es nullable porque quedaron dominios reales registrados antes de que existiera el login — se backfillean a mano, no se les asigna un dueño automático. Si el dominio ya existe y pertenece a otro usuario, `register_domain()` devuelve `(None, False)` en vez de reactivarlo o duplicarlo.
* Rutas gateadas con `@login_required`: `/` (checker), `POST /check`, `GET/POST /monitoreo` (alta), `GET /monitoreo/lista`. **No gateadas a propósito**: `GET /api/check/<domain>` (API JSON pública, documentada como de acceso libre) y todas las rutas por `access_token` (`/monitoreo/<token>`, `/dns`, `/toggle`, `/verificar-dns`) — el token ya es su propio mecanismo de acceso tipo "link mágico", independiente del login.
* Rutas de sesión: `GET/POST /registro`, `GET/POST /ingresar` (respeta `?next=` para volver a la ruta que pedía login), `POST /salir`. Nombres de función `auth_register`/`auth_login`/`auth_logout` — no chocan con nada de `services/`.
* `@login_manager.unauthorized_handler` (`handle_unauthorized()`): personaliza el redirect que hace Flask-Login cuando `@login_required` bloquea una petición — si el destino era la home sin parámetros (`/`, el caso más común, ej. al entrar directo al dominio), redirige a `/ingresar` limpio, sin `?next=%2F`. Para cualquier otra ruta, sí agrega `?next=<ruta>` (necesario para volver ahí después de loguearse).
* `app.secret_key`: si no hay `SECRET_KEY` en el entorno, se genera una al azar en cada arranque (las sesiones activas se invalidan en cada reinicio/deploy, pero la app no se rompe). Para sesiones persistentes en producción, definir `SECRET_KEY` en Railway.
* `current_user` está disponible en cualquier template sin pasarlo explícitamente (Flask-Login registra su propio context processor) — `header.html` lo usa para mostrar "Ingresar" o "Salir".

## Base de datos: Postgres

Se migró por completo desde SQLite (antes de tener datos reales, sin nada que preservar). `DATABASE_URL` es obligatoria — `app.py` lanza un `RuntimeError` claro si falta, sin fallback local.

* Railway/Heroku entregan la variable con esquema `postgres://`; SQLAlchemy 2.x sólo reconoce `postgresql://` — `app.py` reescribe el prefijo automáticamente.
* No hay Alembic. `db.create_all()` sólo crea tablas nuevas, no altera una existente para sumarle una columna. Se usó `db.drop_all()` + `db.create_all()` un par de veces mientras el proyecto estaba en pruebas sin datos reales — **ya no aplica**: desde que hay usuarios reales y reportes DMARC reales llegando (`octapus.io` y otros), cualquier columna nueva se agrega con `ALTER TABLE` manual (sintaxis Postgres: `DEFAULT FALSE`/`TRUE`, `TIMESTAMPTZ`, no la de SQLite), nunca borrando tablas. `drop_all()`/cualquier borrado sigue cayendo bajo la regla de "nunca tocar la base sin autorización explícita" — confirmar con el usuario cada vez.
* Postgres exige integridad referencial; SQLite no, por defecto. No hay ningún `.delete()` en el código hoy (se prefiere desactivar, ver arriba) — si se agrega uno, usar `db.session.delete(instancia)`, no `Query.delete()` en bloque, para que el `cascade` de las relaciones funcione.
* Usar siempre tipos de SQLAlchemy dialecto-agnósticos en los modelos (`db.Boolean`, `db.DateTime(timezone=True)`, `db.JSON`, etc.), nunca SQL crudo específico de un motor — es lo que permitió migrar de SQLite a Postgres sin tocar `models/monitoring.py`.

## Librerías base — no reimplementar su lógica

* **[checkdmarc](https://github.com/domainaware/checkdmarc)**: motor principal para SPF/DMARC/BIMI/MTA-STS/TLS-RPT/MX/DNSSEC/NS/SOA. Usarla siempre que sea posible.
* **[dkimpy](https://pypi.org/project/dkimpy/)**: única responsable de todo lo relacionado a DKIM (validar, firmar, ARC, RSA/Ed25519), apoyada en `dnspython` para las consultas DNS.
* **[parsedmarc](https://github.com/domainaware/parsedmarc)** (mismo autor que checkdmarc): ingesta/parseo de reportes DMARC agregados y SMTP TLS vía IMAP — sólo para monitoreo continuo, no para el checker puntual. **Consultar siempre su documentación** ante dudas de `config.ini`, variables `PARSEDMARC_*`, o el esquema del JSON que produce — no asumir sintaxis.

## Pendiente (fuera del alcance de código)

* Crear la casilla de correo real (`DMARC_REPORTS_MAILBOX`) y su TXT de verificación de destino externo (RFC 7489 §7.1) si vive en otro dominio.
* Desplegar el worker de parsedmarc como servicio aparte en Railway (`config/parsedmarc.ini.example`).
* Prueba end-to-end con reportes reales (tardan 24-48h en llegar).

## Restricciones

* No duplicar lógica ya resuelta por `checkdmarc`, `dkimpy` o `parsedmarc`.
* `dkimpy` únicamente para todo lo relacionado con DKIM.
* Arquitectura desacoplada: cualquiera de estas librerías debe poder sustituirse sin afectar el resto del sistema.
