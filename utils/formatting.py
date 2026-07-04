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
