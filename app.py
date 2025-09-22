import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from math import radians, cos, sin, sqrt, atan2

# App Flask
app = Flask(__name__)

# Configurazione DB da Render
db_url = os.environ.get("DATABASE_URL")
if not db_url:
    raise RuntimeError("❌ DATABASE_URL non impostata. Vai su Render e aggiungi la variabile ambiente.")

# Fix: compatibilità psycopg2
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# ---------------- MODELLI ---------------- #
class Squadra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    partecipanti = db.relationship("Partecipante", backref="squadra", lazy=True)


class Gioco(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    punteggi = db.relationship("Punteggio", backref="gioco", lazy=True)


class Punteggio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    valore = db.Column(db.Float, nullable=False)
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadra.id"), nullable=False)
    gioco_id = db.Column(db.Integer, db.ForeignKey("gioco.id"), nullable=False)


class Partecipante(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    data_nascita = db.Column(db.Date, nullable=False)
    paese = db.Column(db.String(100), nullable=False)
    provincia = db.Column(db.String(10), nullable=False)
    sesso = db.Column(db.String(10), nullable=False)  # M/F/ALTRO
    maneggio = db.Column(db.String(100), nullable=True)
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadra.id"), nullable=False)
    lat = db.Column(db.Float, nullable=True)
    lon = db.Column(db.Float, nullable=True)


# Creazione tabelle
with app.app_context():
    db.create_all()


# ---------------- UTILITY ---------------- #
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2) ** 2
    return R * (2 * atan2(sqrt(a), sqrt(1 - a)))


# ---------------- ROUTES ---------------- #
@app.route("/")
def home():
    # Classifica generale
    punteggi = (
        db.session.query(Squadra, db.func.sum(Punteggio.valore).label("totale"))
        .outerjoin(Punteggio)
        .group_by(Squadra.id)
        .order_by(db.desc("totale"))
        .all()
    )
    totali = [(s, t or 0) for s, t in punteggi]

    # Partecipante più lontano da Ragazzola
    base_lat, base_lon = 45.0176, 10.2217
    partecipanti = Partecipante.query.filter(Partecipante.lat.isnot(None), Partecipante.lon.isnot(None)).all()
    partecipante_lontano, distanza_max = None, 0
    for p in partecipanti:
        d = haversine(base_lat, base_lon, p.lat, p.lon)
        if d > distanza_max:
            distanza_max = d
            partecipante_lontano = p

    # Conteggio maneggi
    maneggi = db.session.query(Partecipante.maneggio, db.func.count(Partecipante.id)).group_by(Partecipante.maneggio).all()
    conteggio_maneggi = {m: n for m, n in maneggi}

    return render_template(
        "home.html",
        totali=totali,
        partecipante_lontano=partecipante_lontano,
        distanza_partecipante_max=distanza_max,
        conteggio_maneggi=conteggio_maneggi,
    )


@app.route("/squadre", methods=["GET", "POST"])
def squadre():
    if request.method == "POST":
        nome = request.form["nome"]
        db.session.add(Squadra(nome=nome))
        db.session.commit()
        return redirect(url_for("squadre"))
    squadre = Squadra.query.order_by(Squadra.nome).all()
    return render_template("squadre.html", squadre=squadre)


@app.route("/giochi", methods=["GET", "POST"])
def giochi():
    if request.method == "POST":
        nome = request.form["nome"]
        db.session.add(Gioco(nome=nome))
        db.session.commit()
        return redirect(url_for("giochi"))
    giochi = Gioco.query.all()
    squadre = Squadra.query.order_by(Squadra.nome).all()
    return render_template("giochi.html", giochi=giochi, squadre=squadre)


@app.route("/partecipanti", methods=["GET", "POST"])
def partecipanti():
    if request.method == "POST":
        nome = request.form["nome"]
        data_nascita = datetime.strptime(request.form["data_nascita"], "%Y-%m-%d")
        paese = request.form["paese"]
        provincia = request.form["provincia"]
        sesso = request.form["sesso"]
        maneggio = request.form["maneggio"]
        squadra_id = request.form["squadra_id"]

        p = Partecipante(
            nome=nome,
            data_nascita=data_nascita,
            paese=paese,
            provincia=provincia,
            sesso=sesso,
            maneggio=maneggio,
            squadra_id=squadra_id
        )
        db.session.add(p)
        db.session.commit()
        return redirect(url_for("partecipanti"))

    partecipanti = Partecipante.query.all()
    squadre = Squadra.query.order_by(Squadra.nome).all()
    return render_template("partecipanti.html", partecipanti=partecipanti, squadre=squadre)


@app.route("/classifica")
def classifica():
    punteggi = (
        db.session.query(Squadra, db.func.sum(Punteggio.valore).label("totale"))
        .outerjoin(Punteggio)
        .group_by(Squadra.id)
        .order_by(db.desc("totale"))
        .all()
    )
    totali = [(s, t or 0) for s, t in punteggi]

    maneggi = db.session.query(Partecipante.maneggio, db.func.count(Partecipante.id)).group_by(Partecipante.maneggio).all()
    conteggio_maneggi = {m: n for m, n in maneggi}

    return render_template("classifica.html", totali=totali, conteggio_maneggi=conteggio_maneggi)


@app.route("/statistiche")
def statistiche():
    oggi = datetime.today()

    # Partecipanti maschi e femmine
    maschi = Partecipante.query.filter_by(sesso="M").all()
    femmine = Partecipante.query.filter_by(sesso="F").all()
    tutti = Partecipante.query.all()

    piu_piccolo_m = min(maschi, key=lambda p: (oggi - p.data_nascita).days) if maschi else None
    piu_piccola_f = min(femmine, key=lambda p: (oggi - p.data_nascita).days) if femmine else None
    piu_vecchio = max(tutti, key=lambda p: (oggi - p.data_nascita).days) if tutti else None

    # Conteggio maneggi
    maneggi = db.session.query(Partecipante.maneggio, db.func.count(Partecipante.id)).group_by(Partecipante.maneggio).all()
    conteggio_maneggi = {m: n for m, n in maneggi}

    # Partecipante più lontano
    base_lat, base_lon = 45.0176, 10.2217
    partecipanti_geo = Partecipante.query.filter(Partecipante.lat.isnot(None), Partecipante.lon.isnot(None)).all()
    partecipante_lontano, distanza_max = None, 0
    for p in partecipanti_geo:
        d = haversine(base_lat, base_lon, p.lat, p.lon)
        if d > distanza_max:
            distanza_max = d
            partecipante_lontano = p

    return render_template(
        "statistiche.html",
        piu_piccolo_m=piu_piccolo_m,
        piu_piccola_f=piu_piccola_f,
        piu_vecchio=piu_vecchio,
        conteggio_maneggi=conteggio_maneggi,
        partecipante_lontano=partecipante_lontano,
        distanza_partecipante_max=distanza_max
    )


# ---------------- MAIN ---------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)

