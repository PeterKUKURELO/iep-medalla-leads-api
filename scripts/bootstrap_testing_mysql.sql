-- SOLO TESTING. Ejecutar por bloques desde DBeaver, deteniendo ante errores.
-- Compatible con el esquema final de Alembic 20260911_03.
-- No crea bases, no contiene credenciales y no modifica tablas ajenas.
-- MySQL hace COMMIT implicito de DDL: un ROLLBACK no recupera DROP TABLE.
-- Detener API/worker durante esta operacion y exportar leads antes de eliminarla.

USE `bsnfd7xjtjpoktciyb3o`;

-- BLOQUE 1: comprobar destino y estado. Ejecutar primero, por separado.
SELECT DATABASE() AS target_database, VERSION() AS mysql_version;
SELECT COUNT(*) AS legacy_lead_count FROM leads;
SELECT table_name FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name IN ('leads', 'lead_notifications', 'consumer_complaints', 'alembic_version');
SELECT table_name, column_name, constraint_name
FROM information_schema.key_column_usage
WHERE referenced_table_schema = DATABASE() AND referenced_table_name = 'leads';

-- BLOQUE 2: SOLO si leads sigue vacia y no tiene tablas dependientes.
-- Si lead_notifications o consumer_complaints ya existen, detener: no borrarlas.
-- Seleccionar y ejecutar la siguiente sentencia manualmente (quitar --).
-- DROP TABLE `leads`;
-- No desactivar FOREIGN_KEY_CHECKS: una dependencia inesperada debe bloquear DROP.

-- BLOQUE 3: ejecutar SOLO despues de completar y revisar los bloques anteriores.
-- Sin IF NOT EXISTS: una tabla preexistente debe dar error, no ocultar diferencias.
CREATE TABLE `leads` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `brand_key` VARCHAR(50) NOT NULL DEFAULT 'iep-medalla',
    `form_type` VARCHAR(50) NOT NULL,
    `source_key` VARCHAR(100) NULL,
    `full_name` VARCHAR(150) NOT NULL,
    `phone` VARCHAR(30) NOT NULL,
    `phone_country` VARCHAR(2) NULL,
    `email` VARCHAR(254) NOT NULL,
    `organization_name` VARCHAR(200) NULL,
    `job_title` VARCHAR(120) NULL,
    `education_level` VARCHAR(50) NULL,
    `grade` VARCHAR(50) NULL,
    `contact_reason` VARCHAR(150) NULL,
    `message` TEXT NULL,
    `form_data` JSON NOT NULL,
    `privacy_accepted` BOOLEAN NOT NULL,
    `privacy_accepted_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `source_url` VARCHAR(500) NULL,
    `utm_source` VARCHAR(100) NULL,
    `utm_medium` VARCHAR(100) NULL,
    `utm_campaign` VARCHAR(150) NULL,
    `utm_content` VARCHAR(150) NULL,
    `utm_term` VARCHAR(150) NULL,
    `device_type` VARCHAR(30) NULL,
    `status` VARCHAR(30) NOT NULL DEFAULT 'new',
    `classification` VARCHAR(30) NULL,
    `assigned_to` VARCHAR(120) NULL,
    `next_follow_up_at` DATETIME NULL,
    `admin_email_status` VARCHAR(20) NOT NULL DEFAULT 'pending',
    `admin_email_sent_at` DATETIME NULL,
    `user_email_status` VARCHAR(20) NOT NULL DEFAULT 'pending',
    `user_email_sent_at` DATETIME NULL,
    `email_error` VARCHAR(500) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    INDEX `ix_leads_email` (`email`),
    INDEX `ix_leads_form_type` (`form_type`),
    INDEX `ix_leads_brand_key` (`brand_key`),
    INDEX `ix_leads_brand_created_at` (`brand_key`, `created_at`),
    INDEX `ix_leads_brand_form_created_at` (`brand_key`, `form_type`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `lead_notifications` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `lead_id` INTEGER NOT NULL,
    `kind` VARCHAR(20) NOT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending',
    `attempt_count` INTEGER NOT NULL DEFAULT 0,
    `next_attempt_at` DATETIME NULL,
    `locked_until` DATETIME NULL,
    `claim_token` VARCHAR(36) NULL,
    `sent_at` DATETIME NULL,
    `last_error_code` VARCHAR(100) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    CONSTRAINT `uq_lead_notifications_lead_kind` UNIQUE (`lead_id`, `kind`),
    CONSTRAINT `fk_lead_notifications_lead_id` FOREIGN KEY (`lead_id`)
        REFERENCES `leads` (`id`) ON DELETE CASCADE,
    INDEX `ix_lead_notifications_lead_id` (`lead_id`),
    INDEX `ix_lead_notifications_due` (`status`, `next_attempt_at`, `locked_until`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `consumer_complaints` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `complaint_type` VARCHAR(20) NOT NULL,
    `full_name` VARCHAR(150) NOT NULL,
    `document_type` VARCHAR(20) NOT NULL,
    `document_number` VARCHAR(30) NOT NULL,
    `address` VARCHAR(300) NOT NULL,
    `email` VARCHAR(254) NOT NULL,
    `phone` VARCHAR(30) NOT NULL,
    `is_minor` BOOLEAN NOT NULL DEFAULT 0,
    `representative_name` VARCHAR(150) NULL,
    `item_type` VARCHAR(20) NOT NULL,
    `amount` NUMERIC(12, 2) NULL,
    `description` TEXT NOT NULL,
    `requested_action` TEXT NOT NULL,
    `privacy_accepted` BOOLEAN NOT NULL,
    `source_url` VARCHAR(500) NULL,
    `status` VARCHAR(30) NOT NULL DEFAULT 'received',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    INDEX `ix_consumer_complaints_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- BLOQUE 4: verificacion de las tres tablas antes de marcar revision.
SHOW CREATE TABLE leads;
SHOW CREATE TABLE lead_notifications;
SHOW CREATE TABLE consumer_complaints;
SELECT 'leads' AS table_name, COUNT(*) AS total FROM leads
UNION ALL SELECT 'lead_notifications', COUNT(*) FROM lead_notifications
UNION ALL SELECT 'consumer_complaints', COUNT(*) FROM consumer_complaints;

-- BLOQUE 5: SOLO si las tres tablas se crearon correctamente y alembic_version
-- NO existe. Seleccionar y ejecutar manualmente las dos sentencias siguientes.
-- Si ya existe alembic_version, consultar sus filas y detenerse para revisarla:
-- nunca sobrescribir el historial de otro sistema ni marcar una creacion parcial.
-- CREATE TABLE `alembic_version` (
--     `version_num` VARCHAR(32) NOT NULL,
--     CONSTRAINT `alembic_version_pkc` PRIMARY KEY (`version_num`)
-- ) ENGINE=InnoDB;
-- INSERT INTO `alembic_version` (`version_num`) VALUES ('20260911_03');
-- SELECT * FROM alembic_version;
