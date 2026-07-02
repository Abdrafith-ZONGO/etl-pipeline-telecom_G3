import streamlit as st
import pandas as pd
import pymysql
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import os, warnings
warnings.filterwarnings("ignore")

# =====================================================================
# CONFIGURATION PAGE
# =====================================================================
st.set_page_config(
    page_title="Sahel Telecom – Tableau de Bord BI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================================
# CSS — Design clair, moderne et professionnel
# =====================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #f4f6fa; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a237e 0%, #283593 60%, #3949ab 100%);
    color: white;
}
[data-testid="stSidebar"] * { color: white !important; }
[data-testid="stSidebar"] .stRadio > div { gap: 0.3rem; }
[data-testid="stSidebar"] .stRadio label {
    background: rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 0.5rem 0.8rem;
    margin: 2px 0;
    transition: background 0.2s;
}
[data-testid="stSidebar"] .stRadio label:hover { background: rgba(255,255,255,0.18); }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.2) !important; }

/* Cartes métriques KPI */
[data-testid="metric-container"] {
    background: white;
    border: none;
    border-radius: 14px;
    padding: 1.2rem 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    border-left: 5px solid #3949ab;
}
[data-testid="metric-container"] label {
    color: #5f6368 !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #1a237e !important;
    font-size: 1.8rem !important;
    font-weight: 700 !important;
}

/* Titres */
h1 { color: #1a237e !important; font-weight: 700 !important; font-size: 1.8rem !important; }
h2, h3 { color: #283593 !important; font-weight: 600 !important; }

/* Bandeau page */
.page-header {
    background: linear-gradient(135deg, #e8eaf6 0%, #c5cae9 100%);
    border-left: 5px solid #3949ab;
    border-radius: 10px;
    padding: 1rem 1.4rem;
    margin-bottom: 1.5rem;
    color: #1a237e;
    font-size: 0.92rem;
}

/* Tableaux */
[data-testid="stDataFrame"] {
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
}

/* Séparateur */
hr { border: 1px solid #e0e0e0; }
</style>
""", unsafe_allow_html=True)

# =====================================================================
# COULEURS GRAPHIQUES
# =====================================================================
BLEU  = "#3949ab"
ROUGE = "#e53935"
VERT  = "#43a047"
OR    = "#fb8c00"
PALETTE = [BLEU, "#5c6bc0", "#7986cb", "#9fa8da", "#c5cae9"]
PALETTE_MULTI = [BLEU, ROUGE, VERT, OR, "#8e24aa", "#00897b"]

def plotly_style():
    return dict(
        plot_bgcolor="white",
        paper_bgcolor="white",
        font_color="#424242",
        title_font_color="#1a237e",
        xaxis=dict(gridcolor="#eeeeee", linecolor="#bdbdbd", showgrid=True),
        yaxis=dict(gridcolor="#eeeeee", linecolor="#bdbdbd", showgrid=True),
        margin=dict(t=40, b=30, l=10, r=10)
    )

# =====================================================================
# CONNEXION MYSQL OU SQLITE (CLOUD) — avec cache 10 minutes
# =====================================================================
DB = dict(host="127.0.0.1", user="root", password="1234", database="edw_sahel_telecom", port=3306)

@st.cache_data(ttl=600)
def sql(query: str) -> pd.DataFrame:
    # 1. Tentative de connexion à MySQL (Local/Serveur Complet)
    try:
        conn = pymysql.connect(**DB)
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        # 2. Mode Cloud/Hors-ligne (Fallback sur SQLite)
        db_path = "cloud_data/kpis.db"
        if os.path.exists(db_path):
            try:
                conn_sqlite = sqlite3.connect(db_path)
                df = pd.read_sql(query, conn_sqlite)
                conn_sqlite.close()
                return df
            except Exception as e_sqlite:
                st.error(f"Erreur d'exécution SQLite (Mode hors-ligne) : {e_sqlite}")
                return pd.DataFrame()
        else:
            st.error(f"Erreur de connexion MySQL : {e} — La base locale (SQLite) est également introuvable. Lancez `py export_kpis_for_cloud.py` au préalable.")
            return pd.DataFrame()

# =====================================================================
# SIDEBAR
# =====================================================================
with st.sidebar:
    st.markdown(
        "<h2 style='margin:0; font-size:1.3rem; font-weight:700'>Sahel Telecom</h2>"
        "<p style='margin:0; font-size:0.78rem; opacity:0.7'>Tableau de Bord BI & Analytics</p>",
        unsafe_allow_html=True
    )
    st.markdown("---")
    page = st.radio("Navigation", [
        "Vue d'ensemble",
        "Réseau & Antennes",
        "Offres & Abonnements",
        "Prédiction IA – Churn"
    ])
    st.markdown("---")
    st.markdown(
        "<div style='font-size:0.75rem; opacity:0.8; line-height:1.7'>"
        "<b>Projet Master 1 – IFOAD 2026</b><br>"
        "Entrepôt de Données &bull; ETL &bull; BI<br>"
        "Machine Learning &bull; Gouvernance<br><br>"
        "<span style='opacity:0.6'>Données en direct – MySQL</span>"
        "</div>",
        unsafe_allow_html=True
    )

# =====================================================================
# PAGE 1 – VUE D'ENSEMBLE
# =====================================================================
if page == "Vue d'ensemble":
    st.title("Vue d'ensemble — Indicateurs Exécutifs")
    st.markdown(
        "<div class='page-header'>Suivi des métriques stratégiques de Sahel Telecom : revenu moyen par abonné, taux de résiliation et évolution mensuelle, ventilés par pays.</div>",
        unsafe_allow_html=True
    )

    # Requêtes SQL pré-agrégées côté serveur (très rapide)
    df_arpu_mois = sql("""
        SELECT annee, mois, country,
               ROUND(AVG(arpu),0) AS arpu_fcfa,
               ROUND(SUM(revenu_total),0) AS revenu_total,
               SUM(nb_abonnes_actifs) AS nb_abonnes
        FROM kpi_arpu
        GROUP BY annee, mois, country
        ORDER BY annee, mois
    """)

    df_churn_mois = sql("""
        SELECT annee, mois, country,
               SUM(total_abonnes) AS total_abonnes,
               SUM(nb_churnes) AS nb_churnes
        FROM kpi_churn_mensuel
        GROUP BY annee, mois, country
        ORDER BY annee, mois
    """)

    if df_arpu_mois.empty and df_churn_mois.empty:
        st.warning("Impossible de charger les données. Vérifiez que Docker et l'ETL ont bien tournés.")
        st.stop()

    # Calcul de la colonne période pour l'axe des X
    if not df_arpu_mois.empty:
        df_arpu_mois['periode'] = df_arpu_mois['annee'].astype(str) + '-' + df_arpu_mois['mois'].astype(str).str.zfill(2)
    if not df_churn_mois.empty:
        df_churn_mois['periode'] = df_churn_mois['annee'].astype(str) + '-' + df_churn_mois['mois'].astype(str).str.zfill(2)
        df_churn_mois['taux_pct'] = (df_churn_mois['nb_churnes'] / df_churn_mois['total_abonnes'] * 100).round(2)

    # KPIs calculés en Python (ultra rapide, pas de requête supplémentaire)
    arpu_global  = round(df_arpu_mois['arpu_fcfa'].mean()) if not df_arpu_mois.empty else 0
    revenu_total = int(df_arpu_mois['revenu_total'].sum()) if not df_arpu_mois.empty else 0
    moy_abonnes  = int(df_churn_mois.groupby('periode')['total_abonnes'].sum().mean()) if not df_churn_mois.empty else 0
    total_churnes = df_churn_mois['nb_churnes'].sum() if not df_churn_mois.empty else 0
    total_abs     = df_churn_mois['total_abonnes'].sum() if not df_churn_mois.empty else 1
    taux_churn   = round(total_churnes / total_abs * 100, 2) if total_abs > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenu Moyen / Abonné", f"{arpu_global:,} FCFA".replace(',', ' '))
    c2.metric("Revenu Total Cumulé", f"{revenu_total:,} FCFA".replace(',', ' '))
    c3.metric("Abonnés (Moy. mensuelle)", f"{moy_abonnes:,}".replace(',', ' '))
    c4.metric("Taux de Résiliation Global", f"{taux_churn:.2f} %")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Revenu Moyen par Abonné (FCFA) — par mois")
        fig = px.line(df_arpu_mois, x='periode', y='arpu_fcfa', color='country',
                      color_discrete_sequence=PALETTE_MULTI, markers=True)
        fig.update_layout(**plotly_style(), xaxis_title="", yaxis_title="FCFA", legend_title="Pays")
        fig.update_traces(line=dict(width=2.5))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        if not df_churn_mois.empty:
            st.subheader("Taux de Résiliation mensuel (%) — par pays")
            fig2 = px.area(df_churn_mois, x='periode', y='taux_pct', color='country',
                           color_discrete_sequence=PALETTE_MULTI)
            fig2.update_layout(**plotly_style(), xaxis_title="", yaxis_title="Taux (%)", legend_title="Pays")
            st.plotly_chart(fig2, use_container_width=True)

    if not df_arpu_mois.empty:
        st.subheader("Revenu total mensuel par pays (FCFA)")
        fig3 = px.bar(df_arpu_mois, x='periode', y='revenu_total', color='country',
                      color_discrete_sequence=PALETTE_MULTI, barmode='group')
        fig3.update_layout(**plotly_style(), xaxis_title="", yaxis_title="Revenu (FCFA)", legend_title="Pays")
        st.plotly_chart(fig3, use_container_width=True)

# =====================================================================
# PAGE 2 – RÉSEAU & ANTENNES
# =====================================================================
elif page == "Réseau & Antennes":
    st.title("Performance Réseau & Qualité de Service")
    st.markdown(
        "<div class='page-header'>Analyse de la consommation internet par zone géographique, suivi des incidents réseau et taux de saturation des antennes.</div>",
        unsafe_allow_html=True
    )

    df_data = sql("""
        SELECT country, city,
               ROUND(SUM(total_mb)/1024, 1) AS volume_go,
               SUM(nb_sessions_data) AS nb_sessions,
               SUM(abonnes_data) AS abonnes_actifs
        FROM kpi_data_par_region
        GROUP BY country, city
        ORDER BY volume_go DESC
    """)

    df_inc = sql("""
        SELECT country, city,
               SUM(nb_incidents) AS total_incidents,
               SUM(incidents_eleves) AS incidents_graves,
               SUM(incidents_moyens) AS incidents_moderes,
               SUM(total_abonnes_affectes) AS abonnes_touches,
               ROUND(AVG(duree_resolution_moy_min), 0) AS resolution_moy_min,
               ROUND(AVG(taux_resolution_pct), 1) AS taux_resolution
        FROM kpi_incidents_qualite
        GROUP BY country, city
        ORDER BY total_incidents DESC
    """)

    df_antennes = sql("""
        SELECT country, technology,
               ROUND(AVG(taux_utilisation_pct), 1) AS utilisation_pct,
               ROUND(SUM(volume_data_gb), 0) AS volume_go,
               SUM(abonnes_actifs) AS abonnes
        FROM kpi_utilisation_reseau
        GROUP BY country, technology
    """)

    if not df_data.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Volume Internet Total", f"{df_data['volume_go'].sum():,.0f} Go".replace(',', ' '))
        c2.metric("Sessions Internet", f"{df_data['nb_sessions'].sum():,.0f}".replace(',', ' '))
        if not df_inc.empty:
            c3.metric("Abonnés Touchés par Incidents", f"{df_inc['abonnes_touches'].sum():,.0f}".replace(',', ' '))

        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Volume Internet par Ville (Gigaoctets)")
            df_data['Localisation'] = df_data['country'] + ' – ' + df_data['city']
            fig = px.bar(df_data.sort_values('volume_go'), x='volume_go', y='Localisation',
                         orientation='h', color='country', color_discrete_sequence=PALETTE_MULTI,
                         text='volume_go')
            fig.update_traces(texttemplate='%{text:.0f} Go', textposition='outside')
            fig.update_layout(**plotly_style(), xaxis_title="Gigaoctets", yaxis_title="", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            if not df_inc.empty:
                st.subheader("Incidents Réseau par Ville (Abonnés touchés)")
                df_inc['Localisation'] = df_inc['country'] + ' – ' + df_inc['city']
                fig2 = px.bar(df_inc.sort_values('abonnes_touches'), x='abonnes_touches', y='Localisation',
                              orientation='h', color='country', color_discrete_sequence=PALETTE_MULTI,
                              text='abonnes_touches')
                fig2.update_traces(texttemplate='%{text:,}', textposition='outside')
                fig2.update_layout(**plotly_style(), xaxis_title="Abonnés touchés", yaxis_title="", showlegend=False)
                st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")

        if not df_antennes.empty:
            col3, col4 = st.columns(2)
            with col3:
                st.subheader("Taux de Saturation des Antennes par Technologie (%)")
                fig3 = px.bar(df_antennes, x='technology', y='utilisation_pct', color='country',
                              color_discrete_sequence=PALETTE_MULTI, barmode='group', text='utilisation_pct')
                fig3.update_traces(texttemplate='%{text}%', textposition='outside')
                fig3.update_layout(**plotly_style(), xaxis_title="Technologie",
                                   yaxis_title="Taux d'utilisation (%)", legend_title="Pays")
                st.plotly_chart(fig3, use_container_width=True)

            with col4:
                if not df_inc.empty:
                    st.subheader("Gravité des Incidents (Élevée vs Modérée)")
                    df_sev = pd.DataFrame({
                        'Gravité': ['Élevée', 'Modérée'],
                        'Nombre': [int(df_inc['incidents_graves'].sum()), int(df_inc['incidents_moderes'].sum())]
                    })
                    fig4 = px.pie(df_sev, names='Gravité', values='Nombre', hole=0.45,
                                  color_discrete_sequence=[ROUGE, OR])
                    fig4.update_layout(**plotly_style(), showlegend=True)
                    st.plotly_chart(fig4, use_container_width=True)

        if not df_inc.empty:
            st.subheader("Tableau de Bord des Incidents")
            df_inc_disp = df_inc.rename(columns={
                'country': 'Pays', 'city': 'Ville', 'total_incidents': 'Total Incidents',
                'incidents_graves': 'Gravité Élevée', 'incidents_moderes': 'Gravité Modérée',
                'abonnes_touches': 'Abonnés Touchés',
                'resolution_moy_min': 'Résolution Moy. (min)', 'taux_resolution': 'Taux Résolution (%)'
            })
            st.dataframe(df_inc_disp, use_container_width=True, hide_index=True)

# =====================================================================
# PAGE 3 – OFFRES & ABONNEMENTS
# =====================================================================
elif page == "Offres & Abonnements":
    st.title("Analyse des Offres Commerciales & Fidélisation")
    st.markdown(
        "<div class='page-header'>Comparaison des forfaits selon leur taux de rétention, leur contribution au revenu et la qualité de service associée.</div>",
        unsafe_allow_html=True
    )

    df_ret = sql("""
        SELECT plan_name, type_abonnement, country,
               ROUND(monthly_fee, 0) AS prix_fcfa,
               total_abonnes, abonnes_retenus, abonnes_perdus,
               taux_retention_pct, taux_churn_pct,
               ROUND(anciennete_moy_mois, 1) AS anciennete_mois
        FROM kpi_retention_par_offre
        ORDER BY taux_retention_pct DESC
    """)

    df_appels = sql("""
        SELECT network_type,
               SUM(nb_appels) AS nb_appels,
               ROUND(AVG(duree_moy_min), 1) AS duree_moy_min,
               ROUND(SUM(volume_total_heures), 0) AS volume_heures,
               ROUND(AVG(taux_echec_pct), 2) AS taux_echec_pct
        FROM kpi_duree_appels
        GROUP BY network_type
        ORDER BY volume_heures DESC
    """)

    if not df_ret.empty:
        c1, c2, c3, c4 = st.columns(4)
        total_ab = df_ret['total_abonnes'].sum()
        total_ret = df_ret['abonnes_retenus'].sum()
        taux_ret = round(total_ret / total_ab * 100, 1) if total_ab > 0 else 0
        c1.metric("Total Abonnés", f"{total_ab:,}".replace(',', ' '))
        c2.metric("Abonnés Fidèles", f"{total_ret:,}".replace(',', ' '))
        c3.metric("Taux de Fidélisation", f"{taux_ret} %")
        c4.metric("Nombre de Forfaits", str(df_ret['plan_name'].nunique()))

        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Taux de Fidélisation par Forfait (%)")
            fig = px.bar(df_ret.sort_values('taux_retention_pct', ascending=True),
                         x='taux_retention_pct', y='plan_name', orientation='h',
                         color='taux_retention_pct',
                         color_continuous_scale=[[0, '#e53935'], [0.5, OR], [1, '#43a047']],
                         range_color=[50, 100], text='taux_retention_pct')
            fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig.update_layout(**plotly_style(), xaxis_title="Taux de fidélisation (%)",
                              yaxis_title="", coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Abonnés Fidèles vs Résiliés par Forfait")
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(name='Fidèles', x=df_ret['plan_name'],
                                   y=df_ret['abonnes_retenus'], marker_color=VERT,
                                   text=df_ret['abonnes_retenus'], textposition='auto'))
            fig2.add_trace(go.Bar(name='Résiliés', x=df_ret['plan_name'],
                                   y=df_ret['abonnes_perdus'], marker_color=ROUGE,
                                   text=df_ret['abonnes_perdus'], textposition='auto'))
            fig2.update_layout(**plotly_style(), barmode='stack',
                               xaxis_title="Forfait", yaxis_title="Nombre d'abonnés",
                               legend_title="")
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")
        col3, col4 = st.columns(2)

        with col3:
            st.subheader("Ancienneté Moyenne des Abonnés par Forfait (Mois)")
            fig3 = px.bar(df_ret.sort_values('anciennete_mois', ascending=True),
                          x='anciennete_mois', y='plan_name', orientation='h',
                          color='country', color_discrete_sequence=PALETTE_MULTI,
                          text='anciennete_mois')
            fig3.update_traces(texttemplate='%{text:.1f} mois', textposition='outside')
            fig3.update_layout(**plotly_style(), xaxis_title="Ancienneté (mois)",
                               yaxis_title="", legend_title="Pays")
            st.plotly_chart(fig3, use_container_width=True)

        with col4:
            if not df_appels.empty:
                st.subheader("Volume d'Appels (Heures) par Type de Réseau")
                fig4 = px.pie(df_appels, names='network_type', values='volume_heures',
                              color_discrete_sequence=PALETTE_MULTI, hole=0.4)
                fig4.update_layout(**plotly_style(), legend_title="Réseau")
                st.plotly_chart(fig4, use_container_width=True)

        if not df_appels.empty:
            st.subheader("Taux d'Échec des Appels par Type de Réseau (%)")
            fig5 = px.bar(df_appels, x='network_type', y='taux_echec_pct',
                          color='network_type', color_discrete_sequence=PALETTE_MULTI,
                          text='taux_echec_pct')
            fig5.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
            fig5.update_layout(**plotly_style(), xaxis_title="Type de réseau",
                               yaxis_title="Taux d'échec (%)", showlegend=False)
            st.plotly_chart(fig5, use_container_width=True)

        st.markdown("---")
        st.subheader("Tableau Détaillé par Forfait")
        st.dataframe(
            df_ret.rename(columns={
                'plan_name': 'Forfait', 'type_abonnement': 'Type',
                'country': 'Pays', 'prix_fcfa': 'Prix Mensuel (FCFA)',
                'total_abonnes': 'Total Abonnés', 'abonnes_retenus': 'Fidèles',
                'abonnes_perdus': 'Résiliés', 'taux_retention_pct': 'Fidélisation (%)',
                'taux_churn_pct': 'Résiliation (%)', 'anciennete_mois': 'Ancienneté (Mois)'
            }),
            use_container_width=True, hide_index=True
        )

# =====================================================================
# PAGE 4 – PRÉDICTION IA – CHURN
# =====================================================================
elif page == "Prédiction IA – Churn":
    st.title("Intelligence Artificielle – Prédiction du Churn")
    st.markdown(
        "<div class='page-header'>"
        "Modèle <b>XGBoost</b> entraîné sur l'historique des 6 derniers mois. "
        "L'algorithme <b>SHAP</b> permet d'expliquer mathématiquement chaque prédiction : "
        "pourquoi un abonné est considéré à risque de résiliation."
        "</div>", unsafe_allow_html=True
    )

    OUT = "churn_model_outputs"

    if os.path.exists(OUT):
        # Métriques du modèle
        try:
            res = pd.read_csv(f"{OUT}/resultats_modeles_xgboost.csv")
            acc  = res["Accuracy"].iloc[0] * 100
            auc  = res["AUC"].iloc[0] * 100
            prec = res["Précision"].iloc[0] * 100
            rap  = res["Rappel"].iloc[0] * 100
            f1   = res["F1-Score"].iloc[0] * 100

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Précision Globale", f"{acc:.1f} %")
            c2.metric("AUC-ROC", f"{auc:.1f} %")
            c3.metric("Précision (Churn)", f"{prec:.1f} %")
            c4.metric("Rappel (Churn)", f"{rap:.1f} %")
            c5.metric("Score F1", f"{f1:.1f} %")
        except Exception:
            st.info("Métriques non disponibles — lancez d'abord `py churn_prediction.py`.")

        st.markdown("---")
        col_a, col_b = st.columns([1, 2])

        with col_a:
            st.subheader("Matrice de Confusion")
            st.markdown("Vrais positifs et faux positifs du modèle sur les données de test.")
            try:
                st.image(f"{OUT}/matrice_confusion_xgboost.png", use_container_width=True)
            except Exception:
                st.info("Image non disponible.")

        with col_b:
            st.subheader("Facteurs de Résiliation – Analyse SHAP")
            st.markdown(
                "Chaque point représente un abonné. Les variables en haut ont le plus d'impact. "
                "**Rouge** = valeur élevée de la variable. **Bleu** = valeur faible. "
                "À droite du centre = augmente le risque de résiliation."
            )
            try:
                st.image(f"{OUT}/shap_summary.png", use_container_width=True)
            except Exception:
                st.info("Graphique SHAP non disponible.")

        st.markdown("---")
        col_c, col_d = st.columns(2)

        with col_c:
            st.subheader("Importance des Variables")
            try:
                df_imp = pd.read_csv(f"{OUT}/importance_variables.csv")
                if not df_imp.empty:
                    # Adapter selon les colonnes réelles du CSV
                    cols = df_imp.columns.tolist()
                    var_col = cols[0]
                    imp_col = cols[1] if len(cols) > 1 else cols[0]
                    df_imp = df_imp.rename(columns={var_col: 'Variable', imp_col: 'Importance'})
                    df_imp['Variable'] = df_imp['Variable'].replace({
                        'monthly_fee':        'Prix du Forfait (FCFA)',
                        'data_quota_gb':       'Quota Internet (Go)',
                        'days_since_active':   "Jours d'Inactivité",
                        'network_incidents':   'Pannes Réseau Subies',
                        'failed_calls':        'Appels en Échec',
                        'data_usage_ratio':    'Taux de Consommation Internet',
                        'call_failure_rate':   "Taux d'Échec des Appels",
                        'revenue_fcfa':        'Revenu Généré (FCFA)',
                        'voice_used_sec':      'Durée des Appels (sec)',
                        'data_used_mb':        'Internet Consommé (Mo)',
                        'sms_used':            'SMS Envoyés',
                        'age':                 'Âge du Client',
                        'gender':              'Genre',
                        'segment':             'Segment Client',
                        'country':             'Pays',
                        'nb_evenements_total': 'Nombre total d\'événements',
                        'nb_sessions':         'Nombre de Sessions',
                        'type':                'Type de Forfait',
                        'montant_total_depense':'Montant Total Dépensé',
                        'duree_appels_totale': 'Durée Totale des Appels',
                        'data_totale_mb':      'Volume Internet Total (Mo)',
                        'monthly_revenue':     'Revenu Mensuel (FCFA)'
                    })
                    df_imp = df_imp.sort_values('Importance', ascending=True).tail(15)
                    fig_imp = px.bar(df_imp, x='Importance', y='Variable', orientation='h',
                                     color='Importance', color_continuous_scale=PALETTE,
                                     text='Importance')
                    fig_imp.update_traces(texttemplate='%{text:.3f}', textposition='outside')
                    fig_imp.update_layout(**plotly_style(), coloraxis_showscale=False,
                                          xaxis_title="Score d'importance", yaxis_title="")
                    st.plotly_chart(fig_imp, use_container_width=True)
            except Exception:
                st.image(f"{OUT}/importance_variables.png", use_container_width=True)

        with col_d:
            st.subheader("Courbe ROC")
            try:
                st.image(f"{OUT}/courbes_roc.png", use_container_width=True)
            except Exception:
                st.info("Courbe ROC non disponible.")

        st.markdown("---")
        st.subheader("Liste des Abonnés Prioritaires – Campagne de Rétention")
        st.markdown(
            "Abonnés **actifs** les plus susceptibles de résilier dans les 30 prochains jours. "
            "À transmettre en priorité au service commercial pour action."
        )
        try:
            df_top = pd.read_csv(f"{OUT}/top_500_abonnes_a_risque.csv")

            # Arrondir la probabilité
            if 'risque_churn_pct' in df_top.columns:
                df_top['risque_churn_pct'] = df_top['risque_churn_pct'].apply(lambda x: f"{x:.1f} %")

            # Renommage exhaustif de toutes les colonnes techniques
            df_top = df_top.rename(columns={
                'subscriber_id':      'Identifiant Client',
                'snapshot_month':     'Mois Analysé',
                'plan_name':          'Forfait Souscrit',
                'gender':             'Genre',
                'age':                'Âge',
                'segment':            'Segment Client',
                'country':            'Pays',
                'monthly_fee':        'Prix Mensuel (FCFA)',
                'data_quota_gb':      'Quota Internet (Go)',
                'data_used_mb':       'Consommation Internet (Mo)',
                'voice_used_sec':     'Durée Appels (sec)',
                'sms_used':           'SMS Envoyés',
                'revenue_fcfa':       'Revenu Généré (FCFA)',
                'network_incidents':  'Pannes Réseau Subies',
                'failed_calls':       'Appels en Échec',
                'days_since_active':  "Jours sans Activité",
                'churn_status':       'Statut Résiliation',
                'data_usage_ratio':   'Taux Consommation Internet',
                'call_failure_rate':  "Taux Échec Appels",
                'risque_churn_pct':   'Probabilité de Résiliation'
            })

            # Colonnes prioritaires en tête
            prio = ['Identifiant Client', 'Probabilité de Résiliation', 'Forfait Souscrit',
                    'Pays', 'Âge', 'Segment Client', 'Jours sans Activité',
                    'Pannes Réseau Subies', 'Appels en Échec', 'Prix Mensuel (FCFA)']
            prio = [c for c in prio if c in df_top.columns]
            reste = [c for c in df_top.columns if c not in prio]
            st.dataframe(df_top[prio + reste], use_container_width=True, hide_index=True)
        except Exception as e:
            st.warning(f"Fichier de clients à risque introuvable ({e}).")
    else:
        st.error("Dossier 'churn_model_outputs' introuvable. Lancez d'abord `py churn_prediction.py`.")
