import os
import io
import csv
from datetime import datetime, date
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                    session, flash, send_file, abort, jsonify)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from db import get_db, init_db
from data import (INTERETS_ACADEMIQUES, INTERETS_EXTRA, PERSONNALITE_QUESTIONS,
                   JOURS, CRENEAUX, OBJECTIFS, NIVEAUX, LANGUES)
from compatibility import compute_score, meilleur_parrain

BASE_DIR = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mentorstan-dev-secret-change-me")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
init_db()


# ---------------------------------------------------------------- helpers
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    return row


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("user_id"):
            flash("Veuillez vous connecter.", "warning")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        u = current_user()
        if not u or u["role"] != "admin":
            abort(403)
        return f(*a, **kw)
    return wrapper


def calc_age(date_naissance):
    try:
        y, m, d = [int(x) for x in date_naissance.split("-")]
        b = date(y, m, d)
        today = date.today()
        return today.year - b.year - ((today.month, today.day) < (b.month, b.day))
    except Exception:
        return None


def get_full_profile(user_id):
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    p = db.execute("SELECT * FROM profiles WHERE user_id=?", (user_id,)).fetchone()
    db.close()
    if not u:
        return None
    return {"user": dict(u), "profile": dict(p) if p else {}}


app.jinja_env.globals.update(calc_age=calc_age)


# ---------------------------------------------------------------- accueil
@app.route("/")
def index():
    if session.get("user_id"):
        u = current_user()
        if u["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("dashboard"))
    return render_template("index.html")


# ---------------------------------------------------------------- auth
@app.route("/inscription", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        role = request.form.get("role")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        nom = request.form.get("nom", "").strip()
        prenom = request.form.get("prenom", "").strip()

        if role not in ("parrain", "filleul"):
            flash("Veuillez choisir un rôle.", "danger")
            return redirect(url_for("register"))
        if not email or not password or not nom or not prenom:
            flash("Merci de remplir tous les champs obligatoires.", "danger")
            return redirect(url_for("register"))

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            db.close()
            flash("Cet e-mail est déjà utilisé.", "danger")
            return redirect(url_for("register"))

        photo_path = None
        file = request.files.get("photo")
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{email}_{file.filename}")
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            photo_path = filename

        langues = ",".join(request.form.getlist("langues"))

        cur = db.execute(
            """INSERT INTO users (role,email,password_hash,nom,prenom,telephone,
               date_naissance,sexe,ville_origine,nationalite,niveau,
               annee_universitaire,photo_path,langues)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (role, email, generate_password_hash(password), nom, prenom,
             request.form.get("telephone", ""), request.form.get("date_naissance", ""),
             request.form.get("sexe", ""), request.form.get("ville_origine", ""),
             request.form.get("nationalite", ""), request.form.get("niveau", ""),
             request.form.get("annee_universitaire", ""), photo_path, langues),
        )
        db.execute("INSERT INTO profiles (user_id) VALUES (?)", (cur.lastrowid,))
        db.commit()
        session["user_id"] = cur.lastrowid
        db.close()
        flash("Compte créé ! Complétez maintenant votre questionnaire.", "success")
        return redirect(url_for("questionnaire"))

    return render_template("register.html", niveaux=NIVEAUX, langues=LANGUES)


@app.route("/connexion", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        u = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        db.close()
        if u and check_password_hash(u["password_hash"], password):
            session["user_id"] = u["id"]
            flash(f"Bienvenue, {u['prenom']} !", "success")
            if u["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            if not u["profil_complet"]:
                return redirect(url_for("questionnaire"))
            return redirect(url_for("dashboard"))
        flash("E-mail ou mot de passe incorrect.", "danger")
    return render_template("login.html")


@app.route("/deconnexion")
def logout():
    session.clear()
    flash("Vous êtes déconnecté(e).", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------- questionnaire
@app.route("/questionnaire", methods=["GET", "POST"])
@login_required
def questionnaire():
    u = current_user()
    if u["role"] == "admin":
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        db = get_db()
        interets_academiques = ",".join(request.form.getlist("interets_academiques"))
        interets_extra = ",".join(request.form.getlist("interets_extra"))
        personnalite = ",".join(
            request.form.get(f"q{i}", "3") for i in range(1, len(PERSONNALITE_QUESTIONS) + 1)
        )
        jours_dispo = ",".join(request.form.getlist("jours_dispo"))
        creneaux_dispo = ",".join(request.form.getlist("creneaux_dispo"))
        objectifs = ",".join(request.form.getlist("objectifs"))

        db.execute(
            """UPDATE profiles SET interets_academiques=?, interets_extra=?,
               personnalite=?, matieres_preferees=?, matieres_accompagnement=?,
               competences=?, experience_labo=?, participation_projets=?,
               participation_associations=?, projet_professionnel=?,
               projet_poursuite_etudes=?, jours_dispo=?, creneaux_dispo=?,
               objectifs=? WHERE user_id=?""",
            (interets_academiques, interets_extra, personnalite,
             request.form.get("matieres_preferees", ""),
             request.form.get("matieres_accompagnement", ""),
             request.form.get("competences", ""),
             1 if request.form.get("experience_labo") else 0,
             request.form.get("participation_projets", ""),
             request.form.get("participation_associations", ""),
             request.form.get("projet_professionnel", ""),
             request.form.get("projet_poursuite_etudes", ""),
             jours_dispo, creneaux_dispo, objectifs, u["id"]),
        )
        db.execute("UPDATE users SET profil_complet=1 WHERE id=?", (u["id"],))
        db.commit()
        db.close()

        # tentative d'association automatique pour un filleul
        if u["role"] == "filleul":
            try_auto_match(u["id"])

        flash("Merci ! Votre profil est complet.", "success")
        return redirect(url_for("dashboard"))

    return render_template(
        "questionnaire.html", u=u,
        interets_academiques=INTERETS_ACADEMIQUES, interets_extra=INTERETS_EXTRA,
        personnalite_questions=list(enumerate(PERSONNALITE_QUESTIONS, start=1)),
        jours=JOURS, creneaux=CRENEAUX, objectifs=OBJECTIFS,
    )


def try_auto_match(filleul_id):
    """Associe automatiquement un filleul au meilleur parrain disponible."""
    db = get_db()
    already = db.execute("SELECT id FROM matches WHERE filleul_id=?", (filleul_id,)).fetchone()
    if already:
        db.close()
        return None
    parrain_rows = db.execute(
        """SELECT u.id FROM users u WHERE u.role='parrain' AND u.profil_complet=1
           AND u.id NOT IN (SELECT parrain_id FROM matches)"""
    ).fetchall()
    db.close()
    if not parrain_rows:
        return None
    parrains = [get_full_profile(r["id"]) for r in parrain_rows]
    filleul = get_full_profile(filleul_id)
    result = meilleur_parrain(filleul, parrains)
    if not result:
        return None
    parrain, score, detail = result
    db = get_db()
    db.execute(
        "INSERT INTO matches (parrain_id, filleul_id, score, detail, status) VALUES (?,?,?,?,?)",
        (parrain["user"]["id"], filleul_id, score, str(detail), "proposé"),
    )
    for uid, msg in [
        (parrain["user"]["id"], f"Un nouveau filleul vous a été associé (score {score}%)."),
        (filleul_id, f"Vous avez été associé(e) à un parrain (score {score}%)."),
    ]:
        db.execute("INSERT INTO notifications (user_id, contenu) VALUES (?,?)", (uid, msg))
    db.commit()
    db.close()
    return score


# ---------------------------------------------------------------- profil
@app.route("/profil", methods=["GET", "POST"])
@login_required
def profil():
    u = current_user()
    if request.method == "POST":
        db = get_db()
        langues = ",".join(request.form.getlist("langues"))
        photo_path = u["photo_path"]
        file = request.files.get("photo")
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{u['email']}_{file.filename}")
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            photo_path = filename
        db.execute(
            """UPDATE users SET nom=?, prenom=?, telephone=?, date_naissance=?, sexe=?,
               ville_origine=?, nationalite=?, niveau=?, annee_universitaire=?,
               photo_path=?, langues=? WHERE id=?""",
            (request.form.get("nom"), request.form.get("prenom"),
             request.form.get("telephone"), request.form.get("date_naissance"),
             request.form.get("sexe"), request.form.get("ville_origine"),
             request.form.get("nationalite"), request.form.get("niveau"),
             request.form.get("annee_universitaire"), photo_path, langues, u["id"]),
        )
        db.commit()
        db.close()
        flash("Profil mis à jour.", "success")
        return redirect(url_for("profil"))
    return render_template("profil.html", u=u, niveaux=NIVEAUX, langues=LANGUES)


# ---------------------------------------------------------------- dashboard étudiant
@app.route("/tableau-de-bord")
@login_required
def dashboard():
    u = current_user()
    if u["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    if not u["profil_complet"]:
        return redirect(url_for("questionnaire"))

    db = get_db()
    if u["role"] == "parrain":
        matches = db.execute(
            "SELECT * FROM matches WHERE parrain_id=? ORDER BY score DESC", (u["id"],)
        ).fetchall()
    else:
        matches = db.execute(
            "SELECT * FROM matches WHERE filleul_id=?", (u["id"],)
        ).fetchall()

    binomes = []
    for m in matches:
        other_id = m["filleul_id"] if u["role"] == "parrain" else m["parrain_id"]
        other = db.execute("SELECT * FROM users WHERE id=?", (other_id,)).fetchone()
        own_profile = db.execute("SELECT * FROM profiles WHERE user_id=?", (u["id"],)).fetchone()
        other_profile = db.execute("SELECT * FROM profiles WHERE user_id=?", (other_id,)).fetchone()
        communs_acad = set((own_profile["interets_academiques"] or "").split(",")) & \
                       set((other_profile["interets_academiques"] or "").split(","))
        communs_extra = set((own_profile["interets_extra"] or "").split(",")) & \
                        set((other_profile["interets_extra"] or "").split(","))
        binomes.append({
            "match": m, "other": other,
            "communs_acad": [x for x in communs_acad if x],
            "communs_extra": [x for x in communs_extra if x],
        })

    notifs = db.execute(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 10", (u["id"],)
    ).fetchall()
    db.execute("UPDATE notifications SET lu=1 WHERE user_id=?", (u["id"],))
    db.commit()
    db.close()

    return render_template("dashboard.html", u=u, binomes=binomes, notifs=notifs)


# ---------------------------------------------------------------- messagerie
@app.route("/messages/<int:other_id>", methods=["GET", "POST"])
@login_required
def messages(other_id):
    u = current_user()
    db = get_db()
    other = db.execute("SELECT * FROM users WHERE id=?", (other_id,)).fetchone()
    if not other:
        db.close()
        abort(404)

    # vérifie que ces deux personnes sont bien en binôme
    link = db.execute(
        """SELECT id FROM matches WHERE (parrain_id=? AND filleul_id=?)
           OR (parrain_id=? AND filleul_id=?)""",
        (u["id"], other_id, other_id, u["id"]),
    ).fetchone()
    if not link and u["role"] != "admin":
        db.close()
        abort(403)

    if request.method == "POST":
        contenu = request.form.get("contenu", "").strip()
        if contenu:
            db.execute(
                "INSERT INTO messages (sender_id, receiver_id, contenu) VALUES (?,?,?)",
                (u["id"], other_id, contenu),
            )
            db.execute(
                "INSERT INTO notifications (user_id, contenu) VALUES (?,?)",
                (other_id, f"Nouveau message de {u['prenom']}."),
            )
            db.commit()

    msgs = db.execute(
        """SELECT * FROM messages WHERE (sender_id=? AND receiver_id=?)
           OR (sender_id=? AND receiver_id=?) ORDER BY created_at ASC""",
        (u["id"], other_id, other_id, u["id"]),
    ).fetchall()
    db.execute(
        "UPDATE messages SET lu=1 WHERE receiver_id=? AND sender_id=?", (u["id"], other_id)
    )
    db.commit()
    db.close()
    return render_template("messages.html", u=u, other=other, msgs=msgs)


# ---------------------------------------------------------------- rencontres
@app.route("/rencontres/<int:match_id>", methods=["POST"])
@login_required
def creer_rencontre(match_id):
    u = current_user()
    db = get_db()
    m = db.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
    if not m or u["id"] not in (m["parrain_id"], m["filleul_id"]):
        db.close()
        abort(403)
    db.execute(
        "INSERT INTO rencontres (match_id, titre, date_rencontre, lieu, created_by) VALUES (?,?,?,?,?)",
        (match_id, request.form.get("titre"), request.form.get("date_rencontre"),
         request.form.get("lieu"), u["id"]),
    )
    other_id = m["filleul_id"] if u["id"] == m["parrain_id"] else m["parrain_id"]
    db.execute(
        "INSERT INTO notifications (user_id, contenu) VALUES (?,?)",
        (other_id, f"Nouvelle rencontre programmée : {request.form.get('titre')}"),
    )
    db.commit()
    db.close()
    flash("Rencontre programmée.", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------- admin
@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    total = db.execute("SELECT COUNT(*) c FROM users WHERE role!='admin'").fetchone()["c"]
    parrains = db.execute("SELECT COUNT(*) c FROM users WHERE role='parrain'").fetchone()["c"]
    filleuls = db.execute("SELECT COUNT(*) c FROM users WHERE role='filleul'").fetchone()["c"]
    binomes = db.execute("SELECT COUNT(*) c FROM matches").fetchone()["c"]
    complets = db.execute("SELECT COUNT(*) c FROM users WHERE profil_complet=1 AND role!='admin'").fetchone()["c"]
    taux_participation = round((complets / total) * 100, 1) if total else 0

    par_niveau = db.execute(
        "SELECT niveau, COUNT(*) c FROM users WHERE role!='admin' AND niveau!='' GROUP BY niveau"
    ).fetchall()
    par_sexe = db.execute(
        "SELECT sexe, COUNT(*) c FROM users WHERE role!='admin' AND sexe!='' GROUP BY sexe"
    ).fetchall()
    par_ville = db.execute(
        "SELECT ville_origine, COUNT(*) c FROM users WHERE role!='admin' AND ville_origine!='' GROUP BY ville_origine ORDER BY c DESC LIMIT 10"
    ).fetchall()
    moyenne_score = db.execute("SELECT AVG(score) m FROM matches").fetchone()["m"]

    # intérêts les plus populaires
    interets_count = {}
    for row in db.execute("SELECT interets_academiques FROM profiles"):
        for it in (row["interets_academiques"] or "").split(","):
            it = it.strip()
            if it:
                interets_count[it] = interets_count.get(it, 0) + 1
    top_interets = sorted(interets_count.items(), key=lambda x: -x[1])[:10]

    users = db.execute("SELECT * FROM users WHERE role!='admin' ORDER BY created_at DESC").fetchall()
    matches = db.execute(
        """SELECT m.*, up.prenom as p_prenom, up.nom as p_nom, uf.prenom as f_prenom, uf.nom as f_nom
           FROM matches m JOIN users up ON up.id=m.parrain_id JOIN users uf ON uf.id=m.filleul_id
           ORDER BY m.created_at DESC"""
    ).fetchall()
    db.close()

    return render_template(
        "admin_dashboard.html", total=total, parrains=parrains, filleuls=filleuls,
        binomes=binomes, taux_participation=taux_participation, par_niveau=par_niveau,
        par_sexe=par_sexe, par_ville=par_ville, moyenne_score=round(moyenne_score, 1) if moyenne_score else 0,
        top_interets=top_interets, users=users, matches=matches,
    )


@app.route("/admin/lancer-associations", methods=["POST"])
@admin_required
def lancer_associations():
    db = get_db()
    filleuls = db.execute(
        """SELECT id FROM users WHERE role='filleul' AND profil_complet=1
           AND id NOT IN (SELECT filleul_id FROM matches)"""
    ).fetchall()
    db.close()
    count = 0
    for f in filleuls:
        if try_auto_match(f["id"]) is not None:
            count += 1
    flash(f"{count} nouveau(x) binôme(s) créé(s).", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/match/<int:match_id>/<action>", methods=["POST"])
@admin_required
def gerer_match(match_id, action):
    db = get_db()
    if action == "valider":
        db.execute("UPDATE matches SET status='validé' WHERE id=?", (match_id,))
    elif action == "refuser":
        m = db.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
        db.execute("DELETE FROM matches WHERE id=?", (match_id,))
        if m:
            db.execute(
                "INSERT INTO notifications (user_id, contenu) VALUES (?,?)",
                (m["filleul_id"], "Votre binôme a été annulé. Une nouvelle association sera proposée."),
            )
    db.commit()
    db.close()
    flash("Binôme mis à jour.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/utilisateur/<int:user_id>/reinitialiser", methods=["POST"])
@admin_required
def reinitialiser_utilisateur(user_id):
    import secrets
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not u:
        db.close()
        abort(404)
    nouveau_mdp = secrets.token_urlsafe(6)
    db.execute("UPDATE users SET password_hash=? WHERE id=?",
               (generate_password_hash(nouveau_mdp), user_id))
    db.execute(
        "INSERT INTO notifications (user_id, contenu) VALUES (?,?)",
        (user_id, "Votre mot de passe a été réinitialisé par un administrateur."),
    )
    db.commit()
    db.close()
    flash(f"Mot de passe de {u['prenom']} {u['nom']} réinitialisé. "
          f"Nouveau mot de passe temporaire : {nouveau_mdp}", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/utilisateur/<int:user_id>/supprimer", methods=["POST"])
@admin_required
def supprimer_utilisateur(user_id):
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not u:
        db.close()
        abort(404)
    if u["role"] == "admin":
        db.close()
        flash("Impossible de supprimer un compte administrateur.", "danger")
        return redirect(url_for("admin_dashboard"))
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.commit()
    db.close()
    flash(f"{u['role'].capitalize()} {u['prenom']} {u['nom']} supprimé(e).", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/export/csv")
@admin_required
def export_csv():
    db = get_db()
    users = db.execute("SELECT * FROM users WHERE role!='admin'").fetchall()
    db.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Rôle", "Nom", "Prénom", "Email", "Téléphone", "Niveau",
                      "Ville d'origine", "Nationalité", "Sexe", "Profil complet"])
    for u in users:
        writer.writerow([u["id"], u["role"], u["nom"], u["prenom"], u["email"],
                          u["telephone"], u["niveau"], u["ville_origine"],
                          u["nationalite"], u["sexe"], "Oui" if u["profil_complet"] else "Non"])
    mem = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    return send_file(mem, mimetype="text/csv", as_attachment=True,
                      download_name="mentorstan_etudiants.csv")


@app.route("/admin/export/excel")
@admin_required
def export_excel():
    from openpyxl import Workbook
    db = get_db()
    users = db.execute("SELECT * FROM users WHERE role!='admin'").fetchall()
    matches = db.execute(
        """SELECT m.*, up.prenom as p_prenom, up.nom as p_nom, uf.prenom as f_prenom, uf.nom as f_nom
           FROM matches m JOIN users up ON up.id=m.parrain_id JOIN users uf ON uf.id=m.filleul_id"""
    ).fetchall()
    db.close()

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Étudiants"
    ws1.append(["ID", "Rôle", "Nom", "Prénom", "Email", "Téléphone", "Niveau",
                "Ville d'origine", "Nationalité", "Sexe", "Profil complet"])
    for u in users:
        ws1.append([u["id"], u["role"], u["nom"], u["prenom"], u["email"], u["telephone"],
                    u["niveau"], u["ville_origine"], u["nationalite"], u["sexe"],
                    "Oui" if u["profil_complet"] else "Non"])

    ws2 = wb.create_sheet("Binômes")
    ws2.append(["Parrain", "Filleul", "Score (%)", "Statut"])
    for m in matches:
        ws2.append([f"{m['p_prenom']} {m['p_nom']}", f"{m['f_prenom']} {m['f_nom']}",
                    m["score"], m["status"]])

    mem = io.BytesIO()
    wb.save(mem)
    mem.seek(0)
    return send_file(mem, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                      as_attachment=True, download_name="mentorstan_export.xlsx")


@app.route("/admin/export/pdf")
@admin_required
def export_pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    db = get_db()
    matches = db.execute(
        """SELECT m.*, up.prenom as p_prenom, up.nom as p_nom, uf.prenom as f_prenom, uf.nom as f_nom
           FROM matches m JOIN users up ON up.id=m.parrain_id JOIN users uf ON uf.id=m.filleul_id
           ORDER BY m.score DESC"""
    ).fetchall()
    db.close()

    mem = io.BytesIO()
    doc = SimpleDocTemplate(mem, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph("MentorSTAN — Rapport des binômes", styles["Title"]), Spacer(1, 12)]

    data = [["Parrain", "Filleul", "Score (%)", "Statut"]]
    for m in matches:
        data.append([f"{m['p_prenom']} {m['p_nom']}", f"{m['f_prenom']} {m['f_nom']}",
                     f"{m['score']}", m["status"]])
    table = Table(data, colWidths=[150, 150, 80, 80])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
    ]))
    elements.append(table)
    doc.build(elements)
    mem.seek(0)
    return send_file(mem, mimetype="application/pdf", as_attachment=True,
                      download_name="mentorstan_rapport.pdf")


@app.route("/offline")
def offline():
    return render_template("offline.html")


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Accès interdit."), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page introuvable."), 404


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
