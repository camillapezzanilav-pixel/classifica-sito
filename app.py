import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from math import radians, cos, sin, sqrt, atan2
from collections import Counter

# -------------------
# CONFIGURAZIONE APP
# -------------------
app = Flask(__name__)

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    raise RuntimeError("❌ DATABASE_URL non impostata.")

# Fix compatibilità postgres:// → postgresql://
app.config["SQLALCHEMY_DATABASE_URI"] = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# -------------------
# MODELLI DB
# -------------------
class Squadra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)


class Gioco(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)


class Punteggio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    valore = db.Column(db.Float, nullable=False)  # punti
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadra.id"), nullable=False)
    gioco_id = db.Column(db.Integer, db.ForeignKey("gioco.id"), nullable=False)


class Partecipante(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    data_nascita = db.Column(db.Date, nullable=True)
    paese = db.Column(db.String(100))
    provincia = db.Column(db.String(50))
    sesso = db.Column(db.String(10))
    maneggio = db.Column(db.String(100))
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadra.id"))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)


# -------------------
# FUNZIONE DISTANZA
# -------------------
def distanza_km(lat1, lon1, lat2, lon2):
    """Calcola la distanza tra due coordinate (km)"""
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


# -------------------
# HOME
# -------------------
@app.route("/")
def home():
    # Classifica generale squadre
    totali = (
        db.session.query(Squadra, db.func.sum(Punteggio.valore).label("totale"))
        .outerjoin(Punteggio, Squadra.id == Punteggio.squadra_id)
        .group_by(Squadra.id)
        .order_by(db.desc("totale"))
        .all()
    )

    # Maneggio con più partecipanti
    maneggi = [p.maneggio for p in Partecipante.query.all() if p.maneggio]
    conteggio_maneggi = dict(Counter(maneggi))

    # Partecipante più lontano da Ragazzola
    lat_rag, lon_rag = 44.939, 10.323
    partecipanti = Partecipante.query.all()
    partecipante_lontano = None
    distanza_max = 0
    for p in partecipanti:
        if p.lat and p.lon:
            d = distanza_km(lat_rag, lon_rag, p.lat, p.lon)
            if d > distanza_max:
                distanza_max = d
                partecipante_lontano = p

    return render_template(
        "home.html",
        totali=totali,
        conteggio_maneggi=conteggio_maneggi,
        partecipante_lontano=partecipante_lontano,
        distanza_partecipante_max=distanza_max,
    )


# -------------------
# CLASSIFICA
# -------------------
@app.route("/classifica")
def classifica():
    # Classifica squadre
    totali = (
        db.session.query(Squadra, db.func.sum(Punteggio.valore).label("totale"))
        .outerjoin(Punteggio, Squadra.id == Punteggio.squadra_id)
        .group_by(Squadra.id)
        .order_by(db.desc("totale"))
        .all()
    )

    # Classifica maneggi
    maneggi = [p.maneggio for p in Partecipante.query.all() if p.maneggio]
    conteggio_maneggi = dict(Counter(maneggi))

    return render_template("classifica.html", totali=totali, conteggio_maneggi=conteggio_maneggi)


# -------------------
# SQUADRE
# -------------------
@app.route("/squadre", methods=["GET", "POST"])
def squadre():
    if request.method == "POST":
        nome = request.form["nome"]
        if nome:
            nuova = Squadra(nome=nome)
            db.session.add(nuova)
            db.session.commit()
        return redirect(url_for("squadre"))

    squadre = Squadra.query.all()
    return render_template("squadre.html", squadre=squadre)


# -------------------
# GIOCHI + PUNTEGGI
# -------------------
@app.route("/giochi", methods=["GET", "POST"])
def giochi():
    if request.method == "POST":
        nome = request.form["nome"]
        if nome:
            nuovo = Gioco(nome=nome)
            db.session.add(nuovo)
            db.session.commit()
        return redirect(url_for("giochi"))

    giochi = Gioco.query.all()
    return render_template("giochi.html", giochi=giochi)


@app.route("/giochi/<int:gioco_id>", methods=["GET", "POST"])
def dettaglio_gioco(gioco_id):
    gioco = Gioco.query.get_or_404(gioco_id)
    squadre = Squadra.query.order_by(Squadra.nome).all()

    if request.method == "POST":
        squadra_id = request.form["squadra_id"]
        valore = float(request.form["valore"])
        nuovo = Punteggio(valore=valore, squadra_id=squadra_id, gioco_id=gioco_id)
        db.session.add(nuovo)
        db.session.commit()
        return redirect(url_for("dettaglio_gioco", gioco_id=gioco_id))

    punteggi = (
        db.session.query(Punteggio, Squadra)
        .join(Squadra, Squadra.id == Punteggio.squadra_id)
        .filter(Punteggio.gioco_id == gioco_id)
        .all()
    )

    return render_template("dettaglio_gioco.html", gioco=gioco, squadre=squadre, punteggi=punteggi)


# -------------------
# PARTECIPANTI
# -------------------
@app.route("/partecipanti", methods=["GET", "POST"])
def partecipanti():
    if request.method == "POST":
        nome = request.form["nome"]
        data_nascita = datetime.strptime(request.form["data_nascita"], "%Y-%m-%d").date()
        paese = request.form["paese"]
        provincia = request.form["provincia"]
        sesso = request.form["sesso"]
        maneggio = request.form["maneggio"]
        squadra_id = request.form["squadra_id"]

        nuovo = Partecipante(
            nome=nome,
            data_nascita=data_nascita,
            paese=paese,
            provincia=provincia,
            sesso=sesso,
            maneggio=maneggio,
            squadra_id=squadra_id,
        )
        db.session.add(nuovo)
        db.session.commit()
        return redirect(url_for("partecipanti"))

    partecipanti = Partecipante.query.all()
    squadre = Squadra.query.all()
    return render_template("partecipanti.html", partecipanti=partecipanti, squadre=squadre)


# -------------------
# STATISTICHE
# -------------------
@app.route("/statistiche")
def statistiche():
    partecipanti = Partecipante.query.all()

    maschi = [p for p in partecipanti if p.sesso == "M" and p.data_nascita]
    femmine = [p for p in partecipanti if p.sesso == "F" and p.data_nascita]

    maschio_giovane = min(maschi, key=lambda p: p.data_nascita, default=None)
    femmina_giovane = min(femmine, key=lambda p: p.data_nascita, default=None)
    piu_vecchio = max(partecipanti, key=lambda p: p.data_nascita or datetime.max.date(), default=None)

    # Partecipante più lontano
    lat_rag, lon_rag = 44.939, 10.323
    partecipante_lontano = None
    distanza_max = 0
    for p in partecipanti:
        if p.lat and p.lon:
            d = distanza_km(lat_rag, lon_rag, p.lat, p.lon)
            if d > distanza_max:
                distanza_max = d
                partecipante_lontano = p

    # Maneggio più numeroso
    maneggi = [p.maneggio for p in partecipanti if p.maneggio]
    maneggio_top = None
    n_partecipanti = 0
    if maneggi:
        conteggio = Counter(maneggi)
        maneggio_top, n_partecipanti = conteggio.most_common(1)[0]

    return render_template(
        "statistiche.html",
        maschio_giovane=maschio_giovane,
        femmina_giovane=femmina_giovane,
        piu_vecchio=piu_vecchio,
        partecipante_lontano=partecipante_lontano,
        distanza_partecipante_max=distanza_max,
        maneggio_top=maneggio_top,
        n_partecipanti=n_partecipanti,
    )


# -------------------
# CREAZIONE TABELLE
# -------------------
with app.app_context():
    db.create_all()


# -------------------
# MAIN
# -------------------
if __name__ == "__main__":
    app.run(debug=True)

