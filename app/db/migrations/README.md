# RailYatri — Database Migrations

This directory is reserved for schema migration files.

All future schema changes (ALTER TABLE, new columns, new indexes)
after the baseline `schema.sql` MUST be applied as numbered migration
files here, following Alembic or Flyway naming conventions.

Example:
    0001_add_user_preferences.sql
    0002_add_pnr_fare_column.sql

No migration tooling is introduced at baseline. This directory is a
structural placeholder only.
