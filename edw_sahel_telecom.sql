DROP DATABASE IF EXISTS edw_sahel_telecom;
CREATE DATABASE edw_sahel_telecom
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE edw_sahel_telecom;
CREATE TABLE stg_subscribers (
    subscriber_id      VARCHAR(20),
    first_name         VARCHAR(100),
    last_name          VARCHAR(100),
    gender             VARCHAR(10),
    age                VARCHAR(10),          -- VARCHAR car peut contenir NULL ou valeur aberrante

    city               VARCHAR(100),
    country            VARCHAR(100),
    plan_id            VARCHAR(20),
    tower_id           VARCHAR(20),
    subscription_date  VARCHAR(20),
    phone_number       VARCHAR(30),
    email              VARCHAR(200),
    churn              VARCHAR(5),
    churn_date         VARCHAR(20),
    monthly_revenue    VARCHAR(20),
    segment            VARCHAR(50),
    _loaded_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    _source_file       VARCHAR(200) DEFAULT 'subscribers.csv'
) ENGINE=InnoDB COMMENT='Staging : données brutes abonnés';

CREATE TABLE stg_usage (
    usage_id           VARCHAR(20),
    subscriber_id      VARCHAR(20),
    tower_id           VARCHAR(20),
    event_type         VARCHAR(50),
    event_datetime     VARCHAR(30),
    duration_sec       VARCHAR(20),
    data_mb            VARCHAR(20),
    amount_fcfa        VARCHAR(20),
    status             VARCHAR(30),
    network_type       VARCHAR(10),
    roaming            VARCHAR(5),
    _loaded_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    _source_file       VARCHAR(200) DEFAULT 'usage.csv'
) ENGINE=InnoDB COMMENT='Staging : données brutes événements usage';

CREATE TABLE stg_towers (
    tower_id           VARCHAR(20),
    tower_name         VARCHAR(100),
    city               VARCHAR(100),
    region             VARCHAR(100),
    country            VARCHAR(100),
    latitude           VARCHAR(20),
    longitude          VARCHAR(20),
    capacity_users     VARCHAR(10),
    technology         VARCHAR(10),
    installation_date  VARCHAR(20),
    status             VARCHAR(30),
    etat_batterie      VARCHAR(20),
    _loaded_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    _source_file       VARCHAR(200) DEFAULT 'towers.csv'
) ENGINE=InnoDB COMMENT='Staging : données brutes antennes';

CREATE TABLE stg_plans (
    plan_id            VARCHAR(20),
    plan_name          VARCHAR(100),
    country            VARCHAR(100),
    monthly_fee        VARCHAR(20),
    data_quota_gb      VARCHAR(10),
    call_minutes       VARCHAR(10),
    sms_quota          VARCHAR(10),
    type               VARCHAR(30),
    _loaded_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    _source_file       VARCHAR(200) DEFAULT 'plans.csv'
) ENGINE=InnoDB COMMENT='Staging : données brutes plans tarifaires';

CREATE TABLE stg_incidents (
    incident_id           VARCHAR(20),
    tower_id              VARCHAR(20),
    incident_type         VARCHAR(50),
    severity              VARCHAR(20),
    incident_datetime     VARCHAR(30),
    resolution_minutes    VARCHAR(10),
    resolved              VARCHAR(10),
    resolution_date       VARCHAR(30),
    description           VARCHAR(500),
    nb_abonnes_affectes   VARCHAR(10),
    _loaded_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    _source_file          VARCHAR(200) DEFAULT 'incidents_qualite_legers.csv'
) ENGINE=InnoDB COMMENT='Staging : données brutes incidents qualité';

-- ============================================================
--  TABLE DE CONTRÔLE ETL
--  Journalise chaque exécution du pipeline
-- ============================================================

CREATE TABLE etl_log (
    log_id           INT AUTO_INCREMENT PRIMARY KEY,
    table_name       VARCHAR(100)  NOT NULL,
    operation        VARCHAR(50)   NOT NULL COMMENT 'EXTRACT | TRANSFORM | LOAD',
    status           VARCHAR(20)   NOT NULL COMMENT 'RUNNING | SUCCESS | FAILED',
    rows_extracted   INT           DEFAULT 0,
    rows_inserted    INT           DEFAULT 0,
    rows_rejected    INT           DEFAULT 0,
    rows_updated     INT           DEFAULT 0,
    start_time       TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    end_time         TIMESTAMP     NULL,
    error_message    TEXT          NULL,
    duration_seconds DECIMAL(10,2) GENERATED ALWAYS AS
                     (TIMESTAMPDIFF(SECOND, start_time, end_time)) STORED
) ENGINE=InnoDB COMMENT='Journal des exécutions ETL';

CREATE TABLE etl_rejected_rows (
    reject_id        INT AUTO_INCREMENT PRIMARY KEY,
    source_table     VARCHAR(100),
    raw_data         TEXT,
    rejection_reason VARCHAR(500),
    rejected_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='Lignes rejetées lors des transformations ETL';

-- ============================================================
--  COUCHE DIMENSIONS
-- ============================================================

-- ─────────────────────────────────────────────────────────────
-- DIM_DATE : dimension temporelle
-- ─────────────────────────────────────────────────────────────
CREATE TABLE dim_date (
    date_sk           INT          NOT NULL PRIMARY KEY COMMENT 'Clé YYYYMMDD ex: 20240315',
    date_complete     DATE         NOT NULL,
    jour              TINYINT      NOT NULL COMMENT 'Jour du mois 1-31',
    jour_semaine      TINYINT      NOT NULL COMMENT '1=Lundi ... 7=Dimanche',
    nom_jour          VARCHAR(20)  NOT NULL COMMENT 'Lundi, Mardi...',
    semaine_annee     TINYINT      NOT NULL COMMENT 'Semaine ISO 1-53',
    mois              TINYINT      NOT NULL COMMENT '1-12',
    nom_mois          VARCHAR(20)  NOT NULL,
    trimestre         TINYINT      NOT NULL COMMENT '1-4',
    semestre          TINYINT      NOT NULL COMMENT '1-2',
    annee             SMALLINT     NOT NULL,
    is_weekend        TINYINT(1)   NOT NULL DEFAULT 0,
    is_jour_ouvre     TINYINT(1)   NOT NULL DEFAULT 1,
    is_ferie          TINYINT(1)   NOT NULL DEFAULT 0,
    saison            VARCHAR(20)  NOT NULL COMMENT 'Hivernage | Saison sèche',
    periode_fiscale   VARCHAR(20)  NOT NULL COMMENT 'Ex: FY2024-Q1',
    mois_annee        VARCHAR(10)  NOT NULL COMMENT 'Ex: 2024-03',
    annee_trimestre   VARCHAR(10)  NOT NULL COMMENT 'Ex: 2024-Q1',
    heure             TINYINT      NULL     COMMENT 'Optionnel pour granularité heure',
    tranche_horaire   VARCHAR(30)  NULL     COMMENT 'Nuit | Matin | Après-midi | Soir'
) ENGINE=InnoDB COMMENT='Dimension temporelle - pré-remplie 2020-2030';

CREATE INDEX idx_dim_date_annee       ON dim_date(annee);
CREATE INDEX idx_dim_date_mois        ON dim_date(mois, annee);
CREATE INDEX idx_dim_date_trimestre   ON dim_date(trimestre, annee);
CREATE INDEX idx_dim_date_complete    ON dim_date(date_complete);

-- ─────────────────────────────────────────────────────────────
-- DIM_PLAN : offres tarifaires
-- ─────────────────────────────────────────────────────────────
CREATE TABLE dim_plan (
    plan_sk           INT          NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT 'Surrogate key',
    plan_id           VARCHAR(20)  NOT NULL                            COMMENT 'Natural key (P001...P010)',
    plan_name         VARCHAR(100) NOT NULL,
    type_abonnement   VARCHAR(30)  NOT NULL COMMENT 'Prépayé | Postpayé | Entreprise',
    country           VARCHAR(100) NOT NULL,
    monthly_fee       DECIMAL(10,2) NOT NULL,
    data_quota_gb     DECIMAL(8,2) NOT NULL,
    call_minutes      INT          NOT NULL,
    sms_quota         INT          NOT NULL,
    categorie_prix    VARCHAR(20)  NOT NULL COMMENT 'Économique | Standard | Premium',
    -- Champs SCD Type 2
    date_debut        DATE         NOT NULL DEFAULT (CURRENT_DATE),
    date_fin          DATE         NULL,
    is_current        TINYINT(1)   NOT NULL DEFAULT 1,
    version           INT          NOT NULL DEFAULT 1
) ENGINE=InnoDB COMMENT='Dimension plans tarifaires (SCD Type 2)';

CREATE UNIQUE INDEX idx_dim_plan_nk ON dim_plan(plan_id, version);
CREATE INDEX idx_dim_plan_country    ON dim_plan(country);
CREATE INDEX idx_dim_plan_current    ON dim_plan(is_current);

-- ─────────────────────────────────────────────────────────────
-- DIM_TOWER : antennes réseau
-- ─────────────────────────────────────────────────────────────
CREATE TABLE dim_tower (
    tower_sk          INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tower_id          VARCHAR(20)  NOT NULL COMMENT 'Natural key (T001...T027)',
    tower_name        VARCHAR(100) NOT NULL,
    city              VARCHAR(100) NOT NULL,
    region            VARCHAR(100) NOT NULL,
    country           VARCHAR(100) NOT NULL,
    latitude          DECIMAL(9,6) NULL,
    longitude         DECIMAL(9,6) NULL,
    capacity_users    INT          NOT NULL DEFAULT 0,
    technology        VARCHAR(10)  NOT NULL COMMENT '2G | 3G | 4G',
    installation_date DATE         NULL,
    status            VARCHAR(20)  NOT NULL COMMENT 'Actif | Maintenance | Inactif',
    etat_batterie     VARCHAR(20)  NULL     COMMENT 'Bon | Moyen | Faible',
    zone_type         VARCHAR(30)  NOT NULL COMMENT 'Urbain | Péri-urbain | Rural',
    -- SCD Type 1 (on écrase les mises à jour de statut)
    last_updated      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='Dimension antennes réseau (SCD Type 1)';

CREATE UNIQUE INDEX idx_dim_tower_nk ON dim_tower(tower_id);
CREATE INDEX idx_dim_tower_city      ON dim_tower(city);
CREATE INDEX idx_dim_tower_country   ON dim_tower(country);
CREATE INDEX idx_dim_tower_tech      ON dim_tower(technology);

-- ─────────────────────────────────────────────────────────────
-- DIM_SUBSCRIBER : abonnés (SCD Type 2 pour le churn et segment)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE dim_subscriber (
    subscriber_sk     INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    subscriber_id     VARCHAR(20)  NOT NULL COMMENT 'Natural key (SUB000001...)',
    first_name        VARCHAR(100) NOT NULL,
    last_name         VARCHAR(100) NOT NULL,
    nom_complet       VARCHAR(200) GENERATED ALWAYS AS
                      (CONCAT(first_name, ' ', last_name)) STORED,
    gender            VARCHAR(10)  NULL     COMMENT 'M | F | Inconnu',
    age               TINYINT      NULL,
    tranche_age       VARCHAR(20)  NULL     COMMENT '16-24 | 25-34 | 35-49 | 50+',
    city              VARCHAR(100) NOT NULL,
    country           VARCHAR(100) NOT NULL,
    plan_id           VARCHAR(20)  NOT NULL,
    tower_id          VARCHAR(20)  NULL,
    phone_number      VARCHAR(30)  NULL,
    email             VARCHAR(200) NULL,
    segment           VARCHAR(30)  NOT NULL COMMENT 'Particulier | Professionnel | Entreprise',
    churn             TINYINT(1)   NOT NULL DEFAULT 0,
    churn_date        DATE         NULL,
    subscription_date DATE         NOT NULL,
    monthly_revenue   DECIMAL(10,2) NULL,
    anciennete_mois   INT NULL,   -- colonne classique, mise à jour par ETL
    -- SCD Type 2
    date_debut        DATE         NOT NULL DEFAULT (CURRENT_DATE),
    date_fin          DATE         NULL,
    is_current        TINYINT(1)   NOT NULL DEFAULT 1,
    version           INT          NOT NULL DEFAULT 1
) ENGINE=InnoDB COMMENT='Dimension abonnés (SCD Type 2)';



CREATE INDEX idx_dim_sub_nk       ON dim_subscriber(subscriber_id);
CREATE INDEX idx_dim_sub_city     ON dim_subscriber(city);
CREATE INDEX idx_dim_sub_country  ON dim_subscriber(country);
CREATE INDEX idx_dim_sub_churn    ON dim_subscriber(churn);
CREATE INDEX idx_dim_sub_current  ON dim_subscriber(is_current);
CREATE INDEX idx_dim_sub_plan     ON dim_subscriber(plan_id);

-- ─────────────────────────────────────────────────────────────
-- DIM_LOCALISATION : géographie (dimension conformée)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE dim_localisation (
    location_sk       INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    city              VARCHAR(100) NOT NULL,
    region            VARCHAR(100) NOT NULL,
    country           VARCHAR(100) NOT NULL,
    continent         VARCHAR(50)  NOT NULL DEFAULT 'Afrique de l''Ouest',
    latitude          DECIMAL(9,6) NULL,
    longitude         DECIMAL(9,6) NULL,
    zone_type         VARCHAR(30)  NOT NULL COMMENT 'Urbain | Péri-urbain | Rural',
    population_zone   VARCHAR(30)  NULL     COMMENT 'Petite | Moyenne | Grande ville',
    fuseau_horaire    VARCHAR(50)  NOT NULL DEFAULT 'Africa/Ouagadougou'
) ENGINE=InnoDB COMMENT='Dimension géographique conformée';

CREATE UNIQUE INDEX idx_dim_loc_city ON dim_localisation(city, country);
CREATE INDEX idx_dim_loc_country     ON dim_localisation(country);

-- ============================================================
--  COUCHE FAITS
-- ============================================================

-- ─────────────────────────────────────────────────────────────
-- FACT_USAGE : table de faits principale (transactionnelle)
-- 550 000+ lignes - une ligne = un événement réseau
-- ─────────────────────────────────────────────────────────────
CREATE TABLE fact_usage (
    usage_sk          BIGINT       NOT NULL AUTO_INCREMENT,
    date_sk           INT          NOT NULL,
    subscriber_sk     INT          NOT NULL,
    tower_sk          INT          NOT NULL,
    plan_sk           INT          NOT NULL,
    location_sk       INT          NOT NULL,
    usage_id          VARCHAR(20)  NOT NULL COMMENT 'ID source - dimension dégénérée',
    duration_sec      INT          NOT NULL DEFAULT 0 COMMENT 'Durée en secondes (0 si SMS/Data)',
    duration_min      DECIMAL(8,2) GENERATED ALWAYS AS (duration_sec / 60.0) STORED,
    data_mb           DECIMAL(12,4) NOT NULL DEFAULT 0,
    data_gb           DECIMAL(12,6) GENERATED ALWAYS AS (data_mb / 1024.0) STORED,
    amount_fcfa       DECIMAL(12,2) NULL,
    event_type        VARCHAR(30)  NOT NULL COMMENT 'Appel_Sortant | Appel_Entrant | SMS | Data',
    status            VARCHAR(20)  NOT NULL COMMENT 'Succès | Échec | Interrompu',
    network_type      VARCHAR(10)  NOT NULL COMMENT '2G | 3G | 4G',
    roaming           TINYINT(1)   NOT NULL DEFAULT 0,
    _loaded_at        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (usage_sk, date_sk)   -- clé composite obligatoire avec partitionnement
)
ENGINE=InnoDB
COMMENT='Faits usage réseau - granularité : 1 ligne = 1 événement'
PARTITION BY RANGE (date_sk) (
    PARTITION p2023 VALUES LESS THAN (20240101),
    PARTITION p2024 VALUES LESS THAN (20250101),
    PARTITION p2025 VALUES LESS THAN (20260101),
    PARTITION p2026 VALUES LESS THAN (20270101),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);


CREATE INDEX idx_fu_subscriber   ON fact_usage(subscriber_sk);
CREATE INDEX idx_fu_date         ON fact_usage(date_sk);
CREATE INDEX idx_fu_tower        ON fact_usage(tower_sk);
CREATE INDEX idx_fu_plan         ON fact_usage(plan_sk);
CREATE INDEX idx_fu_event_type   ON fact_usage(event_type);
CREATE INDEX idx_fu_status       ON fact_usage(status);

-- ─────────────────────────────────────────────────────────────
-- FACT_INCIDENT : table de faits incidents réseau
-- ─────────────────────────────────────────────────────────────
CREATE TABLE fact_incident (
    incident_sk           BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
    -- Clés étrangères
    tower_sk              INT          NOT NULL,
    date_sk               INT          NOT NULL,
    location_sk           INT          NOT NULL,
    -- Dimension dégénérée
    incident_id           VARCHAR(20)  NOT NULL,
    -- Attributs catégoriels
    incident_type         VARCHAR(50)  NOT NULL,
    severity              VARCHAR(20)  NOT NULL COMMENT 'Faible | Moyen | Élevé',
    resolved              TINYINT(1)   NOT NULL DEFAULT 0,
    description           VARCHAR(500) NULL,
    -- Mesures
    resolution_minutes    INT          NULL,
    nb_abonnes_affectes   INT          NOT NULL DEFAULT 0,
    -- Méta-données
    _loaded_at            TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_fi_tower    FOREIGN KEY (tower_sk)
        REFERENCES dim_tower(tower_sk),
    CONSTRAINT fk_fi_date     FOREIGN KEY (date_sk)
        REFERENCES dim_date(date_sk),
    CONSTRAINT fk_fi_location FOREIGN KEY (location_sk)
        REFERENCES dim_localisation(location_sk)
) ENGINE=InnoDB COMMENT='Faits incidents qualité réseau';

CREATE INDEX idx_fi_tower        ON fact_incident(tower_sk);
CREATE INDEX idx_fi_date         ON fact_incident(date_sk);
CREATE INDEX idx_fi_severity     ON fact_incident(severity);
CREATE INDEX idx_fi_type         ON fact_incident(incident_type);

-- ============================================================
--  COUCHE SÉMANTIQUE - VUES ANALYTIQUES (pour Excel / BI)
-- ============================================================

-- Vue 1 : KPI 1 - Taux de churn mensuel
CREATE OR REPLACE VIEW v_kpi_churn_mensuel AS
SELECT
    d.annee,
    d.mois,
    d.nom_mois,
    d.annee_trimestre,
    s.country,
    s.city,
    s.segment,
    p.plan_name,
    p.type_abonnement,
    COUNT(DISTINCT s.subscriber_sk)                            AS total_abonnes,
    SUM(s.churn)                                               AS nb_churnes,
    ROUND(SUM(s.churn) * 100.0 / COUNT(DISTINCT s.subscriber_sk), 2) AS taux_churn_pct
FROM dim_subscriber s
JOIN dim_plan       p ON s.plan_id = p.plan_id AND p.is_current = 1
JOIN dim_date       d ON d.date_complete = IFNULL(s.churn_date, CURDATE())
WHERE s.is_current = 1
GROUP BY d.annee, d.mois, d.nom_mois, d.annee_trimestre,
         s.country, s.city, s.segment, p.plan_name, p.type_abonnement;

-- Vue 2 : KPI 2 - ARPU (revenu moyen par abonné)
CREATE OR REPLACE VIEW v_kpi_arpu AS
SELECT
    d.annee,
    d.mois,
    d.nom_mois,
    d.annee_trimestre,
    s.country,
    s.city,
    p.plan_name,
    p.type_abonnement,
    COUNT(DISTINCT fu.subscriber_sk)              AS nb_abonnes_actifs,
    ROUND(SUM(fu.amount_fcfa), 2)                 AS revenu_total,
    ROUND(AVG(fu.amount_fcfa), 2)                 AS revenu_moyen_par_evenement,
    ROUND(SUM(fu.amount_fcfa) /
          NULLIF(COUNT(DISTINCT fu.subscriber_sk), 0), 2) AS arpu
FROM fact_usage    fu
JOIN dim_subscriber s ON fu.subscriber_sk = s.subscriber_sk
JOIN dim_date       d ON fu.date_sk       = d.date_sk
JOIN dim_plan       p ON fu.plan_sk       = p.plan_sk
WHERE fu.amount_fcfa IS NOT NULL
GROUP BY d.annee, d.mois, d.nom_mois, d.annee_trimestre,
         s.country, s.city, p.plan_name, p.type_abonnement;

-- Vue 3 : KPI 3 - Taux d'utilisation réseau par antenne
CREATE OR REPLACE VIEW v_kpi_utilisation_reseau AS
SELECT
    d.annee,
    d.mois,
    d.nom_mois,
    t.tower_id,
    t.tower_name,
    t.city,
    t.country,
    t.technology,
    t.capacity_users,
    COUNT(DISTINCT fu.subscriber_sk)                          AS abonnes_actifs,
    COUNT(fu.usage_sk)                                        AS nb_evenements,
    ROUND(COUNT(DISTINCT fu.subscriber_sk) * 100.0 /
          NULLIF(t.capacity_users, 0), 2)                     AS taux_utilisation_pct,
    ROUND(SUM(fu.data_mb) / 1024.0, 2)                       AS volume_data_gb,
    ROUND(SUM(fu.duration_sec) / 3600.0, 2)                  AS volume_appels_heures
FROM fact_usage fu
JOIN dim_tower  t ON fu.tower_sk = t.tower_sk
JOIN dim_date   d ON fu.date_sk  = d.date_sk
GROUP BY d.annee, d.mois, d.nom_mois,
         t.tower_id, t.tower_name, t.city, t.country,
         t.technology, t.capacity_users;

-- Vue 4 : KPI 4 - Taux d'incidents qualité par antenne
CREATE OR REPLACE VIEW v_kpi_incidents_qualite AS
SELECT
    d.annee,
    d.mois,
    d.nom_mois,
    t.tower_id,
    t.tower_name,
    t.city,
    t.country,
    t.technology,
    COUNT(fi.incident_sk)                                     AS nb_incidents,
    SUM(CASE WHEN fi.severity = 'Élevé' THEN 1 ELSE 0 END)  AS incidents_eleves,
    SUM(CASE WHEN fi.severity = 'Moyen' THEN 1 ELSE 0 END)  AS incidents_moyens,
    SUM(fi.nb_abonnes_affectes)                              AS total_abonnes_affectes,
    ROUND(AVG(fi.resolution_minutes), 1)                     AS duree_resolution_moy_min,
    ROUND(SUM(fi.resolved) * 100.0 / NULLIF(COUNT(*), 0), 2) AS taux_resolution_pct
FROM fact_incident fi
JOIN dim_tower    t ON fi.tower_sk = t.tower_sk
JOIN dim_date     d ON fi.date_sk  = d.date_sk
GROUP BY d.annee, d.mois, d.nom_mois,
         t.tower_id, t.tower_name, t.city, t.country, t.technology;

-- Vue 5 : KPI 5 - Durée moyenne des appels
CREATE OR REPLACE VIEW v_kpi_duree_appels AS
SELECT
    d.annee,
    d.mois,
    d.nom_mois,
    d.annee_trimestre,
    d.tranche_horaire,
    s.country,
    s.city,
    s.segment,
    fu.network_type,
    COUNT(fu.usage_sk)                              AS nb_appels,
    ROUND(AVG(fu.duration_sec), 1)                  AS duree_moy_sec,
    ROUND(AVG(fu.duration_sec) / 60.0, 2)           AS duree_moy_min,
    ROUND(SUM(fu.duration_sec) / 3600.0, 2)         AS volume_total_heures,
    SUM(CASE WHEN fu.status = 'Échec' THEN 1 ELSE 0 END) AS nb_appels_echoues,
    ROUND(SUM(CASE WHEN fu.status = 'Échec' THEN 1 ELSE 0 END)
          * 100.0 / NULLIF(COUNT(*), 0), 2)         AS taux_echec_pct
FROM fact_usage    fu
JOIN dim_subscriber s ON fu.subscriber_sk = s.subscriber_sk
JOIN dim_date       d ON fu.date_sk       = d.date_sk
WHERE fu.event_type IN ('Appel_Sortant', 'Appel_Entrant')
GROUP BY d.annee, d.mois, d.nom_mois, d.annee_trimestre,
         d.tranche_horaire, s.country, s.city,
         s.segment, fu.network_type;

-- Vue 6 : KPI 6 - Taux de rétention par offre
CREATE OR REPLACE VIEW v_kpi_retention_par_offre AS
SELECT
    p.plan_name,
    p.type_abonnement,
    p.country,
    p.monthly_fee,
    COUNT(DISTINCT s.subscriber_sk)                         AS total_abonnes,
    SUM(CASE WHEN s.churn = 0 THEN 1 ELSE 0 END)          AS abonnes_retenus,
    SUM(s.churn)                                            AS abonnes_perdus,
    ROUND(SUM(CASE WHEN s.churn = 0 THEN 1 ELSE 0 END)
          * 100.0 / NULLIF(COUNT(*), 0), 2)                AS taux_retention_pct,
    ROUND(SUM(s.churn) * 100.0 / NULLIF(COUNT(*), 0), 2)  AS taux_churn_pct,
    ROUND(AVG(s.anciennete_mois), 1)                       AS anciennete_moy_mois
FROM dim_subscriber s
JOIN dim_plan       p ON s.plan_id = p.plan_id AND p.is_current = 1
WHERE s.is_current = 1
GROUP BY p.plan_name, p.type_abonnement, p.country, p.monthly_fee;

-- Vue 7 : KPI 7 - Volume de données consommées par région
CREATE OR REPLACE VIEW v_kpi_data_par_region AS
SELECT
    d.annee,
    d.mois,
    d.nom_mois,
    d.annee_trimestre,
    l.country,
    l.city,
    l.region,
    t.technology,
    COUNT(DISTINCT fu.subscriber_sk)          AS abonnes_data,
    COUNT(fu.usage_sk)                        AS nb_sessions_data,
    ROUND(SUM(fu.data_mb), 2)                AS total_mb,
    ROUND(SUM(fu.data_gb), 4)                AS total_gb,
    ROUND(AVG(fu.data_mb), 2)                AS data_moy_par_session_mb,
    ROUND(SUM(fu.amount_fcfa), 2)            AS revenu_data_total
FROM fact_usage      fu
JOIN dim_localisation l  ON fu.location_sk   = l.location_sk
JOIN dim_tower        t  ON fu.tower_sk       = t.tower_sk
JOIN dim_date         d  ON fu.date_sk        = d.date_sk
WHERE fu.event_type = 'Data'
GROUP BY d.annee, d.mois, d.nom_mois, d.annee_trimestre,
         l.country, l.city, l.region, t.technology;

-- ============================================================
--  TABLE SNAPSHOT MENSUEL POUR LE MACHINE LEARNING
-- ============================================================

CREATE TABLE fact_subscriber_monthly (
    snapshot_id          INT AUTO_INCREMENT PRIMARY KEY,
    subscriber_sk        INT NOT NULL,
    snapshot_month       VARCHAR(7) NOT NULL COMMENT 'Format YYYY-MM',
    plan_sk              INT,
    data_used_mb         DECIMAL(12,2) DEFAULT 0,
    voice_used_sec       INT DEFAULT 0,
    sms_used             INT DEFAULT 0,
    revenue_fcfa         DECIMAL(12,2) DEFAULT 0,
    network_incidents    INT DEFAULT 0,
    failed_calls         INT DEFAULT 0,
    days_since_active    INT DEFAULT 0,
    churn_status         TINYINT DEFAULT 0,
    UNIQUE KEY (subscriber_sk, snapshot_month)
) ENGINE=InnoDB COMMENT='Snapshot mensuel des abonnés pour ML';

-- ============================================================
--  VÉRIFICATION FINALE
-- ============================================================
SELECT 'TABLES CRÉÉES' AS message,
       table_name,
       table_comment
FROM information_schema.tables
WHERE table_schema = 'edw_sahel_telecom'
ORDER BY table_type, table_name;


-- Trouver les dates dans vos données source qui manquent dans dim_date
SELECT DISTINCT 
    STR_TO_DATE(incident_datetime, '%Y-%m-%d %H:%i:%s') as incident_date
FROM stg_incidents
WHERE STR_TO_DATE(incident_datetime, '%Y-%m-%d %H:%i:%s') NOT IN (
    SELECT date_complete FROM dim_date
);

-- Vérifier aussi les autres dates sources
SELECT DISTINCT 
    STR_TO_DATE(subscription_date, '%Y-%m-%d') as subscription_date
FROM stg_subscribers
WHERE STR_TO_DATE(subscription_date, '%Y-%m-%d') NOT IN (
    SELECT date_complete FROM dim_date
);
ALTER TABLE fact_usage MODIFY plan_sk INT NULL;