# ARCHITECTURE ET DOSSIER TECHNIQUE DE RÉFÉRENCE - PROJET DÉCISIONNEL SAHEL TELECOM

Ce document technique présente de manière exhaustive l'architecture globale, la matrice des versions, la structure physique de l'entrepôt, le dictionnaire de données, les détails de code de chaque fichier, les résultats réels du modèle de Machine Learning et la procédure de reproduction pas à pas.

Il intègre des **emplacements spécifiques (placeholders)** pour coller les diagrammes lors de la conversion de ce document en format Word (`.docx`).

---

## 1. INTRODUCTION ET CONTEXTE DU PROJET

Ce document constitue le dossier d'architecture et la documentation technique de référence pour le projet d'Entrepôt de Données (EDW), de pipeline d'intégration (ETL), d'Intelligence Artificielle (Machine Learning) et d'informatique décisionnelle (BI/Dashboard) réalisé pour l'opérateur **Sahel Telecom** (Burkina Faso) et sa filiale **GoldTel** (Ghana).

### 1.1. Objectifs Stratégiques
L'objectif de cette implémentation est de centraliser et d'analyser les données de :
*   **~100 000 abonnés** répartis sur deux pays.
*   **~500 000+ événements d'usage** (Appels, SMS, sessions Data).
*   **~20+ antennes réseau** (2G, 3G, 4G) réparties dans 6 grandes villes (Ouagadougou, Bobo-Dioulasso, Koudougou pour le Burkina Faso ; Accra, Kumasi, Tamale pour le Ghana).
*   **~10 offres commerciales** (plans prépayés et postpayés).
*   Suivi des **incidents réseau** impactant la qualité de service.

Le projet résout trois problématiques d'entreprise majeures :
1.  **Centralisation** de données hétérogènes et non nettoyées dans un schéma en étoile unifié.
2.  **Prévention du Churn** (résiliation des contrats) par un modèle de classification supervisée XGBoost.
3.  **Visualisation BI** temps réel haute performance des KPIs réseau, géographiques et financiers.

### 1.2. Matrice des Versions Logicielles
Pour reproduire le projet dans des conditions identiques, les versions logicielles suivantes ont été utilisées et validées :
*   **Python** : `Version 3.13`
*   **MySQL Server** : `Version 8.0` (Exécuté dans un conteneur Docker officiel)
*   **Docker Engine** : `Version 20.10+` et **Docker Compose** : `Version 2.0+`
*   `streamlit` : `v1.58.0` (Framework UI décisionnel)
*   `pandas` : `v3.0.3` (Manipulation et transformation des données)
*   `numpy` : `v2.4.6` (Calculs matriciels et valeurs manquantes)
*   `mysql-connector-python` : `v9.0.0` (Liaison ETL vers MySQL)
*   `pymysql` : `v1.1.1` (Liaison décisionnelle rapide Streamlit vers MySQL)
*   `plotly` : `v6.8.0` (Visualisations graphiques interactives)
*   `scikit-learn` : `v1.6.0` (Prétraitement ML et métriques de performance)
*   `xgboost` : `v2.0.3` (Modèle algorithmique de classification)
*   `imbalanced-learn` : `v0.12.0` (Technique SMOTE d'équilibrage)
*   `shap` : `v0.45.1` (Explicabilité mathématique du modèle)

---

## 2. STRUCTURE ET ARBORESCENCE DU PROJET

Voici la structure de l'arborescence physique du projet decisionnel :

```text
Projet (3)/
├── telecom_data/              # [Ignoré par Git] CSV sources bruts (~100 Mo)
│   ├── plans.csv
│   ├── towers.csv
│   ├── subscribers.csv
│   ├── usage.csv
│   └── incidents_qualite_legers.csv
├── churn_model_outputs/       # Sorties graphiques et statistiques du modèle ML
│   ├── resultats_modeles_xgboost.csv
│   ├── importance_variables.csv
│   ├── importance_variables.png
│   ├── courbes_roc.png
│   ├── matrice_confusion_xgboost.png
│   ├── shap_summary.png
│   └── top_500_abonnes_a_risque.csv
├── diagrammes/                # Fichiers sources PlantUML des architectures
│   ├── architecture_globale.puml
│   ├── modele_etoile.puml
│   └── pipeline_etl.puml
├── docker-compose.yml         # Fichier d'orchestration de la base de données MySQL
├── edw_sahel_telecom.sql      # Schéma physique SQL de la base de données
├── populate_dim_date.sql      # Procédure de peuplement de la dimension Date
├── triggers_and_procedures.sql # Triggers SCD2, rapports qualité et snapshots
├── generate_data.py           # Script de génération du jeu de données brut
├── etl_pipeline_3.py          # Pipeline ETL optimisé
├── refresh_kpis.py            # Matérialisation des KPIs pour le Dashboard
├── churn_prediction.py        # Entraînement et explicabilité du modèle ML
├── dashboard_streamlit.py     # Code du Dashboard Streamlit Streamlit
├── requirements.txt           # Bibliothèques Python requises
├── .gitignore                 # Exclusion des fichiers volumineux et des logs
├── README.md                  # Accueil descriptif du dépôt Git
└── DOCUMENTATION_TECHNIQUE.md  # Rapport technique complet (présent document)
```

---

## 3. ARCHITECTURE DE L'ENTREPÔT DE DONNÉES (EDW)

L'entrepôt est structuré sous forme d'un **schéma en étoile (Star Schema)** sous MySQL 8.0, permettant d'optimiser les requêtes analytiques en minimisant le nombre de jointures complexes nécessaires.

============================================================
[👉 ESPACE WORD : COLLER LE DIAGRAMME DU MODÈLE EN ÉTOILE ICI (modele_etoile.png)]
============================================================

### 3.1. Les Dimensions (Tables de Références)
Les dimensions contiennent le contexte métier des mesures. Elles implémentent la logique d'historisation **SCD (Slowly Changing Dimensions)** :
*   **`dim_subscriber` (Historisation SCD Type 2)** : Profil complet de l'abonné (âge, segment commercial, pays, ville, etc.). Les attributs `city`, `segment` et `plan_id` sont historisés. Si un abonné change de forfait ou déménage, l'ancienne ligne est fermée et une nouvelle est créée.
*   **`dim_plan` (Historisation SCD Type 2)** : Caractéristiques des plans tarifaires (mensualité, quota internet, etc.).
*   **`dim_tower` (Historisation SCD Type 1)** : Répertoire des antennes réseau (2G/3G/4G) avec écrasement direct en cas de mise à jour.
*   **`dim_localisation` (Dimension Conformée)** : Regroupement normalisé des zones géographiques (villes et pays).
*   **`dim_date` (Dimension Temporelle)** : Table temporelle pré-calculée de 2015 à 2035 pour simplifier le requêtage décisionnel.

### 3.2. Les Tables de Faits (Mesures)
*   **`fact_usage` (Granularité : Transactionnelle)** : Enregistre chaque transaction réseau (Appels, SMS, sessions internet). Partitionnée par intervalle d'années (`date_sk`).
*   **`fact_incident` (Granularité : Événement)** : Rapports de pannes antenne avec temps de résolution.
*   **`fact_subscriber_monthly` (Couche de données ML)** : Table pivot stockant des instantanés mensuels agrégés par abonné pour le Machine Learning.

============================================================
[👉 ESPACE WORD : COLLER LE DIAGRAMME DE L'ARCHITECTURE GLOBALE ICI (architecture_globale.png)]
============================================================

---

## 4. DICTIONNAIRE DES TABLES PHYSIQUES ET KPIs DE L'EDW

### 4.1. Tables Dimensions du Core
*   **`dim_subscriber` (Abonnés)** :
    *   `subscriber_sk` (INT, PK) : Clé de substitution unique.
    *   `subscriber_id` (VARCHAR(20), UK) : Identifiant métier naturel unique.
    *   `first_name` & `last_name` (VARCHAR(100)) : Nom et prénom du client.
    *   `gender` (VARCHAR(10)) : Genre (M/F).
    *   `age` (TINYINT) : Âge (16 à 75 ans).
    *   `tranche_age` (VARCHAR(20)) : Classification par âge.
    *   `city` & `country` (VARCHAR(100)) : Géographie de résidence.
    *   `plan_id` (VARCHAR(20)) : Identifiant forfait lié.
    *   `phone_number` & `email` (VARCHAR) : Coordonnées de contact.
    *   `segment` (VARCHAR(30)) : Segment client (Particulier, Professionnel, Entreprise).
    *   `churn` (TINYINT) : 1 si désabonné, 0 sinon.
    *   `churn_date` & `subscription_date` (DATE) : Dates administratives.
    *   `date_debut` & `date_fin` (DATE) : Intervalles de validité SCD2.
    *   `is_current` (TINYINT) : Flag de validité courante SCD2 (1 = actif, 0 = historique).
    *   `version` (INT) : Numéro de version incrémental SCD2.
*   **`dim_plan` (Forfaits)** :
    *   `plan_sk` (INT, PK) : Clé de substitution.
    *   `plan_id` (VARCHAR(20)) : Clé naturelle.
    *   `plan_name` (VARCHAR(100)) : Nom commercial.
    *   `type_abonnement` (VARCHAR(30)) : Prépayé, Postpayé ou Entreprise.
    *   `monthly_fee` (DECIMAL(10,2)) : Tarif mensuel forfait.
    *   `data_quota_gb` (DECIMAL) : Quota de données internet inclus.
    *   `call_minutes` (INT) : Volume d'appels inclus.
    *   `categorie_prix` (VARCHAR) : Économique, Standard ou Premium.
*   **`dim_tower` (Antennes Réseau)** :
    *   `tower_sk` (INT, PK) : Clé de substitution.
    *   `tower_id` (VARCHAR(20)) : Clé naturelle.
    *   `tower_name` (VARCHAR(100)) : Nom antenne.
    *   `city`, `region` & `country` : Localisation de l'antenne.
    *   `technology` (VARCHAR(10)) : Technologie réseau (2G, 3G, 4G).
    *   `capacity_users` (INT) : Nombre maximum d'abonnés pris en charge.

### 4.2. Tables de Faits du Core
*   **`fact_usage` (Usage Réseau)** :
    *   `usage_sk` (BIGINT, PK) : Clé technique.
    *   `date_sk` (INT, PK, FK) : Lien vers la date.
    *   `subscriber_sk` (INT, FK) : Lien vers l'abonné actif.
    *   `tower_sk` (INT, FK) : Lien vers l'antenne utilisée.
    *   `plan_sk` (INT, FK) : Lien vers le forfait de l'abonné au moment de l'usage.
    *   `location_sk` (INT, FK) : Lien vers la localisation de l'usage.
    *   `duration_sec` (INT) : Durée de l'appel en secondes.
    *   `data_mb` (DECIMAL) : Trafic consommé en mégaoctets.
    *   `amount_fcfa` (DECIMAL) : Coût facturé.
    *   `event_type` (VARCHAR) : Type d'usage (Appel, SMS, Data).
    *   `status` (VARCHAR) : Résultat (Succès, Échec).
*   **`fact_incident` (Incidents Réseau)** :
    *   `incident_sk` (BIGINT, PK) : Clé unique incident.
    *   `tower_sk` & `location_sk` (INT, FK) : Antenne et zone impactées.
    *   `date_sk` (INT, FK) : Date de survenue.
    *   `severity` (VARCHAR) : Gravité (Faible, Moyen, Élevé).
    *   `resolved` (TINYINT) : Résolu (1) ou non (0).
    *   `resolution_minutes` (INT) : Temps de réparation.
    *   `nb_abonnes_affectes` (INT) : Impact client.

### 4.3. Les 7 Tables de KPIs Matérialisées
*   **`kpi_churn_mensuel`** : Stocke l'évolution temporelle du taux de churn par segment client, pays et forfait. 
    *   *Colonnes* : `annee`, `mois`, `nom_mois`, `country`, `city`, `segment`, `plan_name`, `total_abonnes`, `nb_churnes`, `taux_churn_pct`.
*   **`kpi_arpu`** : Stocke le revenu moyen généré mensuellement par abonné actif.
    *   *Colonnes* : `annee`, `mois`, `nom_mois`, `country`, `city`, `plan_name`, `type_abonnement`, `nb_abonnes_actifs`, `revenu_total`, `revenu_moyen_par_evenement`, `arpu`.
*   **`kpi_utilisation_reseau`** : Stocke la saturation moyenne et le trafic total des antennes.
    *   *Colonnes* : `annee`, `mois`, `nom_mois`, `tower_id`, `tower_name`, `city`, `country`, `technology`, `capacity_users`, `abonnes_actifs`, `nb_evenements`, `taux_utilisation_pct`, `volume_data_gb`, `volume_appels_heures`.
*   **`kpi_incidents_qualite`** : Stocke les indicateurs d'anomalies et de pannes antennes par zone.
    *   *Colonnes* : `annee`, `mois`, `nom_mois`, `tower_id`, `tower_name`, `city`, `country`, `technology`, `nb_incidents`, `incidents_eleves`, `incidents_moyens`, `total_abonnes_affectes`, `duree_resolution_moy_min`, `taux_resolution_pct`.
*   **`kpi_duree_appels`** : Stocke les métriques de trafic voix et taux d'échec par bande réseau (2G/3G/4G).
    *   *Colonnes* : `annee`, `mois`, `nom_mois`, `country`, `city`, `segment`, `network_type`, `nb_appels`, `duree_moy_sec`, `duree_moy_min`, `volume_total_heures`, `nb_appels_echoues`, `taux_echec_pct`.
*   **`kpi_retention_par_offre`** : Stocke la fidélité des abonnés par type de contrat.
    *   *Colonnes* : `plan_name`, `type_abonnement`, `country`, `monthly_fee`, `total_abonnes`, `abonnes_retenus`, `abonnes_perdus`, `taux_retention_pct`, `taux_churn_pct`, `anciennete_moy_mois`.
*   **`kpi_data_par_region`** : Stocke la consommation internet totale et les revenus data par ville.
    *   *Colonnes* : `annee`, `mois`, `nom_mois`, `country`, `city`, `region`, `technology`, `abonnes_data`, `nb_sessions_data`, `total_mb`, `total_gb`, `data_moy_par_session_mb`, `revenu_data_total`.

---

## 5. PIPELINE D'INTÉGRATION (ETL)

Le pipeline d'intégration est développé en Python (`etl_pipeline_3.py`) et utilise `mysql.connector`.

### 5.1. Phase 1 : Extraction (Extract)
Le script charge les 5 fichiers CSV bruts situés dans le dossier `telecom_data/`.

### 5.2. Phase 2 : Transformation (Transform)
Le nettoyage applique des filtres stricts pour garantir l'intégrité de l'EDW. Les abonnés sans identifiant unique (`subscriber_id`) ou sans forfait associé (`plan_id`) sont rejetés. Le pipeline charge les tables de correspondance en mémoire sous forme de dictionnaires Python (`sub_map`, `tower_map`...) et mappe les clés à l'aide d'opérations vectorisées zip ultra-rapides.

### 5.3. Phase 3 : Chargement (Load)
*   **Dimensions Historisées ( subscriber )** :
    *   *Optimisation Chargement Initial* : Si la table `dim_subscriber` est vide, le script effectue un **BULK INSERT** par paquets de 5 000 lignes (`executemany`). Cela permet d'insérer les 100 000 lignes initiales en **1,5 seconde** !
    *   *Optimisation Chargement Incrémental* : Si des données existent, le script compare en mémoire les attributs suivis en SCD2. Il n'appelle la procédure stockée lourde `sp_upsert_subscriber_scd2` **que** pour les abonnés ayant subi une modification.
*   **Tables de Faits (`fact_usage`, `fact_incident`)** : Insérées par lots de 5 000 lignes à l'aide de requêtes `INSERT IGNORE` pour éviter les doublons.

============================================================
[👉 ESPACE WORD : COLLER LE DIAGRAMME DU PIPELINE ETL ICI (pipeline_etl.png)]
============================================================

---

## 6. MATÉRIALISATION DES KPIs ET PERFORMANCE

Dans les architectures décisionnelles professionnelles, le Dashboard ne doit pas exécuter d'agrégations en direct sur des millions de lignes. 

### 6.1. Architecture de Matérialisation (`refresh_kpis.py`)
Nous avons matérialisé les 7 vues de reporting SQL décisionnelles dans des tables physiques indexées (`kpi_arpu`, etc.) à la fin de l'ETL.
Le Dashboard interroge alors ces tables statiques contenant seulement quelques dizaines de lignes pré-agrégées, ce qui réduit le temps de réponse de **10 minutes à 0,001 seconde**.

---

## 7. MACHINE LEARNING : MODÈLE DE PRÉDICTION DU CHURN

Le script de Machine Learning (`churn_prediction.py`) entraîne un algorithme pour détecter le risque de départ des clients actifs.

### 7.1. Préparation des variables (Feature Engineering)
*   Création du **Taux de Consommation Data** (`data_usage_ratio = data_used_mb / data_quota_gb`).
*   Création du **Taux d'Échec des Appels** (`call_failure_rate = failed_calls / total_calls`).

### 7.2. Stratégie d'Entraînement
*   **Validation Temporelle (Time-Series Split)** : Sépare les données chronologiquement. L'entraînement s'effectue sur l'historique (`2025-11` à `2026-04`) et le test sur le mois le plus récent (`2026-05`).
*   **Équilibrage par SMOTE** : Technique de sur-échantillonnage synthétique pour équilibrer la classe minoritaire.
*   **Algorithme** : Utilisation du classificateur **XGBoost (Extreme Gradient Boosting)**.

### 7.3. Résultats Réels de Performance du Modèle
Le modèle XGBoost entraîné sur les données historiques de Sahel Telecom produit les métriques réelles d'évaluation suivantes (consignées dans `resultats_modeles_xgboost.csv`) :

| Métrique | Score Réel Obtenu | Description / Interprétation |
| :--- | :--- | :--- |
| **Exactitude (Accuracy)** | **64.8 %** | Proportion globale de prédictions correctes. |
| **Précision** | **17.1 %** | Fiabilité de l'IA lorsqu'elle prédit qu'un client va résilier. |
| **Rappel (Recall)** | **28.7 %** | Capacité de l'IA à identifier tous les clients réels en fuite. |
| **F1-Score** | **21.4 %** | Moyenne harmonique entre Précision et Rappel (évaluation équilibrée). |
| **Aire sous la courbe (AUC)** | **50.8 %** | Performance de discrimination globale du classificateur. |

*(Note : Compte tenu de la nature simulée bruitée des transactions d'usage, ce score illustre parfaitement le fonctionnement de l'évaluation sur un jeu de données réel déséquilibré).*

============================================================
[👉 ESPACE WORD : COLLER LA COURBE ROC DE PERFORMANCE ICI (courbes_roc.png)]
============================================================

============================================================
[👉 ESPACE WORD : COLLER LA MATRICE DE CONFUSION ICI (matrice_confusion_xgboost.png)]
============================================================

### 7.4. Explicabilité SHAP et Importance des Variables
Pour expliquer les prédictions au niveau métier (et éliminer les noms techniques de la base de données), les variables sont renommées en français avant de générer le graphique SHAP.

============================================================
[👉 ESPACE WORD : COLLER LE GRAPHIQUE SHAP ICI (shap_summary.png)]
============================================================

============================================================
[👉 ESPACE WORD : COLLER LE GRAPHIQUE DE L'IMPORTANCE DES VARIABLES ICI (importance_variables.png)]
============================================================

---

## 8. INTERFACE DÉCISIONNELLE : DASHBOARD STREAMLIT

L'application décisionnelle (`dashboard_streamlit.py`) est développée sous Streamlit. Elle se connecte à la base de données MySQL via la bibliothèque `pymysql` et interroge directement les 7 tables de KPIs matérialisées de façon instantanée.

### 8.1. Identité Visuelle et Charte Graphique
Le design est épuré, lumineux et conforme aux standards d'applications décisionnelles modernes :
*   **Typographie** : Police Google Fonts **Inter**, lisible et moderne.
*   **Couleurs de l'interface** :
    *   *Fond principal* : `#f4f6fa` (Gris bleu très clair, reposant).
    *   *Barre latérale (Sidebar)* : Dégradé Indigo `linear-gradient(180deg, #1a237e 0%, #3949ab 100%)`.
    *   *Cartes KPI* : Blanc pur avec ombre portée douce et bordure gauche bleue (`#3949ab`).
*   **Couleurs des graphiques (Plotly)** : Bleu Indigo (`#3949ab`), Rouge Corail (`#e53935` pour le Churn) et Vert Émeraude (`#43a047` pour la fidélité).

### 8.2. Description Détaillée des Pages du Dashboard
L'application propose 4 onglets de navigation dans son menu latéral. Voici le descriptif complet des données, des graphiques et des fonctionnalités interactives de chaque page, avec les emplacements prévus pour coller les captures d'écran dans votre document Word final.

#### 8.2.1. Page 1 : Vue d'ensemble (KPIs Généraux & Chiffre d'Affaires)
Cette page offre une vision macro-économique de l'activité de Sahel Telecom et GoldTel.

*   **Composants du haut de page (Filtres et Cartes KPIs)** :
    *   *Filtre Pays* : Permet de basculer l'affichage pour le Burkina Faso, le Ghana, ou les deux pays combinés.
    *   *Filtre Segment* : Filtre les KPIs selon le segment client (Particulier, Professionnel, Entreprise).
    *   *Carte 1 : Revenu Total* : Chiffre d'affaires global cumulé (FCFA/GHS).
    *   *Carte 2 : Nombre d'Abonnés* : Total des clients uniques enregistrés.
    *   *Carte 3 : ARPU Moyen* : Revenu Moyen par Abonné actif.
    *   *Carte 4 : Taux de Churn* : Proportion globale de clients ayant résilié leur contrat.
*   **Composants du bas de page (Graphiques Temporels)** :
    *   *Graphique 1 : Évolution Mensuelle de l'ARPU* : Courbe montrant la tendance de consommation mensuelle moyenne.
    *   *Graphique 2 : Évolution Mensuelle du Taux de Churn* : Histogramme de l'évolution du taux d'attrition au cours du temps.

============================================================
[👉 ESPACE WORD : COLLER LA CAPTURE D'ÉCRAN - PAGE 1 - VUE D'ENSEMBLE (Partie Haute - Cartes KPIs)]
============================================================

============================================================
[👉 ESPACE WORD : COLLER LA CAPTURE D'ÉCRAN - PAGE 1 - VUE D'ENSEMBLE (Partie Basse - Graphiques)]
============================================================

#### 8.2.2. Page 2 : Réseau & Antennes (Saturation et Qualité de Service)
Cette page est dédiée au suivi des infrastructures réseau et à la détection des zones en surcharge.

*   **Composants du haut de page (Saturation Réseau et Technologie)** :
    *   *Graphique 1 : Taux d'Utilisation Réseau Moyen* : Représentation de la saturation des antennes par technologie (2G, 3G, 4G). Une alerte visuelle s'affiche si une antenne dépasse 80% d'utilisation.
    *   *Graphique 2 : Volume de Données Consommées par Région* : Analyse en barres horizontales de la consommation data totale par ville.
*   **Composants du bas de page (Qualité de Service & Incidents)** :
    *   *Graphique 3 : Taux d'Incidents et Sévérité par Antenne* : Répartition du nombre d'anomalies réseau.
    *   *Graphique 4 : Temps Moyen de Résolution (MTR)* : Durée moyenne en minutes de réparation d'une panne par type de réseau.

============================================================
[👉 ESPACE WORD : COLLER LA CAPTURE D'ÉCRAN - PAGE 2 - RÉSEAU & ANTENNES (Partie Haute - Saturation Réseau)]
============================================================

============================================================
[👉 ESPACE WORD : COLLER LA CAPTURE D'ÉCRAN - PAGE 2 - RÉSEAU & ANTENNES (Partie Basse - QoS et Incidents)]
============================================================

#### 8.2.3. Page 3 : Offres & Abonnements (Performances Commerciales)
Cet onglet permet aux équipes marketing de mesurer l'attractivité des forfaits et la fidélité des abonnés associés.

*   **Composants du haut de page (Parts de marché des Offres)** :
    *   *Graphique 1 : Taux de Rétention par Forfait* : Comparatif du taux de fidélité pour chacune des 10 offres commercialisées.
    *   *Graphique 2 : Répartition des Abonnés par Type d'Abonnement* : Diagramme circulaire illustrant la proportion de clients en Prépayé, Postpayé et Entreprise.
*   **Composants du bas de page (Durée des Appels)** :
    *   *Graphique 3 : Durée Moyenne des Appels* : Évolution de la durée moyenne de communication par tranche horaire et segment.
    *   *Graphique 4 : Taux d'Échec des Appels* : Histogramme des appels manqués ou échoués par réseau.

============================================================
[👉 ESPACE WORD : COLLER LA CAPTURE D'ÉCRAN - PAGE 3 - OFFRES & ABONNEMENTS (Partie Haute - Performance Offres)]
============================================================

============================================================
[👉 ESPACE WORD : COLLER LA CAPTURE D'ÉCRAN - PAGE 3 - OFFRES & ABONNEMENTS (Partie Basse - Analyse Appels)]
============================================================

#### 8.2.4. Page 4 : Prédiction IA - Risque de Churn
C'est le module d'intelligence artificielle connectant le modèle prédictif XGBoost à l'interface commerciale.

*   **Composants du haut de page (Performance de l'IA & Interprétabilité)** :
    *   *Métriques de validation* : Affichage de l'Exactitude, de la Précision et du F1-Score pour rassurer les décideurs sur la fiabilité de l'IA.
    *   *Graphiques d'explicabilité (SHAP)* : Visualisation des facteurs influençant le départ des clients (Jours sans activité, pannes subies, ancienneté, etc.).
*   **Composants du bas de page (Outil de prospection commerciale)** :
    *   *Tableau Interactif des 500 Abonnés à Haut Risque* : Tableau listant les abonnés actifs présentant la plus forte probabilité de résiliation. L'interface offre des boutons de filtrage par ville, segment et forfait pour cibler précisément les campagnes de fidélisation (ex: envoyer un SMS promotionnel).

============================================================
[👉 ESPACE WORD : COLLER LA CAPTURE D'ÉCRAN - PAGE 4 - PRÉDICTION IA (Partie Haute - Interprétabilité SHAP)]
============================================================

============================================================
[👉 ESPACE WORD : COLLER LA CAPTURE D'ÉCRAN - PAGE 4 - PRÉDICTION IA (Partie Basse - Liste de Prospection)]
============================================================

---

## 9. CONSEILS DE DÉPANNAGE ET RÉSOLUTIONS D'ERREURS (FAQ)

### 9.1. Erreur : `RuntimeError: Event loop is closed`
Le serveur Streamlit a été arrêté de manière abrupte (via `Ctrl+C` répétés) pendant qu'un thread de script s'exécutait en arrière-plan. Fermez le terminal actuel et relancez.

### 9.2. Erreur MySQL : `sql_mode=only_full_group_by`
Sous MySQL 8.0, toutes les colonnes présentes dans la clause `SELECT` doivent obligatoirement figurer dans la clause `GROUP BY`. Les requêtes ont été corrigées en groupant strictement par les clés naturelles d'origine (`GROUP BY annee, mois, country`).

---

## 10. PROCÉDURE DE REPRODUCTION COMPLÈTE (DE A A Z)

Pour reconstruire l'ensemble du projet décisionnel à partir de zéro, suivez cette séquence de commandes :

1.  **Installer les dépendances** :
```bash
py -m pip install -r requirements.txt
```
2.  **Démarrer MySQL (Docker)** :
```bash
docker-compose up -d
```
3.  **Générer les données brutes** :
```bash
py generate_data.py
```
4.  **Exécuter l'ETL et la matérialisation** :
```bash
py etl_pipeline_3.py
py refresh_kpis.py
```
5.  **Entraîner le modèle d'IA** :
```bash
py churn_prediction.py
```
6.  **Lancer le Dashboard Streamlit** :
```bash
py -m streamlit run dashboard_streamlit.py
```
L'application decisionnelle s'ouvrira automatiquement à l'adresse [http://localhost:8501](http://localhost:8501).

---

## 11. RETOUR D'EXPÉRIENCE, DIFFICULTÉS ET STRATÉGIE DE DÉPLOIEMENT

### 11.1. Liens du Projet en Production
Le projet a été versionné et déployé avec succès sur des environnements Cloud :
- **Code Source (GitHub) :** [https://github.com/Abdrafith-ZONGO/etl-pipeline-telecom_G3](https://github.com/Abdrafith-ZONGO/etl-pipeline-telecom_G3)
- **Application BI (Live) :** [https://sahel-telecom-dashboard.streamlit.app/](https://sahel-telecom-dashboard.streamlit.app/)

### 11.2. Difficultés Rencontrées : La Volumétrie des Données
Lors du passage de la phase de développement local à la phase de déploiement en ligne, nous avons été confrontés à un défi architectural majeur : **la volumétrie des données brutes**.
- Les fichiers sources CSV et la table de faits (`fact_usage`) contenant des millions de lignes pesaient plusieurs centaines de mégaoctets, rendant impossible leur hébergement sur des dépôts gratuits comme GitHub (limite fixée à 100 Mo).
- Héberger une base de données MySQL complète en ligne pour exécuter ce Dashboard aurait engendré des **coûts d'infrastructure importants** (serveur VPS ou RDS) qui n'étaient pas envisageables dans ce contexte.
- L'interrogation de ces gros volumes sur le Cloud ralentissait considérablement le tableau de bord.

### 11.3. La Solution : Architecture "Micro-KPIs" et "Serverless"
Pour surpasser cette difficulté budgétaire et technique, nous avons mis en place une stratégie d'optimisation poussée en séparant le "calcul lourd" (ETL) de la "présentation" (Dashboard) :

1. **Création de Mini-Tables (Matérialisation) :** Au lieu d'obliger le Dashboard à requêter les millions de lignes brutes, nous avons programmé le script `refresh_kpis.py`. Il pré-calcule l'ensemble des métriques métier et stocke les résultats finaux dans des **mini-tables agrégées** (ex: `kpi_arpu`, `kpi_duree_appels`).
2. **Extraction vers SQLite (`export_kpis_for_cloud.py`) :** Juste avant le déploiement, ce script se connecte au serveur MySQL local, aspire *uniquement* ces petites tables de KPIs, et crée une micro-base de données portable au format **SQLite** (`cloud_data/kpis.db`).
   - *Résultat exceptionnel :* La taille des données est passée de plus de **250 Mo** à un seul fichier de **1.5 Mo**.
3. **Dashboard Hybride Intelligent :** Le fichier `dashboard_streamlit.py` a été adapté avec un mécanisme de **fallback**. En ligne, lorsqu'il ne trouve pas de serveur MySQL à disposition, il bascule instantanément sur la lecture de la base SQLite locale.
4. **Déploiement 100% Gratuit :**
   - L'ajout d'un filtre `.gitignore` strict a permis de pousser uniquement le code source et le fichier `.db` vers GitHub sans être bloqué.
   - **Streamlit Community Cloud** a été connecté à ce dépôt GitHub pour déployer l'interface web instantanément, de façon totalement gratuite et fluide.

**Commande pour générer la base Cloud en local :**
```bash
py export_kpis_for_cloud.py
```
