import re

from checkdmarc import check_dmarc, check_domains
import dkim

# Selectores DKIM más comunes en proveedores de correo (Google Workspace,
# Microsoft 365, SendGrid, Mailchimp, etc.). checkdmarc no reporta DKIM, así
# que se prueban "a ciegas" contra <selector>._domainkey.<dominio>.
COMMON_DKIM_SELECTORS = [
    "default", "selector1", "selector2", "google", "k1", "k2",
    "s1", "s2", "dkim", "mail",
]


def check_dkim(domain, selectors):
    """Prueba una lista de selectores DKIM contra el dominio y devuelve el resultado de cada uno."""
    results = []
    for selector in selectors:
        name = f"{selector}._domainkey.{domain}".encode("ascii")
        entry = {"selector": selector, "found": False}
        try:
            record_bytes = dkim.get_txt(name)
        except dkim.DKIMException as error:
            entry["error"] = str(error)
            results.append(entry)
            continue

        if record_bytes:
            entry["found"] = True
            entry["record"] = record_bytes.decode("utf-8", errors="replace")
            try:
                _pk, keysize, ktag, _seqtlsrpt = dkim.load_pk_from_dns(
                    name, dnsfunc=dkim.get_txt
                )
                entry["valid"] = True
                entry["key_type"] = ktag.decode() if isinstance(ktag, bytes) else ktag
                entry["key_size"] = keysize
            except dkim.DKIMException as error:
                entry["valid"] = False
                entry["error"] = str(error)
        results.append(entry)
    return results


def run_check(domain, extra_selector=None):
    """Ejecuta la auditoría completa del dominio (checkdmarc + DKIM) y la devuelve en un solo dict."""
    result = check_domains([domain])
    selectors = list(COMMON_DKIM_SELECTORS)
    if extra_selector and extra_selector not in selectors:
        selectors.append(extra_selector)
    result["dkim"] = check_dkim(domain, selectors)
    return result


def merge_rua_into_dmarc_record(raw_record, mailbox):
    """Agrega `mailbox` al tag rua= de un registro DMARC crudo (o se lo agrega si no tenía)."""
    rua_pattern = re.compile(r"(rua=)([^;]*)", re.IGNORECASE)
    match = rua_pattern.search(raw_record)
    target = f"mailto:{mailbox}"

    if match:
        existing_value = match.group(2).strip()
        if mailbox in existing_value:
            return raw_record  # ya está agregado, no duplicar
        new_value = f"{existing_value},{target}"
        return raw_record[:match.start(2)] + new_value + raw_record[match.end(2):]

    record = raw_record.rstrip()
    if not record.endswith(";"):
        record += ";"
    return f"{record} rua={target}"


def dns_has_mailbox_in_rua(domain, mailbox):
    """Consulta el DNS en vivo y dice si el registro DMARC publicado ahora mismo ya incluye `mailbox` en su rua=."""
    try:
        result = check_dmarc(domain, timeout=5)
    except Exception:
        return False

    record = result.get("record") if not result.get("error") else None
    if not record:
        return False

    rua_match = re.search(r"rua=([^;]*)", record, re.IGNORECASE)
    if not rua_match:
        return False

    return mailbox.lower() in rua_match.group(1).lower()


def build_dmarc_dns_instructions(domain, mailbox):
    """Arma el registro DNS exacto (host/tipo/valor) que hay que publicar para recibir reportes DMARC.

    Si el dominio ya tiene un registro DMARC, fusiona `mailbox` a su rua= existente
    (conservando el resto tal cual). Si no tiene ninguno, sugiere uno nuevo en modo
    "sólo monitoreo" (p=none), que no bloquea ningún correo.
    """
    try:
        result = check_dmarc(domain, timeout=5)
    except Exception:
        result = {}

    existing_record = result.get("record") if not result.get("error") else None
    if existing_record:
        value = merge_rua_into_dmarc_record(existing_record, mailbox)
    else:
        value = f"v=DMARC1; p=none; rua=mailto:{mailbox}"

    return {
        "host": f"_dmarc.{domain}",
        "type": "TXT",
        "value": value,
        "has_existing_record": bool(existing_record),
    }
