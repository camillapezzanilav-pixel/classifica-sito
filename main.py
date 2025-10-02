import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import date

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
    partecipanti = db.relationship("Partecipante", backref="squadra", lazy=True)
    punteggi = db.relationship("Punteggio", backref="squadra", lazy=True)


class Partecipante(db.Model):
    __tablename__ = "partecipanti"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    nascita = db.Column(db.Date, nullable=False)
    sesso = db.Column(db.String(1), nullable=False)  # M o F
    luogo = db.Column(db.String(100))
    provincia = db.Column(db.String(10))
    maneggio = db.Column(db.String(100))
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadre.id"))


class Gioco(db.Model):
    __tablename__ = "giochi"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    punteggi = db.relationship("Punteggio", backref="gioco", lazy=True)


class Punteggio(db.Model):
    __tablename__ = "punteggi"
    id = db.Column(db.Integer, primary_key=True)
    punti = db.Column(db.Float, default=0.0, nullable=False)
    gioco_id = db.Column(db.Integer, db.ForeignKey("giochi.id"))
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadre.id"))

# -------------------
# HOME + CLASSIFICHE
# -------------------
@app.route("/")
def home():
    # classifica squadre
    classifica_generale = (
        db.session.query(Squadra, db.func.sum(Punteggio.punti).label("totale"))
        .join(Punteggio, isouter=True)
        .group_by(Squadra.id)
        .order_by(db.desc("totale"))
        .all()
    )

    # classifica maneggi
    classifica_maneggi = (
        db.session.query(Partecipante.maneggio, db.func.count(Partecipante.id))
        .group_by(Partecipante.maneggio)
        .order_by(db.desc(db.func.count(Partecipante.id)))
        .all()
    )

    # premi speciali
    youngest_f = (
        Partecipante.query.filter_by(sesso="F")
        .order_by(Partecipante.nascita.desc())
        .first()
    )
    youngest_m = (
        Partecipante.query.filter_by(sesso="M")
        .order_by(Partecipante.nascita.desc())
        .first()
    )
    oldest = Partecipante.query.order_by(Partecipante.nascita.asc()).first()

    return render_template(
        "home.html",
        classifica_generale=classifica_generale,
        classifica_maneggi=classifica_maneggi,
        youngest_f=youngest_f,
        youngest_m=youngest_m,
        oldest=oldest,
        farthest=None,  # distanza gestibile più avanti se serve
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
    squadre = Squadra.query.order_by(Squadra.nome).all()
    return render_template("squadre.html", squadre=squadre)

@app.route("/squadre/<int:id>")
def dettaglio_squadra(id):
    squadra = Squadra.query.get_or_404(id)
    giochi = Gioco.query.order_by(Gioco.nome).all()
    punteggi = {p.gioco_id: p.punti for p in Punteggio.query.filter_by(squadra_id=squadra.id).all()}
    return render_template("dettaglio_squadra.html", squadra=squadra, giochi=giochi, punteggi=punteggi)

@app.route("/squadre/<int:squadra_id>/gioco/<int:gioco_id>/save", methods=["POST"])
def salva_punteggio_gioco(squadra_id, gioco_id):
    squadra = Squadra.query.get_or_404(squadra_id)
    gioco = Gioco.query.get_or_404(gioco_id)

    punti_str = request.form.get("punti", "").strip()
    try:
        punti = float(punti_str) if punti_str else 0.0
    except ValueError:
        punti = 0.0

    existing = Punteggio.query.filter_by(squadra_id=squadra.id, gioco_id=gioco.id).first()
    if existing:
        existing.punti = punti
    else:
        db.session.add(Punteggio(squadra_id=squadra.id, gioco_id=gioco.id, punti=punti))
    db.session.commit()
    return redirect(url_for("dettaglio_squadra", id=squadra_id))

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
    giochi = Gioco.query.order_by(Gioco.nome).all()
    return render_template("giochi.html", giochi=giochi)

@app.route("/giochi/<int:id>/edit", methods=["POST"])
def edit_gioco(id):
    gioco = Gioco.query.get_or_404(id)
    nome = request.form["nome"].strip()
    if nome:
        gioco.nome = nome
        db.session.commit()
    return redirect(url_for("giochi"))

@app.route("/giochi/<int:id>/delete", methods=["POST"])
def delete_gioco(id):
    gioco = Gioco.query.get_or_404(id)
    for p in gioco.punteggi:
        db.session.delete(p)
    db.session.delete(gioco)
    db.session.commit()
    return redirect(url_for("giochi"))

# -------------------
# PARTECIPANTI
# -------------------
@app.route("/partecipanti", methods=["GET", "POST"])
def partecipanti():
    squadre = Squadra.query.order_by(Squadra.nome).all()
    if request.method == "POST":
        nome = request.form["nome"].strip()
        nascita = request.form["nascita"]
        sesso = request.form["sesso"]
        luogo = request.form.get("luogo")
        provincia = request.form.get("provincia")
        maneggio = request.form.get("maneggio")
        squadra_id = request.form.get("squadra_id")

        if nome and nascita and sesso:
            p = Partecipante(
                nome=nome,
                nascita=date.fromisoformat(nascita),
                sesso=sesso,
                luogo=luogo,
                provincia=provincia,
                maneggio=maneggio,
                squadra_id=int(squadra_id) if squadra_id else None,
            )
            db.session.add(p)
            db.session.commit()
        return redirect(url_for("partecipanti"))

    partecipanti = Partecipante.query.order_by(Partecipante.nome).all()
    return render_template("partecipanti.html", partecipanti=partecipanti, squadre=squadre)

# -------------------
# AVVIO
# -------------------
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)

