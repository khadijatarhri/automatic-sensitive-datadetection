# Plateforme de Détection Automatique de Données Sensibles et Gouvernance Intelligente des Métadonnées

## 📋 Table des Matières
- [🎯 Vue d'ensemble](#-vue-densemble)
- [🏗️ Architecture du Système](#️-architecture-du-système)
- [🧩 Prérequis](#-prérequis)
- [⚙️ Installation et Déploiement](#️-installation-et-déploiement)
- [🔧 Configuration des Services Externes](#-configuration-des-services-externes)
- [📥 Chargement des Données dans HDP Sandbox](#-chargement-des-données-dans-hdp-sandbox)
- [🔄 Migration des Métadonnées vers Apache Atlas](#-migration-des-métadonnées-vers-apache-atlas)
- [💻 Démonstration des Interfaces](#-démonstration-des-interfaces)
- [🧠 Technologies Utilisées](#-technologies-utilisées)
- [🤝 Contribution](#-contribution)

---

## 🎯 Vue d'ensemble

Cette plateforme intégrée offre une solution complète pour la **détection automatique de données sensibles** conforme au **RGPD** et la **gouvernance intelligente des métadonnées**.  
Le système combine plusieurs composants d’**intelligence artificielle** (*Microsoft Presidio*, *spaCy*, *Google Gemini*) avec des outils de **gouvernance d’entreprise** (*Apache Atlas*, *Apache Hive*) afin d’assurer une gestion optimale des données personnelles.

### Fonctionnalités principales

✅ Détection automatique d’entités **PII/SPI** avec reconnaissance d’entités marocaines spécifiques (*CIN, RIB, numéros de téléphone*)  
✅ Double mode d’ingestion : **traitement par lots (CSV)** et **streaming temps réel (Apache Kafka)**  
✅ **Recommandations intelligentes** générées par **IA (Google Gemini API)**  
✅ **Workflows de validation** pour les *data stewards* avec interface intuitive  
✅ **Synchronisation automatique** avec **Apache Atlas** pour création de glossaires métiers  
✅ **Analyse de qualité des données** avec suggestions d’amélioration  
✅ **Intégration avec Odoo ERP** pour surveillance continue de la conformité RGPD

## 🏗️ Architecture du Système
![Page de connexion](assets/login.png)

## ⚙️ Workflow Général du Système

Le système implémente un workflow en **quatre étapes principales** :

### 🧩 Étape 1 : Ingestion des Données

- **Upload CSV (Administrateur)** : Téléchargement manuel de fichiers CSV via l'interface Django, stockage dans **MongoDB GridFS**.  
- **Streaming Temps Réel (Kafka)** : Flux continu de données clients depuis **Odoo ERP** via **Apache Kafka**.

---

### 🤖 Étape 2 : Analyse IA

- **Microsoft Presidio** : Détection d'entités PII (*PERSON, EMAIL, PHONE, ID_MAROC, IBAN_CODE*, etc.)  
- **spaCy NLP** : Analyse sémantique et classification contextuelle  
- **Google Gemini API** : Génération de recommandations intelligentes (*COMPLIANCE, SECURITY, QUALITY, GOVERNANCE*)

---

### 👩‍💼 Étape 3 : Validation Humaine

- Interface de révision des métadonnées enrichies par IA  
- Validation, rejet ou modification des recommandations par les **data stewards**  
- Gestion des annotations et contrôles qualité

---

### 🧭 Étape 4 : Gouvernance des Métadonnées

- **Apache Hive** : Mapping des colonnes validées vers les structures de tables existantes  
- **Apache Atlas** : Création automatique de glossaires métiers, termes, classifications RGPD  
- **Hortonworks Data Platform (HDP)** : Intégration avec l’infrastructure de gouvernance d’entreprise

---

## 🔧 Prérequis

### Logiciels requis
- Docker (version 20.10+)
- Docker Compose (version 1.29+)
- Git
- Python 3.8+

### Services externes
- **HDP Sandbox** : Environnement Hortonworks Data Platform avec Apache Atlas et Hive  
- **Google Gemini API** : Clé API pour génération de recommandations intelligentes  
- **MongoDB** : Base de données documentaire pour stockage des métadonnées  
- **Apache Kafka** : Plateforme de streaming pour ingestion temps réel

---

## 🚀 Installation et Déploiement

### 1️⃣ Cloner le dépôt principal
```bash
git clone https://github.com/khadijatarhri/Automatic-detection-of-sensitive-data-recommendation-engine-for-metadata-govnance.git
cd Automatic-detection-of-sensitive-data-recommendation-engine-for-metadata-govnance.git
```


---

##  Prérequis

- Docker et Docker Compose  
- Git  

---

##  Installation et Démarrage

### 1. Cloner le repository

```bash
git clone https://github.com/khadijatarhri/Automatic-detection-of-sensitive-data-recommendation-engine-for-metadata-govnance.git  
cd Automatic-detection-of-sensitive-data-recommendation-engine-for-metadata-govnance
```
### 2. Lancer l'application avec Docker
```bash
sudo docker-compose up --build
```
### 3. Créer l'utilisateur administrateur  
Dans un nouveau terminal, exécutez :

```bash
sudo docker exec -it sensitive-data-detection-web-1 python create_admin.py
```
### 4. Accéder à l'application
Ouvrez votre navigateur et allez à :
http://127.0.0.1:8000/login

### 5. Se connecter
Utilisez les identifiants par défaut :

Email : admin@example.com

Mot de passe : admin123

##  Architecture

L'application utilise :

Django : Framework web backend 

MongoDB : Base de données pour les utilisateurs et données CSV

Presidio : Moteur de détection et d’anonymisation

spaCy : Modèle de traitement du langage naturel (en_core_web_sm)

Tailwind CSS : Framework CSS pour l’interface

##  Fonctionnalités
Authentification : Système de login/register avec sessions 

Upload CSV : Interface pour télécharger des fichiers CSV

Détection PII : Identification automatique des données personnelles

Anonymisation : Remplacement des données sensibles

Interface responsive : Design moderne avec thème sombre/clair

##  Structure du Projet
```bash
├── authapp/              # Système d'authentification  
├── csv_anonymizer/       # Logique d'anonymisation  
├── backend_with_mongodb/ # Configuration Django  
├── theme/                # Thème Tailwind CSS  
├── api/                  # API REST  
├── mongo_auth/           # Authentification MongoDB  
├── docker-compose.yml    # Configuration Docker  
├── Dockerfile            # Image Docker  
├── requirements.txt      # Dépendances Python  
└── create_admin.py       # Script création admin
```
##  Arrêter l'application
```bash
sudo docker-compose down
```
##  Développement
Pour le développement local, vous pouvez modifier les fichiers et relancer :

```bash
sudo docker-compose up --build
```


##  Aperçu de l'application



### Login : Connexion à la plateforme.
![Page de connexion](assets/login.png)

### Téléversement : Upload de fichiers CSV ou TXT à analyser.
![Page de connexion](assets/upload.png)

### Statistiques : Affichage des entités sensibles détectées sous forme de graphiques.
![Page de connexion](assets/SelectEntities.png)

### Administration : Gestion des utilisateurs (ajout, modification, suppression).
![Page de connexion](assets/addingUsers.png)
![Page de connexion](assets/addkhadija.png)


### Statistiques globales : Vue d’ensemble des entités détectées.
![Page de connexion](assets/Statistics.png)
![Page de connexion](assets/statistics2.png)


### Interface utilisateur simple : Accès uniquement aux fichiers anonymisés.
![Page de connexion](assets/usersinterface.png)


## 📄 Licence
Ce projet est sous licence MIT.
