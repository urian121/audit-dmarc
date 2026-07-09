import os
import secrets

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

from models import db
from services.ai_summary import generate_summary
from services.card_builder import build_cards, build_risks, build_summary
from services.checkdmarc_service import build_dmarc_dns_instructions, run_check
from utils.dmarc_builder import build_dmarc_value
from services.monitoring_service import get_dashboard_data, get_domain_by_token, list_domains, register_domain, set_active, verify_dns
from services.reports_service import ingest_aggregate_report
from utils.domain_validation import is_valid_domain

# Sólo tiene efecto en local: .env está en .gitignore, así que Railway (que
# despliega desde el repo de GitHub) nunca ve este archivo. Las variables de
# producción se definen en el dashboard de Railway, no acá.
load_dotenv()

app = Flask(__name__)

# Monitoreo continuo (fases 1-7 del plan): persistencia en Postgres. No hay
# fallback a SQLite — DATABASE_URL es obligatoria (ver AGENTS.md). Railway la
# inyecta solo al agregar el addon de Postgres; en local hay que copiarla a .env.
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "Falta DATABASE_URL. Este proyecto usa Postgres — copia la cadena de "
        "conexión del addon de Postgres en Railway (o de tu Postgres local) a .env."
    )
# Railway/Heroku entregan el esquema como "postgres://", pero SQLAlchemy 2.x
# sólo reconoce "postgresql://" — sin este reemplazo, falla al conectar.
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)
with app.app_context():
    db.create_all()

# Casilla que recibe los reportes DMARC (se le pide al usuario que la agregue
# a su rua=) y secreto que debe traer la URL del webhook de parsedmarc.
DMARC_REPORTS_MAILBOX = os.environ.get("DMARC_REPORTS_MAILBOX", "reports@tudominio.com")
DMARC_WEBHOOK_SECRET = os.environ.get("DMARC_WEBHOOK_SECRET")


def render_result(domain, extra_selector=None):
    """Corre la auditoría del dominio, pide el resumen con IA y renderiza el fragmento HTML de resultados."""
    data = run_check(domain, extra_selector)
    cards = build_cards(data)
    return render_template(
        "partials/check_result.html",
        cards=cards,
        risks=build_risks(cards, data.get("domain") or domain),
        summary=build_summary(data),
        result_domain=data.get("domain"),
        base_domain=data.get("base_domain"),
        ai_summary=generate_summary(data.get("domain") or domain, cards),
    )


@app.route("/", methods=["GET"])
def inicio():
    """Sirve la página principal; si viene ?domain=, renderiza el resultado directamente (SSR)."""
    domain = request.args.get("domain", "").strip().lower()
    context = {"domain": domain}
    if domain:
        if not is_valid_domain(domain):
            context["error"] = "Ingresa un dominio válido, por ejemplo: tudominio.com"
        else:
            try:
                context["result_html"] = render_result(domain)
            except Exception as error:
                context["error"] = f"No se pudo completar el análisis: {error}"
    return render_template("index.html", **context)


@app.route("/check", methods=["POST"])
def check_partial():
    """Endpoint HTML consumido por htmx (hx-post) — devuelve un fragmento renderizado."""
    domain = request.form.get("domain", "").strip().lower()
    selector = request.form.get("selector") or None

    if not is_valid_domain(domain):
        return render_template(
            "partials/error.html",
            message="Ingresa un dominio válido, por ejemplo: tudominio.com",
        )

    try:
        return render_result(domain, selector)
    except Exception as error:
        return render_template(
            "partials/error.html",
            message=f"No se pudo completar el análisis: {error}",
        )


@app.route("/api/check/<domain>", methods=["GET"])
def check(domain):
    """API JSON: ejecuta la auditoría del dominio indicado y la devuelve completa."""
    custom_selector = request.args.get("selector")
    result = run_check(domain, custom_selector)
    return jsonify(result)


@app.route("/monitoreo", methods=["GET", "POST"])
def monitoring_register():
    """Formulario de alta de un dominio para monitoreo continuo (vigilancia DNS + reportes DMARC)."""
    if request.method == "GET":
        return render_template("monitoring/register.html")

    domain = request.form.get("domain", "").strip().lower()
    owner_email = request.form.get("owner_email", "").strip()

    if not is_valid_domain(domain):
        return render_template(
            "monitoring/register.html",
            error="Ingresa un dominio válido, por ejemplo: tudominio.com",
            domain=domain, owner_email=owner_email,
        )
    if "@" not in owner_email:
        return render_template(
            "monitoring/register.html",
            error="Ingresa un correo válido para recibir las alertas.",
            domain=domain, owner_email=owner_email,
        )

    monitored, created = register_domain(domain, owner_email)
    return render_template(
        "monitoring/registered.html",
        monitored=monitored,
        rua_mailbox=DMARC_REPORTS_MAILBOX,
        already_existed=not created,
        dns=build_dmarc_dns_instructions(domain, DMARC_REPORTS_MAILBOX),
    )


@app.route("/monitoreo/dns/preview", methods=["POST"])
def monitoring_dns_preview():
    """htmx: recalcula el Valor del registro DMARC según los controles de política (p/sp/pct/adkim/aspf) del generador."""
    value = build_dmarc_value(
        rua=request.form.get("rua", ""),
        ruf=request.form.get("ruf", ""),
        p=request.form.get("p", "none"),
        sp=request.form.get("sp", ""),
        pct=request.form.get("pct", "100"),
        adkim="s" if request.form.get("adkim") == "s" else "r",
        aspf="s" if request.form.get("aspf") == "s" else "r",
    )
    return render_template("partials/dns_value_preview.html", value=value)


@app.route("/monitoreo/<access_token>/dns", methods=["GET"])
def monitoring_dns(access_token):
    """Vuelve a mostrar las instrucciones de DNS (host/tipo/valor) de un dominio ya registrado."""
    monitored = get_domain_by_token(access_token)
    if monitored is None:
        return render_template("partials/error.html", message="No se encontró ese dashboard."), 404
    return render_template(
        "monitoring/registered.html",
        monitored=monitored,
        rua_mailbox=DMARC_REPORTS_MAILBOX,
        already_existed=True,
        dns=build_dmarc_dns_instructions(monitored.domain, DMARC_REPORTS_MAILBOX),
    )


@app.route("/monitoreo/<access_token>/verificar-dns", methods=["POST"])
def monitoring_verify_dns(access_token):
    """htmx: vuelve a consultar el DNS en vivo y guarda si ya se publicó la casilla de monitoreo en el rua=."""
    monitored = verify_dns(access_token, DMARC_REPORTS_MAILBOX)
    if monitored is None:
        return render_template("partials/error.html", message="No se encontró ese dashboard."), 404
    return render_template("partials/dns_verify_status.html", monitored=monitored)


@app.route("/monitoreo/lista", methods=["GET"])
def monitoring_list():
    """Lista pública de todos los dominios registrados para monitoreo (sin protección — decisión explícita)."""
    return render_template("monitoring/list.html", monitored_domains=list_domains())


@app.route("/monitoreo/<access_token>", methods=["GET"])
def monitoring_dashboard(access_token):
    """Dashboard privado de un dominio monitoreado: reportes recibidos y alertas generadas."""
    data = get_dashboard_data(access_token)
    if data is None:
        return render_template("partials/error.html", message="No se encontró ese dashboard."), 404
    return render_template("monitoring/dashboard.html", rua_mailbox=DMARC_REPORTS_MAILBOX, **data)


@app.route("/monitoreo/<access_token>/toggle", methods=["POST"])
def monitoring_toggle(access_token):
    """Activa o desactiva el monitoreo de un dominio (no borra su historial) y vuelve al dashboard."""
    monitored = set_active(access_token, request.form.get("activar") == "1")
    if monitored is None:
        return render_template("partials/error.html", message="No se encontró ese dashboard."), 404
    return redirect(url_for("monitoring_dashboard", access_token=access_token))


@app.route("/webhooks/dmarc-aggregate/<secret>", methods=["POST"])
def webhook_dmarc_aggregate(secret):
    """Recibe el JSON de un reporte DMARC agregado ya parseado por parsedmarc (salida 'webhook' de su config)."""
    if not DMARC_WEBHOOK_SECRET or not secrets.compare_digest(secret, DMARC_WEBHOOK_SECRET):
        abort(404)  # 404 en vez de 401: no delatar que la ruta existe a quien no trae el secreto
    payload = request.get_json(silent=True) or {}
    try:
        ingest_aggregate_report(payload)
    except Exception as error:
        # Nunca devolver 500 acá: un payload inesperado no debe hacer que
        # parsedmarc reintente indefinidamente la misma entrega.
        db.session.rollback()
        print(f"[webhook_dmarc_aggregate] error procesando payload: {error}")
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    # Railway (y la mayoría de PaaS) inyectan el puerto real en $PORT y sólo
    # enrutan tráfico a 0.0.0.0 — escuchar en 127.0.0.1:5000 fijo no es alcanzable
    # desde afuera del contenedor.
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
