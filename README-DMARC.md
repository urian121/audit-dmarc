Configurar políticas DMARC para un dominio (none, quarantine, reject).
Verificar que SPF y DKIM estén correctamente configurados (DMARC depende de estos mecanismos).
Monitorear reportes DMARC enviados por proveedores de correo.
Detectar intentos de suplantación usando el dominio.
Medir el porcentaje de correos autenticados correctamente.
Generar alertas o dashboards sobre problemas de entrega o seguridad.
Ajustar reglas sin tener que editar manualmente registros DNS todo el tiempo.


APIs que permiten gestionar, monitorear y analizar implementaciones de DMARC (muchas también incluyen SPF y DKIM).


¿Qué cubre DMARC?
Valida quién puede enviar correos usando tu dominio.
Bloquea o reduce suplantación (spoofing).
Protege contra phishing usando tu marca.
Genera reportes de quién está enviando correos en nombre de tu dominio.
Mejora reputación y entregabilidad del correo.

¿Cómo funciona?

DMARC se apoya en dos tecnologías (protocolos):

SPF → valida qué servidores pueden enviar correos.
DKIM → valida que el correo no fue alterado.

Si SPF/DKIM fallan → DMARC aplica la política.



¿Cómo saber si un dominio tiene DMARC desde consola?
dig TXT _dmarc.midominio.com
o
nslookup -type=TXT _dmarc.midominio.com

SPF:
dig TXT midominio.com
Buscar un registro que empiece por:
v=spf1

DKIM:
Necesitas conocer el selector.
Ejemplo:
selector1._domainkey.midominio.com
Consultar:
dig TXT selector1._domainkey.midominio.com
nslookup -type=TXT google._domainkey.octapus.io





* **Validar DMARC**

```bash
nslookup -type=TXT _dmarc.octapus.io
```

Busca el registro DMARC del dominio.

---

* **Validar SPF**

```bash
nslookup -type=TXT octapus.io
```

Busca el registro SPF (`v=spf1`) que indica qué servidores pueden enviar correos.

---

* **Validar DKIM**

```bash
nslookup -type=TXT <selector>._domainkey.octapus.io
```

Busca el registro DKIM usando el selector (ej.: `google`, `default`, `mail`) para verificar que el dominio tenga firma DKIM configurada.

**Ejemplo:**

```bash
nslookup -type=TXT google._domainkey.octapus.io
```

---

### Interpretación rápida

* `v=DMARC1` → DMARC configurado.
* `v=spf1` → SPF configurado.
* `v=DKIM1` → DKIM configurado.
