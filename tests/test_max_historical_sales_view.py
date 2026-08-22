from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from unittest.mock import patch


def load_migration() -> ModuleType:
    path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20260821_0013_create_max_historical_sales_view.py"
    )
    spec = spec_from_file_location("max_historical_sales_view", path)
    assert spec is not None
    assert spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_migration_creates_grouped_max_historical_sales_view() -> None:
    migration = load_migration()

    with patch.object(migration.op, "execute") as execute:
        migration.upgrade()

    statements = [str(call.args[0]) for call in execute.call_args_list]
    create_view = statements[0]
    assert 'CREATE VIEW "public"."vst_max_vta_historica" AS' in create_view
    assert "MAX(qty_vendida) AS max_qty_vendida" in create_view
    assert 'FROM "public"."lacteos_ventas_historicas"' in create_view
    assert "GROUP BY item, location" in create_view
    assert (
        statements[1]
        == 'ALTER VIEW "public"."vst_max_vta_historica" OWNER TO "smartadmin"'
    )


def test_migration_drops_only_the_view_on_downgrade() -> None:
    migration = load_migration()

    with patch.object(migration.op, "execute") as execute:
        migration.downgrade()

    statement = str(execute.call_args.args[0])
    assert statement == 'DROP VIEW IF EXISTS "public"."vst_max_vta_historica"'
