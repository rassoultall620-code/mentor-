import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "mentorstan.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL CHECK(role IN ('admin','parrain','filleul')),
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        nom TEXT, prenom TEXT, telephone TEXT,
        date_naissance TEXT, sexe TEXT,
        ville_origine TEXT, nationalite TEXT,
        niveau TEXT, annee_universitaire TEXT,
        photo_path TEXT,
        langues TEXT DEFAULT '',
        profil_complet INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS profiles (
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        interets_academiques TEXT DEFAULT '',
        interets_extra TEXT DEFAULT '',
        personnalite TEXT DEFAULT '',
        matieres_preferees TEXT DEFAULT '',
        matieres_accompagnement TEXT DEFAULT '',
        competences TEXT DEFAULT '',
        experience_labo INTEGER DEFAULT 0,
        participation_projets TEXT DEFAULT '',
        participation_associations TEXT DEFAULT '',
        projet_professionnel TEXT DEFAULT '',
        projet_poursuite_etudes TEXT DEFAULT '',
        jours_dispo TEXT DEFAULT '',
        creneaux_dispo TEXT DEFAULT '',
        objectifs TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parrain_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        filleul_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        score REAL,
        detail TEXT,
        status TEXT DEFAULT 'proposé' CHECK(status IN ('proposé','validé','refusé')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        receiver_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        contenu TEXT,
        lu INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS rencontres (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
        titre TEXT,
        date_rencontre TEXT,
        lieu TEXT,
        created_by INTEGER REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        contenu TEXT,
        lu INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()

    # admin par défaut
    admin = c.execute("SELECT id FROM users WHERE role='admin'").fetchone()
    if not admin:
        from werkzeug.security import generate_password_hash
        c.execute("""INSERT INTO users (role,email,password_hash,nom,prenom,profil_complet)
                     VALUES ('admin','admin@stan.sn',?,'Administrateur','STAN',1)""",
                  (generate_password_hash("ngom123456789"),))
        conn.commit()
    conn.close()
