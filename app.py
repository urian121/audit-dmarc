from flask import Flask, jsonify
from checkdmarc import check_domains

app = Flask(__name__)

@app.route("/", methods=["GET"])
def inicio():
    return jsonify({'resp':"Hola Mundo"})


@app.route("/api/check/<domain>", methods=["GET"])
def check(domain):
    result = check_domains([domain])
    print(type(result))
    print(result)

    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)