import base64
import io
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from acesso import cadastrar_conta
from app import app

RAIZ = Path(__file__).resolve().parents[1]
OBRA = {
    "nome": "Casa Aurora",
    "construtora_id": 1,
    "local": "Cascavel, PR",
    "data_inicio": "2026-11-01",
    "previsao_entrega": "2026-12-20",
}
FOTO_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
)


class FluxoObraTest(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.banco = Path(self.pasta.name) / "teste.db"
        configuracao = app.config.copy()
        self.addCleanup(app.config.update, configuracao)
        app.config.update(TESTING=True, AUTH_REQUIRED=True, DB_PATH=self.banco)
        with closing(sqlite3.connect(self.banco)) as db, db:
            db.row_factory = sqlite3.Row
            for arquivo in ("script.sql", "modulos.sql"):
                db.executescript((RAIZ / "bd" / arquivo).read_text(encoding="utf-8"))
            db.executemany("INSERT INTO construtoras(nome) VALUES (?)", [("Aurora",), ("Outra",)])
            db.execute("INSERT INTO obras(construtora_id,nome) VALUES (2,'Obra privada')")
            cadastrar_conta(db, "Ana", "ana@exemplo.test", "tony-teste", "construtora", 1)

    def token(self, cliente, pagina):
        resposta = cliente.get(pagina)
        self.assertEqual(resposta.status_code, 200, resposta.get_data(as_text=True))
        return re.search(r'(?:name="csrf-token" content|name="_csrf" value)="([^"]+)"',
                         resposta.get_data(as_text=True)).group(1)

    def entrar(self, email):
        cliente = app.test_client()
        resposta = cliente.post(
            "/painel/entrar",
            data={"email": email, "senha": "tony-teste", "_csrf": self.token(cliente, "/painel/entrar")},
        )
        self.assertEqual(resposta.status_code, 303)
        return cliente

    def formulario(self, cliente, url, token, **dados):
        resposta = cliente.post(url, data={"_csrf": token, **dados}, follow_redirects=True)
        self.assertEqual(resposta.status_code, 200, resposta.get_data(as_text=True))
        return resposta.get_data(as_text=True)

    def criar_obra(self, admin):
        token = self.token(admin, "/painel")
        resposta = admin.post("/obras", json=OBRA, headers={"X-CSRF-Token": token})
        self.assertEqual(resposta.status_code, 201, resposta.get_data(as_text=True))
        return resposta.get_json()["id"], token

    def test_validacao_e_isolamento(self):
        sem_login = app.test_client()
        self.assertEqual(sem_login.get("/obras").status_code, 401)
        admin = self.entrar("ana@exemplo.test")
        obra_id, token = self.criar_obra(admin)
        self.assertEqual([x["id"] for x in admin.get("/obras").get_json()], [obra_id])
        self.assertEqual(admin.get("/obras/1").status_code, 404)
        self.assertEqual(admin.get("/painel/obras/1").status_code, 404)
        self.assertEqual(admin.get("/obras/9223372036854775808").status_code, 404)
        self.assertEqual(admin.put(f"/obras/{obra_id}", json=OBRA).status_code, 403)
        headers = {"X-CSRF-Token": token}
        self.assertEqual(admin.put("/obras/1", json=OBRA, headers=headers).status_code, 404)
        self.assertEqual(admin.delete("/obras/1", headers=headers).status_code, 404)
        self.assertEqual(admin.post("/obras", json={**OBRA, "nome": "x" * 121}, headers=headers).status_code, 400)
        self.assertEqual(admin.post("/obras", json={**OBRA, "data_inicio": "2026-02-31"}, headers=headers).status_code, 400)
        editada = admin.put(f"/obras/{obra_id}", json={**OBRA, "status": "em_andamento"}, headers=headers)
        self.assertEqual(editada.get_json()["status"], "em_andamento")

    def test_etapas_diario_financeiro_e_aprovacao(self):
        admin = self.entrar("ana@exemplo.test")
        obra_id, token = self.criar_obra(admin)
        caminho = f"/painel/obras/{obra_id}"
        self.formulario(admin, caminho + "/etapas", token, nome="Fundação", prazo="2026-12-01")
        self.assertIn("Fundação", admin.get("/painel/inicio").get_data(as_text=True))
        for perfil, email in (("mestre_de_obras", "mestre"), ("cliente", "cliente")):
            html = self.formulario(
                admin, "/painel/configuracoes", token, obra_id=obra_id, nome=email,
                email=email + "@exemplo.test", senha="tony-teste", perfil=perfil,
            )
            self.assertIn("Acesso vinculado à obra.", html)
        mestre = self.entrar("mestre@exemplo.test")
        cliente = self.entrar("cliente@exemplo.test")
        token_mestre = self.token(mestre, caminho)
        token_cliente = self.token(cliente, caminho)
        self.assertEqual(cliente.get("/painel/financeiro").status_code, 403)
        self.assertEqual(mestre.post("/obras", json=OBRA, headers={"X-CSRF-Token": token_mestre}).status_code, 403)
        self.assertIn("50%", self.formulario(mestre, caminho + "/etapas/1/progresso", token_mestre, progresso=50))
        texto = "Concretagem finalizada"
        self.assertIn(texto, self.formulario(mestre, caminho + "/diario", token_mestre, data_registro="2026-11-10",
                                              atividades=texto, checklist="Verificar nível",
                                              foto=(io.BytesIO(FOTO_PNG), "foto.png")))
        self.assertIn("Checklist atualizado.", self.formulario(
            mestre, caminho + "/diario/1/status", token_mestre, acao="checklist", concluido=1,
        ))
        self.assertNotIn(texto, cliente.get("/painel/diario").get_data(as_text=True))
        self.assertEqual(cliente.get("/painel/diario/fotos/1").status_code, 404)
        self.formulario(mestre, caminho + "/diario/1/status", token_mestre, acao="finalizar")
        self.formulario(admin, caminho + "/diario/1/status", token, acao="compartilhar")
        self.assertIn(texto, cliente.get("/painel/diario").get_data(as_text=True))
        self.assertIn("Verificar nível · Concluído", cliente.get("/painel/diario").get_data(as_text=True))
        self.assertEqual(cliente.get("/painel/diario/fotos/1").data, FOTO_PNG)
        self.formulario(admin, caminho + "/financeiro", token, tipo="orcamento", descricao="Materiais",
                        valor="1000,00", etapa_id=1)
        self.formulario(admin, caminho + "/financeiro", token, tipo="despesa", descricao="Cimento", valor="15", vencimento="2026-11-20")
        self.assertIn("R$ 15,00", self.formulario(admin, caminho + "/financeiro/1/situacao", token, liquidado=1))
        self.formulario(admin, caminho + "/alteracoes", token, titulo="Reforço", justificativa="Solo",
                        impacto_valor="250", impacto_dias=5)
        self.assertIn("Alteração aprovada.", self.formulario(cliente, caminho + "/alteracoes/1/decisao", token_cliente, acao="aprovada"))
        self.assertIn("já foi decidida", self.formulario(cliente, caminho + "/alteracoes/1/decisao", token_cliente, acao="aprovada"))
        self.assertIn("R$ 1.250,00", admin.get("/painel/financeiro").get_data(as_text=True))
        self.assertEqual(admin.get(f"/obras/{obra_id}").get_json()["previsao_entrega"], "2026-12-25")
        self.formulario(admin, caminho + "/alteracoes", token, titulo="Outra mudança", justificativa="Revisão",
                        impacto_valor="500", impacto_dias=2)
        self.assertIn("Pedido de ajuste registrado.", self.formulario(
            cliente, caminho + "/alteracoes/2/decisao", token_cliente, acao="ajuste", motivo="Rever custo",
        ))
        self.assertEqual(admin.get(f"/obras/{obra_id}").get_json()["previsao_entrega"], "2026-12-25")
        self.assertEqual(admin.delete(f"/obras/{obra_id}", headers={"X-CSRF-Token": token}).status_code, 409)
        self.formulario(admin, caminho + "/equipe/2/remover", token)
        self.assertEqual(mestre.get(f"/obras/{obra_id}").status_code, 404)
        self.assertIn(texto, admin.get("/painel/diario").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
