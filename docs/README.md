# Documentacao Tecnica - Sistema Restaurante

Este diretorio centraliza a documentacao operacional e de arquitetura do projeto.
Todo conteudo foi escrito para permitir continuidade por qualquer IA ou pessoa sem contexto previo.

## 1. Ordem Recomendada de Leitura

1. `../ARCHITECTURE.md`
2. `AI_HANDOFF.md`
3. `backend.md`
4. `database.md`
5. `frontend.md`
6. `development-standards.md`
7. `security.md`
8. `performance.md`

## 2. Objetivo de Cada Documento

- `AI_HANDOFF.md`: contexto de entrada rapido para agentes de IA.
- `backend.md`: stack, rotas, servicos e fluxo de negocio no backend.
- `database.md`: tabelas, relacoes, tenancy e migracoes.
- `frontend.md`: arquitetura Next.js, proxies, guardas e padrao de UI.
- `development-standards.md`: padroes obrigatorios de implementacao.
- `security.md`: controles atuais, riscos e backlog de hardening.
- `performance.md`: gargalos, metricas alvo e plano de melhoria.

## 3. Setup Rapido (Local)

### Backend

```powershell
cd roksell-backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```powershell
cd roksell-frontend
npm ci
npm run dev
```

## 4. Variaveis de Ambiente (Resumo)

Nao versionar segredos. Usar `.env` local e secret manager no deploy.

Grupos principais:

- Backend core: `DATABASE_URL`, `AUTH_SECRET`, `AUTH_SECRET_PREVIOUS`, `AUTH_SECRETS`
- Sessao/auth: `ACCESS_TOKEN_EXPIRE_MINUTES`, `ADMIN_SESSION_EXPIRE_MINUTES`, `AUTH_ALGORITHM`
- CORS/host: `CORS_ALLOWED_ORIGINS`, `TRUSTED_HOSTS`
- Billing webhook: `BILLING_WEBHOOK_SECRET`, `BILLING_WEBHOOK_SECRETS`
- Storage: `STORAGE_BACKEND`, `S3_BUCKET`, `S3_REGION`, `S3_ENDPOINT_URL`, `S3_PUBLIC_BASE_URL`
- Rate limit: `RATE_LIMIT_REDIS_URL` ou `REDIS_URL`
- WhatsApp: `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_WEBHOOK_VERIFY_TOKEN`
- Web push: `WEB_PUSH_PUBLIC_KEY`, `WEB_PUSH_PRIVATE_KEY`, `WEB_PUSH_SUBJECT`
- Frontend: `API_URL`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_TENANT_SLUG`, `NEXT_PUBLIC_SUPER_ADMIN_SLUG`

## 5. CI Atual

Arquivo: `.github/workflows/ci.yml`

- Backend: install deps + `python -m compileall`
- Frontend: `npm ci`, `npm run lint`, `npm run build`

Observacao: nao ha pipeline de testes automatizados hoje.

