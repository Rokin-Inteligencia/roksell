# Backup/DR

Este documento define um basico de backup e recovery (DR) para banco e midia.

## Escopo
- Banco de dados (PostgreSQL).
- Midias no Object Storage (Oracle / S3-compat).

## Objetivos (ajuste conforme necessidade)
- RPO (perda maxima aceitavel de dados): 24h.
- RTO (tempo maximo de recuperacao): 4h.

## Backup do banco (manual)
Requisitos:
- `pg_dump` instalado na maquina que executa o backup.
- `DATABASE_URL` definido no ambiente (ou em `roksell-backend/.env`).

Executar:
```
python roksell-backend/scripts/backup_db.py
```

Saida:
- Arquivo `db-YYYYMMDD-HHMMSS.dump` em `roksell-backend/backups/` (por padrao).

### Upload opcional para bucket
Se quiser enviar o backup para Object Storage, defina:
- `BACKUP_S3_BUCKET` (bucket destino)
- `BACKUP_S3_PREFIX` (opcional, default: `backups/db`)
- `S3_ENDPOINT_URL`, `S3_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

## Restore do banco (DR)
Requisitos:
- `pg_restore` instalado.
- `DATABASE_URL` apontando para o banco alvo.

Executar:
```
python roksell-backend/scripts/restore_db.py --backup <arquivo.dump> --confirm
```

Observacoes:
- O restore usa `--clean --if-exists` e sobrescreve dados do banco alvo.
- Teste primeiro em homolog antes de executar em producao.

## Midias (Object Storage)
Recomendado:
- Habilitar versionamento do bucket.
- Replicacao para bucket secundario (ou copia agendada).
- Politica de retencao para evitar crescimento infinito.

## Rotina sugerida
- Backup diario do banco.
- Retencao local curta (ex: 7 dias) e copia no bucket (ex: 30-90 dias).
- Teste de restore mensal em homolog.


