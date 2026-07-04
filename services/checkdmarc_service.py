from checkdmarc import check_domains
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
