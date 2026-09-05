# Database models and migrations

CloudBox uses SQLAlchemy models and Flask-Migrate/Alembic. SQLite remains the
default local backend; production uses the same models with Amazon RDS MySQL.

## Local development

When `DATABASE_URL` is omitted, the app opens the project `database.db` and
creates missing tables for local convenience.

An existing SQLite database created before Alembic already has the initial
schema. Mark it as current once instead of attempting to recreate its tables:

```powershell
$env:AUTO_CREATE_SCHEMA = "false"
.venv\Scripts\flask.exe --app app/app.py db stamp head
Remove-Item Env:AUTO_CREATE_SCHEMA
```

Back up `database.db` before stamping or applying future migrations.

## New database or RDS MySQL

Set the connection URL and disable automatic schema creation:

```text
DATABASE_URL=mysql+pymysql://cloudbox_user:password@host:3306/cloudbox?charset=utf8mb4
AUTO_CREATE_SCHEMA=false
```

Apply every committed migration before starting the web process:

```powershell
.venv\Scripts\flask.exe --app app/app.py db upgrade
```

The initial migration also inserts the built-in `admin` and `user` roles and
their permissions. It does not create an administrator account; use
`python admin.py` after the migration.

Docker Compose can instead supply `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`,
and `DB_PASSWORD`. The application builds and safely escapes the PyMySQL URL;
`DATABASE_URL` takes precedence when both forms are present. See
`docs/DOCKER_MYSQL.md` for the two-container persistence test.

## Schema development

After changing a model:

```powershell
.venv\Scripts\flask.exe --app app/app.py db migrate -m "describe the change"
.venv\Scripts\flask.exe --app app/app.py db check
.venv\Scripts\flask.exe --app app/app.py db upgrade
```

Review every generated revision before committing it. Production must never
use `db.create_all()` as a replacement for versioned migrations.
