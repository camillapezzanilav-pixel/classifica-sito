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

# ✅ crea le tabelle al boot, anche su Render con Gunicorn
with app.app_context():
    db.create_all()
# -------------------
# MODELLI
# -------------------
class Squadra(db.Model):
    __tablename__ = "squadre"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    maneggio = db.Column(db.String(120))
    partecipanti = db.relationship("Partecipante", backref="squadra", lazy=True)
    punteggi = db.relationship("Punteggio", backref="squadra", lazy=True)

class Partecipante(db.Model):
    __tablename__ = "partecipanti"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    nascita = db.Column(db.Date, nullable=False)
    sesso = db.Column(db.String(1), nullable=False)
    luogo = db.Column(db.String(120))
    provincia = db.Column(db.String(5))
    maneggio = db.Column(db.String(120))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadre.id"))

    @property
    def eta(self):
        oggi = date.today()
        return oggi.year - self.nascita.year - ((oggi.month, oggi.day) < (self.nascita.month, self.nascita.day))

class Gioco(db.Model):
    __tablename__ = "giochi"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    punteggi = db.relationship("Punteggio", backref="gioco", lazy=True)

class Punteggio(db.Model):
    __tablename__ = "punteggi"
    id = db.Column(db.Integer, primary_key=True)
    punti = db.Column(db.Integer, nullable=False, default=0)
    gioco_id = db.Column(db.Integer, db.ForeignKey("giochi.id"))
    squadra_id = db.Column(db.Integer, db.ForeignKey("squadre.id"))

# -------------------
# ROUTE
# -------------------
@app.route("/")
def home():
    # classifica squadre
    classifica_generale = db.session.query(
        Squadra.nome,
        db.func.sum(Punteggio.punti).label("totale")
    ).join(Punteggio, isouter=True).group_by(Squadra.id).order_by(db.desc("totale")).all()

    # classifica maneggi
    classifica_maneggi = db.session.query(
        Squadra.maneggio,
        db.func.count(Partecipante.id).label("n")
    ).join(Partecipante, isouter=True).group_by(Squadra.maneggio).order_by(db.desc("n")).all()

    # premiazioni
    youngest_f = Partecipante.query.filter_by(sesso="F").order_by(Partecipante.nascita.desc()).first()
    youngest_m = Partecipante.query.filter_by(sesso="M").order_by(Partecipante.nascita.desc()).first()
    oldest = Partecipante.query.order_by(Partecipante.nascita).first()

    return render_template("home.html",
                           classifica_generale=classifica_generale,
                           classifica_maneggi=classifica_maneggi,
                           youngest_f=youngest_f,
                           youngest_m=youngest_m,
                           oldest=oldest)

@app.route("/giochi")
def giochi():
    giochi = Gioco.query.all()
    return render_template("giochi.html", giochi=giochi)

@app.route("/squadre")
def squadre():
    squadre = Squadra.query.all()
    return render_template("squadre.html", squadre=squadre)

@app.route("/partecipanti")
def partecipanti():
    partecipanti = Partecipante.query.all()
    return render_template("partecipanti.html", partecipanti=partecipanti)


# -------------------
# AVVIO (solo locale)
# -------------------
if __name__ == "__main__":
    app.run(debug=True)
