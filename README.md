# 📡 Decision Support & Predictive System - Sahel Telecom

🔗 **[Accéder au Dashboard en Direct (Streamlit Cloud)](https://sahel-telecom-dashboard.streamlit.app/)**

Ce projet implémente un système complet d'Informatique Décisionnelle (BI) et de Machine Learning (IA) pour l'opérateur **Sahel Telecom** (Burkina Faso) et sa filiale **GoldTel** (Ghana). 

Il intègre un entrepôt de données décisionnel (EDW), un pipeline ETL automatisé, un modèle prédictif de Churn (XGBoost) et un Dashboard interactif haute performance (Streamlit).

---

## 🛠️ Architecture Technique

*   **EDW (Entrepôt de Données)** : Modélisation en étoile sous **MySQL 8.0** avec gestion de l'historique de type SCD2 (Slowly Changing Dimensions) et partitionnement temporel.
*   **Pipeline ETL (Python)** : Chargement de 550 000+ événements réseau et 100 000 abonnés. Optimisé via des opérations en mémoire et du chargement groupé (*Bulk Insert*).
*   **Matérialisation (Performance)** : Pré-calcul des indicateurs via des tables physiques d'agrégats Decisionnels pour un affichage instantané du Dashboard (moins de 5ms).
*   **Machine Learning (IA)** : Classification supervisée (XGBoost) équilibrée par SMOTE, avec interprétabilité globale et locale (SHAP) entièrement traduite en français.
*   **Dashboard BI (Streamlit)** : Interface de visualisation des indicateurs clés (ARPU, Churn, Saturation Réseau, Qualité de Service) et tableau de prospection marketing.

---

## 📁 Structure du Projet

```
├── telecom_data/              # [Ignoré par Git] CSV sources bruts (~100 Mo)
├── churn_model_outputs/       # Sorties du modèle ML (Images SHAP, ROC, Top 500)
├── diagrammes/                # Fichiers sources PlantUML des architectures
├── docker-compose.yml         # Fichier d'orchestration de la base de données MySQL
├── edw_sahel_telecom.sql      # Schéma physique SQL de la base de données
├── populate_dim_date.sql      # Procédure de peuplement de la dimension Date
├── triggers_and_procedures.sql # Triggers SCD2, rapports qualité et snapshots
├── generate_data.py           # Script de génération du jeu de données brut
├── etl_pipeline_3.py          # Pipeline ETL optimisé
├── refresh_kpis.py            # Matérialisation des KPIs pour le Dashboard
├── export_kpis_for_cloud.py   # Extraction SQLite pour un déploiement Cloud gratuit
├── cloud_data/                # Base SQLite allégée pour Streamlit Cloud
├── churn_prediction.py        # Entraînement et explicabilité du modèle ML
├── dashboard_streamlit.py     # Code du Dashboard (hybride MySQL/SQLite)
├── requirements.txt           # Bibliothèques Python requises
└── DOCUMENTATION_TECHNIQUE.md  # Rapport technique complet et détaillé
```

---

## 🚀 Guide Rapide de Lancement (En 4 étapes)

### 1. Installation des packages Python
```bash
pip install -r requirements.txt
```

### 2. Démarrage de la base de données (Docker)
```bash
docker-compose up -d
```

### 3. Exécution du Pipeline ETL et Matérialisation
```bash
py etl_pipeline_3.py
py refresh_kpis.py
```

### 4. Entraînement de l'IA et Lancement de l'interface
```bash
py churn_prediction.py
py -m streamlit run dashboard_streamlit.py
```

L'application decisionnelle s'ouvrira automatiquement à l'adresse [http://localhost:8501](http://localhost:8501).

### 5. Procédure de Déploiement Cloud (Pour reproduction)
L'application est déjà déployée publiquement. Cependant, si vous souhaitez reproduire ce déploiement sur votre propre compte Streamlit Cloud (sans utiliser le lourd serveur MySQL), exécutez ce script pour exporter les KPIs agrégés vers une micro-base SQLite locale :
```bash
py export_kpis_for_cloud.py
```
Poussez ensuite le projet sur GitHub et connectez le dépôt à Streamlit Community Cloud.

---
*Projet réalisé dans le cadre du Master 1 Data Science / IFOAD - Groupe 3 - Promotion 2026.*
