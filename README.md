# API DMARC

API REST en Python + Flask (con un frontend incluido) para validar la configuración de autenticación de correo electrónico de un dominio: SPF, DMARC, DKIM, MX, DNSSEC, MTA-STS, TLS-RPT y BIMI. Usa [checkdmarc](https://github.com/domainaware/checkdmarc) para la mayoría de los protocolos y [dkimpy](https://pypi.org/project/dkimpy/) para DKIM.

Este proyecto está en una etapa inicial. El objetivo completo, la arquitectura planeada y los endpoints futuros están descritos en [AGENTS.md](AGENTS.md).

## Requisitos

* Python 3.11+

## Instalación

```bash
python -m venv env
env\Scripts\activate      # Windows
pip install -r requirements.txt
```

## Uso

```bash
python app.py
```

El servidor arranca en `http://127.0.0.1:5000` en modo debug.

## Endpoints disponibles

### `GET /`

Sirve el frontend: un formulario para ingresar un dominio y ver el resultado del análisis.

### `GET /api/check/<domain>`

Ejecuta `checkdmarc.check_domains()` sobre el dominio indicado, agrega el chequeo de DKIM y devuelve todo en JSON.

```bash
curl http://127.0.0.1:5000/api/check/example.com
```

DKIM no tiene una ubicación fija en DNS (depende de un selector), así que se prueba una lista de selectores comunes (`default`, `selector1`, `selector2`, `google`, `k1`, `k2`, `s1`, `s2`, `dkim`, `mail`). Para probar un selector adicional propio del dominio:

```bash
curl "http://127.0.0.1:5000/api/check/example.com?selector=mi-selector"
```

## Roadmap

Los endpoints adicionales por protocolo (`/api/spf`, `/api/dmarc`, `/api/dkim`, `/api/bimi`, `/api/mta-sts`, `/api/tls-rpt`, `/api/mx`, `/api/dnssec`, `/api/starttls`, validación en bulk, etc.) y la arquitectura por capas (routes/services/models/utils) todavía no están implementados. Ver [AGENTS.md](AGENTS.md) para el detalle completo.
