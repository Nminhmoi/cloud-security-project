"""Create, verify, and safely restore local SQLite backups."""

import argparse
import hashlib
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def verify_database(path):
    database_path = Path(path).resolve()
    if not database_path.is_file():
        raise FileNotFoundError(f"Database does not exist: {database_path}")

    uri = f"{database_path.as_uri()}?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.DatabaseError as error:
        raise ValueError(f"Invalid SQLite database: {database_path}") from error
    if not result or result[0] != "ok":
        raise ValueError(f"SQLite integrity check failed: {result}")
    return database_path


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_database(source, destination):
    source_path = verify_database(source)
    destination_path = Path(destination).resolve()
    if source_path == destination_path:
        raise ValueError("Source and destination must be different")
    if destination_path.exists():
        raise FileExistsError(f"Refusing to overwrite: {destination_path}")

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"{source_path.as_uri()}?mode=ro"
    try:
        with closing(sqlite3.connect(source_uri, uri=True)) as source_connection:
            with closing(sqlite3.connect(destination_path)) as destination_connection:
                source_connection.backup(destination_connection)
                destination_connection.commit()
        verify_database(destination_path)
    except Exception:
        if destination_path.exists():
            destination_path.unlink()
        raise
    return destination_path, sha256_file(destination_path)


def backup_database(source, destination=None):
    if destination is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = Path("backups") / f"cloudbox-{timestamp}.db"
    return copy_database(source, destination)


def restore_database(backup, output):
    """Restore into a new file; never replace the active database in place."""

    return copy_database(backup, output)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup = subparsers.add_parser("backup", help="Create a consistent backup")
    backup.add_argument("--source", default="database.db")
    backup.add_argument("--output")

    verify = subparsers.add_parser("verify", help="Run SQLite integrity_check")
    verify.add_argument("database")

    restore = subparsers.add_parser(
        "restore",
        help="Copy a verified backup into a new database file",
    )
    restore.add_argument("backup")
    restore.add_argument("--output", required=True)
    return parser


def main():
    args = _parser().parse_args()
    try:
        if args.command == "backup":
            path, checksum = backup_database(args.source, args.output)
        elif args.command == "restore":
            path, checksum = restore_database(args.backup, args.output)
        else:
            path = verify_database(args.database)
            checksum = sha256_file(path)
    except (FileNotFoundError, FileExistsError, ValueError, sqlite3.DatabaseError) as error:
        raise SystemExit(f"ERROR: {error}") from error

    print(f"Database: {path}")
    print(f"SHA256: {checksum}")


if __name__ == "__main__":
    main()
