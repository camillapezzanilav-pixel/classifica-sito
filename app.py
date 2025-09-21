import os
from datetime import date
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from math import radians, sin, cos, sqrt, atan2

# -----------------------------------
# Configurazione Flask + Database
# -----------------------------------
app = Flask(__name__)

db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise ValueError("❌ DATABASE_URL non impostata. Vai su Render e aggiungi la variabile ambiente.")

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# -----------------------------------
# MODELS
# -----------------------------------
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
    paese = db.Column(db.String(100))
    provincia = db.Column(db.String(50))
    sesso = db.Column(db.String(10))
    maneggio = db.Column(db.String(100))
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadra.id"), nullable=True)
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)

class Punteggio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    punti = db.Column(db.Float, nullable=False)
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadra.id"), nullable=False)
    gioco_id = db.Column(db.Integer, db.ForeignKey("gioco.id"), nullable=False)

# Creazione tabelle se non esistono
with app.app_context():
    db.create_all()

# -----------------------------------
# UTILS
# -----------------------------------
def calcola_eta(data_nascita):
    oggi = date.today()
    return oggi.year - data_nascita.year - ((oggi.month, oggi.day) < (data_nascita.month, data_nascita.day))

def calcola_distanza(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

# Coordinate di Ragazzola
BASE_LAT, BASE_LON = 45.0167, 10.2000

# -----------------------------------
# ROUTES
# -----------------------------------

@app.route("/")
def home():
    # Classifica totale
    totali = (
        db.session.query(Squadra.nome, db.func.sum(Punteggio.punti).label("punti"))
        .join(Punteggio, Squadra.id == Punteggio.squadra_id)
        .group_by(Squadra.id)
        .order_by(db.desc("punti"))
        .all()
    )

    # Statistiche veloci
    partecipanti = Partecipante.query.all()

    maschio_piu_piccolo = min([p for p in partecipanti if p.sesso == "M"], key=lambda x: x.data_nascita, default=None)
    femmina_piu_piccola = min([p for p in partecipanti if p.sesso == "F"], key=lambda x: x.data_nascita, default=None)
    piu_vecchio = max(partecipanti, key=lambda x: x.data_nascita, default=None)

    # Partecipante più lontano
    partecipante_piu_lontano = None
    max_distanza = 0
    for p in partecipanti:
        if p.lat and p.lon:
            distanza = calcola_distanza(BASE_LAT, BASE_LON, p.lat, p.lon)
            if distanza > max_distanza:
                max_distanza = distanza
                partecipante_piu_lontano = (p, distanza)

    # Maneggio con più partecipanti
    conteggio_maneggi = {}
    for p in partecipanti:
        if p.maneggio:
            conteggio_maneggi[p.maneggio] = conteggio_maneggi.get(p.maneggio, 0) + 1
    maneggio_top = max(conteggio_maneggi, key=conteggio_maneggi.get) if conteggio_maneggi else None

    return render_template(
        "home.html",
        totali=totali,
        maschio_piu_piccolo=maschio_piu_piccolo,
        femmina_piu_piccola=femmina_piu_piccola,
        piu_vecchio=piu_vecchio,
        partecipante_piu_lontano=partecipante_piu_lontano,
        maneggio_top=maneggio_top,
        conteggio_maneggi=conteggio_maneggi
    )

# ----------------- Squadre -----------------
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

@app.route("/squadre/delete/<int:id>")
def elimina_squadra(id):
    squadra = Squadra.query.get(id)
    if squadra:
        db.session.delete(squadra)
        db.session.commit()
    return redirect(url_for("squadre"))

# ----------------- Giochi -----------------
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
    squadre = Squadra.query.order_by(Squadra.nome).all()  # Ordinate alfabeticamente
    return render_template("giochi.html", giochi=giochi, squadre=squadre)

@app.route("/giochi/delete/<int:id>")
def elimina_gioco(id):
    gioco = Gioco.query.get(id)
    if gioco:
        db.session.delete(gioco)
        db.session.commit()
    return redirect(url_for("giochi"))

@app.route("/punteggi/add", methods=["POST"])
def aggiungi_punteggio():
    squadra_id = request.form["squadra_id"]
    gioco_id = request.form["gioco_id"]
    punti = float(request.form["punti"])
    esistente = Punteggio.query.filter_by(squadra_id=squadra_id, gioco_id=gioco_id).first()
    if esistente:
        esistente.punti = punti
    else:
        nuovo = Punteggio(squadra_id=squadra_id, gioco_id=gioco_id, punti=punti)
        db.session.add(nuovo)
    db.session.commit()
    return redirect(url_for("giochi"))

@app.route("/punteggi/delete/<int:id>")
def elimina_punteggio(id):
    p = Punteggio.query.get(id)
    if p:
        db.session.delete(p)
        db.session.commit()
    return redirect(url_for("giochi"))

# ----------------- Partecipanti -----------------
@app.route("/partecipanti", methods=["GET", "POST"])
def partecipanti():
    if request.method == "POST":
        nome = request.form["nome"]
        data_nascita = date.fromisoformat(request.form["data_nascita"])
        paese = request.form.get("paese")
        provincia = request.form.get("provincia")
        sesso = request.form.get("sesso")
        maneggio = request.form.get("maneggio")
        squadra_id = request.form.get("squadra_id") or None
        lat = request.form.get("lat")
        lon = request.form.get("lon")

        nuovo = Partecipante(
            nome=nome, data_nascita=data_nascita, paese=paese, provincia=provincia,
            sesso=sesso, maneggio=maneggio, squadra_id=squadra_id,
            lat=float(lat) if lat else None, lon=float(lon) if lon else None
        )
        db.session.add(nuovo)
        db.session.commit()
        return redirect(url_for("partecipanti"))

    partecipanti = Partecipante.query.all()
    squadre = Squadra.query.all()
    return render_template("partecipanti.html", partecipanti=partecipanti, squadre=squadre)

@app.route("/partecipanti/delete/<int:id>")
def elimina_partecipante(id):
    p = Partecipante.query.get(id)
    if p:
        db.session.delete(p)
        db.session.commit()
    return redirect(url_for("partecipanti"))

# ----------------- Classifica -----------------
@app.route("/classifica")
def classifica():
    totali = (
        db.session.query(Squadra.nome, db.func.sum(Punteggio.punti).label("punti"))
        .join(Punteggio, Squadra.id == Punteggio.squadra_id)
        .group_by(Squadra.id)
        .order_by(db.desc("punti"))
        .all()
    )
    return render_template("classifica.html", totali=totali)

# ----------------- Statistiche -----------------
@app.route("/statistiche")
def statistiche():
    partecipanti = Partecipante.query.all()
    maschio_piu_piccolo = min([p for p in partecipanti if p.sesso == "M"], key=lambda x: x.data_nascita, default=None)
    femmina_piu_piccola = min([p for p in partecipanti if p.sesso == "F"], key=lambda x: x.data_nascita, default=None)
    piu_vecchio = max(partecipanti, key=lambda x: x.data_nascita, default=None)

    partecipante_piu_lontano = None
    max_distanza = 0
    for p in partecipanti:
        if p.lat and p.lon:
            distanza = calcola_distanza(BASE_LAT, BASE_LON, p.lat, p.lon)
            if distanza > max_distanza:
                max_distanza = distanza
                partecipante_piu_lontano = (p, distanza)

    conteggio_maneggi = {}
    for p in partecipanti:
        if p.maneggio:
            conteggio_maneggi[p.maneggio] = conteggio_maneggi.get(p.maneggio, 0) + 1
    maneggio_top = max(conteggio_maneggi, key=conteggio_maneggi.get) if conteggio_maneggi else None

    return render_template(
        "statistiche.html",
        maschio_piu_piccolo=maschio_piu_piccolo,
        femmina_piu_piccola=femmina_piu_piccola,
        piu_vecchio=piu_vecchio,
        partecipante_piu_lontano=partecipante_piu_lontano,
        maneggio_top=maneggio_top,
        conteggio_maneggi=conteggio_maneggi
    )

# -----------------------------------
# Avvio
# -----------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

