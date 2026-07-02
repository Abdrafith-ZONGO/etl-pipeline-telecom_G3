import pymysql
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger("KPI_REFRESH")

DB = dict(host="127.0.0.1", user="root", password="1234", database="edw_sahel_telecom", port=3306)

def refresh_kpis():
    log.info("Démarrage de la matérialisation des KPIs...")
    start_time = time.time()
    
    try:
        conn = pymysql.connect(**DB)
        cursor = conn.cursor()
        
        kpis = [
            "kpi_churn_mensuel",
            "kpi_arpu",
            "kpi_utilisation_reseau",
            "kpi_incidents_qualite",
            "kpi_duree_appels",
            "kpi_retention_par_offre",
            "kpi_data_par_region"
        ]
        
        for k in kpis:
            log.info(f"Matérialisation de la table {k}...")
            # 1. Création de la table si elle n'existe pas
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {k} AS SELECT * FROM v_{k} WHERE 1=0")
            
            # 2. Vidage
            cursor.execute(f"TRUNCATE TABLE {k}")
            
            # 3. Insertion des données calculées depuis la vue
            cursor.execute(f"INSERT INTO {k} SELECT * FROM v_{k}")
            conn.commit()
            log.info(f"  ✔ Table {k} matérialisée avec succès.")
            
        cursor.close()
        conn.close()
        
        duration = time.time() - start_time
        log.info(f"Matérialisation terminée avec succès en {duration:.1f} secondes !")
        
    except Exception as e:
        log.error(f"Erreur lors de la matérialisation des KPIs : {e}")

if __name__ == "__main__":
    refresh_kpis()
