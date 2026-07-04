from flask import Flask, jsonify, render_template, request
from checkdmarc import check_domains
import dkim

app = Flask(__name__)

COMMON_DKIM_SELECTORS = [
    "default", "selector1", "selector2", "google", "k1", "k2",
    "s1", "s2", "dkim", "mail",
]


def check_dkim(domain, selectors):
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


@app.route("/", methods=["GET"])
def inicio():
    return render_template("index.html")


@app.route("/api/check/<domain>", methods=["GET"])
def check(domain):
    result = check_domains([domain])

    selectors = list(COMMON_DKIM_SELECTORS)
    custom_selector = request.args.get("selector")
    if custom_selector and custom_selector not in selectors:
        selectors.append(custom_selector)

    result["dkim"] = check_dkim(domain, selectors)
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)
