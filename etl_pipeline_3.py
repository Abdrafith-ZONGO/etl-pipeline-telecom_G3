"""
==========================================================
ETL PIPELINE - EDW SAHEL TELECOM / GOLDTEL
Master 1 - IFOAD - Groupe 3 - Juin 2026
==========================================================

Ce script réalise le pipeline ETL complet :
1. EXTRACT  : lecture des 5 fichiers CSV
2. TRANSFORM: nettoyage, typage, gestion des valeurs manquantes,
              calcul des surrogate keys, application des règles SCD
3. LOAD     : chargement dans les tables MySQL via PROCÉDURES STOCKÉES
              (sp_upsert_subscriber_scd2, sp_upsert_plan_scd2,
               sp_upsert_tower_scd1) pour les dimensions historisées,
              et bulk INSERT pour les faits (pas de SCD sur les faits).

PRÉREQUIS D'EXÉCUTION (ordre obligatoire) :
    1. mysql -u root -p < edw_sahel_telecom.sql
    2. mysql -u root -p < populate_dim_date.sql
    3. mysql -u root -p < triggers_and_procedures.sql   <-- requis avant ce script
    4. pip install pandas mysql-connector-python --break-system-packages
    5. python etl_pipeline.py

Configuration :
    Modifier les paramètres de connexion dans DB_CONFIG ci-dessous.

Note sur les performances :
    Les dimensions (subscriber, plan, tower) passent par des appels
    CALL sp_xxx(...) ligne par ligne pour exploiter la vraie logique SCD
    et les triggers de garde-fou définis dans triggers_and_procedures.sql.
    C'est plus lent qu'un bulk INSERT mais nécessaire pour l'historisation
    correcte. Les tables de faits (usage, incident) restent en bulk INSERT
    par lots de 5000 lignes car elles n'ont pas de logique SCD.
"""

import pandas as pd
import numpy as np
import mysql.connector
from mysql.connector import Error
import logging
from datetime import datetime
import sys
import os

# ============================================================
# CONFIGURATION
# ============================================================

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "1234",   # <-- À MODIFIER
    "database": "edw_sahel_telecom",
    "port": 3306,
}

DATA_DIR = "telecom_data"   # dossier contenant les CSV générés

# Logging vers fichier ET console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("etl_run.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("ETL")


# ============================================================
# UTILITAIRES DE CONNEXION ET DE LOG ETL
# ============================================================

def get_connection():
    """Ouvre une connexion MySQL."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        log.error(f"Erreur de connexion MySQL : {e}")
        raise


def etl_log_start(conn, table_name, operation):
    """Crée une entrée de log ETL et retourne son ID."""
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO etl_log (table_name, operation, status, start_time) "
        "VALUES (%s, %s, 'RUNNING', NOW())",
        (table_name, operation)
    )
    conn.commit()
    log_id = cur.lastrowid
    cur.close()
    return log_id


def etl_log_end(conn, log_id, status, rows_extracted=0, rows_inserted=0,
                 rows_rejected=0, rows_updated=0, error_message=None):
    """Met à jour l'entrée de log ETL avec le résultat final."""
    cur = conn.cursor()
    cur.execute(
        """UPDATE etl_log
           SET status=%s, rows_extracted=%s, rows_inserted=%s,
               rows_rejected=%s, rows_updated=%s,
               error_message=%s, end_time=NOW()
           WHERE log_id=%s""",
        (status, rows_extracted, rows_inserted, rows_rejected,
         rows_updated, error_message, log_id)
    )
    conn.commit()
    cur.close()


def log_rejected_row(conn, source_table, raw_data, reason):
    """Enregistre une ligne rejetée dans etl_rejected_rows."""
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO etl_rejected_rows (source_table, raw_data, rejection_reason) "
        "VALUES (%s, %s, %s)",
        (source_table, str(raw_data)[:2000], reason)
    )
    conn.commit()
    cur.close()


# ============================================================
# ÉTAPE 1 : EXTRACTION (Extract)
# ============================================================

def extract_csv(filename):
    """Lit un fichier CSV et retourne un DataFrame pandas."""
    path = os.path.join(DATA_DIR, filename)
    log.info(f"  Extraction de {filename}...")
    df = pd.read_csv(path, low_memory=False)
    log.info(f"  → {len(df):,} lignes extraites")
    return df


# ============================================================
# ÉTAPE 2 : TRANSFORMATION (Transform)
# ============================================================

def transform_plans(df):
    """Nettoie le DataFrame des plans tarifaires."""
    df = df.copy()
    df["monthly_fee"]   = pd.to_numeric(df["monthly_fee"], errors="coerce")
    df["data_quota_gb"] = pd.to_numeric(df["data_quota_gb"], errors="coerce")
    df["call_minutes"]  = pd.to_numeric(df["call_minutes"], errors="coerce")
    df["sms_quota"]     = pd.to_numeric(df["sms_quota"], errors="coerce")

    # Catégorie de prix dérivée (enrichissement)
    def categorie_prix(fee, country):
        # Seuils différents selon devise (FCFA vs Cedis)
        seuil_bas  = 10000 if country == "Burkina Faso" else 70
        seuil_haut = 25000 if country == "Burkina Faso" else 175
        if fee < seuil_bas:
            return "Économique"
        elif fee < seuil_haut:
            return "Standard"
        return "Premium"

    df["categorie_prix"] = df.apply(
        lambda r: categorie_prix(r["monthly_fee"], r["country"]), axis=1
    )
    df = df.rename(columns={"type": "type_abonnement"})
    return df


def transform_towers(df):
    """Nettoie le DataFrame des antennes."""
    df = df.copy()
    df["latitude"]       = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"]      = pd.to_numeric(df["longitude"], errors="coerce")
    df["capacity_users"] = pd.to_numeric(df["capacity_users"], errors="coerce").fillna(0).astype(int)
    df["installation_date"] = pd.to_datetime(df["installation_date"], errors="coerce")

    # Standardisation status
    df["status"] = df["status"].fillna("Inconnu").str.strip()

    # Règle de gestion : valeur manquante etat_batterie -> "Non renseigné"
    df["etat_batterie"] = df["etat_batterie"].fillna("Non renseigné")

    # Enrichissement : zone_type dérivé de la ville (règle métier simple)
    grandes_villes = ["Ouagadougou", "Accra", "Kumasi"]
    df["zone_type"] = df["city"].apply(
        lambda c: "Urbain" if c in grandes_villes else "Péri-urbain"
    )
    return df


def transform_subscribers(df):
    """Nettoie le DataFrame des abonnés."""
    df = df.copy()

    # Âge : conversion numérique, gestion des valeurs manquantes/aberrantes
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    df.loc[(df["age"] < 14) | (df["age"] > 100), "age"] = np.nan

    # Tranche d'âge dérivée
    def tranche_age(age):
        if pd.isna(age):
            return "Inconnu"
        if age < 25:
            return "16-24"
        elif age < 35:
            return "25-34"
        elif age < 50:
            return "35-49"
        return "50+"
    df["tranche_age"] = df["age"].apply(tranche_age)

    # Genre : standardisation
    df["gender"] = df["gender"].fillna("Inconnu").str.upper().str.strip()
    df["gender"] = df["gender"].replace({"M": "M", "F": "F"})
    df.loc[~df["gender"].isin(["M", "F"]), "gender"] = "Inconnu"

    # Dates
    df["subscription_date"] = pd.to_datetime(df["subscription_date"], errors="coerce")
    df["churn_date"]        = pd.to_datetime(df["churn_date"], errors="coerce")

    # Churn : booléen propre
    df["churn"] = pd.to_numeric(df["churn"], errors="coerce").fillna(0).astype(int)

    # Revenu mensuel
    df["monthly_revenue"] = pd.to_numeric(df["monthly_revenue"], errors="coerce")
    df["monthly_revenue"] = df["monthly_revenue"].fillna(df["monthly_revenue"].median())

    # Email manquant -> NULL explicite (déjà NaN)
    # Règle qualité : lignes sans subscriber_id ou sans plan_id sont rejetées
    before = len(df)
    rejected = df[df["subscriber_id"].isna() | df["plan_id"].isna()]
    df = df.dropna(subset=["subscriber_id", "plan_id"])
    log.info(f"  → {before - len(df)} lignes rejetées (subscriber_id ou plan_id manquant)")

    return df, rejected


def transform_usage(df, valid_subscribers, valid_towers):
    """Nettoie le DataFrame des événements d'usage."""
    df = df.copy()

    df["event_datetime"] = pd.to_datetime(df["event_datetime"], errors="coerce")
    df["duration_sec"]   = pd.to_numeric(df["duration_sec"], errors="coerce").fillna(0).astype(int)
    df["data_mb"]        = pd.to_numeric(df["data_mb"], errors="coerce").fillna(0)
    df["amount_fcfa"]    = pd.to_numeric(df["amount_fcfa"], errors="coerce")

    # Règle qualité : amount_fcfa manquant -> imputé par la médiane du type d'événement
    df["amount_fcfa"] = df.groupby("event_type")["amount_fcfa"].transform(
        lambda x: x.fillna(x.median())
    )

    df["roaming"] = pd.to_numeric(df["roaming"], errors="coerce").fillna(0).astype(int)

    # Intégrité référentielle : on ne garde que les événements liés à un abonné
    # et une antenne existants (évite les erreurs de clé étrangère)
    before = len(df)
    df = df[df["subscriber_id"].isin(valid_subscribers)]
    df = df[df["tower_id"].isin(valid_towers)]
    rejected_count = before - len(df)
    log.info(f"  → {rejected_count:,} lignes rejetées (référence abonné/antenne invalide)")

    # Rejet des lignes sans date valide
    before2 = len(df)
    df = df.dropna(subset=["event_datetime"])
    log.info(f"  → {before2 - len(df):,} lignes rejetées (date invalide)")

    return df


def transform_incidents(df, valid_towers):
    """Nettoie le DataFrame des incidents qualité."""
    df = df.copy()
    df["incident_datetime"]  = pd.to_datetime(df["incident_datetime"], errors="coerce")
    df["resolution_minutes"] = pd.to_numeric(df["resolution_minutes"], errors="coerce")
    df["resolved"]           = df["resolved"].astype(str).str.lower().isin(["true", "1"])
    df["nb_abonnes_affectes"] = pd.to_numeric(df["nb_abonnes_affectes"], errors="coerce").fillna(0).astype(int)
    df["description"]        = df["description"].fillna("Non renseigné")

    before = len(df)
    df = df[df["tower_id"].isin(valid_towers)]
    df = df.dropna(subset=["incident_datetime"])
    log.info(f"  → {before - len(df):,} lignes rejetées (antenne invalide ou date manquante)")

    return df


# ============================================================
# ÉTAPE 3 : CHARGEMENT (Load)
# ============================================================

def load_dim_plan(conn, df):
    """
    Charge la dimension Plan via la procédure stockée SCD Type 2
    (sp_upsert_plan_scd2 — définie dans triggers_and_procedures.sql).
    Chaque appel insère la version initiale, ou crée une nouvelle version
    si le tarif a changé depuis le dernier chargement.
    """
    cur = conn.cursor()
    cols = ["plan_id","plan_name","type_abonnement","country","monthly_fee",
            "data_quota_gb","call_minutes","sms_quota","categorie_prix"]
    rows = list(df[cols].itertuples(index=False, name=None))

    for row in rows:
        cur.callproc("sp_upsert_plan_scd2", row)
    conn.commit()

    log.info(f"  ✔ dim_plan : {len(rows)} plans traités via sp_upsert_plan_scd2 (SCD Type 2)")
    cur.close()
    return len(rows)


def load_dim_tower(conn, df):
    """
    Charge la dimension Tower via la procédure stockée SCD Type 1
    (sp_upsert_tower_scd1 — écrasement direct, pas d'historique conservé,
    cohérent avec le principe SCD1 vu au Module 2 du cours).
    """
    cur = conn.cursor()
    cols = ["tower_id","tower_name","city","region","country","latitude","longitude",
            "capacity_users","technology","installation_date","status",
            "etat_batterie","zone_type"]
    df_load = df[cols].copy()
    df_load["installation_date"] = df_load["installation_date"].dt.strftime("%Y-%m-%d")
    df_load = df_load.where(pd.notnull(df_load), None)
    rows = list(df_load.itertuples(index=False, name=None))

    for row in rows:
        cur.callproc("sp_upsert_tower_scd1", row)
    conn.commit()

    log.info(f"  ✔ dim_tower : {len(rows)} antennes traitées via sp_upsert_tower_scd1 (SCD Type 1)")
    cur.close()
    return len(rows)


def load_dim_localisation(conn, df_towers, df_subscribers):
    """Construit et charge la dimension Localisation (combinaison ville/pays unique)."""
    cur = conn.cursor()
    cur.execute("DELETE FROM dim_localisation")

    locs = df_towers[["city", "region", "country", "latitude", "longitude", "zone_type"]].drop_duplicates(subset=["city","country"])

    def pop_zone(city):
        grandes = ["Ouagadougou", "Accra"]
        moyennes = ["Bobo-Dioulasso", "Kumasi"]
        if city in grandes: return "Grande ville"
        if city in moyennes: return "Ville moyenne"
        return "Petite ville"

    locs["population_zone"] = locs["city"].apply(pop_zone)
    locs["fuseau_horaire"] = locs["country"].apply(
        lambda c: "Africa/Ouagadougou" if c == "Burkina Faso" else "Africa/Accra"
    )

    sql = """INSERT INTO dim_localisation
        (city, region, country, latitude, longitude, zone_type, population_zone, fuseau_horaire)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"""
    rows = list(locs.itertuples(index=False, name=None))
    cur.executemany(sql, rows)
    conn.commit()
    log.info(f"  ✔ dim_localisation : {cur.rowcount} lignes chargées")
    cur.close()
    return len(rows)


def load_dim_subscriber(conn, df):
    """
    Charge la dimension Subscriber via la procédure stockée SCD Type 2
    (sp_upsert_subscriber_scd2). Nettoie automatiquement les NaN/NaT.
    """
    cur = conn.cursor()

    cols = ["subscriber_id","first_name","last_name","gender","age","tranche_age",
            "city","country","plan_id","tower_id","phone_number","email","segment",
            "churn","churn_date","subscription_date","monthly_revenue"]
    df_load = df[cols].copy()

    # Dates en string, NaT -> None
    df_load["subscription_date"] = df_load["subscription_date"].dt.strftime("%Y-%m-%d")
    df_load["churn_date"] = df_load["churn_date"].dt.strftime("%Y-%m-%d")

    # Remplacer NaN par None
    df_load = df_load.where(pd.notnull(df_load), None)

    rows = list(df_load.itertuples(index=False, name=None))
    total = len(rows)
    batch_log_size = 5000

    for i, row in enumerate(rows, start=1):
        row = list(row)

        # Age : int ou None
        row[4] = None if row[4] is None or pd.isna(row[4]) else int(row[4])

        # Churn : 0/1 ou None
        row[13] = 0 if row[13] is None or pd.isna(row[13]) else int(row[13])

        # Dates invalides -> None
        if row[14] is None or pd.isna(row[14]) or str(row[14]).lower() == "nan":
            row[14] = None  # churn_date
        if row[15] is None or pd.isna(row[15]) or str(row[15]).lower() == "nan":
            row[15] = None  # subscription_date

        # Email vide -> None
        if row[11] is None or pd.isna(row[11]) or str(row[11]).strip() == "":
            row[11] = None

        # Segment vide -> None
        if row[12] is None or pd.isna(row[12]) or str(row[12]).strip() == "":
            row[12] = None

        # Revenu mensuel : float ou None
        row[16] = None if row[16] is None or pd.isna(row[16]) else float(row[16])

        cur.callproc("sp_upsert_subscriber_scd2", row)

        if i % batch_log_size == 0:
            conn.commit()
            log.info(f"    ... {i:,}/{total:,} abonnés traités via sp_upsert_subscriber_scd2")


    conn.commit()
    log.info(f"  ✔ dim_subscriber : {total:,} abonnés traités via sp_upsert_subscriber_scd2 (SCD Type 2)")
    cur.close()
    return total



def get_surrogate_key_maps(conn):
    """Récupère les mappings natural_key -> surrogate_key pour toutes les dimensions."""
    cur = conn.cursor()

    cur.execute("SELECT subscriber_id, subscriber_sk FROM dim_subscriber WHERE is_current=1")
    sub_map = dict(cur.fetchall())

    cur.execute("SELECT tower_id, tower_sk FROM dim_tower")
    tower_map = dict(cur.fetchall())

    cur.execute("SELECT plan_id, plan_sk FROM dim_plan")
    plan_map = dict(cur.fetchall())

    cur.execute("SELECT city, country, location_sk FROM dim_localisation")
    loc_map = {(c, p): sk for c, p, sk in cur.fetchall()}

    cur.close()
    return sub_map, tower_map, plan_map, loc_map


def load_fact_usage(conn, df, sub_map, tower_map, plan_map, loc_map, tower_to_city, sub_to_country):
    """Charge la table de faits Usage avec résolution des surrogate keys."""
    cur = conn.cursor()
    cur.execute("DELETE FROM fact_usage")

    sql = """INSERT INTO fact_usage
        (subscriber_sk, date_sk, tower_sk, plan_sk, location_sk, usage_id,
         duration_sec, data_mb, amount_fcfa, event_type, status, network_type, roaming)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""

    # Préparation vectorisée des surrogate keys
    df = df.copy()
    df["date_sk"]       = df["event_datetime"].dt.strftime("%Y%m%d").astype(int)
    df["subscriber_sk"] = df["subscriber_id"].map(sub_map)
    df["tower_sk"]      = df["tower_id"].map(tower_map)
    # plan_sk vient du plan de l'abonné (jointure indirecte) -> on le récupère via subscriber
    df["city"]          = df["tower_id"].map(tower_to_city)
    df["country"]       = df["subscriber_id"].map(sub_to_country)
    df["location_sk"]   = df.apply(lambda r: loc_map.get((r["city"], r["country"])), axis=1)

    rows_to_insert = []
    rejected = 0

    # Résolution du plan_sk en Python avant insertion (évite le UPDATE lent)
    cur2 = conn.cursor()
    cur2.execute("""
        SELECT s.subscriber_sk, p.plan_sk
        FROM dim_subscriber s
        JOIN dim_plan p ON s.plan_id = p.plan_id AND p.is_current = 1
        WHERE s.is_current = 1
    """)
    sk_to_plan_sk = {int(row[0]): int(row[1]) for row in cur2.fetchall()}
    cur2.close()
    log.info(f"  → plan_sk pré-résolu pour {len(sk_to_plan_sk):,} abonnés actifs")

    for r in df.itertuples(index=False):
        if pd.isna(r.subscriber_sk) or pd.isna(r.tower_sk) or pd.isna(r.location_sk):
            rejected += 1
            continue
        sub_sk = int(r.subscriber_sk)
        rows_to_insert.append((
            sub_sk,
            int(r.date_sk),
            int(r.tower_sk),
            sk_to_plan_sk.get(sub_sk),   # plan_sk résolu directement
            int(r.location_sk),
            r.usage_id,
            int(r.duration_sec),
            float(r.data_mb),
            None if pd.isna(r.amount_fcfa) else float(r.amount_fcfa),
            r.event_type,
            r.status,
            r.network_type,
            int(r.roaming)
        ))

    log.info(f"  → {rejected:,} lignes rejetées (clé étrangère introuvable)")

    batch_size = 5000
    total = 0
    for i in range(0, len(rows_to_insert), batch_size):
        batch = rows_to_insert[i:i+batch_size]
        cur.executemany(sql, batch)
        conn.commit()
        total += len(batch)
        if total % 50000 == 0 or total == len(rows_to_insert):
            log.info(f"    ... {total:,}/{len(rows_to_insert):,} événements chargés")

    log.info(f"  ✔ fact_usage : {total:,} lignes chargées")
    cur.close()
    return total, rejected


def load_fact_incident(conn, df, tower_map, loc_map, tower_to_city, tower_to_country):
    """Charge la table de faits Incident — version corrigée sans verrou dim_date."""
    cur = conn.cursor()
    cur.execute("DELETE FROM fact_incident")

    df = df.copy()

    if not pd.api.types.is_datetime64_any_dtype(df["incident_datetime"]):
        df["incident_datetime"] = pd.to_datetime(df["incident_datetime"])

    # Calcul date_sk en int Python natif (évite numpy.int64 qui cause des bugs MySQL)
    df["date_sk"] = df["incident_datetime"].apply(
        lambda d: int(d.strftime("%Y%m%d")) if pd.notna(d) else None
    )

    # Mapping clés étrangères
    df["tower_sk"]    = df["tower_id"].map(tower_map)
    df["city"]        = df["tower_id"].map(tower_to_city)
    df["country"]     = df["tower_id"].map(tower_to_country)
    df["location_sk"] = df.apply(lambda r: loc_map.get((r["city"], r["country"])), axis=1)

    # Construction des lignes à insérer
    sql = """INSERT INTO fact_incident
        (tower_sk, date_sk, location_sk, incident_id, incident_type, severity,
         resolved, description, resolution_minutes, nb_abonnes_affectes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""

    rows = []
    rejected = 0

    for r in df.itertuples(index=False):
        if pd.isna(r.tower_sk) or pd.isna(r.location_sk) or r.date_sk is None:
            rejected += 1
            continue

        resolved_val = 1 if r.resolved else 0

        desc_val = None
        if r.description and not pd.isna(r.description):
            desc_val = str(r.description)[:500]

        res_min = None
        if not pd.isna(r.resolution_minutes):
            try:
                res_min = int(float(r.resolution_minutes))
            except (ValueError, TypeError):
                res_min = None

        try:
            nb_aff = int(float(r.nb_abonnes_affectes)) if not pd.isna(r.nb_abonnes_affectes) else 0
        except (ValueError, TypeError):
            nb_aff = 0

        rows.append((
            int(r.tower_sk),
            int(r.date_sk),
            int(r.location_sk),
            r.incident_id,
            r.incident_type,
            r.severity,
            resolved_val,
            desc_val,
            res_min,
            nb_aff
        ))

    log.info(f"  → {rejected} lignes rejetées (clé manquante)")

    # Insertion bulk en lots de 5000
    batch_size = 5000
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        cur.executemany(sql, batch)
        conn.commit()
        total += len(batch)

    log.info(f"  ✔ fact_incident : {total:,} lignes chargées ({rejected} rejetées)")
    cur.close()
    return total, rejected

def print_data_quality_report(conn):
    """Affiche le rapport de qualité des données via sp_data_quality_report."""
    cur = conn.cursor()
    cur.callproc("sp_data_quality_report")
    log.info("\n[RAPPORT QUALITÉ DES DONNÉES]")
    for result in cur.stored_results():
        for row in result.fetchall():
            log.info(f"  {row}")
    cur.close()


# ============================================================
# PIPELINE PRINCIPAL
# ============================================================

def run_etl():
    start_time = datetime.now()
    log.info("=" * 60)
    log.info("DÉMARRAGE DU PIPELINE ETL - EDW SAHEL TELECOM")
    log.info("=" * 60)

    conn = get_connection()

    try:
        # ───────────── EXTRACT ─────────────
        log.info("\n[EXTRACT] Lecture des fichiers CSV sources")
        df_plans_raw       = extract_csv("c:/Users/savad/OneDrive/Documents/DATA SCIENCE/M1/S2/entrepot de donnée/Projet/telecom_data/plans.csv")
        df_towers_raw      = extract_csv("c:/Users/savad/OneDrive/Documents/DATA SCIENCE/M1/S2/entrepot de donnée/Projet/telecom_data/towers.csv")
        df_subscribers_raw = extract_csv("c:/Users/savad/OneDrive/Documents/DATA SCIENCE/M1/S2/entrepot de donnée/Projet/telecom_data/subscribers.csv")
        df_usage_raw       = extract_csv("c:/Users/savad/OneDrive/Documents/DATA SCIENCE/M1/S2/entrepot de donnée/Projet/telecom_data/usage.csv")
        df_incidents_raw   = extract_csv("c:/Users/savad/OneDrive/Documents/DATA SCIENCE/M1/S2/entrepot de donnée/Projet/telecom_data/incidents_qualite_legers.csv")

        # ───────────── TRANSFORM ─────────────
        log.info("\n[TRANSFORM] Nettoyage et enrichissement des données")

        log.info("Transformation : plans")
        df_plans = transform_plans(df_plans_raw)

        log.info("Transformation : towers")
        df_towers = transform_towers(df_towers_raw)

        log.info("Transformation : subscribers")
        df_subscribers, rejected_subs = transform_subscribers(df_subscribers_raw)
        df_subscribers = df_subscribers.where(pd.notnull(df_subscribers), None)
        valid_subscribers = set(df_subscribers["subscriber_id"])
        valid_towers      = set(df_towers["tower_id"])

        log.info("Transformation : usage")
        df_usage = transform_usage(df_usage_raw, valid_subscribers, valid_towers)

        log.info("Transformation : incidents")
        df_incidents = transform_incidents(df_incidents_raw, valid_towers)

        # ───────────── PURGE DES FAITS (avant les dimensions) ─────────────
        # Important : si ce script a déjà tourné une fois, fact_usage et
        # fact_incident contiennent des lignes qui référencent dim_localisation
        # via une clé étrangère. Il faut vider les faits AVANT de vider les
        # dimensions, sinon MySQL refuse le DELETE sur dim_localisation
        # (erreur 1451 : Cannot delete or update a parent row).
        log.info("\n[PURGE] Nettoyage des tables de faits avant rechargement")
        cur_purge = conn.cursor()
        cur_purge.execute("DELETE FROM fact_usage")
        cur_purge.execute("DELETE FROM fact_incident")
        conn.commit()
        cur_purge.close()
        log.info("  ✔ fact_usage et fact_incident vidées")

        # ───────────── LOAD : DIMENSIONS ─────────────
        log.info("\n[LOAD] Chargement des dimensions")

        log_id = etl_log_start(conn, "dim_plan", "LOAD")
        n = load_dim_plan(conn, df_plans)
        etl_log_end(conn, log_id, "SUCCESS", rows_extracted=len(df_plans_raw), rows_inserted=n)

        log_id = etl_log_start(conn, "dim_tower", "LOAD")
        n = load_dim_tower(conn, df_towers)
        etl_log_end(conn, log_id, "SUCCESS", rows_extracted=len(df_towers_raw), rows_inserted=n)

        log_id = etl_log_start(conn, "dim_localisation", "LOAD")
        n = load_dim_localisation(conn, df_towers, df_subscribers)
        etl_log_end(conn, log_id, "SUCCESS", rows_inserted=n)

        log_id = etl_log_start(conn, "dim_subscriber", "LOAD")
        n = load_dim_subscriber(conn, df_subscribers)
        etl_log_end(conn, log_id, "SUCCESS",
                    rows_extracted=len(df_subscribers_raw), rows_inserted=n,
                    rows_rejected=len(rejected_subs))

        # ───────────── LOAD : FAITS ─────────────
        log.info("\n[LOAD] Chargement des tables de faits")

        sub_map, tower_map, plan_map, loc_map = get_surrogate_key_maps(conn)
        tower_to_city    = df_towers.set_index("tower_id")["city"].to_dict()
        tower_to_country = df_towers.set_index("tower_id")["country"].to_dict()
        sub_to_country   = df_subscribers.set_index("subscriber_id")["country"].to_dict()

        log_id = etl_log_start(conn, "fact_usage", "LOAD")
        n, rej = load_fact_usage(conn, df_usage, sub_map, tower_map, plan_map,
                                   loc_map, tower_to_city, sub_to_country)
        etl_log_end(conn, log_id, "SUCCESS",
                    rows_extracted=len(df_usage_raw), rows_inserted=n, rows_rejected=rej)

        log_id = etl_log_start(conn, "fact_incident", "LOAD")
        n, rej = load_fact_incident(conn, df_incidents, tower_map, loc_map,
                                      tower_to_city, tower_to_country)
        etl_log_end(conn, log_id, "SUCCESS",
                    rows_extracted=len(df_incidents_raw), rows_inserted=n, rows_rejected=rej)

        duration = (datetime.now() - start_time).total_seconds()

        # Rapport de gouvernance final (procédure stockée)
        print_data_quality_report(conn)

        log.info("\n" + "=" * 60)
        log.info(f" PIPELINE ETL TERMINÉ AVEC SUCCÈS en {duration:.1f}s")
        log.info("=" * 60)

    except Exception as e:
        log.error(f" ERREUR DANS LE PIPELINE : {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_etl()
