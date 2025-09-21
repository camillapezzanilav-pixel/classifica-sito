from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from math import radians, sin, cos, sqrt, atan2
from collections import defaultdict

app = Flask(__name__)
app.secret_key = "supersegreto"

# Configurazione DB PostgreSQL
db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

if not db_url:
    raise RuntimeError("❌ DATABASE_URL non impostata. Aggiungila su Render.")

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# --- MODELLI ---
class Squadra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    partecipanti = db.relationship("Partecipante", backref="squadra", lazy=True)
    punteggi = db.relationship("Punteggio", backref="squadra", lazy=True)


class Gioco(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    punteggi = db.relationship("Punteggio", backref="gioco", lazy=True)


class Partecipante(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    data_nascita = db.Column(db.Date)
    paese = db.Column(db.String(100))
    provincia = db.Column(db.String(10))
    sesso = db.Column(db.String(10))   # M, F, Altro
    maneggio = db.Column(db.String(100))
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadra.id"), nullable=False)
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)


class Punteggio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    punti = db.Column(db.Float, default=0)
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadra.id"), nullable=False)
    gioco_id = db.Column(db.Integer, db.ForeignKey("gioco.id"), nullable=False)


# --- Creazione tabelle forzata ---
@app.before_request
def create_tables():
    db.create_all()


# --- Funzione per calcolare distanza ---
def distanza_km(lat1, lon1, lat2, lon2):
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2 * 6371 * atan2(sqrt(a), sqrt(1-a))


# --- ROUTES ---
@app.route("/")
def home():
    squadre = Squadra.query.all()
    totali = [(s, sum(p.punti for p in s.punteggi)) for s in squadre]
    totali.sort(key=lambda x: x[1], reverse=True)

    # Statistiche
    stats = calcola_statistiche()

    return render_template(
        "home.html",
        totali=totali,
        stats=stats,
        ref="Ragazzola (PR)"
    )


# --- GIOCHI ---
@app.route("/giochi", methods=["GET", "POST"])
def giochi():
    if request.method == "POST":
        nome = request.form["nome"]
        if nome:
            db.session.add(Gioco(nome=nome))
            db.session.commit()
            flash("Gioco aggiunto!", "success")
        return redirect(url_for("giochi"))

    return render_template("giochi.html", giochi=Gioco.query.all())


@app.route("/giochi/<int:gid>", methods=["GET", "POST"])
def gioco_detail(gid):
    gioco = Gioco.query.get_or_404(gid)
    squadre = Squadra.query.order_by(Squadra.nome.asc()).all()

    if request.method == "POST":
        for s in squadre:
            val = request.form.get(f"punti_{s.id}")
            if val:
                try:
                    punti = float(val.replace(",", "."))
                except ValueError:
                    punti = 0
                punteggio = Punteggio.query.filter_by(squadra_id=s.id, gioco_id=gioco.id).first()
                if not punteggio:
                    punteggio = Punteggio(squadra_id=s.id, gioco_id=gioco.id)
                    db.session.add(punteggio)
                punteggio.punti = punti
        db.session.commit()
        flash("Punteggi aggiornati!", "success")
        return redirect(url_for("gioco_detail", gid=gid))

    punteggi = {p.squadra_id: p.punti for p in gioco.punteggi}
    return render_template("gioco_detail.html", gioco=gioco, squadre=squadre, punteggi=punteggi)


@app.route("/giochi/<int:gid>/delete", methods=["POST"])
def delete_gioco(gid):
    gioco = Gioco.query.get_or_404(gid)
    db.session.delete(gioco)
    db.session.commit()
    flash("Gioco eliminato!", "success")
    return redirect(url_for("giochi"))


@app.route("/giochi/<int:gid>/punteggio/<int:pid>/delete", methods=["POST"])
def delete_punteggio(gid, pid):
    punteggio = Punteggio.query.get_or_404(pid)
    db.session.delete(punteggio)
    db.session.commit()
    flash("Punteggio eliminato!", "success")
    return redirect(url_for("gioco_detail", gid=gid))


# --- SQUADRE ---
@app.route("/squadre", methods=["GET", "POST"])
def squadre():
    if request.method == "POST":
        nome = request.form["nome"]
        if nome:
            db.session.add(Squadra(nome=nome))
            db.session.commit()
            flash("Squadra aggiunta!", "success")
        return redirect(url_for("squadre"))

    return render_template("squadre.html", squadre=Squadra.query.all())


@app.route("/squadre/<int:sid>/delete", methods=["POST"])
def delete_squadra(sid):
    squadra = Squadra.query.get_or_404(sid)
    db.session.delete(squadra)
    db.session.commit()
    flash("Squadra eliminata!", "success")
    return redirect(url_for("squadre"))


# --- PARTECIPANTI ---
@app.route("/partecipanti", methods=["GET", "POST"])
def partecipanti():
    if request.method == "POST":
        nome = request.form["nome"]
        data_nascita = request.form.get("data_nascita")
        paese = request.form.get("paese")
        provincia = request.form.get("provincia")
        sesso = request.form.get("sesso")
        maneggio = request.form.get("maneggio")
        squadra_id = request.form.get("squadra_id")

        nascita = datetime.strptime(data_nascita, "%Y-%m-%d").date() if data_nascita else None
        if nome and squadra_id:
            p = Partecipante(
                nome=nome,
                data_nascita=nascita,
                paese=paese,
                provincia=provincia,
                sesso=sesso,
                maneggio=maneggio,
                squadra_id=int(squadra_id)
            )
            db.session.add(p)
            db.session.commit()
            flash("Partecipante aggiunto!", "success")
        return redirect(url_for("partecipanti"))

    return render_template("partecipanti.html", partecipanti=Partecipante.query.all(), squadre=Squadra.query.all())


@app.route("/partecipanti/<int:pid>/delete", methods=["POST"])
def delete_partecipante(pid):
    partecipante = Partecipante.query.get_or_404(pid)
    db.session.delete(partecipante)
    db.session.commit()
    flash("Partecipante eliminato!", "success")
    return redirect(url_for("partecipanti"))


@app.route("/partecipanti/<int:pid>/edit", methods=["POST"])
def edit_partecipante(pid):
    partecipante = Partecipante.query.get_or_404(pid)
    partecipante.nome = request.form["nome"]
    data_nascita = request.form.get("data_nascita")
    partecipante.data_nascita = datetime.strptime(data_nascita, "%Y-%m-%d").date() if data_nascita else None
    partecipante.paese = request.form.get("paese")
    partecipante.provincia = request.form.get("provincia")
    partecipante.sesso = request.form.get("sesso")
    partecipante.maneggio = request.form.get("maneggio")
    partecipante.squadra_id = int(request.form.get("squadra_id"))
    db.session.commit()
    flash("Partecipante aggiornato!", "success")
    return redirect(url_for("partecipanti"))


# --- CLASSIFICA ---
@app.route("/classifica")
def classifica():
    squadre = Squadra.query.all()
    totali = [(s, sum(p.punti for p in s.punteggi)) for s in squadre]
    totali.sort(key=lambda x: x[1], reverse=True)
    return render_template("classifica.html", totali=totali)


# --- STATISTICHE ---
def calcola_statistiche():
    partecipanti = Partecipante.query.all()
    giovani = [p for p in partecipanti if p.data_nascita]

    piu_giovane_m = max([p for p in giovani if p.sesso == "M"], key=lambda p: p.data_nascita, default=None)
    piu_giovane_f = max([p for p in giovani if p.sesso == "F"], key=lambda p: p.data_nascita, default=None)
    piu_vecchio = min(giovani, key=lambda p: p.data_nascita, default=None)

    # Maneggio con più partecipanti
    conteggio_maneggi = defaultdict(int)
    for p in partecipanti:
        if p.maneggio:
            conteggio_maneggi[p.maneggio] += 1
    maneggio_top = max(conteggio_maneggi, key=conteggio_maneggi.get, default=None)

    # Maneggio più lontano
    ref_lat, ref_lon = 45.0123, 10.2585
    distanze_maneggi = {}
    for p in partecipanti:
        if p.lat and p.lon and p.maneggio:
            dist = distanza_km(ref_lat, ref_lon, p.lat, p.lon)
            if p.maneggio not in distanze_maneggi or dist > distanze_maneggi[p.maneggio]:
                distanze_maneggi[p.maneggio] = dist
    maneggio_lontano = max(distanze_maneggi, key=distanze_maneggi.get, default=None)
    distanza_lontano = distanze_maneggi.get(maneggio_lontano)

    return {
        "piu_giovane_m": piu_giovane_m,
        "piu_giovane_f": piu_giovane_f,
        "piu_vecchio": piu_vecchio,
        "maneggio_top": maneggio_top,
        "maneggio_lontano": maneggio_lontano,
        "distanza_lontano": distanza_lontano,
    }


@app.route("/statistiche")
def statistiche():
    stats = calcola_statistiche()
    return render_template("statistiche.html", stats=stats)


# --- MAIN ---
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)

