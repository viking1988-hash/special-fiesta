"""Actual login ACL checks in loopback crm_test_* DB, no production connection."""
import os
import subprocess

ROLE = 'crm_clients_backup_reader'


def test_permissions(db):
    if not db.startswith('crm_test_') or os.environ.get('PGHOST') != '127.0.0.1':
        raise RuntimeError('ROLE_TEST_ISOLATION_REQUIRED')
    env = dict(os.environ, PGUSER=ROLE, PGOPTIONS='-c default_transaction_read_only=off')

    def query(sql, *, forbidden=False):
        result = subprocess.run(['psql', '-X', '-d', db, '-v', 'ON_ERROR_STOP=1',
                                 '-v', 'VERBOSITY=verbose', '-Atqc', sql], env=env,
                                capture_output=True, text=True, timeout=20)
        if forbidden:
            if result.returncode == 0 or '42501' not in result.stderr:
                raise RuntimeError('READER_FORBIDDEN_OPERATION_NOT_DENIED')
            return
        if result.returncode:
            raise RuntimeError('READER_ALLOWED_READ_FAILED')
        return result.stdout.strip()

    if query('SELECT current_user') != ROLE:
        raise RuntimeError('READER_LOGIN_IDENTITY_MISMATCH')
    if query('SELECT count(*) FROM customers') != '2' or query('SELECT count(*) FROM vehicles') != '3':
        raise RuntimeError('READER_COUNTS_MISMATCH')
    for table in ('customers', 'vehicles'):
        query('SELECT last_value,is_called FROM public.' + table + '_id_seq')
        for sql in ('UPDATE public.'+table+' SET id=id WHERE false',
                    'DELETE FROM public.'+table+' WHERE false',
                    'TRUNCATE public.'+table,
                    'ALTER TABLE public.'+table+' ADD COLUMN forbidden_test integer',
                    'DROP TABLE public.'+table,
                    "SELECT nextval('public."+table+"_id_seq')",
                    "SELECT setval('public."+table+"_id_seq',99999)"):
            query(sql, forbidden=True)
    query("INSERT INTO customers(organization_id,name,phone) VALUES(1,'ARTIFICIAL FORBIDDEN','+70000000999')", forbidden=True)
    query("INSERT INTO vehicles(organization_id,make,model) VALUES(1,'ARTIFICIAL','FORBIDDEN')", forbidden=True)
    for table in ('organizations', 'bookings', 'work_orders', 'customer_contact_events'):
        query('SELECT count(*) FROM public.' + table, forbidden=True)
    query('CREATE TABLE public.forbidden_test(id int)', forbidden=True)
    query('CREATE ROLE forbidden_role', forbidden=True)
    query('SET ROLE postgres', forbidden=True)
    # Enabling transaction writes is deliberate: ACLs, not a mutable default GUC,
    # must protect real data and sequence state.
    print('READER_ROLE_ACL_OK login=reader tables_select=2 sequences_select=2 writes=DENIED deletes=DENIED ddl=DENIED nextval=DENIED setval=DENIED other_crm_tables=DENIED escalation=DENIED readonly_default_overridden_for_test=YES', flush=True)


if __name__ == '__main__':
    import sys
    try:
        test_permissions(sys.argv[1])
    except Exception:
        raise SystemExit('READER_PERMISSION_TEST_FAILED')
