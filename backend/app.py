import sqlite3

from flask import Flask, jsonify, render_template, request
from flask_cors import cross_origin

from database import DB_PATH, obter_conexao

app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend/assets",
    static_url_path="/painel/assets",
)
app.config["DB_PATH"] = DB_PATH

STATUS_OBRA = ("planejada", "em_andamento", "concluida")
COLUNAS_OBRA = "id, construtora_id, nome, local, data_inicio, previsao_entrega, status"


@app.get("/")
@cross_origin()
def status_api():
    return jsonify(
        status="sucesso",
        projeto="TONY Gestão de Obras",
        mensagem="API da Etapa 1 em execução.",
    )


@app.get("/painel")
def painel_obras():
    with obter_conexao(app.config["DB_PATH"]) as conexao:
        construtoras = conexao.execute(
            "SELECT id, nome FROM construtoras ORDER BY nome, id"
        ).fetchall()
    return render_template("obras.html", construtoras=construtoras)


def ler_dados_obra():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return None, "Envie os dados da obra como um objeto JSON."

    nome = dados.get("nome")
    if not isinstance(nome, str) or not nome.strip():
        return None, "Informe o nome da obra."

    construtora_id = dados.get("construtora_id")
    if type(construtora_id) is not int or not 1 <= construtora_id <= 2**63 - 1:
        return None, "Informe um construtora_id inteiro positivo válido."

    status = dados.get("status", "planejada")
    if status not in STATUS_OBRA:
        return None, "Status inválido. Use planejada, em_andamento ou concluida."

    obra = {"construtora_id": construtora_id, "nome": nome.strip(), "status": status}
    for campo in ("local", "data_inicio", "previsao_entrega"):
        valor = dados.get(campo)
        if valor is not None and not isinstance(valor, str):
            return None, f"O campo {campo} deve ser texto ou nulo."
        obra[campo] = (valor or "").strip() or None

    return obra, None


@app.get("/obras")
def listar_obras():
    with obter_conexao(app.config["DB_PATH"]) as conexao:
        obras = conexao.execute(f"SELECT {COLUNAS_OBRA} FROM obras ORDER BY id").fetchall()
    return jsonify([dict(obra) for obra in obras]), 200


@app.get("/obras/<int:obra_id>")
def consultar_obra(obra_id):
    with obter_conexao(app.config["DB_PATH"]) as conexao:
        obra = conexao.execute(
            f"SELECT {COLUNAS_OBRA} FROM obras WHERE id = ?", (obra_id,)
        ).fetchone()
    if obra is None:
        return jsonify(erro="Obra não encontrada."), 404
    return jsonify(dict(obra)), 200


@app.post("/obras")
def cadastrar_obra():
    obra, erro = ler_dados_obra()
    if erro:
        return jsonify(erro=erro), 400

    try:
        with obter_conexao(app.config["DB_PATH"]) as conexao:
            resultado = conexao.execute(
                """INSERT INTO obras
                   (construtora_id, nome, local, data_inicio, previsao_entrega, status)
                   VALUES (:construtora_id, :nome, :local, :data_inicio,
                           :previsao_entrega, :status)""",
                obra,
            )
            obra_id = resultado.lastrowid
    except sqlite3.IntegrityError:
        return jsonify(erro="A construtora informada não existe."), 400

    return jsonify(id=obra_id, **obra), 201, {"Location": f"/obras/{obra_id}"}


@app.put("/obras/<int:obra_id>")
def atualizar_obra(obra_id):
    obra, erro = ler_dados_obra()
    if erro:
        return jsonify(erro=erro), 400

    try:
        with obter_conexao(app.config["DB_PATH"]) as conexao:
            resultado = conexao.execute(
                """UPDATE obras
                   SET construtora_id = :construtora_id, nome = :nome, local = :local,
                       data_inicio = :data_inicio, previsao_entrega = :previsao_entrega,
                       status = :status
                   WHERE id = :id""",
                {"id": obra_id, **obra},
            )
            if resultado.rowcount == 0:
                return jsonify(erro="Obra não encontrada."), 404
    except sqlite3.IntegrityError:
        return jsonify(erro="A construtora informada não existe."), 400

    return jsonify(id=obra_id, **obra), 200


@app.delete("/obras/<int:obra_id>")
def excluir_obra(obra_id):
    try:
        with obter_conexao(app.config["DB_PATH"]) as conexao:
            resultado = conexao.execute("DELETE FROM obras WHERE id = ?", (obra_id,))
            if resultado.rowcount == 0:
                return jsonify(erro="Obra não encontrada."), 404
    except sqlite3.IntegrityError:
        return jsonify(erro="A obra tem etapas, participantes ou registros vinculados."), 409

    return jsonify(mensagem="Obra excluída.", id=obra_id), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
