"""Cria o banco local do TONY a partir do script SQL da Etapa 1."""

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path


def inicializar_banco(com_dados_demo: bool = False) -> None:
    pasta = Path(__file__).resolve().parent
    banco = pasta / "tony.db"
    script = "\n".join((pasta / nome).read_text(encoding="utf-8") for nome in ("script.sql", "modulos.sql"))

    with closing(sqlite3.connect(banco)) as conexao:
        with conexao:
            conexao.executescript(script)
            if com_dados_demo:
                nome = "Construtora Demo TONY"
                conexao.execute(
                    """INSERT INTO construtoras (nome)
                       SELECT ? WHERE NOT EXISTS (
                           SELECT 1 FROM construtoras WHERE nome = ?
                       )""",
                    (nome, nome),
                )
                demo_id = conexao.execute(
                    "SELECT MIN(id) FROM construtoras WHERE nome = ?", (nome,)
                ).fetchone()[0]

    print(f"Banco SQLite inicializado: {banco}")
    if com_dados_demo:
        print(f"Construtora de demonstração: {nome} (construtora_id: {demo_id})")


if __name__ == "__main__":
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--demo", action="store_true", help="cadastra uma construtora fictícia")
    inicializar_banco(argumentos.parse_args().demo)
