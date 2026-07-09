Sí, casi todos usan el mismo mecanismo (registro TXT), salvo uno:

- SPF — TXT en la raíz del dominio (@), ej. v=spf1 include:_spf.google.com ~all. Mismo mecanismo que DMARC.

- TLS-RPT — TXT en _smtp._tls.tudominio.com (ya viste el ejemplo arriba).

- BIMI — TXT en default._bimi.tudominio.com, pero el valor apunta a una URL de un logo SVG (y a veces un certificado VMC) — necesitas tener ese logo hospedado antes.

- DKIM — TXT en <selector>._domainkey.tudominio.com, pero el valor (la clave pública) te lo da tu proveedor de correo (Google Workspace, M365, etc.) — tú no lo inventas, solo lo copias y pegas.
Las dos excepciones:

- MTA-STS — sí necesita un TXT en _mta-sts.tudominio.com, pero además exige hospedar un archivo de política en https://mta-sts.tudominio.com/.well-known/mta-sts.txt — no es sólo DNS, también necesitas un servidor web.

- DNSSEC — no es un TXT. Es otro mecanismo completamente distinto (registros DS/DNSKEY), y normalmente se activa con un botón/toggle en tu proveedor de DNS o registrador, no pegando un valor a mano.


- Se requiere saber que servidor de envios de correos usan, para configurar el SPF puede ser:
(Gmail Workspace, Zoho, Outlook/M365, etc.) — cada uno tiene su propio include
Cualquier herramienta de marketing/transaccional que envíe correo con ese dominio (Mailchimp, SendGrid, Postmark, etc.)
Si envías correo desde un servidor propio (VPS, aplicación backend) — necesitarías la IP fija de ese servidor