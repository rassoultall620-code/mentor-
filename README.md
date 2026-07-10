# MentorSTAN

Plateforme intelligente de parrainage des étudiants du Département STAN — application web complète (Flask + SQLite), **accessible depuis un ordinateur ou un smartphone** grâce à un design entièrement responsive (Bootstrap 5).

## 🚀 Installation et lancement

```bash
# 1. Créer un environnement virtuel (recommandé)
python3 -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer l'application
python app.py
```

L'application démarre sur **http://localhost:5000**.
Elle est accessible :
- **Sur PC** : ouvrez ce lien dans un navigateur.
- **Sur téléphone (même réseau Wi-Fi)** : remplacez `localhost` par l'adresse IP locale de votre ordinateur, par exemple `http://192.168.1.10:5000`.

Pour trouver votre adresse IP locale :
- macOS/Linux : `ifconfig` ou `ip a`
- Windows : `ipconfig`

## 📲 Installer MentorSTAN comme une vraie application

MentorSTAN est une **Progressive Web App (PWA)** : une fois ouverte dans le navigateur, elle peut être installée comme une application native, avec sa propre icône, son propre écran de lancement, et un fonctionnement hors-ligne basique.

- **Sur PC (Chrome / Edge)** : une icône d'installation apparaît dans la barre d'adresse, ou cliquez sur le bouton **"Installer l'application"** dans le menu en haut à droite du site.
- **Sur Android (Chrome)** : ouvrez le site, appuyez sur **"Installer l'application"** ou sur le menu ⋮ puis **"Ajouter à l'écran d'accueil"**.
- **Sur iPhone (Safari)** : ouvrez le site, appuyez sur le bouton Partager, puis **"Sur l'écran d'accueil"**.

Une fois installée, l'application s'ouvre en plein écran (sans barre d'adresse), comme n'importe quelle app installée sur PC ou smartphone.

Pour un accès depuis n'importe où (pas seulement le même Wi-Fi), déployez l'application sur un serveur/hébergeur (voir section Déploiement).

## 🔑 Compte administrateur par défaut

Un compte admin est créé automatiquement au premier lancement :

- **Email** : `admin@stan.sn`
- **Mot de passe** : `ngom123456789`

⚠️ Changez ce mot de passe en production (modifiez le fichier `db.py`, fonction `init_db`).

## 📁 Structure du projet

```
mentorstan/
├── app.py              # Application Flask (routes, logique)
├── db.py                # Connexion SQLite + création des tables
├── data.py               # Listes de référence (intérêts, questions, objectifs...)
├── compatibility.py      # Algorithme de compatibilité (score sur 100)
├── requirements.txt
├── templates/            # Pages HTML (Jinja2 + Bootstrap 5, responsive)
│   ├── base.html
│   ├── index.html
│   ├── register.html
│   ├── login.html
│   ├── questionnaire.html
│   ├── profil.html
│   ├── dashboard.html         (étudiant : parrain / filleul)
│   ├── admin_dashboard.html
│   ├── messages.html
│   ├── offline.html      # Page affichée hors-connexion (PWA)
│   └── error.html
└── static/
    ├── css/style.css     # Thème + adaptations mobiles
    ├── icons/             # Icônes de l'application (192px, 512px, favicon)
    ├── uploads/           # Photos de profil
    ├── manifest.json      # Déclaration de l'app installable (PWA)
    └── service-worker.js  # Mise en cache et support hors-ligne
```

## ✨ Fonctionnalités implémentées

- **Inscription** (rôle Parrain/Filleul, infos personnelles, calcul automatique de l'âge, photo facultative).
- **Questionnaire complet** : intérêts académiques, intérêts extrascolaires, personnalité (10 affirmations notées 1-5), parcours académique, disponibilités (jours/créneaux), objectifs du mentorat.
- **Algorithme de compatibilité** (`compatibility.py`) : score sur 100%, pondéré sur 8 critères (niveau, intérêts académiques, intérêts extrascolaires, personnalité, disponibilités, objectifs, ville d'origine, langues). Association automatique du filleul au meilleur parrain disponible dès la fin du questionnaire.
- **Tableau de bord étudiant** : profil, binôme(s), score de compatibilité, intérêts communs, messagerie intégrée, programmation de rencontres, notifications.
- **Tableau de bord administrateur** : gestion des utilisateurs, lancement des associations automatiques, validation/annulation des binômes, statistiques détaillées, export CSV/Excel/PDF.
- **Sécurité** : mots de passe hachés (Werkzeug), sessions sécurisées, contrôle d'accès par rôle, uploads limités aux formats image.
- **Responsive design** : interface identique et pleinement utilisable sur PC, tablette et smartphone ; support PWA (installable sur l'écran d'accueil du téléphone).

## 🧮 Algorithme de compatibilité — détail des poids

| Critère                        | Poids |
|--------------------------------|-------|
| Intérêts académiques communs   | 25%   |
| Personnalité (proximité)       | 20%   |
| Disponibilités communes        | 15%   |
| Intérêts extrascolaires        | 12%   |
| Niveau (proximité)             | 12%   |
| Langues communes               | 5%    |
| Objectifs similaires           | 8%    |
| Ville d'origine                | 3%    |

Le score final est un nombre sur 100%. Chaque filleul est automatiquement associé au parrain disponible ayant le meilleur score.

## 🌐 Déploiement (optionnel, pour un accès permanent)

Pour rendre l'application accessible en permanence (et non uniquement sur le même Wi-Fi), déployez-la sur un service comme **Render**, **Railway**, **PythonAnywhere** ou un VPS, avec un serveur de production (`gunicorn app:app`) et éventuellement une base **PostgreSQL** comme suggéré dans le cahier des charges.

## 🔧 Prochaines évolutions possibles

- Notifications en temps réel (WebSocket)
- Application mobile native (React Native / Flutter) consommant une API
- Édition des questionnaires par l'administrateur depuis l'interface
- Historique et export des conversations
