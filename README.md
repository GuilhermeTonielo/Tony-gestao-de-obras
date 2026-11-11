# TONY Gestão de Obras

Projeto escolar de recuperação do 3º C. O TONY organiza etapas e diários de obra e prevê acessos para construtoras, mestres de obras e clientes.

## Equipe

- **Guilherme Tonielo** — modelagem do banco, API e testes.
- **Mauricio Torres Queiroz** — apoio no design e na interface.

## Etapa 1

- `bd/tony-der.drawio`: diagrama entidade-relacionamento editável no draw.io.
- `bd/script.sql`: definição das tabelas do SQLite.
- `bd/init_db.py`: cria o banco local a partir do script SQL.
- `backend/app.py`: API Flask com rota de verificação.
- `backend/requirements.txt`: dependências da API.

A primeira etapa entrega a estrutura do banco e uma rota de verificação. As telas, os cadastros funcionais e as regras de acesso serão implementados nas próximas etapas.

## Como executar no Windows

Abra a pasta raiz deste projeto no VS Code. No terminal, confirme que `python --version` indica Python 3.10 ou superior. Em seguida, execute a partir da raiz:

```powershell
python -m venv backend/venv
.\backend\venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\backend\venv\Scripts\python.exe bd/init_db.py
.\backend\venv\Scripts\python.exe backend/app.py
```

Abra [http://localhost:5000/](http://localhost:5000/) e confira se o navegador exibe a resposta JSON. O inicializador cria `bd/tony.db` e pode ser executado novamente sem apagar os dados existentes.

Para o relatório, capture o DER, as tabelas criadas, o terminal com o Flask rodando e o navegador com a URL e o JSON visíveis.

## Etapa 2 — CRUD de obras

A API acessa `bd/tony.db` por meio de `backend/database.py`. Para preparar uma construtora fictícia, rode na raiz do projeto:

```powershell
.\backend\venv\Scripts\python.exe bd/init_db.py --demo
```

Anote o `construtora_id` exibido. O comando pode ser repetido sem duplicar a construtora de demonstração. Inicie a API como na Etapa 1.

| Método | Rota | Resultado esperado |
|---|---|---|
| POST | `/obras` | Cadastra uma obra e retorna o registro com seu ID (201). |
| GET | `/obras` | Lista as obras salvas (200). |
| GET | `/obras/<id>` | Consulta uma obra pelo ID (200). |
| PUT | `/obras/<id>` | Substitui os dados da obra pelo JSON enviado (200). |
| DELETE | `/obras/<id>` | Exclui uma obra sem dependências (200). |

### Demonstração no Thunder Client

Se preferir importar as quatro requisições, use `docs/tony-etapa-2.postman_collection.json` em **Collections → Import** no Thunder Client ou no Postman. Ajuste `construtora_id` e preencha `obra_id` com o ID que o POST retornar antes de editar ou excluir.

Crie uma coleção para o TONY e use `http://localhost:5000` como endereço base. Em POST e PUT, selecione **Body → JSON**. No exemplo, substitua `1` pelo ID da construtora fictícia exibido no terminal.

```json
{
  "construtora_id": 1,
  "nome": "Reforma de demonstração",
  "local": "Cascavel, PR",
  "status": "planejada"
}
```

1. Envie o POST e anote o ID da obra retornado. Capture o status 201.
2. Reinicie a API e faça o GET de listagem. Capture o status 200 e a obra na resposta.
3. Faça o PUT com o ID da obra, envie o corpo completo e troque o status para `em_andamento`. Capture o status 200 e o novo valor.
4. Faça o DELETE dessa obra de demonstração. Capture o status 200. Repetir a exclusão do mesmo ID deve retornar 404.

Dados inválidos retornam 400. Consultar, editar ou excluir um ID inexistente retorna 404. A exclusão de obra com dados vinculados retorna 409 e preserva os registros. As datas são campos de texto opcionais. Se usá-las, prefira o formato `AAAA-MM-DD`.

## Etapa 3 — Cadastro e listagem pela interface

Prepare o banco com `bd/init_db.py --demo`, inicie `backend/app.py` e abra [http://127.0.0.1:5000/painel](http://127.0.0.1:5000/painel).

O Flask serve a página e a API na mesma origem. A tela em `frontend/obras.html` usa as cores, os ícones e a tipografia do protótipo do Figma. O JavaScript em `frontend/assets/obras.js` faz o `POST /obras` ao enviar o formulário e o `GET /obras` ao abrir a página e depois de cada cadastro.

Para as evidências da recuperação, abra **Nova obra**, preencha uma obra fictícia e capture o formulário antes do envio. Cadastre a obra e capture a confirmação e a listagem. Recarregue para verificar que a obra continua na lista. Por fim, confira a linha na tabela `obras` de `bd/tony.db` no VS Code.
