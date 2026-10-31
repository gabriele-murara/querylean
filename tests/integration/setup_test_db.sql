-- Prepara un database di test isolato e un account in sola lettura.
-- Da eseguire una sola volta come amministratore, ad esempio:
--   sudo mysql < tests/integration/setup_test_db.sql
-- Sostituisci la password prima dell'uso o modificala in seguito.
-- Richiede MySQL 8.0+.

CREATE DATABASE IF NOT EXISTS querylean_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE querylean_test;

DROP TABLE IF EXISTS people;
CREATE TABLE people (
    id INT PRIMARY KEY,
    name VARCHAR(100) NULL,
    note VARCHAR(100) NOT NULL DEFAULT '',
    born DATE NULL,
    amount DECIMAL(10, 2) NULL,
    active TINYINT(1) NOT NULL DEFAULT 1,
    payload VARBINARY(16) NULL
);
INSERT INTO people VALUES
    (1, 'Alice', 'UPDATE; DELETE', '1990-05-01', 10.50, 1, 0x00FF),
    (2, NULL, '', NULL, NULL, 0, NULL),
    (3, 'Carlo', 'tab\there', '1985-12-31', -3.25, 1, 0xCAFE);

DROP TABLE IF EXISTS numbers;
CREATE TABLE numbers (n INT PRIMARY KEY);
SET SESSION cte_max_recursion_depth = 5000;
INSERT INTO numbers (n)
    WITH RECURSIVE seq AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM seq WHERE n < 2500)
    SELECT n FROM seq;

CREATE USER IF NOT EXISTS 'querylean_ro'@'localhost' IDENTIFIED BY 'querylean_ro_password';
CREATE USER IF NOT EXISTS 'querylean_ro'@'127.0.0.1' IDENTIFIED BY 'querylean_ro_password';
GRANT SELECT ON querylean_test.* TO 'querylean_ro'@'localhost';
GRANT SELECT ON querylean_test.* TO 'querylean_ro'@'127.0.0.1';
FLUSH PRIVILEGES;
