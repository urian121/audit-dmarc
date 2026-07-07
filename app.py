import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from services.ai_summary import generate_summary
from services.card_builder import build_cards, build_summary
from services.checkdmarc_service import run_check
from utils.domain_validation import is_valid_domain

# Sólo tiene efecto en local: .env está en .gitignore, así que Railway (que
# despliega desde el repo de GitHub) nunca ve este archivo. Las variables de
# producción se definen en el dashboard de Railway, no acá.
load_dotenv()

app = Flask(__name__)


def render_result(domain, extra_selector=None):
    """Corre la auditoría del dominio, pide el resumen con IA y renderiza el fragmento HTML de resultados."""
    data = run_check(domain, extra_selector)
    cards = build_cards(data)
    return render_template(
        "partials/check_result.html",
        cards=cards,
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


if __name__ == "__main__":
    # Railway (y la mayoría de PaaS) inyectan el puerto real en $PORT y sólo
    # enrutan tráfico a 0.0.0.0 — escuchar en 127.0.0.1:5000 fijo no es alcanzable
    # desde afuera del contenedor.
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
