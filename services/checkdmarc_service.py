from checkdmarc import check_dmarc, check_domains
import dkim

from utils.dmarc_builder import build_dmarc_value

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


def _mailto_addresses(tag):
    """Extrae la lista de direcciones (sin el prefijo mailto:) de un tag rua/ruf ya parseado por checkdmarc."""
    if not tag:
        return []
    return [entry["address"] for entry in tag.get("value") or [] if entry.get("address")]


def dns_has_mailbox_in_rua(domain, mailbox):
    """Consulta el DNS en vivo y dice si el registro DMARC publicado ahora mismo ya incluye `mailbox` en su rua=."""
    try:
        result = check_dmarc(domain, timeout=5)
    except Exception:
        return False

    if result.get("error"):
        return False

    tags = result.get("tags") or {}
    return mailbox.lower() in [a.lower() for a in _mailto_addresses(tags.get("rua"))]


def build_dmarc_dns_instructions(domain, mailbox):
    """Arma el registro DNS (host/tipo/valor) que hay que publicar, más la política actual para editarla.

    Si el dominio ya tiene un registro DMARC, reconstruye su valor a partir de los tags ya
    parseados por checkdmarc, agregando `mailbox` a su rua= si no estaba. Si no tiene ninguno,
    arma uno nuevo en modo "sólo monitoreo" (p=none), que no bloquea ningún correo. En ambos
    casos devuelve también `policy` (p/sp/pct/adkim/aspf) y `rua`/`ruf` sueltos, para que el
    generador interactivo de la UI pueda recalcular `value` sin volver a consultar el DNS.
    """
    try:
        result = check_dmarc(domain, timeout=5)
    except Exception:
        result = {}

    existing_record = result.get("record") if not result.get("error") else None
    tags = result.get("tags") or {}

    rua_addresses = _mailto_addresses(tags.get("rua"))
    if mailbox not in rua_addresses:
        rua_addresses.append(mailbox)
    rua = ",".join(f"mailto:{address}" for address in rua_addresses)
    ruf = ",".join(f"mailto:{address}" for address in _mailto_addresses(tags.get("ruf")))

    p = (tags.get("p") or {}).get("value") or "none"
    sp_tag = tags.get("sp") or {}
    sp = sp_tag.get("value") if sp_tag.get("explicit") else ""
    pct = (tags.get("pct") or {}).get("value") or 100
    adkim = (tags.get("adkim") or {}).get("value") or "r"
    aspf = (tags.get("aspf") or {}).get("value") or "r"

    value = build_dmarc_value(rua, ruf, p, sp, pct, adkim, aspf)

    return {
        "host": f"_dmarc.{domain}",
        "type": "TXT",
        "value": value,
        "has_existing_record": bool(existing_record),
        "policy": {"p": p, "sp": sp, "pct": pct, "adkim": adkim, "aspf": aspf},
        "rua": rua,
        "ruf": ruf,
    }
