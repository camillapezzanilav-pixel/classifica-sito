import os
from math import sin, cos, sqrt, atan2, radians
from datetime import date

from flask import Flask, render_template, request, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
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

# -------------------
# MODELLI
# -------------------
class Squadra(db.Model):
    __tablename__ = "squadre"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    maneggio = db.Column(db.String(120))
    partecipanti = db.relationship("Partecipante", backref="squadra", lazy=True, cascade="all, delete")
    punteggi = db.relationship("Punteggio", backref="squadra", lazy=True, cascade="all, delete")


class Partecipante(db.Model):
    __tablename__ = "partecipanti"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    nascita = db.Column(db.Date, nullable=False)
    sesso = db.Column(db.String(1), nullable=False)  # F/M/N
    luogo = db.Column(db.String(120))
    provincia = db.Column(db.String(10))
    maneggio = db.Column(db.String(120))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadre.id"))

    @property
    def eta(self):
        oggi = date.today()
        return oggi.year - self.nascita.year - (
            (oggi.month, oggi.day) < (self.nascita.month, self.nascita.day)
        )


class Gioco(db.Model):
    __tablename__ = "giochi"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    punteggi = db.relationship("Punteggio", backref="gioco", lazy=True, cascade="all, delete")


class Punteggio(db.Model):
    __tablename__ = "punteggi"
    id = db.Column(db.Integer, primary_key=True)
    punti = db.Column(db.Float, default=0, nullable=False)
    gioco_id = db.Column(db.Integer, db.ForeignKey("giochi.id"))
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadre.id"))


# ✅ CREA LE TABELLE
with app.app_context():
    db.drop_all()
    db.create_all()

# -------------------
# GEOLOCATOR
# -------------------
geolocator = Nominatim(user_agent="giochi-maneggi")

def geocode_location(luogo, provincia):
    try:
        query = f"{luogo}, {provincia}, Italia"
        location = geolocator.geocode(query, timeout=10)
        if location:
            return location.latitude, location.longitude
    except Exception:
        pass
    return None, None

# -------------------
# UTILS
# -------------------
BASE_LAT = float(os.environ.get("BASE_LAT", "44.8015"))
BASE_LNG = float(os.environ.get("BASE_LNG", "10.3279"))

def haversine_km(lat1, lon1, lat2, lon2):
    try:
        R = 6371.0
        dLat = radians(lat2 - lat1)
        dLon = radians(lon2 - lon1)
        a = sin(dLat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c
    except Exception:
        return None

# -------------------
# ROUTE
# -------------------
@app.route("/")
def home():
    classifica_generale = (
        db.session.query(Squadra, db.func.coalesce(db.func.sum(Punteggio.punti), 0).label("totale"))
        .outerjoin(Punteggio)
        .group_by(Squadra.id)
        .order_by(db.desc("totale"), Squadra.nome.asc())
        .all()
    )

    classifica_maneggi = (
        db.session.query(Partecipante.maneggio, db.func.count(Partecipante.id).label("n"))
        .group_by(Partecipante.maneggio)
        .order_by(db.desc("n"), Partecipante.maneggio.asc())
        .all()
    )

    youngest_f = Partecipante.query.filter_by(sesso="F").order_by(Partecipante.nascita.desc()).first()
    youngest_m = Partecipante.query.filter_by(sesso="M").order_by(Partecipante.nascita.desc()).first()
    oldest = Partecipante.query.order_by(Partecipante.nascita.asc()).first()

    partecipanti_con_geo = Partecipante.query.filter(Partecipante.lat.isnot(None), Partecipante.lng.isnot(None)).all()
    farthest = None
    maxdist = -1
    for p in partecipanti_con_geo:
        d = haversine_km(BASE_LAT, BASE_LNG, p.lat, p.lng)
        if d is not None and d > maxdist:
            maxdist = d
            farthest = (p, d)

    return render_template(
        "home.html",
        classifica_generale=classifica_generale,
        classifica_maneggi=classifica_maneggi,
        youngest_f=youngest_f,
        youngest_m=youngest_m,
        oldest=oldest,
        farthest=farthest,
        base_coords=(BASE_LAT, BASE_LNG),
    )

# ---- Squadre ----
@app.route("/squadre", methods=["GET", "POST"])
def squadre():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        maneggio = request.form.get("maneggio", "").strip()
        if not nome:
            abort(400, "Nome squadra obbligatorio")
        db.session.add(Squadra(nome=nome, maneggio=maneggio))
        db.session.commit()
        return redirect(url_for("squadre"))

    squadre = Squadra.query.order_by(Squadra.nome.asc()).all()
    return render_template("squadre.html", squadre=squadre)

@app.route("/squadre/edit/<int:id>", methods=["POST"])
def edit_squadra(id):
    s = Squadra.query.get_or_404(id)
    s.nome = request.form.get("nome", s.nome).strip()
    s.maneggio = request.form.get("maneggio", s.maneggio).strip()
    db.session.commit()
    return redirect(url_for("squadre"))

@app.route("/squadre/delete/<int:id>", methods=["POST"])
def delete_squadra(id):
    s = Squadra.query.get_or_404(id)
    db.session.delete(s)
    db.session.commit()
    return redirect(url_for("squadre"))

# ---- Giochi ----
@app.route("/giochi", methods=["GET", "POST"])
def giochi():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        if not nome:
            abort(400, "Nome gioco obbligatorio")
        db.session.add(Gioco(nome=nome))
        db.session.commit()
        return redirect(url_for("giochi"))

    giochi = Gioco.query.order_by(Gioco.nome.asc()).all()
    return render_template("giochi.html", giochi=giochi)

@app.route("/giochi/edit/<int:id>", methods=["POST"])
def edit_gioco(id):
    g = Gioco.query.get_or_404(id)
    g.nome = request.form.get("nome", g.nome).strip()
    db.session.commit()
    return redirect(url_for("giochi"))

@app.route("/giochi/delete/<int:id>", methods=["POST"])
def delete_gioco(id):
    g = Gioco.query.get_or_404(id)
    db.session.delete(g)
    db.session.commit()
    return redirect(url_for("giochi"))

# ---- Dettaglio Gioco + punteggi ----
@app.route("/giochi/<int:id>", methods=["GET", "POST"])
def dettaglio_gioco(id):
    gioco = Gioco.query.get_or_404(id)

    if request.method == "POST":
        squadra_id = int(request.form["squadra_id"])
        punti = float(request.form["punti"])
        existing = Punteggio.query.filter_by(gioco_id=gioco.id, squadra_id=squadra_id).first()
        if existing:
            existing.punti = punti
        else:
            db.session.add(Punteggio(gioco_id=gioco.id, squadra_id=squadra_id, punti=punti))
        db.session.commit()
        return redirect(url_for("dettaglio_gioco", id=gioco.id))

    righe = (
        db.session.query(Squadra, Punteggio)
        .outerjoin(Punteggio, (Punteggio.squadra_id == Squadra.id) & (Punteggio.gioco_id == gioco.id))
        .order_by(Squadra.nome.asc())
        .all()
    )
    return render_template("dettaglio_gioco.html", gioco=gioco, righe=righe)

@app.route("/giochi/<int:gioco_id>/delete/<int:squadra_id>", methods=["POST"])
def delete_punteggio(gioco_id, squadra_id):
    p = Punteggio.query.filter_by(gioco_id=gioco_id, squadra_id=squadra_id).first_or_404()
    db.session.delete(p)
    db.session.commit()
    return redirect(url_for("dettaglio_gioco", id=gioco_id))

# ---- Partecipanti ----
@app.route("/partecipanti", methods=["GET", "POST"])
def partecipanti():
    squadre = Squadra.query.order_by(Squadra.nome.asc()).all()
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        nascita = date.fromisoformat(request.form["nascita"])
        sesso = request.form["sesso"].strip().upper()
        luogo = request.form.get("luogo", "").strip()
        provincia = request.form.get("provincia", "").strip()
        maneggio = request.form.get("maneggio", "").strip()
        lat = request.form.get("lat") or None
        lng = request.form.get("lng") or None
        squadra_id = request.form.get("squadra_id") or None

        if (not lat or not lng) and luogo and provincia:
            geo_lat, geo_lng = geocode_location(luogo, provincia)
            if geo_lat and geo_lng:
                lat, lng = geo_lat, geo_lng

        p = Partecipante(
            nome=nome, nascita=nascita, sesso=sesso, luogo=luogo, provincia=provincia,
            maneggio=maneggio,
            lat=float(lat) if lat else None,
            lng=float(lng) if lng else None,
            squadra_id=int(squadra_id) if squadra_id else None
        )
        db.session.add(p)
        db.session.commit()
        return redirect(url_for("partecipanti"))

    partecipanti = Partecipante.query.order_by(Partecipante.nome.asc()).all()
    return render_template("partecipanti.html", partecipanti=partecipanti, squadre=squadre)

@app.route("/partecipanti/edit/<int:id>", methods=["POST"])
def edit_partecipante(id):
    p = Partecipante.query.get_or_404(id)
    p.nome = request.form.get("nome", p.nome).strip()
    p.nascita = date.fromisoformat(request.form.get("nascita", p.nascita.isoformat()))
    p.sesso = request.form.get("sesso", p.sesso).strip().upper()
    p.luogo = request.form.get("luogo", p.luogo).strip()
    p.provincia = request.form.get("provincia", p.provincia).strip()
    p.maneggio = request.form.get("maneggio", p.maneggio).strip()

    lat = request.form.get("lat")
    lng = request.form.get("lng")
    squadra_id = request.form.get("squadra_id")

    if (not lat or not lng) and p.luogo and p.provincia:
        geo_lat, geo_lng = geocode_location(p.luogo, p.provincia)
        if geo_lat and geo_lng:
            lat, lng = geo_lat, geo_lng

    p.lat = float(lat) if lat else None
    p.lng = float(lng) if lng else None
    p.squadra_id = int(squadra_id) if squadra_id else None

    db.session.commit()
    return redirect(url_for("partecipanti"))

@app.route("/partecipanti/delete/<int:id>", methods=["POST"])
def delete_partecipante(id):
    p = Partecipante.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    return redirect(url_for("partecipanti"))

# -------------------
# AVVIO LOCALE
# -------------------
if __name__ == "__main__":
    app.run(debug=True)

