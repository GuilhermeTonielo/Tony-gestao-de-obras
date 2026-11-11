# TONY Gestão de Obras

Projeto escolar de recuperação do 3º C. O painel web reúne obras, etapas, diário, orçamento, lançamentos e aprovações. Construtoras, mestres de obras e clientes têm acessos diferentes quando o modo com login está ativo.

- **Guilherme Tonielo** — modelagem do banco, API e testes.
- **Mauricio Torres Queiroz** — apoio no design e na interface.

## Como executar no Windows

Na raiz do projeto, use o PowerShell com Python 3.10 ou superior.

```powershell
python -m venv backend/venv
.\backend\venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\backend\venv\Scripts\python.exe bd/init_db.py --demo
.\backend\venv\Scripts\python.exe backend/app.py
```

O inicializador cria `bd/tony.db` e prepara uma construtora fictícia. Anote o `construtora_id` que o terminal mostrar para usar nos exemplos. Reexecutar o inicializador preserva os registros e evita duplicar a construtora de demonstração.

Com o Flask em execução, abra o [painel de obras](http://127.0.0.1:5000/painel). Use a porta indicada no terminal se ela for diferente de `5000`.

Para atualizar um banco criado em uma etapa anterior, execute novamente `bd/init_db.py --demo` antes de iniciar o servidor. O inicializador acrescenta as tabelas dos módulos.

## Fluxo de demonstração

1. Cadastre uma obra com previsão de entrega. Abra seu cartão, cadastre uma etapa e registre o progresso.
2. Em **Diário de obra**, salve um registro com atividades, checklist e uma foto opcional. Finalize e compartilhe com o cliente.
3. Em **Financeiro**, cadastre um item de orçamento e uma despesa. Marque a despesa como liquidada e confira o saldo.
4. Em **Aprovações**, solicite uma mudança com impacto no valor e no prazo. Uma aprovação atualiza o orçamento e a previsão de entrega. Um pedido de ajuste registra o motivo.
5. Volte à **Visão geral** para conferir as etapas abertas e as aprovações pendentes.

## Acessos por perfil

O modo padrão é uma demonstração local sem login, com acesso de gestão e possibilidade de simular a decisão do cliente. Para testar os perfis com autenticação obrigatória, pare o Flask e execute a partir da raiz do projeto. Substitua `1` pelo ID da sua construtora.

```powershell
$env:TONY_AUTH_REQUIRED = '1'
$env:TONY_SECRET_KEY = & .\backend\venv\Scripts\python.exe -c 'import secrets; print(secrets.token_hex(32))'
.\backend\venv\Scripts\python.exe -m flask --app backend/app.py criar-administrador --construtora-id 1
.\backend\venv\Scripts\python.exe backend/app.py
```

Use o e-mail e a senha informados no comando para entrar. Em **Configurações**, crie ou vincule contas de mestre de obras e cliente à obra escolhida. Use janelas separadas do navegador para conferir os perfis.

| Perfil | Acesso |
| --- | --- |
| Construtora | Gerencia as obras da própria construtora, etapas, diário, financeiro e acessos. Pode enviar alterações para aprovação. |
| Mestre de obras | Acompanha as obras vinculadas, atualiza o progresso das etapas e registra o diário. |
| Cliente | Acompanha as obras vinculadas, lê os registros de diário compartilhados e responde às alterações. |

No modo com login, requisições de alteração da API exigem a sessão e o cabeçalho `X-CSRF-Token` da página. A coleção do Thunder Client pode ser usada no modo local de demonstração.

## API REST

**Endereço base** `http://127.0.0.1:5000` · **Formato** JSON

| Verbo | Endpoint | Operação | Sucesso | Erros |
| --- | --- | --- | --- | --- |
| GET | `/` | Verifica se a API está em execução | `200` objeto de status | |
| GET | `/obras` | Lista as obras em ordem de ID | `200` array de obras | |
| GET | `/obras/{id}` | Consulta uma obra | `200` objeto da obra | `404` |
| POST | `/obras` | Cadastra uma obra | `201` objeto da obra e cabeçalho `Location` | `400` |
| PUT | `/obras/{id}` | Substitui os dados de uma obra | `200` objeto atualizado | `400`, `404` |
| DELETE | `/obras/{id}` | Exclui uma obra sem registros vinculados | `200` objeto de confirmação | `404`, `409` |

Substitua `{id}` pelo ID numérico retornado no cadastro. O painel em `GET /painel` entrega HTML e usa `GET /obras` e `POST /obras` pelo JavaScript.

### Enviar JSON com POST e PUT

Selecione **Body → JSON** no Thunder Client ou envie o cabeçalho `Content-Type: application/json`. Exemplo de corpo para `POST /obras` ou `PUT /obras/1`:

```json
{
  "construtora_id": 1,
  "nome": "Reforma de demonstração",
  "local": "Cascavel, PR",
  "data_inicio": null,
  "previsao_entrega": "2026-12-15",
  "status": "planejada"
}
```

- `construtora_id` e `nome` são obrigatórios. Use o ID inteiro positivo de uma construtora existente e um nome com até 120 caracteres.
- `local` aceita texto com até 120 caracteres ou `null`. Datas são opcionais e, quando informadas, devem ser válidas no formato `AAAA-MM-DD`. A previsão de entrega deve ser igual ou posterior à data de início.
- `status` aceita `planejada`, `em_andamento` ou `concluida`. Se for omitido, a API usa `planejada`.
- O `PUT` substitui todos os dados da obra. Reenvie os campos que deseja manter. Campos opcionais omitidos ficam nulos, e o status omitido volta ao valor padrão.

### Respostas JSON de sucesso

**GET /** · `200 OK`

```json
{
  "status": "sucesso",
  "projeto": "TONY Gestão de Obras",
  "mensagem": "API da Etapa 1 em execução."
}
```

**GET /obras/1** · `200 OK`. O mesmo formato é retornado por **POST /obras** com `201 Created` e por **PUT /obras/1** com `200 OK`. No cadastro, o cabeçalho `Location` indica a rota do ID criado, por exemplo `/obras/1`.

```json
{
  "id": 1,
  "construtora_id": 1,
  "nome": "Reforma de demonstração",
  "local": "Cascavel, PR",
  "data_inicio": null,
  "previsao_entrega": "2026-12-15",
  "status": "planejada"
}
```

**GET /obras** · `200 OK`. Cada item tem o mesmo formato do exemplo acima. Quando o banco está sem obras, a resposta é `[]`.

```json
[
  {
    "id": 1,
    "construtora_id": 1,
    "nome": "Reforma de demonstração",
    "local": "Cascavel, PR",
    "data_inicio": null,
    "previsao_entrega": "2026-12-15",
    "status": "planejada"
  }
]
```

**DELETE /obras/1** · `200 OK`

```json
{"id": 1, "mensagem": "Obra excluída."}
```

### Respostas JSON de erro

| Código | Quando ocorre | Exemplo de resposta |
| --- | --- | --- |
| `400` | JSON inválido, campo obrigatório ausente ou inválido, ou construtora inexistente | `{"erro":"A construtora informada não existe."}` |
| `401` | O modo com login está ativo e a sessão está ausente | `{"erro":"Entre na sua conta para acessar a API."}` |
| `403` | O perfil não permite a operação ou a requisição de alteração não inclui o token da sessão | `{"erro":"Seu perfil não pode editar obras."}` |
| `404` | O ID numérico informado em GET, PUT ou DELETE não identifica uma obra | `{"erro":"Obra não encontrada."}` |
| `409` | A obra a excluir tem etapas, participantes ou registros vinculados | `{"erro":"A obra tem etapas, participantes ou registros vinculados."}` |

### Testar o fluxo de obras

A coleção [Thunder Client / Postman](docs/tony-etapa-2.postman_collection.json) traz as operações de cadastro, listagem, edição e exclusão. Use a URL base da sua execução e substitua `construtora_id` pelo valor informado na inicialização.

1. Cadastre uma obra de teste com `POST /obras` e anote o ID da resposta `201`.
2. Consulte a lista com `GET /obras` e a obra com `GET /obras/{id}`.
3. Envie o JSON completo para `PUT /obras/{id}`, com `status` igual a `em_andamento`.
4. Exclua a obra de teste com `DELETE /obras/{id}`. Uma nova consulta ao mesmo ID deve retornar `404`.

## Estrutura do projeto

| Pasta | Conteúdo |
| --- | --- |
| `backend/` | API Flask, conexão com o SQLite e dependências Python |
| `bd/` | Modelo inicial, tabelas dos módulos, inicializador e [diagrama da Etapa 1](bd/tony-der.drawio) |
| `frontend/` | Telas do painel em HTML, CSS e JavaScript |

O painel envia os dados em JSON por meio de `fetch`. O Flask valida os campos e acessa o SQLite. Depois de cadastrar uma obra ou recarregar o painel, o JavaScript busca a lista atualizada pela API.

Para conferir o fluxo entre perfis, execute `.\backend\venv\Scripts\python.exe -m unittest discover -s backend -v`. Os testes usam um SQLite temporário.
