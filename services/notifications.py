import os
import smtplib
from email.mime.text import MIMEText

from models import db
from models.monitoring import utcnow


def _smtp_config():
    """Lee la configuración SMTP de variables de entorno; None si no está configurada (feature opcional)."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        return None
    return {
        "host": host,
        "port": int(os.environ.get("SMTP_PORT", 587)),
        "user": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASSWORD"),
        "from_addr": os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER"),
    }


def send_alert_email(monitored_domain, alert):
    """Manda por correo una alerta al dueño del dominio; marca notified_at si se envió con éxito."""
    config = _smtp_config()
    if config is None:
        return False

    message = MIMEText(f"Se detectó lo siguiente en {monitored_domain.domain}:\n\n{alert.message}")
    message["Subject"] = f"[Alerta DMARC] {monitored_domain.domain}"
    message["From"] = config["from_addr"]
    message["To"] = monitored_domain.owner_email

    try:
        with smtplib.SMTP(config["host"], config["port"], timeout=10) as server:
            server.starttls()
            if config["user"]:
                server.login(config["user"], config["password"])
            server.sendmail(config["from_addr"], [monitored_domain.owner_email], message.as_string())
    except Exception:
        return False

    alert.notified_at = utcnow()
    db.session.commit()
    return True
