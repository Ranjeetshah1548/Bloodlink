-- Run ONCE on a database created before contact fields existed.
-- (Fresh databases created from schema.sql / create_all already have these.)
ALTER TABLE blood_requests
    ADD COLUMN patient_name  VARCHAR(120) NULL AFTER notes,
    ADD COLUMN contact_name  VARCHAR(120) NULL AFTER patient_name,
    ADD COLUMN contact_phone VARCHAR(20)  NULL AFTER contact_name,
    ADD COLUMN ward_info     VARCHAR(150) NULL AFTER contact_phone;
