"""
Génération de données aléatoires pour le projet EDW - Sahel Telecom
Groupe 3 - Master 1 Data Science - IFOAD - Juin 2026
"""

import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
import os

random.seed(42)
np.random.seed(42)

OUTPUT_DIR = "telecom_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 60)
print("  Génération des données Sahel Telecom / GoldTel")
print("=" * 60)

# ─────────────────────────────────────────────────
# 1. PLANS (offres)
# ─────────────────────────────────────────────────
print("\n[1/5] Génération des plans tarifaires...")

plans = [
    {"plan_id": "P001", "plan_name": "Starter BF",      "country": "Burkina Faso", "monthly_fee": 2000,  "data_quota_gb": 1,   "call_minutes": 60,   "sms_quota": 50,  "type": "Prépayé"},
    {"plan_id": "P002", "plan_name": "Basic BF",        "country": "Burkina Faso", "monthly_fee": 5000,  "data_quota_gb": 3,   "call_minutes": 120,  "sms_quota": 100, "type": "Prépayé"},
    {"plan_id": "P003", "plan_name": "Standard BF",     "country": "Burkina Faso", "monthly_fee": 10000, "data_quota_gb": 7,   "call_minutes": 300,  "sms_quota": 200, "type": "Postpayé"},
    {"plan_id": "P004", "plan_name": "Premium BF",      "country": "Burkina Faso", "monthly_fee": 20000, "data_quota_gb": 20,  "call_minutes": 600,  "sms_quota": 500, "type": "Postpayé"},
    {"plan_id": "P005", "plan_name": "Business BF",     "country": "Burkina Faso", "monthly_fee": 35000, "data_quota_gb": 50,  "call_minutes": 1200, "sms_quota": 1000,"type": "Entreprise"},
    {"plan_id": "P006", "plan_name": "Starter GH",      "country": "Ghana",        "monthly_fee": 15,    "data_quota_gb": 1,   "call_minutes": 60,   "sms_quota": 50,  "type": "Prépayé"},
    {"plan_id": "P007", "plan_name": "Basic GH",        "country": "Ghana",        "monthly_fee": 35,    "data_quota_gb": 3,   "call_minutes": 120,  "sms_quota": 100, "type": "Prépayé"},
    {"plan_id": "P008", "plan_name": "Standard GH",     "country": "Ghana",        "monthly_fee": 70,    "data_quota_gb": 7,   "call_minutes": 300,  "sms_quota": 200, "type": "Postpayé"},
    {"plan_id": "P009", "plan_name": "Premium GH",      "country": "Ghana",        "monthly_fee": 140,   "data_quota_gb": 20,  "call_minutes": 600,  "sms_quota": 500, "type": "Postpayé"},
    {"plan_id": "P010", "plan_name": "Business GH",     "country": "Ghana",        "monthly_fee": 250,   "data_quota_gb": 50,  "call_minutes": 1200, "sms_quota": 1000,"type": "Entreprise"},
]
df_plans = pd.DataFrame(plans)
df_plans.to_csv(f"{OUTPUT_DIR}/plans.csv", index=False)
print(f"  ✔ plans.csv → {len(df_plans)} offres")

# ─────────────────────────────────────────────────
# 2. TOWERS (antennes)
# ─────────────────────────────────────────────────
print("\n[2/5] Génération des antennes réseau...")

cities_bf = [
    ("Ouagadougou", "Centre",    "Burkina Faso", 12.3647, -1.5332),
    ("Bobo-Dioulasso", "Hauts-Bassins", "Burkina Faso", 11.1771, -4.2979),
    ("Koudougou",   "Centre-Ouest", "Burkina Faso", 12.2500, -2.3667),
]
cities_gh = [
    ("Accra",   "Greater Accra", "Ghana",  5.6037, -0.1870),
    ("Kumasi",  "Ashanti",       "Ghana",  6.6884, -1.6244),
    ("Tamale",  "Northern",      "Ghana",  9.4008, -0.8393),
]
all_cities = cities_bf + cities_gh

towers = []
tower_id = 1
for city, region, country, lat, lon in all_cities:
    n = 5 if country == "Burkina Faso" else 4
    for i in range(n):
        towers.append({
            "tower_id":    f"T{tower_id:03d}",
            "tower_name":  f"Antenne_{city[:3].upper()}_{i+1}",
            "city":        city,
            "region":      region,
            "country":     country,
            "latitude":    round(lat + np.random.uniform(-0.05, 0.05), 4),
            "longitude":   round(lon + np.random.uniform(-0.05, 0.05), 4),
            "capacity_users": random.choice([500, 800, 1000, 1500, 2000]),
            "technology":  random.choice(["2G", "3G", "4G", "4G", "4G"]),
            "installation_date": (datetime(2010,1,1) + timedelta(days=random.randint(0,3650))).strftime("%Y-%m-%d"),
            "status":      random.choices(["Actif", "Maintenance", "Inactif"], weights=[88,8,4])[0],
            # Quelques valeurs manquantes volontaires
            "etat_batterie": random.choices(["Bon", "Moyen", "Faible", None], weights=[60,25,10,5])[0],
        })
        tower_id += 1

df_towers = pd.DataFrame(towers)
df_towers.to_csv(f"{OUTPUT_DIR}/towers.csv", index=False)
print(f"  ✔ towers.csv → {len(df_towers)} antennes")

# ─────────────────────────────────────────────────
# 3. SUBSCRIBERS (abonnés)
# ─────────────────────────────────────────────────
print("\n[3/5] Génération des abonnés (100 000)...")

N_SUBSCRIBERS = 100_000

bf_cities   = [c[0] for c in cities_bf]
gh_cities   = [c[0] for c in cities_gh]
bf_plans    = ["P001","P002","P003","P004","P005"]
gh_plans    = ["P006","P007","P008","P009","P010"]

# Répartition pays : 60% BF, 40% GH
countries   = np.random.choice(["Burkina Faso","Ghana"], size=N_SUBSCRIBERS, p=[0.60,0.40])
cities_arr  = np.where(countries=="Burkina Faso",
                        np.random.choice(bf_cities, N_SUBSCRIBERS),
                        np.random.choice(gh_cities, N_SUBSCRIBERS))
plans_arr   = np.where(countries=="Burkina Faso",
                        np.random.choice(bf_plans, N_SUBSCRIBERS, p=[0.30,0.30,0.20,0.15,0.05]),
                        np.random.choice(gh_plans, N_SUBSCRIBERS, p=[0.30,0.30,0.20,0.15,0.05]))

start_dates = [datetime(2018,1,1) + timedelta(days=int(d))
               for d in np.random.randint(0, 2190, N_SUBSCRIBERS)]

genders     = np.random.choice(["M","F", None], N_SUBSCRIBERS, p=[0.50,0.47,0.03])
ages        = np.random.randint(16, 75, N_SUBSCRIBERS).astype(float)
# Introduire ~2% valeurs manquantes sur l'âge
mask_age    = np.random.random(N_SUBSCRIBERS) < 0.02
ages[mask_age] = np.nan

# Statut churn : ~15% ont churné
churn_prob  = np.where(np.char.startswith(plans_arr.astype(str), "P00"), 0.18, 0.10)
churn_flag  = np.random.random(N_SUBSCRIBERS) < churn_prob

churn_dates = []
for i in range(N_SUBSCRIBERS):
    if churn_flag[i]:
        cd = start_dates[i] + timedelta(days=random.randint(30, 1500))
        churn_dates.append(cd.strftime("%Y-%m-%d") if cd < datetime(2026,6,1) else None)
    else:
        churn_dates.append(None)

# Associer une tour à chaque abonné (même ville)
tower_city_map = df_towers.groupby("city")["tower_id"].apply(list).to_dict()
assigned_towers = []
for city in cities_arr:
    towers_in_city = tower_city_map.get(city, df_towers["tower_id"].tolist())
    assigned_towers.append(random.choice(towers_in_city))

subscribers = pd.DataFrame({
    "subscriber_id":    [f"SUB{i+1:06d}" for i in range(N_SUBSCRIBERS)],
    "first_name":       np.random.choice(
        ["Kofi","Ama","Kwame","Abena","Yaw","Akua","Kojo","Efua",     # Ghana
         "Ibrahim","Fatoumata","Moussa","Aminata","Ali","Mariam","Oumar","Rasmata"], # BF
        N_SUBSCRIBERS),
    "last_name":        np.random.choice(
        ["Ouedraogo","Sawadogo","Traore","Compaore","Zoungrana","Kabore",
         "Mensah","Asante","Boateng","Owusu","Amponsah","Amoah"],
        N_SUBSCRIBERS),
    "gender":           genders,
    "age":              ages,
    "city":             cities_arr,
    "country":          countries,
    "plan_id":          plans_arr,
    "tower_id":         assigned_towers,
    "subscription_date": [d.strftime("%Y-%m-%d") for d in start_dates],
    "phone_number":     [f"+{random.choice(['226','233'])}{random.randint(60000000,79999999)}"
                         for _ in range(N_SUBSCRIBERS)],
    "email":            [f"user{i+1}@{'sahel' if c=='Burkina Faso' else 'goldtel'}.com"
                         if random.random() > 0.25 else None
                         for i, c in enumerate(countries)],
    "churn":            churn_flag.astype(int),
    "churn_date":       churn_dates,
    "monthly_revenue":  np.round(np.random.uniform(500, 40000, N_SUBSCRIBERS), 2),
    "segment":          np.random.choice(["Particulier","Professionnel","Entreprise"],
                                          N_SUBSCRIBERS, p=[0.70,0.20,0.10]),
})

df_subscribers = subscribers
df_subscribers.to_csv(f"{OUTPUT_DIR}/subscribers.csv", index=False)
print(f"  ✔ subscribers.csv → {len(df_subscribers):,} abonnés | Churn: {df_subscribers['churn'].sum():,} ({df_subscribers['churn'].mean()*100:.1f}%)")

# ─────────────────────────────────────────────────
# 4. USAGE EVENTS (événements d'usage)
# ─────────────────────────────────────────────────
print("\n[4/5] Génération des événements d'usage (500 000+)...")

N_USAGE = 550_000
sub_sample = df_subscribers["subscriber_id"].values

event_types = ["Appel_Sortant","Appel_Entrant","SMS_Sortant","SMS_Entrant","Data"]
weights_evt  = [0.28, 0.25, 0.10, 0.10, 0.27]

event_types_arr = np.random.choice(event_types, N_USAGE, p=weights_evt)
sub_ids_arr     = np.random.choice(sub_sample, N_USAGE)

# Dates entre 2023-01-01 et 2026-05-31
base_date = datetime(2023, 1, 1)
rand_seconds = np.random.randint(0, int((datetime(2026,6,1)-base_date).total_seconds()), N_USAGE)
event_dates  = [base_date + timedelta(seconds=int(s)) for s in rand_seconds]

durations = []
data_mb   = []
amounts   = []
for et in event_types_arr:
    if et in ["Appel_Sortant","Appel_Entrant"]:
        dur = int(np.random.exponential(120))  # secondes
        durations.append(min(dur, 3600))
        data_mb.append(0)
        amounts.append(round(random.uniform(10, 500), 2))
    elif et in ["SMS_Sortant","SMS_Entrant"]:
        durations.append(0)
        data_mb.append(0)
        amounts.append(round(random.uniform(5, 50), 2))
    else:  # Data
        durations.append(0)
        data_mb.append(round(random.uniform(0.5, 2000), 2))
        amounts.append(round(random.uniform(5, 300), 2))

# Mapper tower depuis subscriber
sub_tower_map = df_subscribers.set_index("subscriber_id")["tower_id"].to_dict()
tower_ids_arr = [sub_tower_map.get(s, df_towers["tower_id"].iloc[0]) for s in sub_ids_arr]

# ~1% valeurs manquantes sur amount
mask_amt = np.random.random(N_USAGE) < 0.01
amounts_arr = np.array(amounts, dtype=float)
amounts_arr[mask_amt] = np.nan

usage = pd.DataFrame({
    "usage_id":       [f"USG{i+1:07d}" for i in range(N_USAGE)],
    "subscriber_id":  sub_ids_arr,
    "tower_id":       tower_ids_arr,
    "event_type":     event_types_arr,
    "event_datetime": [d.strftime("%Y-%m-%d %H:%M:%S") for d in event_dates],
    "duration_sec":   durations,
    "data_mb":        data_mb,
    "amount_fcfa":    amounts_arr,
    "status":         np.random.choice(["Succès","Échec","Interrompu"], N_USAGE, p=[0.92,0.05,0.03]),
    "network_type":   np.random.choice(["2G","3G","4G"], N_USAGE, p=[0.15,0.30,0.55]),
    "roaming":        np.random.choice([0,1], N_USAGE, p=[0.96,0.04]),
})

df_usage = usage
df_usage.to_csv(f"{OUTPUT_DIR}/usage.csv", index=False)
print(f"  ✔ usage.csv → {len(df_usage):,} événements")

# ─────────────────────────────────────────────────
# 5. INCIDENTS QUALITE
# ─────────────────────────────────────────────────
print("\n[5/5] Génération des incidents qualité...")

N_INCIDENTS = 15_000
incident_types = [
    "Coupure_signal","Dégradation_débit","Appel_échoué",
    "SMS_non_livré","Latence_élevée","Interférence"
]
severities = ["Faible","Moyen","Élevé"]

tower_ids_list = df_towers["tower_id"].tolist()
inc_dates = [base_date + timedelta(seconds=int(s))
             for s in np.random.randint(0, int((datetime(2026,6,1)-base_date).total_seconds()), N_INCIDENTS)]

resolution_minutes = np.random.exponential(45, N_INCIDENTS).astype(int) + 5
resolved_flags = np.random.choice([True, False], N_INCIDENTS, p=[0.85, 0.15])

incidents = pd.DataFrame({
    "incident_id":       [f"INC{i+1:06d}" for i in range(N_INCIDENTS)],
    "tower_id":          np.random.choice(tower_ids_list, N_INCIDENTS),
    "incident_type":     np.random.choice(incident_types, N_INCIDENTS),
    "severity":          np.random.choice(severities, N_INCIDENTS, p=[0.55,0.32,0.13]),
    "incident_datetime": [d.strftime("%Y-%m-%d %H:%M:%S") for d in inc_dates],
    "resolution_minutes": resolution_minutes,
    "resolved":          resolved_flags,
    "resolution_date":   [(d + timedelta(minutes=int(r))).strftime("%Y-%m-%d %H:%M:%S")
                          if res else None
                          for d, r, res in zip(inc_dates, resolution_minutes, resolved_flags)],
    "description":       np.random.choice([
        "Signal faible détecté","Surcharge de la cellule","Maintenance planifiée",
        "Problème d'alimentation","Interférence externe","Mise à jour firmware",
        None  # quelques valeurs manquantes
    ], N_INCIDENTS, p=[0.20,0.20,0.15,0.15,0.13,0.12,0.05]),
    "nb_abonnes_affectes": np.random.randint(1, 500, N_INCIDENTS),
})

df_incidents = incidents
df_incidents.to_csv(f"{OUTPUT_DIR}/incidents_qualite_legers.csv", index=False)
print(f"  ✔ incidents_qualite_legers.csv → {len(df_incidents):,} incidents")

# ─────────────────────────────────────────────────
# RÉSUMÉ FINAL
# ─────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  ✅ GÉNÉRATION TERMINÉE")
print("=" * 60)
total_rows = len(df_plans) + len(df_towers) + len(df_subscribers) + len(df_usage) + len(df_incidents)
print(f"\n  📁 Dossier de sortie : ./{OUTPUT_DIR}/")
print(f"\n  Fichier                          | Lignes")
print(f"  {'─'*45}")
print(f"  plans.csv                        | {len(df_plans):>8,}")
print(f"  towers.csv                       | {len(df_towers):>8,}")
print(f"  subscribers.csv                  | {len(df_subscribers):>8,}")
print(f"  usage.csv                        | {len(df_usage):>8,}")
print(f"  incidents_qualite_legers.csv     | {len(df_incidents):>8,}")
print(f"  {'─'*45}")
print(f"  TOTAL                            | {total_rows:>8,}")
print(f"\n  Taux de churn simulé : {df_subscribers['churn'].mean()*100:.1f}%")
print(f"  Pays couverts        : Burkina Faso + Ghana")
print(f"  Période des données  : 2023-01-01 → 2026-05-31")
print("\n  Prochaine étape → Conception du schéma en étoile (MySQL)")
