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
* Severidad de MTA-STS, TLS-RPT y BIMI (`SOFT_ABSENCE_KEYS` en `services/card_builder.py`): `checkdmarc` no distingue "el registro no existe" de "existe pero está mal" (ambos casos llegan como el mismo `{error, valid:false}`); la única pista es que el texto de `error` contiene "does not exist". Por eso, para estos tres protocolos opcionales, la ausencia del registro se muestra como ADVERTENCIA y no como FALLA — un SPF/DMARC ausente sigue siendo FALLA porque son protocolos base, no opcionales.

Pendiente (todo lo demás descrito en este documento): resto de endpoints por protocolo, arquitectura por capas, manejo de excepciones, logging, validación de parámetros y Docker.

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
