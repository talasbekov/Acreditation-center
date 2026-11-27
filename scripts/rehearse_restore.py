"""Offline recovery rehearsal with disposable PostgreSQL 15 and trusted application releases.

Run in the target release's Python environment with --pg-bin and --previous-source.
The previous source must be the release ending at eventproject migration 0024.
Both arguments are read-only inputs. No DB, dump, media or credentials are accepted.
"""

import argparse
from contextlib import closing
from datetime import date
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time


PREVIOUS = "0024_recompute_is_resident"
TARGET = "0035_attendee_dateadd_idx"  # после сведения с security-hardening (этап F: 0030, отчёт 10: 0026)
SOURCE_DB = "restore_rehearsal_source"
RESTORED_DB = "restore_rehearsal_copy"
ADMIN = "restore_rehearsal_admin"
HOST = "127.0.0.1"
PREFIX = "eventproject-restore-"
PACKAGES = ("eventproject", "directories", "qr_event", "en_event", "kz_event")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(command, env, cwd, label, expected=(0,)):
    # Only aggregate results leave the rehearsal. A failed child's diagnostic may
    # contain row data, SQL parameters or credentials.
    # On Windows the server started by pg_ctl may inherit its pipe handles and
    # keep communicate() open even after pg_ctl has returned.
    control = Path(command[0]).stem == "pg_ctl" and "--version" not in command
    output = subprocess.DEVNULL if control else subprocess.PIPE
    result = subprocess.run(
        command, cwd=cwd, env=env, stdout=output, stderr=output, timeout=150,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    require(result.returncode in expected, f"{label} exited with {result.returncode}")
    return result


def stage_release(source, dest, expected):
    migrations = source / "eventproject" / "migrations"
    require(max((p.stem for p in migrations.glob("[0-9]*.py")), default="") == expected,
            f"Expected trusted source with migration {expected}")
    dest.mkdir()
    for package in PACKAGES:
        for path in (source / package).rglob("*.py"):
            relative = path.relative_to(source)
            if "tests" in relative.parts or "__pycache__" in relative.parts:
                continue
            new = dest / relative
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, new)
    # Anchor python-decouple here, before it searches parent directories.
    (dest / ".env").touch()
    (dest / "staticfiles").mkdir()
    (dest / "static").mkdir()


def file_manifest(directory):
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob("*") if p.is_file()}


def restrict_directory(folder):
    if os.name == "nt":
        # An explicit protected DACL also covers all key, archive and media files
        # subsequently created under this fresh directory.
        system32 = Path(os.environ["SystemRoot"]) / "System32"
        env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP") if k in os.environ}
        result = run([system32 / "WindowsPowerShell/v1.0/powershell.exe", "-NoProfile", "-NonInteractive",
                      "-Command", "[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value"],
                     env, folder, "identify rehearsal owner")
        sid = result.stdout.decode("ascii").strip()
        require(sid.startswith("S-1-") and all(c in "0123456789-" for c in sid[2:]), "Unexpected Windows SID")
        run([system32 / "icacls.exe", folder, "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F",
             "*S-1-5-18:(OI)(CI)F"], env, folder, "protect rehearsal files")
    else:
        folder.chmod(0o700)


def assert_database(cursor, folder, database, port):
    cursor.execute("SELECT current_setting('data_directory'), current_database(), "
                   "inet_server_addr(), inet_server_port()")
    data_dir, name, host, actual_port = cursor.fetchone()
    require(Path(data_dir).resolve() == (folder / "cluster").resolve()
            and (name, host, actual_port) == (database, HOST, int(port)),
            "Unexpected PostgreSQL instance")


def django_step(action):
    """Private child entry, in one of the two staged release copies."""
    import django
    from django.conf import settings
    from django.core.management import call_command
    from django.core.management.base import CommandError
    from django.core.files.base import ContentFile
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    from django.test import Client, RequestFactory
    from django.utils import timezone

    folder = Path.cwd().resolve().parent
    require(folder.parent == Path(tempfile.gettempdir()).resolve() and folder.name.startswith(PREFIX),
            "Expected private rehearsal directory")
    require((folder / "owner").read_text() == os.environ["REHEARSAL_OWNER"],
            "Unexpected rehearsal owner")
    django.setup()
    from django.contrib.auth import get_user, get_user_model
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.sessions.models import Session
    from eventproject.models import Attendee, Event, Operator, Request

    database = os.environ["DB_NAME"]
    expected_db = RESTORED_DB if action in ("incompatible", "recover", "rollback-ready") else SOURCE_DB
    require(database == expected_db, "Unexpected rehearsal database name")
    with connection.cursor() as cursor:
        assert_database(cursor, folder, database, os.environ["DB_PORT"])

    def manage(name, *args):
        call_command(name, *args, verbosity=0, stdout=io.StringIO(), stderr=io.StringIO())

    def ready():
        if action in ("seed", "rollback-ready"):
            # The original 0024 release predates check_release_schema.
            executor = MigrationExecutor(connection)
            executor.loader.check_consistent_history(connection)
            graph = executor.loader.graph
            require(graph.leaf_nodes("eventproject") == [("eventproject", PREVIOUS)]
                    and not executor.migration_plan(graph.leaf_nodes()),
                    "Historical release has unapplied or unexpected migrations")
            cache = settings.CACHES["default"]
            require(cache["BACKEND"] == "django.core.cache.backends.db.DatabaseCache"
                    and cache["LOCATION"] in connection.introspection.table_names(),
                    "Historical release is missing its shared cache table")
        else:
            manage("check_release_schema")
        response = Client(HTTP_HOST="localhost").get("/api/health/", secure=True)
        require(response.status_code == 200 and response.json() == {"status": "ok", "db": "ok"},
                "Application readiness failed")

    def session_user(key):
        request = RequestFactory().get("/")
        request.session = SessionStore(session_key=key)
        return get_user(request)

    def media_bytes(index):
        from PIL import Image
        output = io.BytesIO()
        Image.new("RGB", (3, 2), (22, 44, index)).save(output, format="PNG")
        return output.getvalue()

    User = get_user_model()
    fixture_iin = "000000000000"
    if action == "seed":
        manage("migrate", "--noinput")
        manage("createcachetable")
        user = User.objects.create_user("fixture-active", password=os.environ["REHEARSAL_LOGIN"])
        User.objects.create_user("fixture-inactive", is_active=False)
        operator = Operator.objects.create(user=user)
        event = Event.objects.create(name_rus="Rehearsal", date_start=date(2000, 1, 1),
                                     date_end=date(2000, 1, 2))
        operator.events.add(event)
        request = Request.objects.create(name="Fixture", event=event, status="Active",
                                         registration_time=timezone.now(), created_by=operator)
        row = Attendee(iin=fixture_iin, request=request, dateAdd=timezone.now())
        row.photo.save("sample.png", ContentFile(media_bytes(1)), save=False)
        row.docScan.save("sample.png", ContentFile(media_bytes(2)), save=False)
        row.save()
        # Real password authentication on this request exercises the configured backends.
        client = Client()
        require(client.login(username=user.username, password=os.environ["REHEARSAL_LOGIN"],
                             request=RequestFactory().post("/")), "Fixture login failed")
        key = client.session.session_key
        require(Session.objects.count() == 1 and session_user(key).pk == user.pk, "Expected one session")
        (folder / "fixture-session").write_text(key)
        ready()
    elif action == "upgrade":
        from eventproject.models import UserSessionGeneration
        manage("migrate", "--noinput")
        require(UserSessionGeneration.objects.count() == 1
                and UserSessionGeneration.objects.get().user.is_active is False, "0025 seed failed")
        event = Event.objects.get()
        require((event.title, event.start_date, event.end_date)
                == (event.name_rus, event.date_start, event.date_end), "0031 backfill failed")
        # Source-only change gives the rollback a distinguishable point in time.
        Event.objects.create(title="Post-backup sentinel")
        (Path(os.environ["MEDIA_ROOT"]) / "post-backup.bin").write_bytes(b"post-backup")
        ready()
    elif action == "incompatible":
        try:
            manage("check_release_schema")
        except CommandError as exc:
            require(str(exc) == "Release migrations are pending.", "Unexpected readiness failure")
        else:
            raise RuntimeError("Target release accepted the prior schema")
    elif action == "recover":
        require("eventproject_usersessiongeneration" not in connection.introspection.table_names(),
                "Expected the previous schema on the restored database")
        row = Attendee.objects.select_related("request__created_by__user", "request__event").get()
        operator = row.request.created_by
        require((User.objects.count(), Operator.objects.count(), Event.objects.count(),
                 Request.objects.count(), Attendee.objects.count()) == (2, 1, 1, 1, 1)
                and operator.user.username == "fixture-active" and operator.events.get() == row.request.event,
                "Fixture counts or relationships differ")
        event = row.request.event
        require((event.title, event.start_date, event.end_date) == (None, None, None)
                and (event.name_rus, event.date_start, event.date_end)
                == ("Rehearsal", date(2000, 1, 1), date(2000, 1, 2)), "Expected pre-upgrade event fields")
        require(row.iin == fixture_iin, "Restored Fernet keys did not recover the field")
        with connection.cursor() as cursor:
            cursor.execute("SELECT iin FROM eventproject_attendee")
            encoded = bytes(cursor.fetchone()[0])
            require(encoded.startswith(b"gAAAA") and fixture_iin.encode() not in encoded,
                    "Expected ciphertext in PostgreSQL")
        for index, field in enumerate((row.photo, row.docScan), 1):
            with field.open("rb") as handle:
                require(handle.read() == media_bytes(index), "Restored media bytes differ")
        key = (folder / "fixture-session").read_text()
        require(Session.objects.count() == 1 and session_user(key) == operator.user,
                "Restored signing key or original session did not match")
        Session.objects.all().delete()
        require(Session.objects.count() == 0 and not session_user(key).is_authenticated,
                "Old session survived copy-only invalidation")
    elif action == "rollback-ready":
        ready()
        client = Client()
        require(client.login(username="fixture-active", password=os.environ["REHEARSAL_LOGIN"],
                             request=RequestFactory().post("/")), "Fresh rollback login failed")
        require(session_user(client.session.session_key).is_authenticated, "Fresh session invalid")
        client.logout()
        require(Session.objects.count() == 0, "Fresh login cleanup failed")
    else:
        raise ValueError("Unknown rehearsal step")


def rehearse(pg_bin, previous_source, folder):
    import psycopg2
    from psycopg2 import sql
    from cryptography.fernet import Fernet

    target_source = Path(__file__).resolve().parents[1]
    previous, target = folder / "previous", folder / "target"
    stage_release(previous_source, previous, PREVIOUS)
    stage_release(target_source, target, TARGET)
    # Clear inherited app, PostgreSQL and Python configuration. Only harmless OS
    # settings needed to launch trusted binaries are passed through.
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP", "TMPDIR",
                                      "LANG", "LC_ALL") if k in os.environ}
    env["PYTHONIOENCODING"] = "utf-8"
    suffix = ".exe" if os.name == "nt" else ""
    programs = {name: pg_bin / (name + suffix) for name in
                ("pg_ctl", "initdb", "postgres", "pg_dump", "pg_restore")}
    versions = [run([path, "--version"], env, folder, name).stdout.decode().split()[-1]
                for name, path in programs.items()]
    require(len(set(versions)) == 1 and versions[0].startswith("15."), "Require matching PostgreSQL 15 tools")
    with socket.socket() as sock:
        sock.bind((HOST, 0))
        port = sock.getsockname()[1]
    owner = secrets.token_hex(24)
    (folder / "owner").write_text(owner)
    password = secrets.token_urlsafe(36)
    auth = {"dbname": "postgres", "host": HOST, "port": port, "user": ADMIN, "password": password,
            "connect_timeout": 5}
    cluster = folder / "cluster"
    pwfile = folder / "initdb-auth"
    pwfile.write_text(password + "\n", encoding="ascii")
    try:
        run([programs["initdb"], "-D", cluster, "-U", ADMIN, "--auth=scram-sha-256",
             f"--pwfile={pwfile}", "--no-locale", "--encoding=UTF8"], env, folder, "initdb")
    finally:
        pwfile.unlink()
    with (cluster / "postgresql.conf").open("a", encoding="ascii") as config:
        config.write(f"\nlisten_addresses='127.0.0.1'\nport={port}\nunix_socket_directories=''\n")
    storage, restored = folder / "source-files", folder / "restored-files"
    database_backup, media_backup, key_backup = [folder / name for name in
                                                ("backup-database", "backup-media", "backup-keys")]
    for path in (storage, restored, database_backup, key_backup):
        path.mkdir(mode=0o700)
    (storage / "media").mkdir()
    (storage / "keys.json").write_text(json.dumps({
        "SECRET_KEY": secrets.token_urlsafe(52), "FERNET_KEYS": Fernet.generate_key().decode(),
    }))
    fixture_login = secrets.token_urlsafe(32)
    # Older settings require both partner tokens at startup. The rehearsal
    # creates fixtures locally and never contacts the partners.
    partner_env = {name: secrets.token_urlsafe(32) for name in ("AVALON_API_KEY", "KAZENERGY_API_KEY")}

    def step(action, release, db, files):
        child_env = dict(env, **json.loads((files / "keys.json").read_text()),
                         DJANGO_SETTINGS_MODULE="eventproject.settings", ALLOWED_HOSTS="localhost",
                         DB_HOST=HOST, DB_PORT=str(port), DB_NAME=db, DB_USER=ADMIN, DB_PASSWORD=password,
                         MEDIA_ROOT=str(files / "media"), EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                         REHEARSAL_OWNER=owner, REHEARSAL_LOGIN=fixture_login)
        if release == previous:
            child_env.update(partner_env)
        runner = ("import os,runpy,sys;sys.path.insert(0,os.getcwd());"
                  "runpy.run_path(sys.argv[1])['django_step'](sys.argv[2])")
        run([sys.executable, "-I", "-c", runner, Path(__file__).resolve(), action], child_env, release, action)

    def all_counts(database):
        with closing(psycopg2.connect(**dict(auth, dbname=database))) as conn, conn.cursor() as cur:
            assert_database(cur, folder, database, port)
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            counts = {}
            for (name,) in cur.fetchall():
                cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier("public", name)))
                counts[name] = cur.fetchone()[0]
            return counts

    common = ["--host", HOST, "--port", str(port), "--username", ADMIN, "--no-password"]
    client_env = dict(env, PGPASSWORD=password)
    archive = database_backup / "database.dump"
    try:
        run([programs["pg_ctl"], "-D", cluster, "-w", "-l", folder / "postgres.log", "start"],
            env, folder, "start private PostgreSQL")
        with closing(psycopg2.connect(**auth)) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                assert_database(cur, folder, "postgres", port)
                for database in (SOURCE_DB, RESTORED_DB):
                    cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        step("seed", previous, SOURCE_DB, storage)
        baseline = all_counts(SOURCE_DB)
        started = time.monotonic()
        run([programs["pg_dump"], *common, "--format=custom", "--no-owner", "--no-acl",
             "--file", archive, SOURCE_DB], client_env, folder, "pg_dump")
        with archive.open("rb") as handle:
            require(handle.read(5) == b"PGDMP", "Expected custom backup format")
        shutil.copytree(storage / "media", media_backup)
        shutil.copyfile(storage / "keys.json", key_backup / "keys.json")
        media_manifest = file_manifest(storage / "media")
        require(len(media_manifest) == 2 and media_manifest == file_manifest(media_backup),
                "Media backup manifest differs")
        backup_seconds = time.monotonic() - started
        step("upgrade", target, SOURCE_DB, storage)
        upgraded = all_counts(SOURCE_DB)
        require(upgraded["eventproject_event"] == 2 and upgraded["eventproject_usersessiongeneration"] == 1,
                "Expected upgraded source")
        started = time.monotonic()
        require(all_counts(RESTORED_DB) == {}, "Restore requires empty rehearsal copy")
        run([programs["pg_restore"], *common, "--exit-on-error", "--single-transaction", "--no-owner",
             "--no-acl", "--dbname", RESTORED_DB, archive], client_env, folder, "pg_restore")
        require(not any(restored.iterdir()), "Expected empty restored media/key storage")
        shutil.copytree(media_backup, restored / "media")
        shutil.copyfile(key_backup / "keys.json", restored / "keys.json")
        require(all_counts(RESTORED_DB) == baseline, "Restored public-table row counts differ")
        require(file_manifest(restored / "media") == media_manifest, "Restored media manifest differs")
        step("incompatible", target, RESTORED_DB, restored)
        step("recover", previous, RESTORED_DB, restored)
        step("rollback-ready", previous, RESTORED_DB, restored)
        require(all_counts(SOURCE_DB) == upgraded, "Rollback affected upgraded source")
        result = {"postgresql": versions[0], "schema_sequence": [PREVIOUS[:4], TARGET[:4], PREVIOUS[:4]],
                  "archive_bytes": archive.stat().st_size,
                  "tables_with_matching_counts": len(baseline), "rows_at_backup": sum(baseline.values()),
                  "media_files": len(media_manifest),
                  "media_bytes": sum(p.stat().st_size for p in (restored / "media").rglob("*") if p.is_file()),
                  "synthetic_keys_restored": 2, "previous_sessions_invalidated": 1,
                  "fresh_login_checked": True, "prior_upgrade_rollback_readiness_http": [200, 200, 200],
                  "current_code_rejected_restored_0024": True,
                  "backup_seconds": round(backup_seconds, 2),
                  "restore_through_readiness_seconds": round(time.monotonic() - started, 2)}
    finally:
        if (cluster / "postmaster.pid").exists():
            run([programs["pg_ctl"], "-D", cluster, "-m", "fast", "-w", "stop"], env, folder, "stop private PostgreSQL")
        run([programs["pg_ctl"], "-D", cluster, "status"], env, folder, "verify PostgreSQL stopped", expected=(3,))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", required=True, type=Path, help="Trusted PostgreSQL 15 binary directory")
    parser.add_argument("--previous-source", required=True, type=Path, help="Trusted 0024 Django source release")
    args = parser.parse_args()
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix=PREFIX) as private:
        directory = Path(private).resolve()
        restrict_directory(directory)
        outcome = rehearse(args.pg_bin.resolve(), args.previous_source.resolve(), directory)
    print(json.dumps(dict(outcome, private_cluster_stopped=True, temporary_directory_removed=True), indent=2))
