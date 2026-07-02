import pymysql
import sqlite3
import pandas as pd
import os

print("===================================================================")
print("  EXPORTATION DES KPIS POUR DEPLOIEMENT GRATUIT SUR STREAMLIT CLOUD")
print("===================================================================")

# Paramètres de connexion MySQL locale
DB_CONFIG = dict(host="127.0.0.1", user="root", password="1234", database="edw_sahel_telecom", port=3306)

try:
    mysql_conn = pymysql.connect(**DB_CONFIG)
except Exception as e:
    print(f"[ERREUR] Erreur de connexion à MySQL : {e}")
    print("Veuillez vérifier que MySQL est bien lancé (docker-compose up -d)")
    exit()

# Création du dossier cloud_data/
os.makedirs("cloud_data", exist_ok=True)
sqlite_path = "cloud_data/kpis.db"

# Supprimer la base SQLite si elle existe déjà pour la recréer proprement
if os.path.exists(sqlite_path):
    os.remove(sqlite_path)

# Connexion à SQLite
sqlite_conn = sqlite3.connect(sqlite_path)

# Liste des tables KPI à migrer (elles sont petites et agrégées)
tables_a_exporter = [
    "kpi_arpu",
    "kpi_churn_mensuel",
    "kpi_data_par_region",
    "kpi_incidents_qualite",
    "kpi_utilisation_reseau",
    "kpi_retention_par_offre",
    "kpi_duree_appels"
]

print("\nExtraction des données depuis MySQL vers SQLite locale...\n")

for table in tables_a_exporter:
    try:
        # Lecture depuis MySQL
        df = pd.read_sql(f"SELECT * FROM {table}", mysql_conn)
        
        # Ecriture dans SQLite
        df.to_sql(table, sqlite_conn, index=False, if_exists="replace")
        
        taille_ko = df.memory_usage(index=True).sum() / 1024
        print(f"[OK] {table} exportée avec succès : {len(df)} lignes ({taille_ko:.1f} Ko).")
    except Exception as e:
        print(f"[ERREUR] Erreur lors de l'export de {table} : {e}")

mysql_conn.close()
sqlite_conn.close()

print("\n===================================================================")
print("  EXPORTATION TERMINÉE !")
print(f"  -> Les données du Dashboard sont enregistrées dans : '{sqlite_path}'")
print("  -> Pour déployer : Envoyez tout le projet sur GitHub et connectez-le à Streamlit Community Cloud.")
print("===================================================================")
