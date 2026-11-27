from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = "Verify release migrations and the shared database cache without changing the database."

    def handle(self, *args, **options):
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise CommandError("Release migrations are pending.")
        cache = settings.CACHES["default"]
        if cache["BACKEND"] == "django.core.cache.backends.db.DatabaseCache":
            if cache["LOCATION"] not in connection.introspection.table_names():
                raise CommandError("The shared cache table is missing.")
        self.stdout.write("Release schema is ready.")
