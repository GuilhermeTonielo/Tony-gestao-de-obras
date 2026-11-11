import hmac
import os
import secrets

import click
from flask import abort, current_app, g, jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import obter_conexao

PERFIS = {
    "construtora": "Construtora",
    "mestre_de_obras": "Mestre de obras",
    "cliente": "Cliente",
}
MAX_ID = 2**63 - 1


def instalar_acesso(app):
    app.config.update(
        SECRET_KEY=os.environ.get("TONY_SECRET_KEY") or secrets.token_hex(32),
        AUTH_REQUIRED=os.environ.get("TONY_AUTH_REQUIRED") == "1",
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_HTTPONLY=True,
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    )
    app.before_request(identificar)
    app.jinja_env.globals.update(csrf_token=csrf_token, perfis=PERFIS)
    app.cli.add_command(criar_administrador)


def conexao():
    return obter_conexao(current_app.config["DB_PATH"])


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


def token_valido():
    enviado = request.headers.get("X-CSRF-Token") or request.form.get("_csrf", "")
    esperado = session.get("csrf", "")
    return bool(esperado) and hmac.compare_digest(enviado.encode(), esperado.encode())


def validar_csrf():
    if not token_valido():
        abort(403)


def identificar():
    g.usuario = None
    g.demo = not current_app.config["AUTH_REQUIRED"]
    if request.endpoint in (None, "static", "status_api"):
        return None

    if "usuario_id" in session:
        with conexao() as db:
            g.usuario = db.execute(
                """SELECT u.id, u.nome, u.email, c.perfil, c.construtora_id
                   FROM usuarios u JOIN contas c ON c.usuario_id=u.id WHERE u.id=?""",
                (session["usuario_id"],),
            ).fetchone()
        g.demo = False

    if request.endpoint == "painel.entrar":
        return None
    api = request.path == "/obras" or request.path.startswith("/obras/")
    if not g.demo and g.usuario is None:
        if api:
            return jsonify(erro="Entre na sua conta para acessar a API."), 401
        return redirect(url_for("painel.entrar"))
    if api and request.method in ("POST", "PUT", "DELETE") and not g.demo and not token_valido():
        return jsonify(erro="A sessão expirou ou o token de segurança é inválido. Recarregue a página."), 403
    return None


def pode_gerenciar():
    return g.demo or (g.usuario and g.usuario["perfil"] == "construtora")


def filtro_obras():
    if g.demo:
        return "1=1", ()
    if g.usuario["perfil"] == "construtora":
        return "o.construtora_id=?", (g.usuario["construtora_id"],)
    return (
        """EXISTS (SELECT 1 FROM participantes_obra p
                   WHERE p.obra_id=o.id AND p.usuario_id=? AND p.perfil=?
                   AND NOT EXISTS (SELECT 1 FROM acessos_revogados a
                       WHERE a.obra_id=p.obra_id AND a.usuario_id=p.usuario_id AND a.perfil=p.perfil))""",
        (g.usuario["id"], g.usuario["perfil"]),
    )


def obra_acessivel(db, obra_id):
    if not 1 <= obra_id <= MAX_ID:
        return None
    filtro, parametros = filtro_obras()
    return db.execute(
        f"""SELECT o.*, c.nome AS construtora FROM obras o
            JOIN construtoras c ON c.id=o.construtora_id
            WHERE o.id=? AND ({filtro})""",
        (obra_id, *parametros),
    ).fetchone()


def autenticar(email, senha):
    if len(email) > 254 or not 1 <= len(senha) <= 128:
        return False
    with conexao() as db:
        usuario = db.execute(
            "SELECT u.id, c.senha_hash FROM usuarios u JOIN contas c ON c.usuario_id=u.id WHERE u.email=?",
            (email.strip(),),
        ).fetchone()
    if usuario and check_password_hash(usuario["senha_hash"], senha):
        session.clear()
        session["usuario_id"] = usuario["id"]
        return True
    return False


def cadastrar_conta(db, nome, email, senha, perfil, construtora_id=None):
    if not 1 <= len(nome) <= 120 or "@" not in email or len(email) > 254:
        raise ValueError("Informe nome e e-mail válidos.")
    if not 8 <= len(senha) <= 128:
        raise ValueError("A senha deve ter entre 8 e 128 caracteres.")
    usuario = db.execute("SELECT id FROM usuarios WHERE email=?", (email,)).fetchone()
    if usuario:
        usuario_id = usuario["id"]
        if db.execute("SELECT 1 FROM contas WHERE usuario_id=?", (usuario_id,)).fetchone():
            raise ValueError("Já existe uma conta com esse e-mail.")
        db.execute("UPDATE usuarios SET nome=? WHERE id=?", (nome, usuario_id))
    else:
        usuario_id = db.execute("INSERT INTO usuarios(nome,email) VALUES (?,?)", (nome, email)).lastrowid
    db.execute(
        "INSERT INTO contas(usuario_id,senha_hash,perfil,construtora_id) VALUES (?,?,?,?)",
        (usuario_id, generate_password_hash(senha), perfil, construtora_id),
    )
    return usuario_id


@click.command("criar-administrador")
@click.option("--construtora-id", required=True, type=click.IntRange(1, MAX_ID))
@click.option("--nome", prompt=True)
@click.option("--email", prompt=True)
@click.password_option()
def criar_administrador(construtora_id, nome, email, password):
    """Cria uma conta de construtora vinculada ao cadastro existente."""
    with conexao() as db:
        if not db.execute("SELECT 1 FROM construtoras WHERE id=?", (construtora_id,)).fetchone():
            raise click.ClickException("Construtora não encontrada.")
        try:
            cadastrar_conta(db, nome.strip(), email.strip(), password, "construtora", construtora_id)
        except ValueError as erro:
            raise click.ClickException(str(erro)) from erro
    click.echo("Conta criada.")
