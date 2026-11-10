from flask import Flask, jsonify
from flask_cors import cross_origin

app = Flask(__name__)


@app.get("/")
@cross_origin()
def status_api():
    return jsonify(
        status="sucesso",
        projeto="TONY Gestão de Obras",
        mensagem="API da Etapa 1 em execução.",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
