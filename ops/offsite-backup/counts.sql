-- Row counts per table, taken right after a backup. restore_verify.sh compares a restored copy against these.
select 'alembic=' || version_num from alembic_version;
select table_name || '=' || (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from public.%I', table_name), false, true, '')))[1]::text
from information_schema.tables
where table_schema = 'public' and table_type = 'BASE TABLE'
order by table_name;
