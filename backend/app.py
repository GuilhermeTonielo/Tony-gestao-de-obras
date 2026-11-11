import sqlite3
from datetime import date

from flask import Flask, g, jsonify, render_template, request
from flask_cors import cross_origin

from database import DB_PATH, obter_conexao
from acesso import MAX_ID, filtro_obras, instalar_acesso, obra_acessivel, pode_gerenciar
from painel import ROTULOS, painel

app = Flask(
    __name__,
    template_folder="../frontend",
    static_folder="../frontend/assets",
    static_url_path="/painel/assets",
)
app.config["DB_PATH"] = DB_PATH
instalar_acesso(app)
app.register_blueprint(painel)
app.jinja_env.globals.update(rotulos=ROTULOS, pode_gerenciar=pode_gerenciar)

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
    filtro, parametros = filtro_obras()
    with obter_conexao(app.config["DB_PATH"]) as conexao:
        construtoras = conexao.execute(
            "SELECT id, nome FROM construtoras WHERE ? OR id=? ORDER BY nome, id",
            (g.demo, g.usuario["construtora_id"] if g.usuario else None),
        ).fetchall()
        resumo = conexao.execute(
            f"""SELECT o.id,c.nome AS construtora,CAST(ROUND(AVG(e.progresso)) AS INTEGER) AS progresso
                FROM obras o JOIN construtoras c ON c.id=o.construtora_id
                LEFT JOIN etapas e ON e.obra_id=o.id WHERE {filtro} GROUP BY o.id,c.nome""",
            parametros,
        ).fetchall()
    return render_template("obras.html", construtoras=construtoras,
                           resumo={obra["id"]: dict(obra) for obra in resumo})


def ler_dados_obra():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return None, "Envie os dados da obra como um objeto JSON."

    nome = dados.get("nome")
    if not isinstance(nome, str) or not nome.strip():
        return None, "Informe o nome da obra."
    if len(nome.strip()) > 120:
        return None, "O nome deve ter até 120 caracteres."

    construtora_id = dados.get("construtora_id")
    if type(construtora_id) is not int or not 1 <= construtora_id <= MAX_ID:
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
    if obra["local"] and len(obra["local"]) > 120:
        return None, "O local deve ter até 120 caracteres."
    for campo in ("data_inicio", "previsao_entrega"):
        valor = obra[campo]
        if valor:
            try:
                if date.fromisoformat(valor).isoformat() != valor:
                    raise ValueError
            except ValueError:
                return None, f"O campo {campo} deve ser uma data válida no formato AAAA-MM-DD."
    if obra["data_inicio"] and obra["previsao_entrega"]:
        if obra["data_inicio"] > obra["previsao_entrega"]:
            return None, "A previsão de entrega deve ser igual ou posterior ao início."

    return obra, None


@app.get("/obras")
def listar_obras():
    filtro, parametros = filtro_obras()
    with obter_conexao(app.config["DB_PATH"]) as conexao:
        obras = conexao.execute(
            f"SELECT {COLUNAS_OBRA} FROM obras o WHERE {filtro} ORDER BY id",
            parametros,
        ).fetchall()
    return jsonify([dict(obra) for obra in obras]), 200


@app.get("/obras/<int:obra_id>")
def consultar_obra(obra_id):
    filtro, parametros = filtro_obras()
    if not 1 <= obra_id <= MAX_ID:
        return jsonify(erro="Obra não encontrada."), 404
    with obter_conexao(app.config["DB_PATH"]) as conexao:
        obra = conexao.execute(
            f"SELECT {COLUNAS_OBRA} FROM obras o WHERE id = ? AND ({filtro})", (obra_id, *parametros)
        ).fetchone()
    if obra is None:
        return jsonify(erro="Obra não encontrada."), 404
    return jsonify(dict(obra)), 200


@app.post("/obras")
def cadastrar_obra():
    if not pode_gerenciar():
        return jsonify(erro="Seu perfil não pode cadastrar obras."), 403
    obra, erro = ler_dados_obra()
    if erro:
        return jsonify(erro=erro), 400
    if not g.demo and obra["construtora_id"] != g.usuario["construtora_id"]:
        return jsonify(erro="Use a construtora vinculada à sua conta."), 403

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
    if not pode_gerenciar():
        return jsonify(erro="Seu perfil não pode editar obras."), 403
    if not 1 <= obra_id <= MAX_ID:
        return jsonify(erro="Obra não encontrada."), 404
    obra, erro = ler_dados_obra()
    if erro:
        return jsonify(erro=erro), 400
    if not g.demo and obra["construtora_id"] != g.usuario["construtora_id"]:
        return jsonify(erro="Use a construtora vinculada à sua conta."), 403

    try:
        with obter_conexao(app.config["DB_PATH"]) as conexao:
            conexao.execute("BEGIN IMMEDIATE")
            if not obra_acessivel(conexao, obra_id):
                return jsonify(erro="Obra não encontrada."), 404
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
    if not pode_gerenciar():
        return jsonify(erro="Seu perfil não pode excluir obras."), 403
    if not 1 <= obra_id <= MAX_ID:
        return jsonify(erro="Obra não encontrada."), 404
    try:
        with obter_conexao(app.config["DB_PATH"]) as conexao:
            conexao.execute("BEGIN IMMEDIATE")
            if not obra_acessivel(conexao, obra_id):
                return jsonify(erro="Obra não encontrada."), 404
            resultado = conexao.execute("DELETE FROM obras WHERE id = ?", (obra_id,))
            if resultado.rowcount == 0:
                return jsonify(erro="Obra não encontrada."), 404
    except sqlite3.IntegrityError:
        return jsonify(erro="A obra tem etapas, participantes ou registros vinculados."), 409

    return jsonify(mensagem="Obra excluída.", id=obra_id), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
