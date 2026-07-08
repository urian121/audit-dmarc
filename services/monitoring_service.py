from models import Alert, AggregateReport, MonitoredDomain, db


def register_domain(domain, owner_email):
    """Da de alta un dominio para monitoreo continuo; si ya estaba registrado pero inactivo, lo reactiva."""
    existing = MonitoredDomain.query.filter_by(domain=domain).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.session.commit()
        return existing, False
    monitored = MonitoredDomain(domain=domain, owner_email=owner_email)
    db.session.add(monitored)
    db.session.commit()
    return monitored, True


def set_active(access_token, is_active):
    """Activa o desactiva el monitoreo de un dominio (no borra su historial). Devuelve None si el token no existe."""
    monitored = MonitoredDomain.query.filter_by(access_token=access_token).first()
    if not monitored:
        return None
    monitored.is_active = is_active
    db.session.commit()
    return monitored


def list_domains():
    """Devuelve todos los dominios registrados para monitoreo, más recientes primero."""
    return MonitoredDomain.query.order_by(MonitoredDomain.created_at.desc()).all()


def get_dashboard_data(access_token):
    """Arma los datos del dashboard privado de un dominio monitoreado (None si el token no existe)."""
    monitored = MonitoredDomain.query.filter_by(access_token=access_token).first()
    if not monitored:
        return None
    alerts = monitored.alerts.order_by(Alert.created_at.desc()).limit(50).all()
    reports = monitored.aggregate_reports.order_by(AggregateReport.received_at.desc()).limit(20).all()
    return {"monitored": monitored, "alerts": alerts, "reports": reports}
