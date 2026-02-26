# Relatorio de Rename - biscotti -> roksell

Data: 2026-02-25

## Escopo executado

- Revisao global de referencias a `biscotti`, `biscotti-api` e `biscotti-web`.
- Rename aplicado para `roksell`, `roksell-backend` e `roksell-frontend` em codigo e documentacao.
- Atualizacao de CI e metadados do frontend.

## Alteracoes aplicadas

### 1. Arquitetura e documentacao principal

- `ARCHITECTURE.md`
  - `biscotti-api` -> `roksell-backend`
  - `biscotti-web` -> `roksell-frontend`
- `docs/README.md`
  - comandos de setup atualizados para `cd roksell-backend` e `cd roksell-frontend`
- `docs/AI_HANDOFF.md`
  - mapa rapido do workspace atualizado para `roksell-backend` e `roksell-frontend`
- `docs/frontend.md`
  - base do frontend atualizada para `roksell-frontend/src`
- `docs/database.md`
  - caminho de migrations atualizado para `roksell-backend/alembic/versions`
- `BACKUP_DR.md`
  - comandos e paths atualizados para `roksell-backend/...`

### 2. Pipeline de CI

- `.github/workflows/ci.yml`
  - `cache-dependency-path`, `working-directory` e `compileall` atualizados:
    - `biscotti-api` -> `roksell-backend`
    - `biscotti-web` -> `roksell-frontend`

### 3. Backend

- `roksell-backend/WHATSAPP_SETUP.md`
  - referencia de `.env` atualizada para `roksell-backend`
- `roksell-backend/app/services/shipping_distance.py`
  - User-Agent de fallback atualizado para `roksell-backend/1.0`

### 4. Frontend

- `roksell-frontend/package.json`
  - `"name": "roksell-frontend"`
- `roksell-frontend/package-lock.json`
  - nome do pacote raiz atualizado para `roksell-frontend`
- `roksell-frontend/src/app/portal/insights/page.tsx`
  - nomes de lojas mock alterados de `Biscotti - ...` para `Roksell - ...`
- `roksell-frontend/SAAS_RISKS.md`
  - titulo ajustado para `Roksell SaaS`

### 5. Documento de contexto do projeto

- `PROJECT_PROMPT.md`
  - titulo ajustado para `Roksell SaaS`

### 6. Ajustes locais adicionais (executado apos confirmacao)

- Remotes Git atualizados:
  - `roksell-backend/.git/config`
    - `origin` alterado para `https://github.com/oMatheussch/roksell-backend.git`
  - `roksell-frontend/.git/config`
    - `origin` alterado para `https://github.com/oMatheussch/roksell-frontend.git`
- Migracao de midia local (compativel):
  - origem: `roksell-backend/uploads/tenants/Biscotti`
  - destino: `roksell-backend/uploads/tenants/roksell`
  - estrategia: copia (nao destrutiva), mantendo `Biscotti` para compatibilidade com URLs antigas
- Ambiente virtual do backend recriado:
  - `.venv` renomeada para backup local temporario
  - nova `.venv` criada em `roksell-backend/.venv`
  - dependencias reinstaladas via `pip install -r requirements.txt`
  - `activate.bat` validado com:
    - `set VIRTUAL_ENV=C:\\Users\\matis\\Documents\\roksell\\roksell-backend\\.venv`

## Validacao realizada

- Busca global sem exclusoes em arquivos versionaveis:
  - nenhuma ocorrencia restante de `biscotti-api`, `biscotti-web`, `biscotti` ou `Biscotti` fora de artefatos locais.

## Pendencias residuais (nao alteradas propositalmente)

- Metadados locais Git historicos:
  - `roksell-backend/.git/FETCH_HEAD`
  - `roksell-frontend/.git/FETCH_HEAD`
  - podem manter referencias antigas ate novo `git fetch`
- Ambiente virtual local:
  - pasta de backup da venv antiga pode permanecer localmente (`.venv_old_20260225`) se nao for removida manualmente.
- Midias locais:
  - pasta `roksell-backend/uploads/tenants/Biscotti` foi mantida propositalmente para compatibilidade retroativa.

Motivo de nao alteracao automatica:
- itens acima sao artefatos locais/dados e podem exigir migracao coordenada (ex.: ajuste de remote, recriacao de venv, migracao de paths de midia em banco).
