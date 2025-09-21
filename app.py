import os
from math import radians, sin, cos, sqrt, atan2
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configurazione database (Render fornisce DATABASE_URL)
db_url = os.environ.get("DATABASE_URL")
if not db_url:
    raise RuntimeError("❌ DATABASE_URL non impostata. Vai su Render e aggiungila come variabile ambiente.")

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# =====================
# MODELLI
# =====================
class Squadra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    partecipanti = db.relationship("Partecipante", backref="squadra", lazy=True)
    punteggi = db.relationship("Punteggio", backref="squadra", lazy=True)

class Gioco(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    punteggi = db.relationship("Punteggio", backref="gioco", lazy=True)

class Partecipante(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    data_nascita = db.Column(db.Date, nullable=False)
    paese = db.Column(db.String(100), nullable=False)
    provincia = db.Column(db.String(10), nullable=False)
    sesso = db.Column(db.String(10), nullable=False)
    maneggio = db.Column(db.String(100), nullable=True)
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadra.id"), nullable=True)
    lat = db.Column(db.Float, nullable=True)
    lon = db.Column(db.Float, nullable=True)

class Punteggio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadra.id"), nullable=False)
    gioco_id = db.Column(db.Integer, db.ForeignKey("gioco.id"), nullable=False)
    punti = db.Column(db.Float, nullable=False)

# =====================
# FUNZIONE DISTANZA
# =====================
def distanza_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

# =====================
# CREAZIONE TABELLE
# =====================
with app.app_context():
    db.create_all()

# =====================
# ROUTES
# =====================
@app.route("/")
def home():
    squadre = Squadra.query.all()
    totali = []
    for squadra in squadre:
        punteggi = Punteggio.query.filter_by(squadra_id=squadra.id).all()
        totale = sum(p.punti for p in punteggi)
        totali.append((squadra, totale))
    totali.sort(key=lambda x: x[1], reverse=True)

    partecipanti = Partecipante.query.all()
    conteggio_maneggi = {}
    partecipante_lontano = None
    distanza_max = 0
    ref_lat, ref_lon = 45.0166, 10.2187  # Ragazzola

    for p in partecipanti:
        if p.maneggio:
            conteggio_maneggi[p.maneggio] = conteggio_maneggi.get(p.maneggio, 0) + 1
        if p.lat and p.lon:
            dist = distanza_km(ref_lat, ref_lon, p.lat, p.lon)
            if dist > distanza_max:
                distanza_max = dist
                partecipante_lontano = p

    return render_template("home.html",
                           totali=totali,
                           conteggio_maneggi=conteggio_maneggi,
                           partecipante_lontano=partecipante_lontano,
                           distanza_partecipante_max=distanza_max)

@app.route("/classifica")
def classifica():
    squadre = Squadra.query.all()
    totali = []
    for squadra in squadre:
        punteggi = Punteggio.query.filter_by(squadra_id=squadra.id).all()
        totale = sum(p.punti for p in punteggi)
        totali.append((squadra, totale))
    totali.sort(key=lambda x: x[1], reverse=True)

    partecipanti = Partecipante.query.all()
    conteggio_maneggi = {}
    partecipante_lontano = None
    distanza_max = 0
    ref_lat, ref_lon = 45.0166, 10.2187

    for p in partecipanti:
        if p.maneggio:
            conteggio_maneggi[p.maneggio] = conteggio_maneggi.get(p.maneggio, 0) + 1
        if p.lat and p.lon:
            dist = distanza_km(ref_lat, ref_lon, p.lat, p.lon)
            if dist > distanza_max:
                distanza_max = dist
                partecipante_lontano = p

    return render_template("classifica.html",
                           totali=totali,
                           conteggio_maneggi=conteggio_maneggi,
                           partecipante_lontano=partecipante_lontano,
                           distanza_partecipante_max=distanza_max)

@app.route("/statistiche")
def statistiche():
    partecipanti = Partecipante.query.all()
    conteggio_maneggi = {}
    for p in partecipanti:
        if p.maneggio:
            conteggio_maneggi[p.maneggio] = conteggio_maneggi.get(p.maneggio, 0) + 1

    return render_template("statistiche.html", conteggio_maneggi=conteggio_maneggi)

# =====================
# MAIN
# =====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)

