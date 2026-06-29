-- ============================================================
--  EDW SAHEL TELECOM / GOLDTEL
--  TRIGGERS ET PROCÉDURES STOCKÉES - GOUVERNANCE DES DONNÉES
--  Master 1 - IFOAD - Groupe 3 - Juin 2026
--
--  À exécuter APRÈS edw_sahel_telecom.sql ET populate_dim_date.sql
--
--  Contenu :
--    A. Table d'audit générique
--    B. Triggers de QUALITÉ (rejet/validation à l'insertion)
--    C. Triggers d'INTÉGRITÉ SCD (garde-fous anti-incohérence)
--    D. Triggers d'AUDIT (traçabilité des changements sensibles)
--    E. Procédures stockées SCD Type 2 (subscriber, plan)
--    F. Procédures stockées SCD Type 1 (tower)
--    G. Procédures de recalcul / maintenance KPI
--    H. Procédure de purge RGPD (droit à l'oubli)
--    I. Procédure de peuplement de dim_date (version optimisée)
-- ============================================================

USE edw_sahel_telecom;

-- ============================================================
--  A. TABLE D'AUDIT GÉNÉRIQUE
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id        BIGINT AUTO_INCREMENT PRIMARY KEY,
    table_name      VARCHAR(100)  NOT NULL,
    operation       VARCHAR(10)   NOT NULL COMMENT 'INSERT | UPDATE | DELETE',
    record_pk       VARCHAR(100)  NOT NULL COMMENT 'Identifiant de la ligne affectée',
    column_name     VARCHAR(100)  NULL,
    old_value       VARCHAR(500)  NULL,
    new_value       VARCHAR(500)  NULL,
    changed_by      VARCHAR(100)  DEFAULT (CURRENT_USER()),
    changed_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='Journal d''audit des modifications sensibles';

-- Création des index avec vérification préalable
SET @index_exists = (SELECT COUNT(*) FROM information_schema.statistics 
                     WHERE table_schema = 'edw_sahel_telecom' 
                     AND table_name = 'audit_log' 
                     AND index_name = 'idx_audit_table');

SET @sql = IF(@index_exists = 0, 'CREATE INDEX idx_audit_table ON audit_log(table_name)', 'SELECT "Index idx_audit_table already exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @index_exists = (SELECT COUNT(*) FROM information_schema.statistics 
                     WHERE table_schema = 'edw_sahel_telecom' 
                     AND table_name = 'audit_log' 
                     AND index_name = 'idx_audit_date');

SET @sql = IF(@index_exists = 0, 'CREATE INDEX idx_audit_date ON audit_log(changed_at)', 'SELECT "Index idx_audit_date already exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ============================================================
--  B. TRIGGERS DE QUALITÉ DES DONNÉES
--  Bloquent ou corrigent les valeurs invalides AVANT écriture
-- ============================================================

DELIMITER //

-- B1. dim_subscriber : validation âge, email, genre à l'insertion
DROP TRIGGER IF EXISTS trg_subscriber_quality_insert //
CREATE TRIGGER trg_subscriber_quality_insert
BEFORE INSERT ON dim_subscriber
FOR EACH ROW
BEGIN
    -- Âge hors plage réaliste -> NULL plutôt que valeur aberrante
    IF NEW.age IS NOT NULL AND (NEW.age < 14 OR NEW.age > 100) THEN
        SET NEW.age = NULL;
    END IF;

    -- Genre non standard -> valeur par défaut contrôlée
    IF NEW.gender NOT IN ('M', 'F') THEN
        SET NEW.gender = 'Inconnu';
    END IF;

    -- Email mal formé -> mis à NULL plutôt que stocké invalide
    IF NEW.email IS NOT NULL AND NEW.email NOT LIKE '%_@_%.__%' THEN
        SET NEW.email = NULL;
    END IF;

    -- Règle métier obligatoire : pas d'abonné sans ville ni pays
    IF NEW.city IS NULL OR NEW.country IS NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Rejet qualité : ville ou pays manquant pour un abonné';
    END IF;

    -- Cohérence churn / churn_date
    IF NEW.churn = 1 AND NEW.churn_date IS NULL THEN
        SET NEW.churn_date = CURDATE();
    END IF;
    IF NEW.churn = 0 THEN
        SET NEW.churn_date = NULL;
    END IF;
END//

-- B2. dim_subscriber : mêmes contrôles appliqués sur UPDATE
DROP TRIGGER IF EXISTS trg_subscriber_quality_update //
CREATE TRIGGER trg_subscriber_quality_update
BEFORE UPDATE ON dim_subscriber
FOR EACH ROW
BEGIN
    IF NEW.age IS NOT NULL AND (NEW.age < 14 OR NEW.age > 100) THEN
        SET NEW.age = NULL;
    END IF;
    IF NEW.gender NOT IN ('M', 'F') THEN
        SET NEW.gender = 'Inconnu';
    END IF;
    IF NEW.churn = 1 AND NEW.churn_date IS NULL THEN
        SET NEW.churn_date = CURDATE();
    END IF;
    IF NEW.churn = 0 THEN
        SET NEW.churn_date = NULL;
    END IF;
END//

-- B3. fact_usage : rejet des mesures négatives ou incohérentes
DROP TRIGGER IF EXISTS trg_usage_quality_insert //
CREATE TRIGGER trg_usage_quality_insert
BEFORE INSERT ON fact_usage
FOR EACH ROW
BEGIN
    IF NEW.duration_sec < 0 THEN
        SET NEW.duration_sec = 0;
    END IF;
    IF NEW.data_mb < 0 THEN
        SET NEW.data_mb = 0;
    END IF;
    IF NEW.amount_fcfa IS NOT NULL AND NEW.amount_fcfa < 0 THEN
        SET NEW.amount_fcfa = NULL;
    END IF;

    -- Règle métier : un événement Data doit avoir data_mb > 0, sinon log + rejet
    IF NEW.event_type = 'Data' AND NEW.data_mb = 0 THEN
        INSERT INTO etl_rejected_rows (source_table, raw_data, rejection_reason)
        VALUES ('fact_usage', CONCAT('usage_id=', NEW.usage_id),
                'Événement Data avec data_mb=0 — incohérence métier');
    END IF;
END//

-- B4. fact_incident : cohérence resolved / resolution_minutes
DROP TRIGGER IF EXISTS trg_incident_quality_insert //
CREATE TRIGGER trg_incident_quality_insert
BEFORE INSERT ON fact_incident
FOR EACH ROW
BEGIN
    IF NEW.resolved = 0 THEN
        SET NEW.resolution_minutes = NULL;
    END IF;
    IF NEW.nb_abonnes_affectes < 0 THEN
        SET NEW.nb_abonnes_affectes = 0;
    END IF;
END//

-- B5. dim_tower : cohérence géographique minimale
DROP TRIGGER IF EXISTS trg_tower_quality_insert //
CREATE TRIGGER trg_tower_quality_insert
BEFORE INSERT ON dim_tower
FOR EACH ROW
BEGIN
    IF NEW.latitude IS NOT NULL AND (NEW.latitude < -90 OR NEW.latitude > 90) THEN
        SET NEW.latitude = NULL;
    END IF;
    IF NEW.longitude IS NOT NULL AND (NEW.longitude < -180 OR NEW.longitude > 180) THEN
        SET NEW.longitude = NULL;
    END IF;
    IF NEW.capacity_users < 0 THEN
        SET NEW.capacity_users = 0;
    END IF;
END//

DELIMITER ;


-- ============================================================
--  C. TRIGGERS D'INTÉGRITÉ SCD (garde-fous)
--  Empêchent les incohérences dans l'historisation
-- ============================================================

DELIMITER //

-- C1. dim_subscriber : empêcher plusieurs versions "is_current=1" pour le même subscriber_id
DROP TRIGGER IF EXISTS trg_subscriber_scd_guard_insert //
CREATE TRIGGER trg_subscriber_scd_guard_insert
BEFORE INSERT ON dim_subscriber
FOR EACH ROW
BEGIN
    DECLARE nb_current INT DEFAULT 0;

    IF NEW.is_current = 1 THEN
        SELECT COUNT(*) INTO nb_current
        FROM dim_subscriber
        WHERE subscriber_id = NEW.subscriber_id AND is_current = 1;

        IF nb_current > 0 THEN
            -- Ferme automatiquement l'ancienne version active (garde-fou)
            UPDATE dim_subscriber
            SET is_current = 0, date_fin = CURDATE()
            WHERE subscriber_id = NEW.subscriber_id AND is_current = 1;
        END IF;
    END IF;
END//

-- C2. dim_plan : même garde-fou que pour subscriber
DROP TRIGGER IF EXISTS trg_plan_scd_guard_insert //
CREATE TRIGGER trg_plan_scd_guard_insert
BEFORE INSERT ON dim_plan
FOR EACH ROW
BEGIN
    DECLARE nb_current INT DEFAULT 0;

    IF NEW.is_current = 1 THEN
        SELECT COUNT(*) INTO nb_current
        FROM dim_plan
        WHERE plan_id = NEW.plan_id AND is_current = 1;

        IF nb_current > 0 THEN
            UPDATE dim_plan
            SET is_current = 0, date_fin = CURDATE()
            WHERE plan_id = NEW.plan_id AND is_current = 1;
        END IF;
    END IF;
END//

-- C3. Empêcher la suppression physique d'une dimension référencée par les faits
--     (principe de non-volatilité du DW vu en cours - Module 1)
DROP TRIGGER IF EXISTS trg_subscriber_prevent_delete //
CREATE TRIGGER trg_subscriber_prevent_delete
BEFORE DELETE ON dim_subscriber
FOR EACH ROW
BEGIN
    DECLARE nb_faits INT DEFAULT 0;
    SELECT COUNT(*) INTO nb_faits FROM fact_usage WHERE subscriber_sk = OLD.subscriber_sk;
    IF nb_faits > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Suppression interdite : abonné référencé dans fact_usage (principe de non-volatilité EDW)';
    END IF;
END//

DROP TRIGGER IF EXISTS trg_tower_prevent_delete //
CREATE TRIGGER trg_tower_prevent_delete
BEFORE DELETE ON dim_tower
FOR EACH ROW
BEGIN
    DECLARE nb_faits INT DEFAULT 0;
    SELECT COUNT(*) INTO nb_faits FROM fact_usage WHERE tower_sk = OLD.tower_sk;
    IF nb_faits > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Suppression interdite : antenne référencée dans fact_usage';
    END IF;
END//

DELIMITER ;


-- ============================================================
--  D. TRIGGERS D'AUDIT
--  Tracent les changements sur les données sensibles (RGPD, finance)
-- ============================================================

DELIMITER //

-- D1. Audit des changements de churn (donnée stratégique business)
DROP TRIGGER IF EXISTS trg_audit_subscriber_churn //
CREATE TRIGGER trg_audit_subscriber_churn
AFTER UPDATE ON dim_subscriber
FOR EACH ROW
BEGIN
    IF OLD.churn <> NEW.churn THEN
        INSERT INTO audit_log (table_name, operation, record_pk, column_name, old_value, new_value)
        VALUES ('dim_subscriber', 'UPDATE', NEW.subscriber_id, 'churn',
                CAST(OLD.churn AS CHAR), CAST(NEW.churn AS CHAR));
    END IF;
END//

-- D2. Audit des changements de revenu (donnée financière)
DROP TRIGGER IF EXISTS trg_audit_subscriber_revenue //
CREATE TRIGGER trg_audit_subscriber_revenue
AFTER UPDATE ON dim_subscriber
FOR EACH ROW
BEGIN
    IF OLD.monthly_revenue <> NEW.monthly_revenue
       OR (OLD.monthly_revenue IS NULL) <> (NEW.monthly_revenue IS NULL) THEN
        INSERT INTO audit_log (table_name, operation, record_pk, column_name, old_value, new_value)
        VALUES ('dim_subscriber', 'UPDATE', NEW.subscriber_id, 'monthly_revenue',
                CAST(OLD.monthly_revenue AS CHAR), CAST(NEW.monthly_revenue AS CHAR));
    END IF;
END//

-- D3. Audit des changements tarifaires (dim_plan)
DROP TRIGGER IF EXISTS trg_audit_plan_price //
CREATE TRIGGER trg_audit_plan_price
AFTER UPDATE ON dim_plan
FOR EACH ROW
BEGIN
    IF OLD.monthly_fee <> NEW.monthly_fee THEN
        INSERT INTO audit_log (table_name, operation, record_pk, column_name, old_value, new_value)
        VALUES ('dim_plan', 'UPDATE', NEW.plan_id, 'monthly_fee',
                CAST(OLD.monthly_fee AS CHAR), CAST(NEW.monthly_fee AS CHAR));
    END IF;
END//

-- D4. Audit des suppressions (toute table dimension)
DROP TRIGGER IF EXISTS trg_audit_subscriber_delete //
CREATE TRIGGER trg_audit_subscriber_delete
AFTER DELETE ON dim_subscriber
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, operation, record_pk, column_name, old_value, new_value)
    VALUES ('dim_subscriber', 'DELETE', OLD.subscriber_id, 'ALL', 'Ligne supprimée', NULL);
END//

DELIMITER ;


-- ============================================================
--  E. PROCÉDURES STOCKÉES — SCD TYPE 2
--  (dim_subscriber, dim_plan)
-- ============================================================

DELIMITER //

-- E1. Upsert SCD Type 2 pour un abonné
--     Si l'abonné existe et qu'un attribut suivi a changé -> nouvelle version
--     Si l'abonné n'existe pas -> insertion initiale
DROP PROCEDURE IF EXISTS sp_upsert_subscriber_scd2 //
CREATE PROCEDURE sp_upsert_subscriber_scd2(
    IN p_subscriber_id  VARCHAR(20),
    IN p_first_name     VARCHAR(100),
    IN p_last_name      VARCHAR(100),
    IN p_gender         VARCHAR(10),
    IN p_age            TINYINT,
    IN p_tranche_age    VARCHAR(20),
    IN p_city           VARCHAR(100),
    IN p_country        VARCHAR(100),
    IN p_plan_id        VARCHAR(20),
    IN p_tower_id       VARCHAR(20),
    IN p_phone_number   VARCHAR(30),
    IN p_email          VARCHAR(200),
    IN p_segment        VARCHAR(30),
    IN p_churn          TINYINT,
    IN p_churn_date     DATE,
    IN p_subscription_date DATE,
    IN p_monthly_revenue   DECIMAL(10,2)
)
BEGIN
    DECLARE v_exists INT DEFAULT 0;
    DECLARE v_changed INT DEFAULT 0;
    DECLARE v_current_city VARCHAR(100);
    DECLARE v_current_segment VARCHAR(30);
    DECLARE v_current_plan VARCHAR(20);
    DECLARE v_current_version INT;

    SELECT COUNT(*) INTO v_exists
    FROM dim_subscriber
    WHERE subscriber_id = p_subscriber_id AND is_current = 1;

    IF v_exists = 0 THEN
        -- Première insertion (version 1)
        INSERT INTO dim_subscriber
            (subscriber_id, first_name, last_name, gender, age, tranche_age,
             city, country, plan_id, tower_id, phone_number, email, segment,
             churn, churn_date, subscription_date, monthly_revenue,
             date_debut, is_current, version)
        VALUES
            (p_subscriber_id, p_first_name, p_last_name, p_gender, p_age, p_tranche_age,
             p_city, p_country, p_plan_id, p_tower_id, p_phone_number, p_email, p_segment,
             p_churn, p_churn_date, p_subscription_date, p_monthly_revenue,
             CURDATE(), 1, 1);
    ELSE
        -- Vérifier si un attribut "suivi en SCD2" a changé : ville, segment, plan
        SELECT city, segment, plan_id, version
        INTO v_current_city, v_current_segment, v_current_plan, v_current_version
        FROM dim_subscriber
        WHERE subscriber_id = p_subscriber_id AND is_current = 1;

        IF v_current_city <> p_city OR v_current_segment <> p_segment OR v_current_plan <> p_plan_id THEN
            SET v_changed = 1;
        END IF;

        IF v_changed = 1 THEN
            -- Le trigger trg_subscriber_scd_guard_insert ferme automatiquement
            -- l'ancienne version dès l'insertion de la nouvelle (is_current=1)
            INSERT INTO dim_subscriber
                (subscriber_id, first_name, last_name, gender, age, tranche_age,
                 city, country, plan_id, tower_id, phone_number, email, segment,
                 churn, churn_date, subscription_date, monthly_revenue,
                 date_debut, is_current, version)
            VALUES
                (p_subscriber_id, p_first_name, p_last_name, p_gender, p_age, p_tranche_age,
                 p_city, p_country, p_plan_id, p_tower_id, p_phone_number, p_email, p_segment,
                 p_churn, p_churn_date, p_subscription_date, p_monthly_revenue,
                 CURDATE(), 1, v_current_version + 1);
        ELSE
            -- Pas de changement structurel -> simple mise à jour (Type 1 sur attributs mineurs)
            UPDATE dim_subscriber
            SET churn = p_churn,
                churn_date = p_churn_date,
                monthly_revenue = p_monthly_revenue,
                phone_number = p_phone_number,
                email = p_email
            WHERE subscriber_id = p_subscriber_id AND is_current = 1;
        END IF;
    END IF;
END//

-- E2. Upsert SCD Type 2 pour un plan tarifaire
DROP PROCEDURE IF EXISTS sp_upsert_plan_scd2 //
CREATE PROCEDURE sp_upsert_plan_scd2(
    IN p_plan_id          VARCHAR(20),
    IN p_plan_name        VARCHAR(100),
    IN p_type_abonnement  VARCHAR(30),
    IN p_country          VARCHAR(100),
    IN p_monthly_fee      DECIMAL(10,2),
    IN p_data_quota_gb    DECIMAL(8,2),
    IN p_call_minutes     INT,
    IN p_sms_quota        INT,
    IN p_categorie_prix   VARCHAR(20)
)
BEGIN
    DECLARE v_exists INT DEFAULT 0;
    DECLARE v_current_fee DECIMAL(10,2);
    DECLARE v_current_version INT;

    SELECT COUNT(*) INTO v_exists
    FROM dim_plan WHERE plan_id = p_plan_id AND is_current = 1;

    IF v_exists = 0 THEN
        INSERT INTO dim_plan
            (plan_id, plan_name, type_abonnement, country, monthly_fee,
             data_quota_gb, call_minutes, sms_quota, categorie_prix,
             date_debut, is_current, version)
        VALUES
            (p_plan_id, p_plan_name, p_type_abonnement, p_country, p_monthly_fee,
             p_data_quota_gb, p_call_minutes, p_sms_quota, p_categorie_prix,
             CURDATE(), 1, 1);
    ELSE
        SELECT monthly_fee, version INTO v_current_fee, v_current_version
        FROM dim_plan WHERE plan_id = p_plan_id AND is_current = 1;

        IF v_current_fee <> p_monthly_fee THEN
            -- Changement de tarif -> nouvelle version (historisation du prix)
            INSERT INTO dim_plan
                (plan_id, plan_name, type_abonnement, country, monthly_fee,
                 data_quota_gb, call_minutes, sms_quota, categorie_prix,
                 date_debut, is_current, version)
            VALUES
                (p_plan_id, p_plan_name, p_type_abonnement, p_country, p_monthly_fee,
                 p_data_quota_gb, p_call_minutes, p_sms_quota, p_categorie_prix,
                 CURDATE(), 1, v_current_version + 1);
        END IF;
    END IF;
END//

DELIMITER ;


-- ============================================================
--  F. PROCÉDURE STOCKÉE — SCD TYPE 1 (dim_tower)
-- ============================================================

DELIMITER //

-- F1. Upsert SCD Type 1 : écrase simplement les valeurs (pas d'historique)
DROP PROCEDURE IF EXISTS sp_upsert_tower_scd1 //
CREATE PROCEDURE sp_upsert_tower_scd1(
    IN p_tower_id           VARCHAR(20),
    IN p_tower_name         VARCHAR(100),
    IN p_city               VARCHAR(100),
    IN p_region             VARCHAR(100),
    IN p_country             VARCHAR(100),
    IN p_latitude            DECIMAL(9,6),
    IN p_longitude           DECIMAL(9,6),
    IN p_capacity_users      INT,
    IN p_technology          VARCHAR(10),
    IN p_installation_date   DATE,
    IN p_status              VARCHAR(20),
    IN p_etat_batterie       VARCHAR(20),
    IN p_zone_type           VARCHAR(30)
)
BEGIN
    DECLARE v_exists INT DEFAULT 0;

    SELECT COUNT(*) INTO v_exists FROM dim_tower WHERE tower_id = p_tower_id;

    IF v_exists = 0 THEN
        INSERT INTO dim_tower
            (tower_id, tower_name, city, region, country, latitude, longitude,
             capacity_users, technology, installation_date, status, etat_batterie, zone_type)
        VALUES
            (p_tower_id, p_tower_name, p_city, p_region, p_country, p_latitude, p_longitude,
             p_capacity_users, p_technology, p_installation_date, p_status, p_etat_batterie, p_zone_type);
    ELSE
        -- SCD Type 1 : écrasement direct, aucun historique conservé
        UPDATE dim_tower
        SET tower_name = p_tower_name,
            city = p_city,
            region = p_region,
            country = p_country,
            latitude = p_latitude,
            longitude = p_longitude,
            capacity_users = p_capacity_users,
            technology = p_technology,
            status = p_status,
            etat_batterie = p_etat_batterie,
            zone_type = p_zone_type
        WHERE tower_id = p_tower_id;
    END IF;
END//

DELIMITER ;


-- ============================================================
--  G. PROCÉDURES DE MAINTENANCE / RECALCUL KPI
-- ============================================================

DELIMITER //

-- G1. Recalcule et affiche un résumé de qualité des données (data quality score)
DROP PROCEDURE IF EXISTS sp_data_quality_report //
CREATE PROCEDURE sp_data_quality_report()
BEGIN
    SELECT 'dim_subscriber' AS table_name,
        COUNT(*) AS total_lignes,
        SUM(age IS NULL) AS age_manquant,
        SUM(email IS NULL) AS email_manquant,
        SUM(gender = 'Inconnu') AS genre_inconnu,
        ROUND(100 - (SUM(age IS NULL) + SUM(email IS NULL)) * 100.0
              / (COUNT(*) * 2), 2) AS score_completude_pct
    FROM dim_subscriber WHERE is_current = 1
    UNION ALL
    SELECT 'fact_usage',
        COUNT(*),
        SUM(amount_fcfa IS NULL),
        NULL,
        NULL,
        ROUND(100 - SUM(amount_fcfa IS NULL) * 100.0 / COUNT(*), 2)
    FROM fact_usage
    UNION ALL
    SELECT 'fact_incident',
        COUNT(*),
        SUM(resolution_minutes IS NULL),
        NULL,
        NULL,
        ROUND(100 - SUM(resolution_minutes IS NULL) * 100.0 / COUNT(*), 2)
    FROM fact_incident;
END//

-- G2. Rapport de synthèse des exécutions ETL (à utiliser après chaque run)
DROP PROCEDURE IF EXISTS sp_etl_run_summary //
CREATE PROCEDURE sp_etl_run_summary(IN p_hours_back INT)
BEGIN
    SELECT table_name, operation, status,
           rows_extracted, rows_inserted, rows_rejected, rows_updated,
           duration_seconds, start_time, end_time
    FROM etl_log
    WHERE start_time >= DATE_SUB(NOW(), INTERVAL p_hours_back HOUR)
    ORDER BY start_time DESC;
END//

-- G3. Détecte les abonnés "à risque de churn" (règle simple, pré-modèle ML)
--     Critère : aucun événement d'usage depuis 60 jours et non encore marqué churn
DROP PROCEDURE IF EXISTS sp_detect_churn_risk //
CREATE PROCEDURE sp_detect_churn_risk()
BEGIN
    SELECT s.subscriber_id, s.first_name, s.last_name, s.city, s.country,
           MAX(d.date_complete) AS derniere_activite,
           DATEDIFF(CURDATE(), MAX(d.date_complete)) AS jours_inactivite
    FROM dim_subscriber s
    JOIN fact_usage fu ON s.subscriber_sk = fu.subscriber_sk
    JOIN dim_date d ON fu.date_sk = d.date_sk
    WHERE s.churn = 0 AND s.is_current = 1
    GROUP BY s.subscriber_id, s.first_name, s.last_name, s.city, s.country
    HAVING jours_inactivite >= 60
    ORDER BY jours_inactivite DESC;
END//

DELIMITER ;


-- ============================================================
--  H. PROCÉDURE RGPD — DROIT À L'EFFACEMENT
--  (cf. Module 6 du cours : le DW est non-volatile par design,
--   donc on pseudonymise plutôt que supprimer physiquement)
-- ============================================================

DELIMITER //

DROP PROCEDURE IF EXISTS sp_rgpd_pseudonymiser_abonne //
CREATE PROCEDURE sp_rgpd_pseudonymiser_abonne(IN p_subscriber_id VARCHAR(20))
BEGIN
    UPDATE dim_subscriber
    SET first_name   = 'ANONYMISE',
        last_name    = 'ANONYMISE',
        phone_number = NULL,
        email        = NULL
    WHERE subscriber_id = p_subscriber_id;

    INSERT INTO audit_log (table_name, operation, record_pk, column_name, old_value, new_value)
    VALUES ('dim_subscriber', 'UPDATE', p_subscriber_id, 'RGPD_PSEUDONYMISATION',
            'Données identifiantes', 'Anonymisées sur demande RGPD');
END//

DELIMITER ;


-- ============================================================
--  I. PROCÉDURE DE PEUPLEMENT DE dim_date (VERSION OPTIMISÉE)
--  Gère les contraintes de clé étrangère avec INSERT IGNORE
-- ============================================================

DELIMITER //

DROP PROCEDURE IF EXISTS sp_populate_dim_date //
CREATE PROCEDURE sp_populate_dim_date(IN p_start DATE, IN p_end DATE)
BEGIN
    -- Version optimisée qui utilise INSERT IGNORE pour éviter les erreurs de clé étrangère
    -- Les dates existantes ne sont pas supprimées pour préserver l'intégrité référentielle
    
    -- Créer une table temporaire de nombres si elle n'existe pas
    DROP TEMPORARY TABLE IF EXISTS temp_numbers;
    CREATE TEMPORARY TABLE temp_numbers (n INT PRIMARY KEY);
    
    -- Remplir la table temporaire avec des nombres (0 à 99999)
    INSERT IGNORE INTO temp_numbers (n)
    SELECT a.N + b.N * 10 + c.N * 100 + d.N * 1000 + e.N * 10000 AS n
    FROM 
        (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 
         UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) a,
        (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 
         UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) b,
        (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 
         UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) c,
        (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 
         UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) d,
        (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 
         UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) e;
    
    -- Insérer les dates avec INSERT IGNORE pour éviter les doublons
    -- sans supprimer les données existantes (préserve l'intégrité référentielle)
    INSERT IGNORE INTO dim_date (
        date_sk, date_complete, jour, jour_semaine, nom_jour,
        semaine_annee, mois, nom_mois, trimestre, semestre,
        annee, is_weekend, is_jour_ouvre, is_ferie,
        saison, periode_fiscale, mois_annee, annee_trimestre,
        heure, tranche_horaire
    )
    SELECT 
        DATE_FORMAT(DATE_ADD(p_start, INTERVAL tn.n DAY), '%Y%m%d') AS date_sk,
        DATE_ADD(p_start, INTERVAL tn.n DAY) AS date_complete,
        DAY(DATE_ADD(p_start, INTERVAL tn.n DAY)) AS jour,
        DAYOFWEEK(DATE_ADD(p_start, INTERVAL tn.n DAY)) AS jour_semaine,
        DAYNAME(DATE_ADD(p_start, INTERVAL tn.n DAY)) AS nom_jour,
        WEEK(DATE_ADD(p_start, INTERVAL tn.n DAY), 1) AS semaine_annee,
        MONTH(DATE_ADD(p_start, INTERVAL tn.n DAY)) AS mois,
        MONTHNAME(DATE_ADD(p_start, INTERVAL tn.n DAY)) AS nom_mois,
        QUARTER(DATE_ADD(p_start, INTERVAL tn.n DAY)) AS trimestre,
        CASE WHEN MONTH(DATE_ADD(p_start, INTERVAL tn.n DAY)) <= 6 THEN 1 ELSE 2 END AS semestre,
        YEAR(DATE_ADD(p_start, INTERVAL tn.n DAY)) AS annee,
        CASE WHEN DAYOFWEEK(DATE_ADD(p_start, INTERVAL tn.n DAY)) IN (1,7) THEN 1 ELSE 0 END AS is_weekend,
        CASE WHEN DAYOFWEEK(DATE_ADD(p_start, INTERVAL tn.n DAY)) IN (1,7) THEN 0 ELSE 1 END AS is_jour_ouvre,
        0 AS is_ferie,
        CASE 
            WHEN MONTH(DATE_ADD(p_start, INTERVAL tn.n DAY)) BETWEEN 6 AND 10 THEN 'Hivernage'
            ELSE 'Saison sèche'
        END AS saison,
        CONCAT('FY', YEAR(DATE_ADD(p_start, INTERVAL tn.n DAY)), '-Q', QUARTER(DATE_ADD(p_start, INTERVAL tn.n DAY))) AS periode_fiscale,
        DATE_FORMAT(DATE_ADD(p_start, INTERVAL tn.n DAY), '%Y-%m') AS mois_annee,
        CONCAT(YEAR(DATE_ADD(p_start, INTERVAL tn.n DAY)), '-Q', QUARTER(DATE_ADD(p_start, INTERVAL tn.n DAY))) AS annee_trimestre,
        NULL AS heure,
        NULL AS tranche_horaire
    FROM temp_numbers tn
    WHERE DATE_ADD(p_start, INTERVAL tn.n DAY) <= p_end
      AND tn.n <= DATEDIFF(p_end, p_start)
      AND DATE_FORMAT(DATE_ADD(p_start, INTERVAL tn.n DAY), '%Y%m%d') NOT IN (
          SELECT date_sk FROM dim_date
      )
    ORDER BY tn.n;
    
    -- Nettoyer
    DROP TEMPORARY TABLE temp_numbers;
    
    -- Afficher le nombre de nouvelles dates insérées
    SELECT CONCAT('Dates insérées avec succès de ', p_start, ' à ', p_end) AS message;
END //

DELIMITER ;


-- ============================================================
--  J. EXÉCUTION DE LA PROCÉDURE DE PEUPLEMENT DE dim_date
--  Avec augmentation temporaire des timeouts pour éviter les erreurs
-- ============================================================

-- Augmenter temporairement les timeouts pour cette opération
SET SESSION wait_timeout = 600;
SET SESSION interactive_timeout = 600;
SET SESSION net_read_timeout = 600;
SET SESSION net_write_timeout = 600;

-- Exécuter la procédure (rapide, environ 1-3 secondes selon la configuration)
CALL sp_populate_dim_date('2015-01-01', '2035-12-31');

-- Restaurer les valeurs par défaut (optionnel)
SET SESSION wait_timeout = 28800;
SET SESSION interactive_timeout = 28800;
SET SESSION net_read_timeout = 30;
SET SESSION net_write_timeout = 60;

-- ============================================================
--  K. VÉRIFICATION FINALE
-- ============================================================

SELECT 'TRIGGERS CRÉÉS' AS message, trigger_name, event_manipulation, event_object_table
FROM information_schema.triggers
WHERE trigger_schema = 'edw_sahel_telecom';

SELECT 'PROCÉDURES CRÉÉES' AS message, routine_name, routine_type
FROM information_schema.routines
WHERE routine_schema = 'edw_sahel_telecom';

-- Vérification du nombre de dates insérées dans dim_date
SELECT 
    COUNT(*) AS total_dates,
    MIN(date_complete) AS date_min,
    MAX(date_complete) AS date_max,
    DATEDIFF(MAX(date_complete), MIN(date_complete)) + 1 AS jours_attendus
FROM dim_date;

-- Afficher un échantillon des données
SELECT * FROM dim_date LIMIT 10;