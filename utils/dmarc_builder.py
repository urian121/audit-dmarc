def build_dmarc_value(rua, ruf, p, sp="", pct=100, adkim="r", aspf="r"):
    """Arma el string completo de un registro DMARC v1 a partir de sus tags — sp/pct se omiten si están en su valor default, adkim/aspf siempre se muestran."""
    parts = ["v=DMARC1", f"p={p or 'none'}"]

    if sp and sp != p:
        parts.append(f"sp={sp}")
    if rua:
        parts.append(f"rua={rua}")
    if ruf:
        parts.append(f"ruf={ruf}")

    try:
        pct_int = int(pct)
    except (TypeError, ValueError):
        pct_int = 100
    if pct_int != 100:
        parts.append(f"pct={pct_int}")

    parts.append(f"adkim={adkim or 'r'}")
    parts.append(f"aspf={aspf or 'r'}")

    return "; ".join(parts) + ";"
