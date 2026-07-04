# API DMARC

API REST en Python + Flask para validar la configuración de autenticación de correo electrónico de un dominio (SPF, DMARC, MX, DNSSEC, MTA-STS, TLS-RPT, BIMI, entre otros), usando la librería [checkdmarc](https://github.com/domainaware/checkdmarc).

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

Endpoint de prueba, responde:

```json
{ "resp": "Hola Mundo" }
```

### `GET /api/check/<domain>`

Ejecuta `checkdmarc.check_domains()` sobre el dominio indicado y devuelve el resultado en JSON.

```bash
curl http://127.0.0.1:5000/api/check/example.com
```

## Limitación conocida

`checkdmarc.check_domains()` no incluye validación de **DKIM** entre sus resultados (solo devuelve `domain`, `base_domain`, `dnssec`, `soa`, `ns`, `mx`, `spf`, `dmarc`, `smtp_tls_reporting`, `mta_sts`, `bimi`). Para cubrir DKIM es necesario integrar `dkimpy` por separado, tal como se define en [AGENTS.md](AGENTS.md).

## Roadmap

Los endpoints adicionales (`/api/spf`, `/api/dmarc`, `/api/dkim`, `/api/bimi`, `/api/mta-sts`, `/api/tls-rpt`, `/api/mx`, `/api/dnssec`, `/api/starttls`, validación en bulk, etc.) y la arquitectura por capas (routes/services/models/utils) todavía no están implementados. Ver [AGENTS.md](AGENTS.md) para el detalle completo.
