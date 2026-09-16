# Teste formal de restauração

A restauração deve ocorrer somente em um PostgreSQL separado, descartável e
sem tráfego de produção. Nunca defina `RESTORE_DATABASE_URL` igual a
`DATABASE_URL`.

## Procedimento

1. Provisione um banco temporário com a mesma versão principal do PostgreSQL.
2. Configure `RESTORE_DATABASE_URL` para esse banco e mantenha
   `DATABASE_URL` apontando para produção apenas como referência.
3. Escolha um arquivo gerado por `backup.py`.
4. Execute:

```bash
RESTORE_DATABASE_URL='postgresql://usuario:senha@host:5432/restore' \
DATABASE_URL='postgresql://usuario:senha@host:5432/producao' \
python verify_restore.py --file backups/backup_escola_YYYYMMDD_HHMMSS.sql
```

O script usa `ON_ERROR_STOP`, falha no primeiro erro SQL e confirma que
existem tabelas no schema público. Registre data, backup, commit e contagem
de tabelas no histórico operacional. O banco temporário deve ser destruído
após a validação.

## Frequência mínima

- backup: diário;
- teste de restauração: mensal e após mudanças de migration;
- retenção dos logs do teste: conforme a política de auditoria.
