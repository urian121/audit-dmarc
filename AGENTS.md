# Agente: Backend de Validación de Autenticación de Correo

## Reglas de comunicación

* Responder siempre en español.
* Respuestas directas y concisas, sin rodeos.

## Reglas de código

* Cada función o método debe llevar un comentario de una línea (docstring) explicando qué hace.
* No dejar que `app.py` acumule lógica de negocio: la validación/consulta de dominios va en `services/`, los helpers puros (sin dependencias de Flask ni de checkdmarc/dkimpy) van en `utils/`. `app.py` sólo define rutas y arma la respuesta.

## Reglas de frontend

* Evitar JavaScript "puro"/manual para la interactividad de la UI (fetch + manipulación de DOM a mano).
* Usar [htmx](https://htmx.org/) para peticiones AJAX, swapping parcial del DOM, indicadores de carga y validación de formularios. Documentación: [htmx.org/docs](https://htmx.org/docs/)
* El servidor debe responder con fragmentos HTML renderizados (Jinja2, en `templates/partials/`) a las rutas que consume htmx — no JSON. El JSON queda reservado para la API REST pública (`/api/...`).
* Si hace falta algo de lógica puntual en el cliente, preferir atributos `hx-on:` o `hx-*` declarativos antes que añadir un archivo `.js` nuevo.
* Todo botón o link estilizado como botón (las acciones principales tipo `bg-[#ef5184] ... text-zinc-950`) debe llevar un ícono SVG inline junto al texto — sin librerías de íconos externas, mismo patrón que el ícono de lupa en el botón "Analizar" de `templates/index.html` (`inline-flex items-center justify-center gap-2` + `<svg>` con `stroke="currentColor"` para heredar el color del texto).

## Estado actual

Proyecto en etapa inicial. Ya existe una separación básica por capas; todavía faltan `routes/` (Blueprints), `models/`, `exceptions/` y `tests/`.

Estructura actual:

* `app.py` — sólo define las rutas Flask y delega el trabajo a `services/`.
* `services/checkdmarc_service.py` — lógica de negocio: corre `checkdmarc` y el chequeo de DKIM.
* `services/card_builder.py` — convierte el resultado crudo en las "cards" que consume la plantilla (clasificación ok/warn/fail, severidad de ausencia, etc.).
* `utils/domain_validation.py` y `utils/formatting.py` — helpers puros (validar formato de dominio, aplanar valores de tags DMARC, etc.) sin lógica de negocio.
* Cada función/método tiene un comentario de una línea (docstring) explicando qué hace — mantenerlo así en el código nuevo.

Implementado:

* `GET /` — sirve el frontend (`templates/index.html`); si recibe `?domain=`, renderiza el resultado en el propio HTML (SSR).
* `POST /check` — endpoint HTML consumido por htmx (`hx-post` del formulario, `domain`/`selector` como campos del form). Devuelve el fragmento `templates/partials/check_result.html` renderizado. La URL del navegador se queda en `/` (a propósito, no se usa `HX-Push-Url`).
* `GET /api/check/<domain>` — API JSON: llama a `checkdmarc.check_domains()`, agrega el resultado de DKIM (ver abajo) y devuelve todo junto.
* Chequeo de DKIM con `dkimpy` (`services/checkdmarc_service.py`): como `checkdmarc` no reporta DKIM, se prueba una lista de selectores comunes (`default`, `selector1`, `selector2`, `google`, `k1`, `k2`, `s1`, `s2`, `dkim`, `mail`) contra `<selector>._domainkey.<domain>` usando `dkim.get_txt` y `dkim.load_pk_from_dns`. También acepta un selector adicional vía `?selector=`.
* `app.run()` escucha en `host="0.0.0.0"` y en el puerto de `$PORT` (default `5000`) — necesario para que Railway/PaaS puedan enrutar tráfico al contenedor; escuchar sólo en `127.0.0.1` deja la app inalcanzable desde afuera aunque el proceso arranque bien. `debug` se controla con `FLASK_DEBUG` (default `false`); no activarlo en producción, expone el debugger de Werkzeug.
* Severidad de MTA-STS, TLS-RPT y BIMI (`SOFT_ABSENCE_KEYS` en `services/card_builder.py`): `checkdmarc` no distingue "el registro no existe" de "existe pero está mal" (ambos casos llegan como el mismo `{error, valid:false}`); la única pista es que el texto de `error` contiene "does not exist". Por eso, para estos tres protocolos opcionales, la ausencia del registro se muestra como ADVERTENCIA y no como FALLA — un SPF/DMARC ausente sigue siendo FALLA porque son protocolos base, no opcionales. Cuando es ausencia, además se reemplaza el mensaje de error (en inglés) por uno propio en español.
* Timeouts de DNS (`is_timeout_error`/`friendly_error_message` en `utils/formatting.py`): un timeout ("resolution lifetime expired", "timed out") **no** es evidencia de mala configuración, sólo de que la consulta no respondió a tiempo — se clasifica como `na` (badge N/D, gris) en vez de FALLA, en **todas** las tarjetas (`status_of`, `record_status`, `mx_status`), no sólo en las de `SOFT_ABSENCE_KEYS`. El mensaje crudo en inglés se reemplaza por uno en español ("no se pudo verificar ahora mismo..."). Como `na` no suma ni resta en `build_summary()`, un timeout tampoco afecta el `score` — es lo correcto, ya que no sabemos si el protocolo está bien o mal, sólo que no pudimos preguntarle a tiempo al DNS.
* Warnings de checkdmarc (`translate_warnings()` en `utils/formatting.py`, aplicado en `record_card`, `dmarc_card`, `spf_card`, `ns_card` y `mx_card`): los warnings conocidos y en inglés se traducen a español simple. Dos tipos de patrón:
  * Texto fijo (dict `_WARNING_TRANSLATIONS`): ej. "Support for the pct tag was removed in RFC 9989".
  * Con datos variables (función `_translate_external_auth_warning`, regex `_EXTERNAL_AUTH_RE`): el warning de "verificación de destino externo" de DMARC (RFC 7489 §7.1) — sale cuando `rua=`/`ruf=` apunta a un dominio que no autorizó recibir reportes de este dominio (ej. poner un Gmail personal en el `rua=`). Este mismo warning suele venir **duplicado** (uno por `rua`, otro por `ruf`, cuando ambos apuntan al mismo destino externo) — `translate_warnings()` deduplica por el texto ya traducido, no por el mensaje crudo (que puede variar ligeramente entre rua/ruf).
  * Los que duplican algo que ya explicamos en otra parte de la misma tarjeta (ej. "p=none makes DMARC unenforced", que ya decimos nosotros mismos en "Política: Ninguna") se descartan directamente en vez de traducirse.
  * Los warnings que no matchean ningún patrón conocido se muestran tal cual (crudo, en inglés) — no hay traductor genérico, sólo se traduce lo que ya se identificó como recurrente. Antes de agregar un nuevo patrón, confirmar el texto exacto que devuelve checkdmarc (puede variar entre versiones).
* Explicación en lenguaje simple para SPF/DMARC/DKIM (`spf_card`, `dmarc_card`, `dkim_card` en `services/card_builder.py`): cada tarjeta muestra primero un "✔/✘ tiene X configurado", y luego traduce los tags a frases legibles — política DMARC (`p=`/`sp=`) con su significado (none/quarantine/reject), alineación (`adkim`/`aspf`, estricta/relajada), reportes (`rua`/`ruf`), y en SPF cada mecanismo (`include`, `ip4`, `mx`, etc.) más el calificador final (`~all`, `-all`, etc.). Cada tarjeta también lleva un `help_text` (una línea fija por protocolo en `PROTOCOL_HELP`) explicando qué es el protocolo en general. Antes de agregar nuevos tags/mecanismos a traducir, extender los diccionarios `DMARC_POLICY_LABELS`, `DMARC_ALIGNMENT_LABELS`, `SPF_ALL_LABELS` o `SPF_MECHANISM_LABELS` — no hardcodear strings sueltos en la plantilla.
* No se muestra todo lo que devuelve checkdmarc, sólo lo que aporta valor para auditar seguridad de correo: no hay tarjeta de **SOA** (es administración de zona DNS, no tiene relación con autenticación de correo) y la tarjeta de **MX** filtra los warnings de DNS inverso/PTR (`visible_mx_warnings` en `services/card_builder.py`) porque casi siempre son de la infraestructura del proveedor de correo (ej. servidores de Google), no del dominio auditado, y el dueño del dominio no puede corregirlos. El estado (ok/warn/fail) de MX se calcula sobre esos warnings ya filtrados (`mx_status`), tanto en la tarjeta como en el resumen — si se agrega un nuevo filtro de warnings a alguna tarjeta, recalcular el estado de la misma forma para que no queden desincronizados.
* Resumen con IA (`services/ai_summary.py`, `generate_summary()`): después de armar las cards, se le pide a OpenAI (modelo `OPENAI_ANALYSIS_MODEL`, con fallback a `OPENAI_MODEL` y luego a `gpt-4o-mini`) un resumen de máximo 6 líneas en español, en lenguaje simple, sobre la salud de autenticación del dominio. Se le pasan las cards ya interpretadas (no el JSON crudo) para que el resumen no contradiga lo que se ve en pantalla. Es 100% opcional: si `OPENAI_PROJECT_API_KEY` no está en `.env`, o la llamada falla/tarda más de 15s, `generate_summary()` devuelve `None` y la sección de resumen simplemente no se muestra — el resto de la auditoría (DNS/DKIM) nunca depende de que esto funcione. Sólo está conectado en el flujo HTML (`render_result()`, usado por `/` y `POST /check`); `/api/check/<domain>` sigue siendo JSON puro sin IA, para no agregarle costo/latencia de OpenAI a quien sólo quiere los datos crudos.
* Barra de salud (`build_summary()` en `services/card_builder.py`): además de los conteos ok/warn/fail, calcula `score` (0-100) y `score_color`, y los porcentajes `ok_pct`/`warn_pct`/`fail_pct` para pintar una barra segmentada en CSS puro (sin librerías de gráficos ni JS) arriba de las tarjetas. Una advertencia pesa la mitad que un ok en el `score` (coherente con `SOFT_ABSENCE_KEYS`: un protocolo opcional ausente no es tan grave como uno roto).
* El indicador de carga (`#loading`, `.htmx-indicator` en `static/css/home.css`) usa `display:none` por defecto, no sólo `opacity:0` — si se vuelve a opacity-only, el panel deja un hueco vacío en el layout mientras no hay ninguna búsqueda en curso (aunque sea invisible, sigue ocupando su alto).

Pendiente (todo lo demás descrito en este documento): resto de endpoints por protocolo, arquitectura por capas, manejo de excepciones, logging, validación de parámetros y Docker.

---

## Monitoreo continuo de DMARC

A diferencia de `/check` (auditoría puntual, sin guardar nada), esta parte agrega vigilancia a lo largo del tiempo. Dos mecanismos complementarios, con datos distintos:

* **Vigilancia DNS** (`jobs/recheck_domains.py`): reutiliza `run_check()` tal cual, sin lógica nueva de DNS — corre el chequeo de cada dominio registrado, lo compara contra el `DomainSnapshot` anterior, y genera una `Alert` si cambió la política DMARC (`p=`, indicando si se debilitó o se reforzó), el registro SPF, o los selectores DKIM encontrados. Pensado para correr como **cron** (no como servicio de larga duración): termina y se apaga.
* **Vigilancia de tráfico real** (`services/reports_service.py`): ingiere los reportes DMARC agregados (RUA) que llegan vía [parsedmarc](https://github.com/domainaware/parsedmarc) — ver la sección de parsedmarc más arriba —, y compara los remitentes reales (`source_asn_org`/`source_ip` de cada `AggregateRecord`) contra los valores declarados en el SPF del dominio (`include:`/`ip4:`/etc., extraídos también con `run_check()`). Genera una `Alert` tipo `unknown_sender` por cada IP no cubierta y no vista antes. **Ojo**: la comparación es por coincidencia de texto del nombre del ASN, no por rangos CIDR exactos — es una heurística suficiente para detectar remitentes claramente ajenos, no un reemplazo de una validación SPF completa.

Piezas:

* `models/` (`db = SQLAlchemy()` en `__init__.py`, modelos en `monitoring.py`): `MonitoredDomain`, `DomainSnapshot`, `AggregateReport`, `AggregateRecord`, `Alert`. SQLite por defecto (`DATABASE_URL`, ver `.env-example`); sin migraciones (Alembic) todavía, las tablas se crean con `db.create_all()` al arrancar `app.py`.
* `services/monitoring_service.py`: alta de dominios (`register_domain`) y datos del dashboard (`get_dashboard_data`).
* `services/reports_service.py`: `ingest_aggregate_report()` (llamada desde el webhook) y `detect_unknown_senders()`.
* `services/notifications.py`: `send_alert_email()` vía `smtplib` (variables `SMTP_*`) — no es dependencia nueva, es librería estándar de Python. Es quien manda las alertas, tanto las de `jobs/recheck_domains.py` como las de `detect_unknown_senders()` (el webhook sólo crea la `Alert` en la base; el envío de correo se centraliza en el cron para no bloquear la respuesta del webhook con una llamada SMTP).
* Rutas en `app.py`: `GET/POST /monitoreo` (alta), `GET /monitoreo/lista` (lista de todos los dominios registrados), `GET /monitoreo/<access_token>` (dashboard de un dominio), `POST /monitoreo/<access_token>/toggle` (activar/desactivar), `POST /webhooks/dmarc-aggregate/<secret>` (recibe el JSON de parsedmarc; `<secret>` debe matchear `DMARC_WEBHOOK_SECRET` o responde 404 en vez de 401, para no delatar que la ruta existe). Las URLs están en español a propósito (`/monitoreo`, no `/monitoring`) porque son páginas que ve un usuario final; el webhook (no es una página, es un endpoint para parsedmarc) se dejó en inglés. Los nombres de las funciones Python (`monitoring_register`, `monitoring_list`, `monitoring_dashboard`) y sus referencias `url_for(...)` en las plantillas no cambiaron — Flask separa el endpoint (nombre de función) de la URL real, así que renombrar la URL nunca requiere tocar los templates.
* **Activar/desactivar monitoreo** (`MonitoredDomain.is_active`, `services/monitoring_service.set_active()`): pausa el monitoreo de un dominio sin borrar su historial — se eligió esto en vez de "eliminar" porque `/monitoreo/lista` es pública y sin protección (ver nota abajo), así que una acción destructiva ahí sería riesgosa; esto es reversible. Mientras `is_active=False`: `jobs/recheck_domains.py` lo salta (no genera nuevos `DomainSnapshot` ni alertas de cambio de DNS), y `services/reports_service.ingest_aggregate_report()` ignora los reportes entrantes de ese dominio (no los guarda, no dispara `detect_unknown_senders`). El dashboard y la lista siguen mostrando el historial ya guardado, con un badge ACTIVO/INACTIVO. Registrar de nuevo un dominio ya existente pero inactivo lo reactiva automáticamente (`register_domain()`).
* **Nota sobre agregar columnas nuevas a `MonitoredDomain` (o cualquier modelo)**: no hay Alembic todavía, y `db.create_all()` en `app.py` sólo crea tablas que no existen — **no** altera una tabla ya creada para sumarle una columna nueva. Por eso `app.py` tiene un bloque que revisa con `sqlalchemy.inspect` si la columna existe y, si no, corre un `ALTER TABLE ... ADD COLUMN` a mano (ver el bloque después de `db.create_all()`). Si se agrega un campo nuevo a un modelo existente, hay que sumar ahí el `ALTER TABLE` correspondiente — si no, la base local/de producción que ya tenía datos antes del cambio no va a tener la columna nueva y las queries van a fallar con "no such column".
* **Decisión explícita sobre `/monitoreo/lista`**: es pública y sin protección — cualquiera puede ver todos los dominios registrados y entrar a cualquier dashboard sin necesitar su `access_token`. Se preguntó directamente al usuario (proteger con contraseña de admin vs. dejarla pública) y eligió dejarla pública. Esto en la práctica anula la privacidad que el `access_token` daba por sí solo (ver nota abajo) — si en algún momento se quiere volver a restringir el acceso por dominio, hay que revisar primero esta ruta, no solo el dashboard.
* Las 4 páginas de `templates/monitoring/` (`register`, `registered`, `list`, `dashboard`) usan el mismo ancho de contenido (`max-w-4xl`) — mantenerlo así si se agrega una página nueva a esta sección, para que no salte el ancho al navegar entre ellas.
* `config/parsedmarc.ini.example`: plantilla para el worker de parsedmarc (Fase 4 del plan), que corre **aparte** del servicio web (Railway *Worker*, no *Cron*, porque mantiene la conexión IMAP abierta con `mailbox.watch = True`).

Pendiente (fuera del alcance de código, requiere acción del usuario en plataformas externas — ver el plan guardado):

* Fase 0: crear la casilla de correo (`DMARC_REPORTS_MAILBOX`), su MX, y el TXT de verificación de destino externo (RFC 7489 §7.1) en el dominio receptor.
* Fase 4: desplegar el worker de parsedmarc como servicio aparte en Railway con `config/parsedmarc.ini.example` completado.
* Fase 8: prueba end-to-end una vez la infraestructura de correo esté lista (los primeros reportes reales tardan 24-48h en llegar).

---

## Objetivo

Construir un backend REST en **Python + Flask** que exponga una API para validar y verificar la configuración de autenticación de correo electrónico de uno o varios dominios.

El servicio debe ser modular, escalable y desacoplado, de forma que posteriormente pueda integrarse con un frontend desarrollado de manera independiente.

## Tecnologías

* Python 3.11+
* Flask
* checkdmarc
* dkimpy
* dnspython
* htmx (frontend, vía CDN)
* openai (opcional, resumen con IA — ver `services/ai_summary.py`)
* parsedmarc (ingesta/parseo de reportes DMARC agregados y SMTP TLS — ver sección propia más abajo)
* Flask-SQLAlchemy (persistencia del monitoreo continuo — dominios registrados, snapshots, reportes, alertas)

## Librerías base

### CheckDMARC

Repositorio:
https://github.com/domainaware/checkdmarc

Paquete:
https://pypi.org/project/checkdmarc/

Será el motor principal para validar:

* SPF
* DMARC
* BIMI
* MTA-STS
* TLS-RPT
* MX
* DNSSEC
* NS
* SOA
* STARTTLS

No se debe reimplementar la lógica ya existente en esta librería.

---

### DKIMPy

Paquete:
https://pypi.org/project/dkimpy/

Será utilizada para implementar toda la funcionalidad relacionada con DKIM.

Debe permitir:

* Validar registros DKIM.
* Consultar selectores DKIM.
* Verificar firmas DKIM.
* Firmar mensajes.
* Soporte ARC.
* RSA.
* Ed25519.

Cuando sea necesario deberá apoyarse en dnspython para consultar los registros DNS de los selectores.

---

### parsedmarc

Repositorio: [github.com/domainaware/parsedmarc](https://github.com/domainaware/parsedmarc)

Documentación: [domainaware.github.io/parsedmarc](https://domainaware.github.io/parsedmarc/)

Del mismo autor que `checkdmarc`. Se usa para la parte de **monitoreo continuo** (ver "Monitoreo continuo de DMARC" más abajo): lee una casilla de correo (IMAP) donde llegan los reportes DMARC agregados (RUA) y SMTP TLS que los proveedores de correo (Google, Microsoft, etc.) mandan a los dominios registrados, los parsea, y los entrega como JSON estructurado — no hace falta escribir un parser de XML/gzip propio.

**Consultar siempre esta documentación ante cualquier duda** sobre: formato del archivo de configuración (`config.ini`, secciones `[general]`, `[mailbox]`, `[imap]`, `[webhook]`, etc.), variables de entorno soportadas (prefijo `PARSEDMARC_SECCION_CLAVE`), el esquema exacto del JSON que produce (campos de `source`, `policy_evaluated`, `auth_results`, `alignment`), o el comportamiento de `mailbox.watch` (IMAP IDLE) — no asumir ni inventar sintaxis.

Restricciones, igual que con checkdmarc: no reimplementar el parseo de reportes DMARC/SMTP TLS que ya resuelve esta librería; usarla siempre que se necesite ingesta de reportes reales de correo (a diferencia de `checkdmarc`, que solo lee configuración DNS).

---

## Objetivo funcional

La API debe verificar la correcta configuración de los siguientes protocolos:

* SPF
* DKIM
* DMARC
* BIMI
* MTA-STS
* TLS-RPT
* MX
* DNSSEC
* STARTTLS

Cada protocolo debe poder consultarse de manera independiente.

También debe existir un endpoint que realice una auditoría completa del dominio.

---

## Endpoints mínimos

GET /api/check/<domain>

Retorna toda la información del dominio.

---

GET /api/spf/<domain>

Retorna únicamente la validación SPF.

---

GET /api/dmarc/<domain>

Retorna únicamente la validación DMARC.

---

GET /api/dkim/<domain>?selector=<selector>

Valida el selector DKIM indicado.

---

GET /api/bimi/<domain>

---

GET /api/mta-sts/<domain>

---

GET /api/tls-rpt/<domain>

---

GET /api/mx/<domain>

---

GET /api/dnssec/<domain>

---

GET /api/starttls/<domain>

---

POST /api/check

Permite validar un dominio enviado mediante JSON.

Ejemplo:

{
"domain": "example.com"
}

---

POST /api/check/bulk

Permite validar múltiples dominios.

Ejemplo:

{
"domains": [
"google.com",
"github.com",
"openai.com"
]
}

---

## Arquitectura

La aplicación debe estar organizada por capas.

backend/

app.py

config.py

requirements.txt

/routes

/services

/models

/utils

/exceptions

/tests

---

Toda la lógica de negocio debe vivir dentro de la carpeta services.

Las rutas únicamente deben recibir la petición HTTP y delegar el procesamiento al servicio correspondiente.

---

## Requisitos

* Código limpio.
* Uso de Blueprints.
* Manejo de excepciones.
* Validación de parámetros.
* Respuestas JSON consistentes.
* Logging.
* Preparado para Docker.
* Preparado para producción.
* Fácil de extender con nuevos protocolos.

---

## Restricciones

* No duplicar la lógica existente en checkdmarc.
* Utilizar checkdmarc siempre que sea posible.
* Utilizar dkimpy únicamente para todo lo relacionado con DKIM.
* Mantener una arquitectura desacoplada que permita sustituir cualquiera de las librerías en el futuro sin afectar el resto del sistema.

## Objetivo final

Construir una API REST profesional que sirva como backend para una plataforma de análisis y monitoreo de autenticación de correo, similar a servicios como DMARCGuard, PowerDMARC o EasyDMARC, enfocándose inicialmente en la validación de configuraciones y dejando preparada la arquitectura para incorporar en el futuro funcionalidades como procesamiento de reportes DMARC (RUA), monitoreo continuo, alertas, almacenamiento histórico y paneles de administración.
