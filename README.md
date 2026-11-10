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
