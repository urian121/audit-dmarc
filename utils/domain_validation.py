import re

# Acepta dominios tipo "ejemplo.com" o "sub.ejemplo.com"; rechaza guiones al
# inicio/fin de cada etiqueta y dominios sin al menos un punto.
DOMAIN_RE = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$"
)


def is_valid_domain(domain):
    """Indica si el string recibido tiene forma de nombre de dominio válido."""
    return bool(domain) and bool(DOMAIN_RE.match(domain))
