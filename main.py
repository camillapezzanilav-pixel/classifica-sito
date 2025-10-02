import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import date
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

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

# Geopy
geolocator = Nominatim(user_agent="maneggi_app")
BASE_LAT, BASE_LNG = 44.674, 10.317  # Ragazzona (PR)

# -------------------
# MODELLI
# -------------------
class Squadra(db.Model):
    __tablename__ = "squadre"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    partecipanti = db.relationship("Partecipante", backref="squadra", lazy=True)

class Partecipante(db.Model):
    __tablename__ = "partecipanti"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    nascita = db.Column(db.Date, nullable=False)
    sesso = db.Column(db.String(1))
    luogo = db.Column(db.String(100))
    provincia = db.Column(db.String(10))
    maneggio = db.Column(db.String(100))
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadre.id"))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)

class Gioco(db.Model):
    __tablename__ = "giochi"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)

class Punteggio(db.Model):
    __tablename__ = "punteggi"
    id = db.Column(db.Integer, primary_key=True)
    punti = db.Column(db.Float, default=0, nullable=False)   # decimali
    gioco_id = db.Column(db.Integer, db.ForeignKey("giochi.id"))
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadre.id"))

# -------------------
# ROUTES PRINCIPALI
# -------------------
@app.route("/")
def home():
    # Classifica generale (somma punti di tutte le squadre)
    classifica_generale = (
        db.session.query(Squadra, db.func.sum(Punteggio.punti).label("totale"))
        .outerjoin(Punteggio, Squadra.id == Punteggio.squadra_id)
        .group_by(Squadra.id)
        .order_by(db.desc("totale"))
        .all()
    )

    # Classifica maneggi (conta partecipanti)
    classifica_maneggi = (
        db.session.query(Partecipante.maneggio, db.func.count(Partecipante.id))
        .group_by(Partecipante.maneggio)
        .order_by(db.desc(db.func.count(Partecipante.id)))
        .all()
    )

    # Premiazioni
    youngest_f = Partecipante.query.filter_by(sesso="F").order_by(Partecipante.nascita.desc()).first()
    youngest_m = Partecipante.query.filter_by(sesso="M").order_by(Partecipante.nascita.desc()).first()
    oldest = Partecipante.query.order_by(Partecipante.nascita.asc()).first()

    # Più lontano da Ragazzona
    farthest = None
    for p in Partecipante.query.all():
        if p.lat and p.lng:
            dist = geodesic((BASE_LAT, BASE_LNG), (p.lat, p.lng)).km
            if not farthest or dist > farthest[1]:
                farthest = (p, dist)

    return render_template("home.html",
                           classifica_generale=classifica_generale,
                           classifica_maneggi=classifica_maneggi,
                           youngest_f=youngest_f,
                           youngest_m=youngest_m,
                           oldest=oldest,
                           farthest=farthest)

# -------------------
# GIOCHI
# -------------------
@app.route("/giochi", methods=["GET", "POST"])
def giochi():
    if request.method == "POST":
        nome = request.form["nome"].strip()
        if nome:
            db.session.add(Gioco(nome=nome))
            db.session.commit()
        return redirect(url_for("giochi"))

    giochi = Gioco.query.all()
    return render_template("giochi.html", giochi=giochi)

# -------------------
# SQUADRE
# -------------------
@app.route("/squadre", methods=["GET", "POST"])
def squadre():
    if request.method == "POST":
        nome = request.form["nome"].strip()
        if nome:
            db.session.add(Squadra(nome=nome))
            db.session.commit()
        return redirect(url_for("squadre"))

    squadre = Squadra.query.order_by(Squadra.nome).all()
    return render_template("squadre.html", squadre=squadre)

@app.route("/squadre/<int:id>", methods=["GET", "POST"])
def dettaglio_squadra(id):
    squadra = Squadra.query.get_or_404(id)
    giochi = Gioco.query.all()

    if request.method == "POST":
        for gioco in giochi:
            punti = 0.0
            try:
                if gioco.nome.lower() == "quiz":
                    # Somma delle 5 domande
                    vals = []
                    for i in range(1, 6):
                        v = request.form.get(f"quiz_{i}")
                        if v:
                            vals.append(float(v))
                    punti = sum(vals)
                else:
                    punti_str = request.form.get(f"gioco_{gioco.id}")
                    if punti_str and punti_str.strip() != "":
                        punti = float(punti_str)
            except ValueError:

