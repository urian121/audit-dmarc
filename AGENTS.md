# Agente: Backend de Validación de Autenticación de Correo

## Reglas de comunicación

* Responder siempre en español.
* Respuestas directas y concisas, sin rodeos.

## Estado actual

Proyecto en etapa inicial. Solo existen `app.py`, `requirements.txt`, `AGENTS.md` y `README.md` — todavía no hay estructura por capas (`routes/`, `services/`, `models/`, `utils/`, `exceptions/`, `tests/`).

Implementado:

* `GET /` — sirve el frontend (`templates/index.html`, con `static/css/home.css` y `static/js/home.js`).
* `GET /api/check/<domain>` — llama a `checkdmarc.check_domains()`, agrega el resultado de DKIM (ver abajo) y devuelve todo junto.
* Chequeo de DKIM con `dkimpy`: como `checkdmarc` no reporta DKIM, se prueba una lista de selectores comunes (`default`, `selector1`, `selector2`, `google`, `k1`, `k2`, `s1`, `s2`, `dkim`, `mail`) contra `<selector>._domainkey.<domain>` usando `dkim.get_txt` y `dkim.load_pk_from_dns`. También acepta un selector adicional vía `?selector=`.

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
