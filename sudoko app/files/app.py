"""
Sudoku webserver
-----------------
Een kleine Flask-app die:
- de Sudoku-webpagina serveert aan iedereen op je netwerk
- een gedeeld scorebord bijhoudt in een SQLite-database (tijden per moeilijkheid)
- een "race-mode" ondersteunt: iedereen krijgt dezelfde puzzel, met live ranglijst

Starten:
    pip install flask
    python app.py

Daarna is het spel bereikbaar op:
    http://localhost:5000            (op deze computer zelf)
    http://<jouw-lokale-ip>:5000      (voor andere apparaten op hetzelfde wifi-netwerk)

Hoe vind je je lokale IP-adres?
    Windows:      ipconfig            -> kijk bij "IPv4-adres"
    Mac / Linux:  ifconfig  of  ip a  -> kijk bij "inet" onder je wifi-adapter
"""

import json
import random
import sqlite3
import time
import uuid
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request

APP_DIR = Path(__file__).parent
DB_PAD = APP_DIR / "sudoku_scores.db"

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PAD)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def sluit_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PAD)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            naam TEXT NOT NULL,
            moeilijkheid TEXT NOT NULL,
            tijd_seconden REAL NOT NULL,
            aangemaakt_op TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS races (
            race_id TEXT PRIMARY KEY,
            moeilijkheid TEXT NOT NULL,
            puzzel TEXT NOT NULL,
            oplossing TEXT NOT NULL,
            gestart_op TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS race_resultaten (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id TEXT NOT NULL,
            naam TEXT NOT NULL,
            tijd_seconden REAL NOT NULL,
            voltooid_op TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Sudoku-generator (zelfde logica als de losse versies)
# ---------------------------------------------------------------------------

def maak_leeg_bord():
    return [[0] * 9 for _ in range(9)]


def is_geldig(bord, rij, kolom, waarde):
    for i in range(9):
        if bord[rij][i] == waarde or bord[i][kolom] == waarde:
            return False
    blok_rij, blok_kolom = 3 * (rij // 3), 3 * (kolom // 3)
    for r in range(blok_rij, blok_rij + 3):
        for k in range(blok_kolom, blok_kolom + 3):
            if bord[r][k] == waarde:
                return False
    return True


def vind_lege_cel(bord):
    for r in range(9):
        for k in range(9):
            if bord[r][k] == 0:
                return r, k
    return None


def los_op(bord):
    cel = vind_lege_cel(bord)
    if cel is None:
        return True
    rij, kolom = cel
    cijfers = list(range(1, 10))
    random.shuffle(cijfers)
    for waarde in cijfers:
        if is_geldig(bord, rij, kolom, waarde):
            bord[rij][kolom] = waarde
            if los_op(bord):
                return True
            bord[rij][kolom] = 0
    return False


def genereer_volledig_bord():
    bord = maak_leeg_bord()
    los_op(bord)
    return bord


MOEILIJKHEID_CLUES = {"Makkelijk": 42, "Gemiddeld": 32, "Moeilijk": 24}


def genereer_puzzel(moeilijkheid):
    oplossing = genereer_volledig_bord()
    puzzel = [rij[:] for rij in oplossing]

    aantal_clues = MOEILIJKHEID_CLUES.get(moeilijkheid, 32)
    aantal_te_verwijderen = 81 - aantal_clues

    posities = [(r, k) for r in range(9) for k in range(9)]
    random.shuffle(posities)

    for r, k in posities[:aantal_te_verwijderen]:
        puzzel[r][k] = 0

    return puzzel, oplossing


# ---------------------------------------------------------------------------
# Pagina
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# API: eigen puzzel + gedeeld scorebord
# ---------------------------------------------------------------------------

@app.route("/api/puzzel")
def api_puzzel():
    moeilijkheid = request.args.get("moeilijkheid", "Gemiddeld")
    if moeilijkheid not in MOEILIJKHEID_CLUES:
        moeilijkheid = "Gemiddeld"
    puzzel, oplossing = genereer_puzzel(moeilijkheid)
    return jsonify({"moeilijkheid": moeilijkheid, "puzzel": puzzel, "oplossing": oplossing})


@app.route("/api/score", methods=["POST"])
def api_score_opslaan():
    data = request.get_json(force=True)
    naam = (data.get("naam") or "Anoniem").strip()[:30] or "Anoniem"
    moeilijkheid = data.get("moeilijkheid", "Gemiddeld")
    tijd_seconden = float(data.get("tijd_seconden", 0))

    if moeilijkheid not in MOEILIJKHEID_CLUES:
        return jsonify({"fout": "Ongeldige moeilijkheidsgraad"}), 400
    if tijd_seconden <= 0:
        return jsonify({"fout": "Ongeldige tijd"}), 400

    db = get_db()
    db.execute(
        "INSERT INTO scores (naam, moeilijkheid, tijd_seconden) VALUES (?, ?, ?)",
        (naam, moeilijkheid, tijd_seconden),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/leaderboard")
def api_leaderboard():
    moeilijkheid = request.args.get("moeilijkheid", "Gemiddeld")
    limiet = int(request.args.get("limiet", 10))

    db = get_db()
    rijen = db.execute(
        """
        SELECT naam, tijd_seconden, aangemaakt_op
        FROM scores
        WHERE moeilijkheid = ?
        ORDER BY tijd_seconden ASC
        LIMIT ?
        """,
        (moeilijkheid, limiet),
    ).fetchall()

    return jsonify([dict(rij) for rij in rijen])


# ---------------------------------------------------------------------------
# API: race-mode (iedereen dezelfde puzzel, live ranglijst)
# ---------------------------------------------------------------------------

@app.route("/api/race/start", methods=["POST"])
def api_race_start():
    data = request.get_json(force=True)
    moeilijkheid = data.get("moeilijkheid", "Gemiddeld")
    if moeilijkheid not in MOEILIJKHEID_CLUES:
        moeilijkheid = "Gemiddeld"

    puzzel, oplossing = genereer_puzzel(moeilijkheid)
    race_id = uuid.uuid4().hex[:8]

    db = get_db()
    db.execute(
        "INSERT INTO races (race_id, moeilijkheid, puzzel, oplossing) VALUES (?, ?, ?, ?)",
        (race_id, moeilijkheid, json.dumps(puzzel), json.dumps(oplossing)),
    )
    db.commit()

    return jsonify({
        "race_id": race_id,
        "moeilijkheid": moeilijkheid,
        "puzzel": puzzel,
        "oplossing": oplossing,
    })


@app.route("/api/race/current")
def api_race_huidig():
    """Geeft de meest recent gestarte race terug, zodat andere spelers
    kunnen detecteren dat er een nieuwe race gestart is en automatisch meedoen."""
    db = get_db()
    rij = db.execute(
        "SELECT * FROM races ORDER BY gestart_op DESC, rowid DESC LIMIT 1"
    ).fetchone()

    if rij is None:
        return jsonify(None)

    return jsonify({
        "race_id": rij["race_id"],
        "moeilijkheid": rij["moeilijkheid"],
        "puzzel": json.loads(rij["puzzel"]),
        "oplossing": json.loads(rij["oplossing"]),
        "gestart_op": rij["gestart_op"],
    })


@app.route("/api/race/finish", methods=["POST"])
def api_race_finish():
    data = request.get_json(force=True)
    race_id = data.get("race_id")
    naam = (data.get("naam") or "Anoniem").strip()[:30] or "Anoniem"
    tijd_seconden = float(data.get("tijd_seconden", 0))

    if not race_id or tijd_seconden <= 0:
        return jsonify({"fout": "Ongeldige gegevens"}), 400

    db = get_db()

    # Voorkom dubbele inzendingen van dezelfde naam voor dezelfde race
    bestaat_al = db.execute(
        "SELECT 1 FROM race_resultaten WHERE race_id = ? AND naam = ?",
        (race_id, naam),
    ).fetchone()
    if bestaat_al:
        return jsonify({"fout": "Deze naam heeft deze race al voltooid"}), 400

    db.execute(
        "INSERT INTO race_resultaten (race_id, naam, tijd_seconden) VALUES (?, ?, ?)",
        (race_id, naam, tijd_seconden),
    )
    db.commit()

    # Sla ook op in het algemene scorebord
    race_rij = db.execute(
        "SELECT moeilijkheid FROM races WHERE race_id = ?", (race_id,)
    ).fetchone()
    if race_rij:
        db.execute(
            "INSERT INTO scores (naam, moeilijkheid, tijd_seconden) VALUES (?, ?, ?)",
            (naam, race_rij["moeilijkheid"], tijd_seconden),
        )
        db.commit()

    return jsonify({"ok": True})


@app.route("/api/race/resultaten/<race_id>")
def api_race_resultaten(race_id):
    db = get_db()
    rijen = db.execute(
        """
        SELECT naam, tijd_seconden, voltooid_op
        FROM race_resultaten
        WHERE race_id = ?
        ORDER BY tijd_seconden ASC
        """,
        (race_id,),
    ).fetchall()
    return jsonify([dict(rij) for rij in rijen])


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    print("\nSudoku-server draait!")
    print("  Op deze computer:      http://localhost:5000")
    print("  Voor anderen op wifi:  http://<jouw-lokale-ip>:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=False)

'web adres http://192.168.178.143:5000'