def build_dmarc_value(rua, ruf, p, sp="", pct=100, adkim="r", aspf="r"):
    """Arma el string completo de un registro DMARC v1 a partir de sus tags, omitiendo los que están en su valor default."""
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

    if adkim == "s":
        parts.append("adkim=s")
    if aspf == "s":
        parts.append("aspf=s")

    return "; ".join(parts) + ";"
