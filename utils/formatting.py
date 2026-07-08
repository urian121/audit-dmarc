import re


def flatten_tag_value(value):
    """Convierte el valor (posiblemente anidado) de un tag DMARC/TLS-RPT en un texto legible."""
    if value is None:
        return ""
    if isinstance(value, dict) and "value" in value:
        return flatten_tag_value(value["value"])
    if isinstance(value, list):
        return ", ".join(flatten_tag_value(item) for item in value)
    if isinstance(value, dict):
        if value.get("scheme") and value.get("address"):
            return f"{value['scheme']}:{value['address']}"
        return str(value)
    return str(value)


def scalar_items(data, skip=()):
    """Filtra un dict dejando sólo los pares clave/valor cuyo valor es escalar (no dict ni list)."""
    return {
        key: value for key, value in data.items()
        if key not in skip and value is not None and not isinstance(value, (dict, list))
    }


def is_absence_error(message):
    """Detecta si un mensaje de error de checkdmarc indica que el registro simplemente no existe."""
    return bool(message) and "does not exist" in message.lower()


def is_timeout_error(message):
    """Detecta si un mensaje de error de checkdmarc es por timeout de DNS (no por mala configuración)."""
    if not message:
        return False
    lowered = message.lower()
    return "timed out" in lowered or "timeout" in lowered or "resolution lifetime expired" in lowered


def friendly_error_message(message):
    """Traduce errores técnicos y en inglés de checkdmarc a texto claro en español, cuando se reconoce el patrón."""
    if is_timeout_error(message):
        return (
            "No se pudo verificar ahora mismo: se agotó el tiempo de espera consultando el DNS. "
            "Puede ser temporal — vuelve a analizar en un momento."
        )
    return message


# Warnings de checkdmarc que traducimos a español simple cuando se reconoce el patrón.
_WARNING_TRANSLATIONS = {
    "support for the pct tag was removed": (
        "La etiqueta 'pct' (porcentaje) ya no forma parte del estándar más reciente de DMARC "
        "(RFC 9989). No afecta el funcionamiento actual, pero no conviene depender de ella."
    ),
}

# Warnings que ya no se muestran porque duplican algo que explicamos en otra parte de la
# misma tarjeta (ej. "p=none" ya se explica en la política) — mostrarlos dos veces confunde.
_REDUNDANT_WARNING_PATTERNS = (
    "makes dmarc unenforced",
)

# "example.com does not indicate that it accepts DMARC reports about otrodominio.com -
#  Authorization record not found: ..." — falta el registro de "verificación de destino
# externo" que exige DMARC (RFC 7489 §7.1) cuando rua=/ruf= apunta a un dominio distinto
# al propio. Aparece una vez por cada tag (rua y ruf) que apunte a ese destino externo.
_EXTERNAL_AUTH_RE = re.compile(
    r"([\w.-]+) does not indicate that it accepts dmarc reports about ([\w.-]+)"
)


def _translate_external_auth_warning(lowered_message):
    """Traduce el warning de 'destino externo no autorizado a recibir reportes DMARC'."""
    match = _EXTERNAL_AUTH_RE.search(lowered_message)
    if not match:
        return None
    receiver, domain = match.group(1), match.group(2)
    return (
        f'Los reportes se mandarían a una casilla en "{receiver}", pero ese dominio no autorizó '
        f'recibir reportes sobre "{domain}" (el estándar DMARC lo exige) — es probable que esos '
        "reportes nunca lleguen. Lo más seguro es usar una casilla de correo del propio dominio."
    )


def translate_warnings(warnings):
    """Traduce una lista de warnings de checkdmarc a español simple, sin duplicados ni redundantes."""
    translated = []
    for message in warnings or []:
        lowered = message.lower()
        if any(pattern in lowered for pattern in _REDUNDANT_WARNING_PATTERNS):
            continue

        text = next(
            (t for pattern, t in _WARNING_TRANSLATIONS.items() if pattern in lowered),
            None,
        )
        if text is None:
            text = _translate_external_auth_warning(lowered)
        if text is None:
            text = message

        if text not in translated:
            translated.append(text)
    return translated
