-- ============================================================
--  PEUPLEMENT DE DIM_DATE
--  Génère toutes les dates de 2023-01-01 à 2027-12-31
--  À exécuter APRES edw_sahel_telecom.sql
-- ============================================================

USE edw_sahel_telecom;

-- Table numérique temporaire pour générer la séquence de dates
DROP TEMPORARY TABLE IF EXISTS seq_numbers;
CREATE TEMPORARY TABLE seq_numbers (n INT);

-- Génère 0 à 1825 (5 ans) via une astuce de produit cartésien
INSERT INTO seq_numbers (n)
SELECT a.N + b.N * 10 + c.N * 100 + d.N * 1000
FROM
 (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
  UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) a,
 (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
  UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) b,
 (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
  UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) c,
 (SELECT 0 AS N UNION SELECT 1) d
ORDER BY 1;

-- Liste des jours fériés au Burkina Faso et au Ghana (approximation, jours fixes)
DROP TEMPORARY TABLE IF EXISTS jours_feries;
CREATE TEMPORARY TABLE jours_feries (jour_ferie DATE);
INSERT INTO jours_feries (jour_ferie) VALUES
  -- Jours fixes répétés chaque année (2023-2027)
  ('2023-01-01'),('2024-01-01'),('2025-01-01'),('2026-01-01'),('2027-01-01'), -- Nouvel An
  ('2023-03-08'),('2024-03-08'),('2025-03-08'),('2026-03-08'),('2027-03-08'), -- Journée femme (BF)
  ('2023-05-01'),('2024-05-01'),('2025-05-01'),('2026-05-01'),('2027-05-01'), -- Fête du travail
  ('2023-08-05'),('2024-08-05'),('2025-08-05'),('2026-08-05'),('2027-08-05'), -- Indépendance BF
  ('2023-03-06'),('2024-03-06'),('2025-03-06'),('2026-03-06'),('2027-03-06'), -- Indépendance Ghana
  ('2023-12-25'),('2024-12-25'),('2025-12-25'),('2026-12-25'),('2027-12-25'); -- Noël

INSERT INTO dim_date (
    date_sk, date_complete, jour, jour_semaine, nom_jour,
    semaine_annee, mois, nom_mois, trimestre, semestre, annee,
    is_weekend, is_jour_ouvre, is_ferie, saison,
    periode_fiscale, mois_annee, annee_trimestre
)
SELECT
    CAST(DATE_FORMAT(d, '%Y%m%d') AS UNSIGNED)                       AS date_sk,
    d                                                                 AS date_complete,
    DAY(d)                                                            AS jour,
    -- Lundi=1 ... Dimanche=7
    ((WEEKDAY(d) + 1))                                                AS jour_semaine,
    ELT(WEEKDAY(d) + 1, 'Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi','Dimanche') AS nom_jour,
    WEEK(d, 3)                                                        AS semaine_annee,
    MONTH(d)                                                          AS mois,
    ELT(MONTH(d), 'Janvier','Février','Mars','Avril','Mai','Juin',
        'Juillet','Août','Septembre','Octobre','Novembre','Décembre') AS nom_mois,
    QUARTER(d)                                                        AS trimestre,
    IF(MONTH(d) <= 6, 1, 2)                                           AS semestre,
    YEAR(d)                                                           AS annee,
    IF(WEEKDAY(d) >= 5, 1, 0)                                         AS is_weekend,
    IF(WEEKDAY(d) >= 5 OR jf.jour_ferie IS NOT NULL, 0, 1)            AS is_jour_ouvre,
    IF(jf.jour_ferie IS NOT NULL, 1, 0)                               AS is_ferie,
    -- Saison Sahel : Hivernage (juin-sept) / Saison sèche (reste de l'année)
    IF(MONTH(d) BETWEEN 6 AND 9, 'Hivernage', 'Saison sèche')         AS saison,
    CONCAT('FY', YEAR(d), '-Q', QUARTER(d))                           AS periode_fiscale,
    DATE_FORMAT(d, '%Y-%m')                                           AS mois_annee,
    CONCAT(YEAR(d), '-Q', QUARTER(d))                                 AS annee_trimestre
FROM (
    SELECT DATE_ADD('2023-01-01', INTERVAL n DAY) AS d
    FROM seq_numbers
    WHERE n <= 1825
) dates
LEFT JOIN jours_feries jf ON jf.jour_ferie = dates.d;

DROP TEMPORARY TABLE IF EXISTS seq_numbers;
DROP TEMPORARY TABLE IF EXISTS jours_feries;

-- Vérification
SELECT
    MIN(date_complete) AS premiere_date,
    MAX(date_complete) AS derniere_date,
    COUNT(*)            AS nb_jours_total,
    SUM(is_weekend)     AS nb_weekends,
    SUM(is_ferie)        AS nb_feries
FROM dim_date;
