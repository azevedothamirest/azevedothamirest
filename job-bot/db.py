import json
import sqlite3
import os

DB = os.environ.get("JOBBOT_DB", "jobbot.db")


def con():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS vagas(
        id TEXT PRIMARY KEY, dados TEXT, analise TEXT, nota INTEGER,
        status TEXT DEFAULT 'nova', criada TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS inhire(empresa TEXT PRIMARY KEY);
    """)
    return c


def existe(vid):
    with con() as c:
        return c.execute("SELECT 1 FROM vagas WHERE id=?", (vid,)).fetchone() is not None


def salvar(vaga, analise, nota, status):
    with con() as c:
        c.execute("INSERT OR REPLACE INTO vagas(id,dados,analise,nota,status) VALUES(?,?,?,?,?)",
                  (vaga.id, json.dumps(vaga.__dict__, ensure_ascii=False),
                   json.dumps(analise, ensure_ascii=False), nota, status))


def pegar(vid):
    with con() as c:
        return c.execute("SELECT * FROM vagas WHERE id=?", (vid,)).fetchone()


def status(vid, st):
    with con() as c:
        c.execute("UPDATE vagas SET status=? WHERE id=?", (st, vid))


def por_status(*sts):
    with con() as c:
        q = ",".join("?" * len(sts))
        return c.execute(f"SELECT * FROM vagas WHERE status IN ({q}) ORDER BY nota DESC", sts).fetchall()


def empresas_inhire(padrao):
    with con() as c:
        for e in padrao:
            c.execute("INSERT OR IGNORE INTO inhire VALUES(?)", (e,))
        return [r[0] for r in c.execute("SELECT empresa FROM inhire")]


def add_inhire(e):
    with con() as c:
        c.execute("INSERT OR IGNORE INTO inhire VALUES(?)", (e,))
