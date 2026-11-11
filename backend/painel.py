import re
import sqlite3
from datetime import date, timedelta
from decimal import Decimal

from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, session, url_for

from acesso import (
    MAX_ID, PERFIS, autenticar, cadastrar_conta, conexao, filtro_obras,
    obra_acessivel, pode_gerenciar, validar_csrf,
)

painel = Blueprint("painel", __name__, url_prefix="/painel")
ROTULOS = {"planejada": "Planejada", "em_andamento": "Em andamento", "concluida": "Concluída"}


@painel.app_template_filter("reais")
def reais(centavos):
    sinal = "-" if centavos < 0 else ""
    inteiro, decimal = divmod(abs(centavos), 100)
    return f"{sinal}R$ {inteiro:,}".replace(",", ".") + f",{decimal:02d}"


@painel.app_template_filter("data_br")
def data_br(valor):
    if not valor:
        return "—"
    try:
        return date.fromisoformat(valor).strftime("%d/%m/%Y")
    except ValueError:
        return valor


def texto(campo, limite, obrigatorio=True):
    valor = request.form.get(campo, "").strip()
    if (obrigatorio and not valor) or len(valor) > limite:
        raise ValueError(f"Confira o campo {campo.replace('_', ' ')} (até {limite} caracteres).")
    return valor


def inteiro(campo, minimo, maximo):
    valor = request.form.get(campo, "")
    try:
        numero = int(valor)
    except ValueError:
        raise ValueError(f"Informe um número inteiro em {campo.replace('_', ' ')}.") from None
    if not minimo <= numero <= maximo:
        raise ValueError(f"Informe {campo.replace('_', ' ')} entre {minimo} e {maximo}.")
    return numero


def data_form(campo, obrigatorio=True):
    valor = texto(campo, 10, obrigatorio)
    if not valor:
        return None
    try:
        data = date.fromisoformat(valor)
        if data.isoformat() != valor:
            raise ValueError
        return valor
    except ValueError:
        raise ValueError(f"Informe uma data válida em {campo.replace('_', ' ')}.") from None


def dinheiro(campo, impacto=False):
    valor = texto(campo, 16).replace(",", ".")
    if not re.fullmatch(r"[+-]?[0-9]{1,9}(?:\.[0-9]{1,2})?", valor):
        raise ValueError("Informe um valor válido com até duas casas decimais.")
    centavos = int(Decimal(valor) * 100)
    if not impacto and centavos <= 0:
        raise ValueError("Informe um valor maior que zero.")
    return centavos


def gestao():
    if not pode_gerenciar():
        abort(403)


def obra_ou_404(db, obra_id):
    obra = obra_acessivel(db, obra_id)
    if obra is None:
        abort(404)
    return obra


def obras_visiveis(db):
    filtro, parametros = filtro_obras()
    return db.execute(f"SELECT o.* FROM obras o WHERE {filtro} ORDER BY o.nome, o.id", parametros).fetchall()


def escolha_obra(db):
    obras = obras_visiveis(db)
    obra_id = request.args.get("obra", type=int)
    obra = obra_ou_404(db, obra_id) if obra_id is not None else (obras[0] if obras else None)
    return obras, obra


def cliente():
    return not g.demo and g.usuario["perfil"] == "cliente"


def equipe():
    if cliente():
        abort(403)


def retornar(tela, obra_id=None):
    return redirect(url_for(f"painel.{tela}", obra=obra_id), code=303)


@painel.route("/entrar", methods=["GET", "POST"])
def entrar():
    if request.method == "POST":
        validar_csrf()
        if autenticar(request.form.get("email", ""), request.form.get("senha", "")):
            return redirect(url_for("painel.inicio"), code=303)
        flash("E-mail ou senha inválidos.", "erro")
    return render_template("entrar.html")


@painel.post("/sair")
def sair():
    validar_csrf()
    session.clear()
    return redirect(url_for("painel.entrar"), code=303)


@painel.get("/inicio")
def inicio():
    with conexao() as db:
        obras = obras_visiveis(db)
        contagens = {status: sum(o["status"] == status for o in obras) for status in ROTULOS}
        filtro, parametros = filtro_obras()
        prazos = db.execute(
            f"""SELECT e.nome,e.prazo,e.progresso,o.nome AS obra,o.id AS obra_id
                FROM etapas e JOIN obras o ON o.id=e.obra_id WHERE ({filtro})
                AND e.prazo IS NOT NULL AND e.progresso < 100
                ORDER BY e.prazo,e.ordem LIMIT 6""",
            parametros,
        ).fetchall()
        pendencias = []
        if pode_gerenciar() or cliente():
            pendencias = db.execute(
                f"""SELECT a.*,o.nome AS obra FROM alteracoes_obra a JOIN obras o ON o.id=a.obra_id
                    WHERE ({filtro}) AND a.status='pendente' ORDER BY a.id DESC LIMIT 5""",
                parametros,
            ).fetchall()
    return render_template("inicio.html", obras=obras, contagens=contagens, prazos=prazos,
                           pendencias=pendencias)


@painel.get("/obras/<int:obra_id>")
def detalhe(obra_id):
    with conexao() as db:
        obra = obra_ou_404(db, obra_id)
        etapas = db.execute("SELECT * FROM etapas WHERE obra_id=? ORDER BY ordem", (obra_id,)).fetchall()
        construtoras = db.execute(
            "SELECT id,nome FROM construtoras WHERE ? OR id=? ORDER BY nome",
            (g.demo, obra["construtora_id"]),
        ).fetchall()
        membros = db.execute(
            """SELECT u.nome,p.perfil FROM participantes_obra p JOIN usuarios u ON u.id=p.usuario_id
               JOIN contas c ON c.usuario_id=p.usuario_id WHERE p.obra_id=?
               AND NOT EXISTS (SELECT 1 FROM acessos_revogados a WHERE a.obra_id=p.obra_id
                   AND a.usuario_id=p.usuario_id AND a.perfil=p.perfil)
               ORDER BY p.perfil,u.nome""", (obra_id,),
        ).fetchall() if pode_gerenciar() else []
    progresso = int(sum(e["progresso"] for e in etapas) / len(etapas) + 0.5) if etapas else None
    return render_template("detalhe.html", obra=obra, etapas=etapas, construtoras=construtoras,
                           progresso=progresso, membros=membros)


@painel.post("/obras/<int:obra_id>/etapas")
def criar_etapa(obra_id):
    gestao()
    validar_csrf()
    try:
        with conexao() as db:
            obra_ou_404(db, obra_id)
            ordem = db.execute(
                "SELECT COALESCE(MAX(ordem), 0)+1 FROM etapas WHERE obra_id=?", (obra_id,)
            ).fetchone()[0]
            db.execute("INSERT INTO etapas(obra_id,nome,ordem,prazo) VALUES (?,?,?,?)",
                       (obra_id, texto("nome", 120), ordem, data_form("prazo", False)))
        flash("Etapa cadastrada.")
    except ValueError as erro:
        flash(str(erro), "erro")
    except sqlite3.IntegrityError:
        flash("Outra etapa foi criada ao mesmo tempo. Tente novamente.", "erro")
    return redirect(url_for("painel.detalhe", obra_id=obra_id), code=303)


@painel.post("/obras/<int:obra_id>/etapas/<int:etapa_id>/progresso")
def medir_etapa(obra_id, etapa_id):
    equipe()
    validar_csrf()
    try:
        with conexao() as db:
            obra_ou_404(db, obra_id)
            if etapa_id > MAX_ID:
                abort(404)
            resultado = db.execute("UPDATE etapas SET progresso=? WHERE id=? AND obra_id=?",
                                   (inteiro("progresso", 0, 100), etapa_id, obra_id))
            if not resultado.rowcount:
                abort(404)
        flash("Progresso atualizado.")
    except ValueError as erro:
        flash(str(erro), "erro")
    return redirect(url_for("painel.detalhe", obra_id=obra_id), code=303)


def autor_diario(db, obra_id):
    if g.demo:
        email = "diario.demo@tony.invalid"
        db.execute("INSERT OR IGNORE INTO usuarios(nome,email) VALUES (?,?)", ("Equipe TONY", email))
        autor = db.execute("SELECT id FROM usuarios WHERE email=?", (email,)).fetchone()["id"]
        perfil = "construtora"
    else:
        autor, perfil = g.usuario["id"], g.usuario["perfil"]
    if perfil == "construtora":
        db.execute("INSERT OR IGNORE INTO participantes_obra VALUES (?,?,?)", (obra_id, autor, perfil))
    return autor, perfil


@painel.get("/diario")
def diario():
    with conexao() as db:
        obras, obra = escolha_obra(db)
        registros = []
        fotos = {}
        checklist = {}
        if obra:
            registros = db.execute(
                """SELECT r.*,u.nome AS autor FROM registros_diario r JOIN usuarios u ON u.id=r.autor_id
                   WHERE r.obra_id=? AND (?=0 OR (r.status='finalizado' AND r.compartilhado_com_cliente=1))
                   ORDER BY r.data_registro DESC,r.id DESC""",
                (obra["id"], cliente()),
            ).fetchall()
            for foto in db.execute(
                """SELECT f.id, f.registro_id FROM fotos_diario f
                   JOIN imagens_diario i ON i.foto_id=f.id
                   JOIN registros_diario r ON r.id=f.registro_id WHERE r.obra_id=? ORDER BY f.id""",
                (obra["id"],),
            ):
                fotos.setdefault(foto["registro_id"], []).append(foto["id"])
            for item in db.execute(
                """SELECT c.* FROM checklist_diario c JOIN registros_diario r ON r.id=c.registro_id
                   WHERE r.obra_id=? ORDER BY c.id""", (obra["id"],),
            ):
                checklist.setdefault(item["registro_id"], []).append(item)
    return render_template("diario.html", obras=obras, obra=obra, registros=registros, fotos=fotos,
                           checklist=checklist, hoje=date.today())


def foto_enviada():
    foto = request.files.get("foto")
    if not foto or not foto.filename:
        return None
    bytes_foto = foto.read(5 * 1024 * 1024 + 1)
    if len(bytes_foto) > 5 * 1024 * 1024:
        raise ValueError("A foto deve ter até 5 MB.")
    if bytes_foto.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", bytes_foto
    if bytes_foto.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", bytes_foto
    raise ValueError("Selecione uma foto JPEG ou PNG.")


@painel.post("/obras/<int:obra_id>/diario")
def criar_diario(obra_id):
    equipe()
    validar_csrf()
    try:
        foto = foto_enviada()
        itens = [item.strip() for item in texto("checklist", 1500, False).splitlines() if item.strip()]
        if len(itens) > 12 or any(len(item) > 120 for item in itens):
            raise ValueError("Informe até 12 itens de checklist, com no máximo 120 caracteres por item.")
        with conexao() as db:
            obra_ou_404(db, obra_id)
            autor, perfil = autor_diario(db, obra_id)
            registro_id = db.execute(
                """INSERT INTO registros_diario(obra_id,autor_id,perfil_autor,data_registro,atividades,
                   equipe,condicoes,proxima_atividade) VALUES (?,?,?,?,?,?,?,?)""",
                (obra_id, autor, perfil, data_form("data_registro"), texto("atividades", 2000),
                 texto("equipe", 120, False), texto("condicoes", 120, False),
                 texto("proxima_atividade", 300, False)),
            ).lastrowid
            db.executemany("INSERT INTO checklist_diario(registro_id,descricao) VALUES (?,?)",
                           [(registro_id, item) for item in itens])
            if foto:
                foto_id = db.execute(
                    "INSERT INTO fotos_diario(registro_id,caminho) VALUES (?,?)",
                    (registro_id, "sqlite"),
                ).lastrowid
                db.execute("INSERT INTO imagens_diario VALUES (?,?,?)", (foto_id, *foto))
        flash("Registro salvo como rascunho.")
    except ValueError as erro:
        flash(str(erro), "erro")
    return retornar("diario", obra_id)


@painel.get("/diario/fotos/<int:foto_id>")
def foto_diario(foto_id):
    if not 1 <= foto_id <= MAX_ID:
        abort(404)
    with conexao() as db:
        foto = db.execute(
            """SELECT i.*,r.obra_id,r.status,r.compartilhado_com_cliente FROM imagens_diario i
               JOIN fotos_diario f ON f.id=i.foto_id JOIN registros_diario r ON r.id=f.registro_id
               WHERE i.foto_id=?""", (foto_id,),
        ).fetchone()
        if not foto or (cliente() and (foto["status"] != "finalizado" or not foto["compartilhado_com_cliente"])):
            abort(404)
        obra_ou_404(db, foto["obra_id"])
    return Response(foto["conteudo"], mimetype=foto["tipo"],
                    headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@painel.post("/obras/<int:obra_id>/diario/<int:registro_id>/status")
def atualizar_diario(obra_id, registro_id):
    equipe()
    validar_csrf()
    if not 1 <= registro_id <= MAX_ID:
        abort(404)
    acao = request.form.get("acao")
    with conexao() as db:
        db.execute("BEGIN IMMEDIATE")
        obra_ou_404(db, obra_id)
        registro = db.execute("SELECT * FROM registros_diario WHERE id=? AND obra_id=?",
                              (registro_id, obra_id)).fetchone()
        if not registro:
            abort(404)
        if acao == "finalizar":
            if not pode_gerenciar() and registro["autor_id"] != g.usuario["id"]:
                abort(403)
            db.execute("UPDATE registros_diario SET status='finalizado' WHERE id=?", (registro_id,))
            flash("Registro finalizado.")
        elif acao in ("compartilhar", "ocultar") and registro["status"] == "finalizado":
            gestao()
            db.execute("UPDATE registros_diario SET compartilhado_com_cliente=? WHERE id=?",
                       (int(acao == "compartilhar"), registro_id))
            flash("Visibilidade do registro atualizada.")
        elif acao == "checklist" and registro["status"] == "rascunho":
            if not pode_gerenciar() and registro["autor_id"] != g.usuario["id"]:
                abort(403)
            selecionados = set(request.form.getlist("concluido"))
            itens = db.execute("SELECT id FROM checklist_diario WHERE registro_id=?", (registro_id,)).fetchall()
            db.executemany(
                "UPDATE checklist_diario SET concluido=? WHERE id=?",
                [(int(str(item["id"]) in selecionados), item["id"]) for item in itens],
            )
            flash("Checklist atualizado.")
        else:
            abort(400)
    return retornar("diario", obra_id)


@painel.get("/financeiro")
def financeiro():
    gestao()
    with conexao() as db:
        obras, obra = escolha_obra(db)
        itens, lancamentos, etapas = [], [], []
        impacto = 0
        if obra:
            parametros = (obra["id"],)
            itens = db.execute(
                """SELECT i.*,e.nome AS etapa FROM orcamentos_itens i LEFT JOIN etapas e ON e.id=i.etapa_id
                   WHERE i.obra_id=? ORDER BY i.id DESC""", parametros,
            ).fetchall()
            etapas = db.execute("SELECT id,nome FROM etapas WHERE obra_id=? ORDER BY ordem", parametros).fetchall()
            lancamentos = db.execute("SELECT * FROM lancamentos WHERE obra_id=? ORDER BY vencimento,id", parametros).fetchall()
            impacto = db.execute(
                "SELECT COALESCE(SUM(impacto_centavos),0) FROM alteracoes_obra WHERE obra_id=? AND status='aprovada'",
                parametros,
            ).fetchone()[0]
    orcado = sum(i["valor_centavos"] for i in itens) + impacto
    receitas = sum(i["valor_centavos"] for i in lancamentos if i["tipo"] == "receita" and i["liquidado"])
    despesas = sum(i["valor_centavos"] for i in lancamentos if i["tipo"] == "despesa" and i["liquidado"])
    return render_template("financeiro.html", obras=obras, obra=obra, itens=itens, lancamentos=lancamentos,
                           orcado=orcado, receitas=receitas, despesas=despesas, impacto=impacto, etapas=etapas)


@painel.post("/obras/<int:obra_id>/financeiro")
def criar_financeiro(obra_id):
    gestao()
    validar_csrf()
    try:
        descricao = texto("descricao", 160)
        valor = dinheiro("valor")
        tipo = request.form.get("tipo")
        with conexao() as db:
            obra_ou_404(db, obra_id)
            if tipo == "orcamento":
                etapa_id = inteiro("etapa_id", 1, MAX_ID) if request.form.get("etapa_id") else None
                if etapa_id and not db.execute("SELECT 1 FROM etapas WHERE id=? AND obra_id=?",
                                               (etapa_id, obra_id)).fetchone():
                    raise ValueError("Selecione uma etapa desta obra.")
                db.execute("INSERT INTO orcamentos_itens(obra_id,etapa_id,descricao,valor_centavos) VALUES (?,?,?,?)",
                           (obra_id, etapa_id, descricao, valor))
            elif tipo in ("receita", "despesa"):
                db.execute(
                    "INSERT INTO lancamentos(obra_id,descricao,tipo,valor_centavos,vencimento) VALUES (?,?,?,?,?)",
                    (obra_id, descricao, tipo, valor, data_form("vencimento")),
                )
            else:
                abort(400)
        flash("Registro financeiro adicionado.")
    except ValueError as erro:
        flash(str(erro), "erro")
    return retornar("financeiro", obra_id)


@painel.post("/obras/<int:obra_id>/financeiro/<int:lancamento_id>/situacao")
def situacao_financeira(obra_id, lancamento_id):
    gestao()
    validar_csrf()
    if not 1 <= lancamento_id <= MAX_ID:
        abort(404)
    try:
        with conexao() as db:
            obra_ou_404(db, obra_id)
            resultado = db.execute("UPDATE lancamentos SET liquidado=? WHERE id=? AND obra_id=?",
                                   (inteiro("liquidado", 0, 1), lancamento_id, obra_id))
            if not resultado.rowcount:
                abort(404)
        flash("Situação do lançamento atualizada.")
    except ValueError as erro:
        flash(str(erro), "erro")
    return retornar("financeiro", obra_id)


@painel.get("/aprovacoes")
def aprovacoes():
    if not (pode_gerenciar() or cliente()):
        abort(403)
    with conexao() as db:
        obras, obra = escolha_obra(db)
        alteracoes = []
        historico = {}
        if obra:
            alteracoes = db.execute("SELECT * FROM alteracoes_obra WHERE obra_id=? ORDER BY id DESC",
                                    (obra["id"],)).fetchall()
            for decisao in db.execute(
                """SELECT d.*,u.nome AS autor FROM decisoes_obra d
                   JOIN alteracoes_obra a ON a.id=d.alteracao_id LEFT JOIN usuarios u ON u.id=d.autor_id
                   WHERE a.obra_id=? ORDER BY d.id""", (obra["id"],),
            ):
                historico.setdefault(decisao["alteracao_id"], []).append(decisao)
    return render_template("aprovacoes.html", obras=obras, obra=obra, alteracoes=alteracoes, historico=historico)


@painel.post("/obras/<int:obra_id>/alteracoes")
def criar_alteracao(obra_id):
    gestao()
    validar_csrf()
    try:
        with conexao() as db:
            obra_ou_404(db, obra_id)
            db.execute(
                """INSERT INTO alteracoes_obra(obra_id,titulo,previsto,proposto,justificativa,impacto_centavos,impacto_dias)
                   VALUES (?,?,?,?,?,?,?)""",
                (obra_id, texto("titulo", 120), texto("previsto", 300, False),
                 texto("proposto", 300, False), texto("justificativa", 1000),
                 dinheiro("impacto_valor", True), inteiro("impacto_dias", -3650, 3650)),
            )
        flash("Alteração enviada para aprovação.")
    except ValueError as erro:
        flash(str(erro), "erro")
    return retornar("aprovacoes", obra_id)


@painel.post("/obras/<int:obra_id>/alteracoes/<int:alteracao_id>/decisao")
def decidir(obra_id, alteracao_id):
    if not (g.demo or cliente()):
        abort(403)
    validar_csrf()
    if not 1 <= alteracao_id <= MAX_ID:
        abort(404)
    acao = request.form.get("acao")
    if acao not in ("aprovada", "ajuste"):
        abort(400)
    try:
        with conexao() as db:
            db.execute("BEGIN IMMEDIATE")
            obra = obra_ou_404(db, obra_id)
            alteracao = db.execute("SELECT * FROM alteracoes_obra WHERE id=? AND obra_id=?",
                                   (alteracao_id, obra_id)).fetchone()
            if not alteracao:
                abort(404)
            if alteracao["status"] != "pendente":
                raise ValueError("Esta alteração já foi decidida.")
            motivo = texto("motivo", 1000, acao == "ajuste")
            if acao == "aprovada" and alteracao["impacto_dias"]:
                try:
                    entrega = date.fromisoformat(obra["previsao_entrega"] or "")
                    entrega += timedelta(days=alteracao["impacto_dias"])
                    if obra["data_inicio"] and entrega < date.fromisoformat(obra["data_inicio"]):
                        raise ValueError
                except (OverflowError, ValueError):
                    raise ValueError("A obra precisa de uma previsão de entrega válida para aplicar esse ajuste.") from None
                db.execute("UPDATE obras SET previsao_entrega=? WHERE id=?", (entrega.isoformat(), obra_id))
            db.execute("UPDATE alteracoes_obra SET status=? WHERE id=?", (acao, alteracao_id))
            db.execute("INSERT INTO decisoes_obra(alteracao_id,autor_id,acao,motivo) VALUES (?,?,?,?)",
                       (alteracao_id, g.usuario["id"] if g.usuario else None, acao, motivo))
        flash("Alteração aprovada." if acao == "aprovada" else "Pedido de ajuste registrado.")
    except ValueError as erro:
        flash(str(erro), "erro")
    return retornar("aprovacoes", obra_id)


@painel.route("/configuracoes", methods=["GET", "POST"])
def configuracoes():
    if request.method == "POST":
        gestao()
        validar_csrf()
        try:
            with conexao() as db:
                obra_id = inteiro("obra_id", 1, MAX_ID)
                obra_ou_404(db, obra_id)
                perfil = request.form.get("perfil")
                if perfil not in ("mestre_de_obras", "cliente"):
                    abort(400)
                email = texto("email", 254)
                senha = request.form.get("senha", "")
                if senha:
                    usuario_id = cadastrar_conta(db, texto("nome", 120), email, senha, perfil)
                else:
                    conta = db.execute(
                        """SELECT u.id FROM usuarios u JOIN contas c ON c.usuario_id=u.id
                           WHERE u.email=? AND c.perfil=?""", (email, perfil),
                    ).fetchone()
                    if not conta:
                        raise ValueError("Conta desse perfil não encontrada. Para criar uma conta, informe nome e senha.")
                    usuario_id = conta["id"]
                db.execute("INSERT OR IGNORE INTO participantes_obra VALUES (?,?,?)", (obra_id, usuario_id, perfil))
                db.execute("DELETE FROM acessos_revogados WHERE obra_id=? AND usuario_id=? AND perfil=?",
                           (obra_id, usuario_id, perfil))
            flash("Acesso vinculado à obra.")
        except ValueError as erro:
            flash(str(erro), "erro")
        except sqlite3.IntegrityError:
            flash("Não foi possível vincular o acesso. Confira os dados e tente novamente.", "erro")
        return retornar("configuracoes")

    with conexao() as db:
        obras = obras_visiveis(db) if pode_gerenciar() else []
        filtro, parametros = filtro_obras() if pode_gerenciar() else ("0", ())
        membros = db.execute(
            f"""SELECT p.obra_id,p.usuario_id,p.perfil,o.nome AS obra,u.nome,u.email
                FROM participantes_obra p JOIN contas c ON c.usuario_id=p.usuario_id
                JOIN usuarios u ON u.id=p.usuario_id JOIN obras o ON o.id=p.obra_id
                WHERE ({filtro}) AND p.perfil IN ('cliente','mestre_de_obras')
                AND NOT EXISTS (SELECT 1 FROM acessos_revogados a
                    WHERE a.obra_id=p.obra_id AND a.usuario_id=p.usuario_id AND a.perfil=p.perfil)
                ORDER BY o.nome,u.nome""",
            parametros,
        ).fetchall() if pode_gerenciar() else []
    return render_template("configuracoes.html", obras=obras, membros=membros)


@painel.post("/obras/<int:obra_id>/equipe/<int:usuario_id>/remover")
def remover_acesso(obra_id, usuario_id):
    gestao()
    validar_csrf()
    if not 1 <= usuario_id <= MAX_ID:
        abort(404)
    with conexao() as db:
        obra_ou_404(db, obra_id)
        db.execute(
            """INSERT OR IGNORE INTO acessos_revogados
               SELECT obra_id,usuario_id,perfil FROM participantes_obra
               WHERE obra_id=? AND usuario_id=? AND perfil IN ('cliente','mestre_de_obras')""",
            (obra_id, usuario_id),
        )
    flash("Acesso removido.")
    return retornar("configuracoes")
