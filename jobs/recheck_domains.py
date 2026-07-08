"""Job de vigilancia DNS periódica (Fase 5 del plan de monitoreo continuo).

Reutiliza run_check() — la misma función que usa POST /check — para volver a
auditar cada dominio registrado, comparar contra el último snapshot guardado,
y generar una Alert si cambió la política DMARC, el SPF o los selectores DKIM
encontrados. Pensado para correr como Railway Cron Job (ej. cada 6-12h), no
como parte del servicio web (que sólo atiende peticiones bajo demanda).

Uso: python jobs/recheck_domains.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app  # noqa: E402  (necesita el sys.path.insert de arriba)
from models import Alert, DomainSnapshot, MonitoredDomain, db  # noqa: E402
from services.checkdmarc_service import run_check  # noqa: E402
from services.notifications import send_alert_email  # noqa: E402

_POLICY_RANK = {"none": 0, "quarantine": 1, "reject": 2}


def _dmarc_policy(data):
    """Extrae el valor crudo de la política DMARC (p=) del resultado de run_check()."""
    tags = (data.get("dmarc") or {}).get("tags") or {}
    p = tags.get("p")
    return p.get("value") if isinstance(p, dict) else None


def _spf_record(data):
    """Extrae el registro SPF crudo del resultado de run_check()."""
    return (data.get("spf") or {}).get("record")


def _dkim_selectors(data):
    """Extrae la lista ordenada de selectores DKIM encontrados en el resultado de run_check()."""
    return sorted(e["selector"] for e in (data.get("dkim") or []) if e.get("found"))


def _describe_policy_change(previous_policy, current_policy):
    """Arma el mensaje de alerta para un cambio de política DMARC, indicando si se debilitó o se reforzó."""
    prev_rank = _POLICY_RANK.get(previous_policy, -1)
    curr_rank = _POLICY_RANK.get(current_policy, -1)
    if curr_rank < prev_rank:
        direction = "se debilitó"
    elif curr_rank > prev_rank:
        direction = "se reforzó"
    else:
        direction = "cambió"
    return f"La política DMARC {direction}: antes 'p={previous_policy}', ahora 'p={current_policy}'."


def check_domain_for_changes(monitored):
    """Corre run_check() para un dominio, compara contra el último snapshot y crea alertas si cambió algo."""
    data = run_check(monitored.domain)
    current = {
        "dmarc_policy": _dmarc_policy(data),
        "spf_record": _spf_record(data),
        "dkim_selectors": _dkim_selectors(data),
    }

    last_snapshot = monitored.snapshots.order_by(DomainSnapshot.checked_at.desc()).first()
    if last_snapshot is not None:
        previous = last_snapshot.raw_data or {}

        if previous.get("dmarc_policy") != current["dmarc_policy"]:
            db.session.add(Alert(
                monitored_domain_id=monitored.id,
                kind=Alert.KIND_POLICY_CHANGED,
                message=_describe_policy_change(previous.get("dmarc_policy"), current["dmarc_policy"]),
            ))

        if previous.get("spf_record") != current["spf_record"]:
            db.session.add(Alert(
                monitored_domain_id=monitored.id,
                kind=Alert.KIND_SPF_CHANGED,
                message="El registro SPF cambió respecto al último chequeo.",
            ))

        if (previous.get("dkim_selectors") or []) != current["dkim_selectors"]:
            db.session.add(Alert(
                monitored_domain_id=monitored.id,
                kind=Alert.KIND_DKIM_SELECTOR_CHANGED,
                message="Los selectores DKIM encontrados cambiaron respecto al último chequeo.",
            ))

    db.session.add(DomainSnapshot(monitored_domain_id=monitored.id, raw_data=current))
    db.session.commit()


def main():
    """Corre check_domain_for_changes() para todos los dominios registrados y notifica las alertas nuevas."""
    with app.app_context():
        for monitored in MonitoredDomain.query.all():
            try:
                check_domain_for_changes(monitored)
            except Exception as error:
                print(f"[recheck_domains] error con {monitored.domain}: {error}")

        for alert in Alert.query.filter_by(notified_at=None).all():
            send_alert_email(alert.domain_ref, alert)


if __name__ == "__main__":
    main()
