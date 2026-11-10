from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3


DB_PATH = Path(__file__).resolve().parents[1] / "bd" / "tony.db"


@contextmanager
def obter_conexao(caminho: str | Path = DB_PATH):
    # mode=rw evita criar silenciosamente um banco vazio no caminho errado.
    uri = Path(caminho).resolve().as_uri() + "?mode=rw"
    with closing(sqlite3.connect(uri, uri=True)) as conexao:
        conexao.row_factory = sqlite3.Row
        conexao.execute("PRAGMA foreign_keys = ON")
        with conexao:
            yield conexao
