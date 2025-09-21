import os
import math
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Configurazione Flask
app = Flask(__name__)

# Database URL da Render (variabile ambiente)
db_url = os.environ.get("DATABASE_URL")
if db_url is None:
    raise ValueError("❌ DATABASE_URL non impostata. Vai su Render e aggiungi la variabile ambiente.")
# Fix per psycopg su Render
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ================================
# MODELLI
# ================================
class Squadra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)

class Gioco(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)

class Partecipante(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    data_nascita = db.Column(db.Date, nullable=True)
    paese = db.Column(db.String(100), nullable=True)
    provincia = db.Column(db.String(100), nullable=True)
    sesso = db.Column(db.String(10), nullable=True)  # M/F/ALTRO
    maneggio = db.Column(db.String(100), nullable=True)
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadra.id"))
    squadra = db.relationship("Squadra", backref=db.backref("partecipanti", lazy=True))
    lat = db.Column(db.Float, nullable=True)
    lon = db.Column(db.Float, nullable=True)

class Punteggio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadra.id"), nullable=False)
    gioco_id = db.Column(db.Integer, db.ForeignKey("gioco.id"), nullable=False)
    punti = db.Column(db.Float, nullable=False)

    squadra = db.relationship("Squadra", backref=db.backref("punteggi", lazy=True))
    gioco = db.relationship("Gioco", backref=db.backref("punteggi", lazy=True))

# Creazione forzata tabelle
with app.app_context():
    db.create_all()

# ================================
# FUNZIONI DI SUPPORTO
# ================================
def distanza_km(lat1, lon1, lat2, lon2):
    """Calcola distanza in km tra due coordinate (formula Haversine)."""
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

# ================================
# ROUTES
# ================================
@app.route("/")
def home():
    # Classifica generale
    squadre = Squadra.query.all()
    totali = []
    for squadra in squadre:
        punteggi = Punteggio.query.filter_by(squadra_id=squadra.id).all()
        totale = sum(p.punti for p in punteggi)
        totali.append((squadra, totale))
    totali.sort(key=lambda x: x[1], reverse=True)

    return render_template("home.html", totali=totali)

@app.route("/giochi", methods=["GET", "POST"])
def giochi():
    if request.method == "POST":
        nome = request.form.get("nome")
        if nome:
            db.session.add(Gioco(nome=nome))
            db.session.commit()
        return redirect(url_for("giochi"))

    giochi = Gioco.query.all()
    squadre = Squadra.query.order_by(Squadra.nome.asc()).all()
    punteggi = Punteggio.query.all()
    return render_template("giochi.html", giochi=giochi, squadre=squadre, punteggi=punteggi)

@app.route("/squadre", methods=["GET", "POST"])
def squadre():
    if request.method == "POST":
        nome = request.form.get("nome")
        if nome:
            db.session.add(Squadra(nome=nome))
            db.session.commit()
        return redirect(url_for("squadre"))

    squadre = Squadra.query.all()
    return render_template("squadre.html", squadre=squadre)

@app.route("/partecipanti", methods=["GET", "POST"])
def partecipanti():
    if request.method == "POST":
        nome = request.form.get("nome")
        data_nascita = request.form.get("data_nascita")
        paese = request.form.get("paese")
        provincia = request.form.get("provincia")
        sesso = request.form.get("sesso")
        maneggio = request.form.get("maneggio")
        squadra_id = request.form.get("squadra_id")

        data_nascita = datetime.strptime(data_nascita, "%Y-%m-%d").date() if data_nascita else None

        nuovo = Partecipante(
            nome=nome,
            data_nascita=data_nascita,
            paese=paese,
            provincia=provincia,
            sesso=sesso,
            maneggio=maneggio,
            squadra_id=squadra_id
        )
        db.session.add(nuovo)
        db.session.commit()
        return redirect(url_for("partecipanti"))

    partecipanti = Partecipante.query.all()
    squadre = Squadra.query.all()
    return render_template("partecipanti.html", partecipanti=partecipanti, squadre=squadre)

@app.route("/classifica")
def classifica():
    # Totali squadre
    squadre = Squadra.query.all()
    totali = []
    for squadra in squadre:
        punteggi = Punteggio.query.filter_by(squadra_id=squadra.id).all()
        totale = sum(p.punti for p in punteggi)
        totali.append((squadra, totale))
    totali.sort(key=lambda x: x[1], reverse=True)

    # Conteggio maneggi + partecipante più lontano
    partecipanti = Partecipante.query.all()
    conteggio_maneggi = {}
    partecipante_lontano = None
    distanza_partecipante_max = 0.0

    base_lat, base_lon = 45.0126, 10.2153  # 📍 Ragazzola (PR)

    for p in partecipanti:
        if p.maneggio:
            conteggio_maneggi[p.maneggio] = conteggio_maneggi.get(p.maneggio, 0) + 1

        if p.lat and p.lon:
            dist = distanza_km(base_lat, base_lon, p.lat, p.lon)

            # Aggiorna partecipante più lontano
            if dist > distanza_partecipante_max:
                distanza_partecipante_max = dist
                partecipante_lontano = p

    return render_template(
        "classifica.html",
        totali=totali,
        conteggio_maneggi=conteggio_maneggi,
        partecipante_lontano=partecipante_lontano,
        distanza_partecipante_max=distanza_partecipante_max
    )

# ================================
# MAIN
# ================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

