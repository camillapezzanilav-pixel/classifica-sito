import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import date
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

# -------------------
# CONFIG APP
# -------------------
app = Flask(__name__)

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    raise RuntimeError("❌ DATABASE_URL non impostata.")

app.config["SQLALCHEMY_DATABASE_URI"] = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

geolocator = Nominatim(user_agent="dovesiva")

# -------------------
# MODELS
# -------------------
class Squadra(db.Model):
    __tablename__ = "squadre"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    partecipanti = db.relationship("Partecipante", backref="squadra", lazy=True)
    punteggi = db.relationship("Punteggio", backref="squadra", lazy=True)


class Partecipante(db.Model):
    __tablename__ = "partecipanti"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    nascita = db.Column(db.Date, nullable=False)
    sesso = db.Column(db.String(1), nullable=False)  # M/F
    luogo = db.Column(db.String(150))
    provincia = db.Column(db.String(50))
    maneggio = db.Column(db.String(100))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadre.id"))


class Gioco(db.Model):
    __tablename__ = "giochi"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    punteggi = db.relationship("Punteggio", backref="gioco", lazy=True)


class Punteggio(db.Model):
    __tablename__ = "punteggi"
    id = db.Column(db.Integer, primary_key=True)
    punti = db.Column(db.Float, default=0, nullable=False)
    gioco_id = db.Column(db.Integer, db.ForeignKey("giochi.id"))
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadre.id"))


with app.app_context():
    db.create_all()

# -------------------
# ROUTES
# -------------------

@app.route("/")
def home():
    classifica_generale = (
        db.session.query(Squadra, db.func.sum(Punteggio.punti))
        .outerjoin(Punteggio)
        .group_by(Squadra.id)
        .order_by(db.desc(db.func.sum(Punteggio.punti)))
        .all()
    )

    classifica_maneggi = (
        db.session.query(Partecipante.maneggio, db.func.count(Partecipante.id))
        .group_by(Partecipante.maneggio)
        .all()
    )

    youngest_f = (
        Partecipante.query.filter_by(sesso="F").order_by(Partecipante.nascita.desc()).first()
    )
    youngest_m = (
        Partecipante.query.filter_by(sesso="M").order_by(Partecipante.nascita.desc()).first()
    )
    oldest = Partecipante.query.order_by(Partecipante.nascita.asc()).first()

    # distanza max (da Bologna come base)
    base_coords = (44.4949, 11.3426)
    farthest = None
    partecipanti = Partecipante.query.filter(Partecipante.lat.isnot(None), Partecipante.lng.isnot(None)).all()
    if partecipanti:
        distanze = [
            (p, geodesic(base_coords, (p.lat, p.lng)).km) for p in partecipanti if p.lat and p.lng
        ]
        if distanze:
            farthest = max(distanze, key=lambda x: x[1])

    return render_template(
        "home.html",
        classifica_generale=classifica_generale,
        classifica_maneggi=classifica_maneggi,
        youngest_f=youngest_f,
        youngest_m=youngest_m,
        oldest=oldest,
        farthest=farthest,
    )

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
    squadre = Squadra.query.all()
    return render_template("squadre.html", squadre=squadre)


@app.route("/squadre/<int:id>/delete", methods=["POST"])
def delete_squadra(id):
    squadra = Squadra.query.get_or_404(id)
    db.session.delete(squadra)
    db.session.commit()
    return redirect(url_for("squadre"))

# -------------------
# PARTECIPANTI
# -------------------
@app.route("/partecipanti", methods=["GET", "POST"])
def partecipanti():
    squadre = Squadra.query.all()
    if request.method == "POST":
        nome = request.form["nome"]
        nascita = date.fromisoformat(request.form["nascita"])
        sesso = request.form["sesso"]
        luogo = request.form.get("luogo")
        provincia = request.form.get("provincia")
        maneggio = request.form.get("maneggio")
        squadra_id = request.form.get("squadra_id")
        squadra_id = int(squadra_id) if squadra_id else None

        lat, lng = None, None
        if luogo and provincia:
            try:
                location = geolocator.geocode(f"{luogo}, {provincia}, Italia")
                if location:
                    lat, lng = location.latitude, location.longitude
            except Exception:
                pass

        p = Partecipante(
            nome=nome,
            nascita=nascita,
            sesso=sesso,
            luogo=luogo,
            provincia=provincia,
            maneggio=maneggio,
            squadra_id=squadra_id,
            lat=lat,
            lng=lng,
        )
        db.session.add(p)
        db.session.commit()
        return redirect(url_for("partecipanti"))

    partecipanti = Partecipante.query.all()
    return render_template("partecipanti.html", partecipanti=partecipanti, squadre=squadre)


@app.route("/partecipanti/<int:id>/edit", methods=["POST"])
def edit_partecipante(id):
    partecipante = Partecipante.query.get_or_404(id)
    partecipante.nome = request.form["nome"].strip()
    partecipante.nascita = date.fromisoformat(request.form["nascita"])
    partecipante.sesso = request.form["sesso"]
    partecipante.luogo = request.form.get("luogo")
    partecipante.provincia = request.form.get("provincia")
    partecipante.maneggio = request.form.get("maneggio")
    squadra_id = request.form.get("squadra_id")
    partecipante.squadra_id = int(squadra_id) if squadra_id else None
    db.session.commit()
    return redirect(url_for("partecipanti"))


@app.route("/partecipanti/<int:id>/delete", methods=["POST"])
def delete_partecipante(id):
    partecipante = Partecipante.query.get_or_404(id)
    db.session.delete(partecipante)
    db.session.commit()
    return redirect(url_for("partecipanti"))

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


@app.route("/giochi/<int:id>/edit", methods=["POST"])
def edit_gioco(id):
    gioco = Gioco.query.get_or_404(id)
    gioco.nome = request.form["nome"].strip()
    db.session.commit()
    return redirect(url_for("giochi"))


@app.route("/giochi/<int:id>/delete", methods=["POST"])
def delete_gioco(id):
    gioco = Gioco.query.get_or_404(id)
    db.session.delete(gioco)
    db.session.commit()
    return redirect(url_for("giochi"))

# -------------------
# DETTAGLIO SQUADRA + PUNTEGGI
# -------------------
@app.route("/squadre/<int:id>")
def dettaglio_squadra(id):
    squadra = Squadra.query.get_or_404(id)
    giochi = Gioco.query.all()
    punteggi = {p.gioco_id: p for p in squadra.punteggi}
    return render_template("dettaglio_squadra.html", squadra=squadra, giochi=giochi, punteggi=punteggi)


@app.route("/squadre/<int:id>/punteggio/<int:gioco_id>", methods=["POST"])
def salva_punteggio(id, gioco_id):
    squadra = Squadra.query.get_or_404(id)
    gioco = Gioco.query.get_or_404(gioco_id)

    # caso speciale: Quiz → somma 5 domande
    if gioco.nome.lower() == "quiz":
        totale = 0.0
        for i in range(1, 6):
            val = request.form.get(f"quiz_{i}")
            if val:
                try:
                    totale += float(val)
                except ValueError:
                    pass
        punti = totale
    else:
        punti = float(request.form["punti"]) if request.form.get("punti") else 0

    existing = Punteggio.query.filter_by(squadra_id=squadra.id, gioco_id=gioco.id).first()
    if existing:
        existing.punti = punti
    else:
        db.session.add(Punteggio(squadra_id=squadra.id, gioco_id=gioco.id, punti=punti))
    db.session.commit()
    return redirect(url_for("dettaglio_squadra", id=squadra.id))

# -------------------
# AVVIO
# -------------------
if __name__ == "__main__":
    app.run(debug=True)

