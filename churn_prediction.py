"""
Modèle prédictif de churn avancé - EDW Sahel Telecom
Version 2.0 avec MySQL, XGBoost, SMOTE et SHAP
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import os
from sqlalchemy import create_engine, text

print("1. Connexion à l'Entrepôt de Données (MySQL)...")

# Machine Learning
from sklearn.preprocessing import StandardScaler, LabelEncoder
from xgboost import XGBClassifier
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, roc_curve, confusion_matrix)

# Explicabilité
import shap

# Configuration de la base de données
DB_USER = "root"
DB_PASS = "1234"
DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_NAME = "edw_sahel_telecom"

OUT_DIR = "churn_model_outputs"
os.makedirs(OUT_DIR, exist_ok=True)
np.random.seed(42)
plt.rcParams["font.family"] = "DejaVu Sans"
engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

query = """
SELECT 
    f.snapshot_month,
    s.subscriber_id,
    s.gender,
    s.age,
    s.segment,
    s.country,
    p.plan_name,
    p.monthly_fee,
    p.data_quota_gb,
    f.data_used_mb,
    f.voice_used_sec,
    f.sms_used,
    f.revenue_fcfa,
    f.network_incidents,
    f.failed_calls,
    f.days_since_active,
    f.churn_status
FROM fact_subscriber_monthly f
JOIN dim_subscriber s ON f.subscriber_sk = s.subscriber_sk
JOIN dim_plan p ON f.plan_sk = p.plan_sk
"""
import pymysql
print("2. Extraction des données (Snapshots mensuels)...")
conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, port=DB_PORT)
df = pd.read_sql(query, conn)
conn.close()

if len(df) == 0:
    print("ERREUR : Aucune donnée dans fact_subscriber_monthly. L'ETL a-t-il été exécuté ?")
    exit(1)

print(f"   Données extraites : {len(df):,} lignes.")

print("3. Feature Engineering & Nettoyage...")
# Traitement des valeurs nulles
df["age"] = df["age"].fillna(df["age"].median())
df["gender"] = df["gender"].fillna("Inconnu")

# Nouvelles Features basées sur l'usage vs forfait
df["data_usage_ratio"] = df["data_used_mb"] / (df["data_quota_gb"] * 1024 + 1)
df["call_failure_rate"] = df["failed_calls"] / (df["voice_used_sec"]/60 + df["failed_calls"] + 1)

# Variables catégorielles
cat_cols = ["gender", "segment", "country", "snapshot_month"]
label_encoders = {}
for col in cat_cols:
    le = LabelEncoder()
    df[col + "_enc"] = le.fit_transform(df[col].astype(str))
    label_encoders[col] = le

feature_cols = [
    "age", "monthly_fee", "data_quota_gb", "data_used_mb", "voice_used_sec", 
    "sms_used", "revenue_fcfa", "network_incidents", "failed_calls", 
    "days_since_active", "data_usage_ratio", "call_failure_rate",
    "gender_enc", "segment_enc", "country_enc"
]

print("4. Validation Temporelle (Time-Series Split)...")
# Nous utilisons les mois précédents pour entraîner, et le dernier mois pour tester
months_sorted = sorted(df["snapshot_month"].unique())
if len(months_sorted) < 2:
    print("ATTENTION: Pas assez de mois différents pour un Time-Series split strict. Séparation classique.")
    from sklearn.model_selection import train_test_split
    X = df[feature_cols]
    y = df["churn_status"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
else:
    test_month = months_sorted[-1] # Le mois le plus récent
    print(f"   Mois de Test : {test_month}")
    print(f"   Mois d'Entraînement : {', '.join(months_sorted[:-1])}")
    
    train_df = df[df["snapshot_month"] != test_month]
    test_df  = df[df["snapshot_month"] == test_month]
    
    X_train = train_df[feature_cols]
    y_train = train_df["churn_status"]
    
    X_test = test_df[feature_cols]
    y_test = test_df["churn_status"]

print(f"   Train : {len(X_train):,} lignes | Test : {len(X_test):,} lignes")

print("5. Équilibrage des classes (SMOTE)...")
smote = SMOTE(random_state=42)
X_train_sm, y_train_sm = smote.fit_resample(X_train, y_train)
print(f"   Train équilibré : {len(X_train_sm):,} lignes")

# Mise à l'échelle
scaler = StandardScaler()
X_train_sc = scaler.fit_transform(X_train_sm)
X_test_sc  = scaler.transform(X_test)

# Pour XGBoost, les données non scalées fonctionnent très bien, mais on utilise le df mis à l'échelle pour la cohérence
print("6. Entraînement Modèle Avancé (XGBoost)...")
# Note: Dans un vrai contexte, on utiliserait GridSearchCV ici. Pour limiter le temps d'exécution, on fixe de bons hyperparamètres.
xgb = XGBClassifier(
    n_estimators=100, 
    learning_rate=0.1, 
    max_depth=5, 
    random_state=42, 
    use_label_encoder=False, 
    eval_metric='logloss'
)
xgb.fit(X_train_sc, y_train_sm)

y_pred = xgb.predict(X_test_sc)
y_proba = xgb.predict_proba(X_test_sc)[:, 1]

print("\n=== RÉSULTATS XGBOOST ===")
print(f"Accuracy  : {accuracy_score(y_test, y_pred):.3f}")
print(f"Précision : {precision_score(y_test, y_pred):.3f}")
print(f"Rappel    : {recall_score(y_test, y_pred):.3f}")
print(f"F1-Score  : {f1_score(y_test, y_pred):.3f}")
print(f"AUC-ROC   : {roc_auc_score(y_test, y_proba):.3f}")

# Explicabilité avec SHAP (avec noms en français)
print("\n7. Génération de l'explicabilité (SHAP)...")
translation_dict = {
    "age": "Âge du Client",
    "monthly_fee": "Prix du Forfait (FCFA)",
    "data_quota_gb": "Quota Internet (Go)",
    "data_used_mb": "Internet Consommé (Mo)",
    "voice_used_sec": "Durée des Appels (sec)",
    "sms_used": "SMS Envoyés",
    "revenue_fcfa": "Revenu Généré (FCFA)",
    "network_incidents": "Pannes Réseau Subies",
    "failed_calls": "Appels en Échec",
    "days_since_active": "Jours sans Activité",
    "data_usage_ratio": "Taux de Consommation Internet",
    "call_failure_rate": "Taux d'Échec des Appels",
    "gender_enc": "Genre (Encodé)",
    "segment_enc": "Segment Client (Encodé)",
    "country_enc": "Pays (Encodé)"
}
beautiful_feature_names = [translation_dict.get(col, col) for col in feature_cols]

try:
    explainer = shap.TreeExplainer(xgb)
    sample_idx = np.random.choice(X_test_sc.shape[0], min(1000, X_test_sc.shape[0]), replace=False)
    shap_values = explainer.shap_values(X_test_sc[sample_idx])
    
    plt.figure(figsize=(10, 8))
    # Nous passons X_test renommé pour que SHAP affiche les vrais noms français sur le graphique
    X_test_renamed = X_test.iloc[sample_idx].rename(columns=translation_dict)
    shap.summary_plot(shap_values, X_test_renamed, show=False)
    plt.title("Impact des variables sur la prédiction de Churn (SHAP)", fontsize=14, pad=15)
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/shap_summary.png", dpi=120)
    plt.close()
    print("   Graphique SHAP généré avec succès en français.")
except Exception as e:
    print(f"   Erreur lors de la génération SHAP : {e}")

# Importance des variables (CSV et Graphique PNG)
print("8. Génération de l'importance des variables...")
try:
    importances = xgb.feature_importances_
    df_imp = pd.DataFrame({
        "Variable": beautiful_feature_names,
        "Importance": importances
    }).sort_values("Importance", ascending=False)
    
    # Sauvegarde CSV
    df_imp.to_csv(f"{OUT_DIR}/importance_variables.csv", index=False)
    
    # Sauvegarde Graphique PNG
    plt.figure(figsize=(10, 6))
    sns.barplot(x="Importance", y="Variable", data=df_imp, palette="Blues_r")
    plt.title("Importance des variables dans la décision de l'IA", fontsize=14, pad=15)
    plt.xlabel("Score d'Importance")
    plt.ylabel("")
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/importance_variables.png", dpi=120)
    plt.close()
    print("   Importance des variables sauvegardée (CSV & PNG).")
except Exception as e:
    print(f"   Erreur lors de la génération de l'importance des variables : {e}")

# Courbe ROC
print("9. Génération de la Courbe ROC...")
try:
    fpr, tpr, _ = roc_curve(y_test, y_proba)
    plt.figure(figsize=(6, 5))
    plt.plot(fpr, tpr, color="#3949ab", lw=2, label=f"XGBoost (AUC = {roc_auc_score(y_test, y_proba):.3f})")
    plt.plot([0, 1], [0, 1], color="grey", lw=1, linestyle="--")
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel("Taux de Faux Positifs")
    plt.ylabel("Taux de Vrais Positifs")
    plt.title("Courbe ROC - Performance du Modèle")
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/courbes_roc.png", dpi=120)
    plt.close()
    print("   Courbe ROC générée.")
except Exception as e:
    print(f"   Erreur lors de la génération de la courbe ROC : {e}")

# Matrices de confusion
plt.figure(figsize=(6, 5))
cm = confusion_matrix(y_test, y_pred)
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=["Non-Churn", "Churn"], yticklabels=["Non-Churn", "Churn"])
plt.title("Matrice de confusion - XGBoost")
plt.ylabel("Réel")
plt.xlabel("Prédit")
plt.tight_layout()
plt.savefig(f"{OUT_DIR}/matrice_confusion_xgboost.png", dpi=120)
plt.close()

# Sauvegarde des résultats généraux
results = pd.DataFrame({
    "Modèle": ["XGBoost"],
    "Accuracy": [accuracy_score(y_test, y_pred)],
    "Précision": [precision_score(y_test, y_pred)],
    "Rappel": [recall_score(y_test, y_pred)],
    "F1-Score": [f1_score(y_test, y_pred)],
    "AUC": [roc_auc_score(y_test, y_proba)]
})
results.to_csv(f"{OUT_DIR}/resultats_modeles_xgboost.csv", index=False)

# Scoring des clients actifs (sur le dernier mois)
actifs_test = test_df[test_df["churn_status"] == 0].copy()
if len(actifs_test) > 0:
    X_actifs = scaler.transform(actifs_test[feature_cols])
    actifs_test["risque_churn_pct"] = xgb.predict_proba(X_actifs)[:, 1] * 100
    
    top500 = actifs_test.sort_values("risque_churn_pct", ascending=False).head(500)
    # On sauvegarde un jeu complet de colonnes pour le dashboard Streamlit
    cols_to_save = [
        "subscriber_id", "snapshot_month", "country", "age", "segment", 
        "monthly_fee", "days_since_active", "network_incidents", "failed_calls", "risque_churn_pct"
    ]
    # S'assurer que toutes les colonnes existent
    cols_to_save = [c for c in cols_to_save if c in top500.columns]
    top500[cols_to_save].to_csv(f"{OUT_DIR}/top_500_abonnes_a_risque.csv", index=False)
    
    print(f"\n✅ Scoring terminé. {len(actifs_test):,} abonnés actifs analysés.")
    print("   Résultats exportés dans le dossier 'churn_model_outputs/'")
