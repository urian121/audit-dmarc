from utils.formatting import flatten_tag_value, is_absence_error, scalar_items

# Etiqueta y clases Tailwind del badge de estado que se muestra en cada tarjeta.
STATUS_META = {
    "ok":   ("OK", "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"),
    "warn": ("ADVERTENCIA", "bg-amber-500/10 text-amber-400 border-amber-500/30"),
    "fail": ("FALLA", "bg-rose-500/10 text-rose-400 border-rose-500/30"),
    "na":   ("N/D", "bg-zinc-500/10 text-zinc-500 border-zinc-500/30"),
}

# Protocolos opcionales/avanzados: si el registro simplemente no existe, es
# una recomendación (ADVERTENCIA), no una falla como un SPF/DMARC roto.
SOFT_ABSENCE_KEYS = ("mta_sts", "smtp_tls_reporting", "bimi")


def status_of(section):
    """Clasifica una sección del resultado de checkdmarc en ok/warn/fail/na."""
    if section is None:
        return "na"
    if isinstance(section, bool):
        return "ok" if section else "fail"
    if isinstance(section, dict):
        if section.get("error"):
            return "fail"
        if section.get("valid") is False:
            return "fail"
        if section.get("warnings"):
            return "warn"
        return "ok"
    return "na"


def record_status(section, soft_absence=False):
    """Como status_of, pero permite bajar a 'warn' cuando el error es sólo ausencia del registro."""
    if not section:
        return "na"
    if section.get("error"):
        if soft_absence and is_absence_error(section["error"]):
            return "warn"
        return "fail"
    return status_of(section)


def base_card(title, status, kind, **extra):
    """Arma el dict base de una tarjeta: título, badge de estado y tipo de contenido."""
    label, cls = STATUS_META.get(status, STATUS_META["na"])
    return {
        "title": title, "status": status,
        "badge_label": label, "badge_cls": cls,
        "kind": kind, **extra,
    }


def record_card(title, section, soft_absence=False):
    """Construye la tarjeta de un protocolo basado en registro DNS (SPF, DMARC, MTA-STS, TLS-RPT, BIMI)."""
    if not section:
        return base_card(title, "na", "empty")
    status = record_status(section, soft_absence=soft_absence)
    if section.get("error"):
        return base_card(title, status, "error", message=section["error"])

    policy = section.get("policy") or {}
    return base_card(
        title, status, "record",
        record=section.get("record"),
        kv=scalar_items(section, skip=("record", "warnings", "tags", "policy", "valid")),
        tags={k: flatten_tag_value(v) for k, v in (section.get("tags") or {}).items()},
        policy_kv=scalar_items(policy, skip=("mx",)),
        policy_mx=policy.get("mx") or [],
        warnings=section.get("warnings") or [],
    )


def dnssec_card(value):
    """Construye la tarjeta de DNSSEC a partir del booleano que devuelve checkdmarc."""
    status = status_of(value)
    text = "DNSSEC activo y validado" if value else "DNSSEC no está activo"
    return base_card("DNSSEC", status, "text", text=text)


def ns_card(section):
    """Construye la tarjeta de Nameservers."""
    if not section:
        return base_card("Nameservers", "na", "empty")
    status = status_of(section)
    if section.get("error"):
        return base_card("Nameservers", status, "error", message=section["error"])
    return base_card(
        "Nameservers", status, "list",
        hostnames=section.get("hostnames") or [],
        warnings=section.get("warnings") or [],
    )


def mx_card(section):
    """Construye la tarjeta de MX, incluyendo los flags booleanos de cada host (ej. dnssec)."""
    if not section:
        return base_card("MX", "na", "empty")
    status = status_of(section)
    if section.get("error"):
        return base_card("MX", status, "error", message=section["error"])
    hosts = []
    for h in section.get("hosts") or []:
        flags = [(k, v) for k, v in h.items() if isinstance(v, bool)]
        hosts.append({
            "hostname": h.get("hostname", "?"),
            "preference": h.get("preference", "—"),
            "flags": flags,
        })
    return base_card("MX", status, "mx", hosts=hosts, warnings=section.get("warnings") or [])


def soa_card(section):
    """Construye la tarjeta de SOA."""
    if not section:
        return base_card("SOA", "na", "empty")
    status = status_of(section)
    if section.get("error"):
        return base_card("SOA", status, "error", message=section["error"])
    return base_card(
        "SOA", status, "soa",
        record=section.get("record"),
        kv=scalar_items(section.get("values") or {}),
    )


def dkim_status(entries):
    """Calcula el estado global de DKIM a partir de la lista de selectores probados."""
    if not entries:
        return "na"
    found = [e for e in entries if e.get("found")]
    if any(e.get("valid") is False for e in found):
        return "fail"
    if any(e.get("valid") for e in found):
        return "ok"
    return "warn"


def dkim_card(entries):
    """Construye la tarjeta de DKIM con los selectores encontrados y los que no dieron resultado."""
    entries = entries or []
    status = dkim_status(entries)
    return base_card(
        "DKIM", status, "dkim",
        found=[e for e in entries if e.get("found")],
        not_found=[e["selector"] for e in entries if not e.get("found")],
    )


def build_cards(data):
    """Arma la lista completa de tarjetas (una por protocolo) para renderizar en la plantilla."""
    return [
        dnssec_card(data.get("dnssec")),
        record_card("SPF", data.get("spf")),
        record_card("DMARC", data.get("dmarc")),
        dkim_card(data.get("dkim")),
        mx_card(data.get("mx")),
        record_card("MTA-STS", data.get("mta_sts"), soft_absence=True),
        record_card("TLS-RPT", data.get("smtp_tls_reporting"), soft_absence=True),
        record_card("BIMI", data.get("bimi"), soft_absence=True),
        ns_card(data.get("ns")),
        soa_card(data.get("soa")),
    ]


def build_summary(data):
    """Cuenta cuántos protocolos quedaron en ok/warn/fail para el resumen mostrado arriba de las tarjetas."""
    ok = warn = fail = 0
    for key in ("spf", "dmarc", "mx", "ns"):
        s = status_of(data.get(key))
        if s == "ok":
            ok += 1
        elif s == "warn":
            warn += 1
        elif s == "fail":
            fail += 1

    for key in SOFT_ABSENCE_KEYS:
        s = record_status(data.get(key), soft_absence=True)
        if s == "ok":
            ok += 1
        elif s == "warn":
            warn += 1
        elif s == "fail":
            fail += 1

    ok += 1 if status_of(data.get("dnssec")) == "ok" else 0
    fail += 1 if status_of(data.get("dnssec")) != "ok" else 0

    s = dkim_status(data.get("dkim"))
    if s == "ok":
        ok += 1
    elif s == "warn":
        warn += 1
    elif s == "fail":
        fail += 1

    return {"ok": ok, "warn": warn, "fail": fail}
