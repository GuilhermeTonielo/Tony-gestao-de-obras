"""Cria o banco local do TONY a partir do script SQL da Etapa 1."""

import sqlite3
from contextlib import closing
from pathlib import Path


def inicializar_banco() -> None:
    pasta = Path(__file__).resolve().parent
    banco = pasta / "tony.db"
    script = (pasta / "script.sql").read_text(encoding="utf-8")

    with closing(sqlite3.connect(banco)) as conexao:
        with conexao:
            conexao.executescript(script)

    print(f"Banco SQLite inicializado: {banco}")


if __name__ == "__main__":
    inicializar_banco()
