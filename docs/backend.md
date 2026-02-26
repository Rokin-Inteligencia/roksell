# Backend - Arquitetura e Operacao

## 1. Stack e Runtime

- Linguagem: Python 3.12
- Framework: FastAPI
- ORM: SQLAlchemy 2.x
- Migracao: Alembic
- Banco: PostgreSQL
- Servidor ASGI: Uvicorn
- Dependencias relevantes:
  - `python-jose`, `passlib[bcrypt]` (auth)
  - `httpx` (integracoes HTTP)
  - `redis` (rate limit distribuido opcional)
  - `boto3` (storage S3 opcional)
  - `pywebpush` (notificacoes push)
  - `googlemaps` (distancia de frete)

Entrypoint: `app/main.py`

## 2. Bootstrap da Aplicacao

### 2.1 Middlewares ativos

Ordem logica:

1. `TrustedHostMiddleware` (quando `TRUSTED_HOSTS` configurado)
2. `CORSMiddleware`
3. `SecurityHeadersMiddleware`
4. `RequestLoggingMiddleware`
5. `RateLimitMiddleware`

### 2.2 Rotas carregadas

Principais routers registrados:

- publico: `/health`, `/catalog`, `/stores`, `/shipping`, `/checkout`, `/orders`
- auth: `/auth/*`
- admin tenant: `/admin/*` (catalogo, pedidos, config, campanhas, estoque, lojas, usuarios, grupos, insights, billing, whatsapp)
- admin central: `/admin/central/*`
- webhooks: `/billing/webhook/*`, `/webhooks/whatsapp/*`

### 2.3 Startup task

No startup e criada task assincrona de limpeza de midia WhatsApp:

- `run_whatsapp_media_cleanup_loop`

## 3. Configuracao de Ambiente

Classe central: `app/db.py -> Settings`.

Variaveis principais:

- banco: `DATABASE_URL`
- auth: `AUTH_SECRET`, `AUTH_SECRET_PREVIOUS`, `AUTH_SECRETS`, `AUTH_ALGORITHM`
- sessao: `ACCESS_TOKEN_EXPIRE_MINUTES`, `ADMIN_SESSION_EXPIRE_MINUTES`
- webhook billing: `BILLING_WEBHOOK_SECRET`, `BILLING_WEBHOOK_SECRETS`
- tracking pedido: `ORDER_TRACKING_SECRET`
- cors e hosts: `CORS_ALLOWED_ORIGINS`, `TRUSTED_HOSTS`
- rate limit: `RATE_LIMIT_REDIS_URL` ou `REDIS_URL`
- storage: `STORAGE_BACKEND` + vars S3
- whatsapp/telegram/webpush: varias (`WHATSAPP_*`, `TELEGRAM_*`, `WEB_PUSH_*`)

Observacao: `AUTH_SECRET` e segredos de webhook exigem tamanho minimo validado.

## 4. Tenancy

Arquivo chave: `app/tenancy.py`.

Comportamento:

- resolve tenant por:
  - `X-Tenant-Id`
  - `X-Tenant` (slug)
  - fallback tenant legado
- monta `TenantContext` com:
  - `id`, `slug`, `name`
  - `subscription_status`
  - `modules`
  - `users_limit`, `stores_limit`

Regra de assinatura:

- se assinatura nao estiver em `active` ou `trialing`, modulos ficam vazios.

## 5. Auth, Sessao e Autorizacao

## 5.1 JWT e senha

- hash de senha: `bcrypt_sha256` (aceita fallback bcrypt legado)
- token JWT contem:
  - `sub` (user id)
  - `tenant_id`
  - `role`
  - `sid` (session id)

## 5.2 Sessao server-side

Tabela: `user_sessions`.

Fluxo:

- login cria sessao com TTL configuravel
- cada request autenticado valida sessao ativa
- logout revoga sessao (`revoked_at`, `revoked_reason`)
- limite de sessoes por usuario (`max_active_sessions`) com corte automatico

## 5.3 Guards

Dependencias em `app/auth/dependencies.py`:

- `get_current_user`
- `require_roles(...)`
- `require_module(module_key)`
- `require_module_action(module_key, action)`

## 5.4 Cookies

Login grava cookie `admin_token`:

- `HttpOnly`
- `Secure=true` no backend
- `SameSite=lax`

## 6. Mapa de Endpoints por Contexto

## 6.1 Publico

- `GET /catalog`: catalogo por loja
- `GET /stores`: lista lojas ativas
- `POST /shipping/quote`: cotacao de frete
- `POST /checkout/preview`: simulacao de pedido
- `POST /checkout`: cria pedido
- `GET /orders`: lista pedidos (autenticado)
- `GET /orders/{order_id}`: detalhe (autenticado ou token publico)

## 6.2 Auth

- `POST /auth/signup`: bootstrap do primeiro usuario do tenant
- `POST /auth/login`: autenticacao e criacao de sessao
- `GET /auth/me`: usuario atual
- `POST /auth/logout`: revoga sessao atual

## 6.3 Portal/Admin tenant (`/admin/*`)

Blocos:

- pedidos e operacao: `/admin/orders/*`
- catalogo/produtos/adicionais: `/admin/catalog/*`
- configuracoes operacionais: `/admin/config`
- clientes: `/admin/customers/*`
- campanhas: `/admin/campaigns/*`
- lojas e frete por faixa: `/admin/stores/*`, `/admin/shipping/*`
- estoque: `/admin/inventory/*`
- usuarios e grupos: `/admin/users/*`, `/admin/groups/*`
- insights: `/admin/insights`
- billing tenant: `/admin/billing/*`
- whatsapp operacional: `/admin/whatsapp/*`
- onboarding: `/admin/onboarding/*`
- modulos visiveis ao usuario: `/admin/modules`

## 6.4 Admin central SaaS (`/admin/central/*`)

Capacidades:

- dashboard consolidado
- CRUD de tenants
- definicao de limites (`users_limit`, `stores_limit`)
- gestao de modulos por tenant
- CRUD de planos
- atribuicao de plano por tenant
- configuracao de mensageria por tenant
- CRUD de usuarios em tenant especifico
- habilitar modo teste de primeiro acesso por tenant

Acesso restrito a owner do tenant super admin.

## 6.5 Webhooks

- Billing:
  - `POST /billing/webhook/status`
  - `POST /billing/webhook/intake`
  - assinatura HMAC obrigatoria via `X-Signature`
- WhatsApp:
  - `GET /webhooks/whatsapp` e `GET /webhooks/whatsapp/{tenant_slug}` (challenge)
  - `POST /webhooks/whatsapp` e `POST /webhooks/whatsapp/{tenant_slug}` (eventos)

## 7. Servicos de Dominio Relevantes

- `services/subscriptions.py`: aplica plano e sincroniza `tenant_modules`
- `services/shipping_distance.py`: calcula distancia via Google Maps com fallback Haversine/Nominatim
- `services/user_sessions.py`: ciclo de vida de sessao
- `services/whatsapp.py`: envio outbound, janela de conversa, mensagens de status
- `services/webpush.py`: push para mensagens e novos pedidos
- `services/whatsapp_media_cleanup.py`: saneamento de midias antigas/invalidas

## 8. Storage e Midia

Abstracao em `app/storage.py`:

- modo `local`:
  - grava em `MEDIA_ROOT`
  - exposto em `/media` quando local storage
- modo `s3`:
  - grava em bucket via boto3
  - suporta endpoint S3 compativel (OCI, MinIO, etc)

Upload com validacao de tipo e assinatura binaria:

- imagem produto/campanha/loja: max 5 MB
- video produto: max 20 MB

## 9. Regras de Negocio Criticas no Checkout

No `POST /checkout`:

1. valida loja e disponibilidade
2. valida pre-order quando loja fechada
3. valida telefone e cliente
4. valida endereco e CEP para entrega
5. calcula/revalida frete
6. calcula subtotal e campanhas
7. reserva estoque com lock
8. cria pedido, itens, pagamento e entrega
9. envia notificacoes

Protecoes relevantes:

- frete pode ser recalculado no backend; divergencia invalida pedido
- itens indisponiveis bloqueiam venda
- baixa de estoque usa `with_for_update`

## 10. Scripts Operacionais

Diretorio `scripts/`:

- `seed.py`: dados iniciais (tenant, modulos, plano, produtos demo)
- `import_customers.py`, `import_products.py`, `import_orders.py`
- `normalize_customers_phone.py`, `merge_customer_conflicts.py`
- `backup_db.py`, `restore_db.py`

## 11. Migracoes

- Alembic configurado para ler `DATABASE_URL` do settings.
- Convencao atual de historico: nomes em ingles, com prefixos por data/revisao.
- Migrations cobrem tenancy, auth, billing, catalogo expandido, configuracoes operacionais, estoque, whatsapp e sessoes.

## 12. Logging e Observabilidade Atual

`RequestLoggingMiddleware` registra JSON com:

- `request_id`
- metodo/path/status
- `duration_ms`
- tenant e IP de cliente

Limitacoes atuais:

- sem tracing distribuido
- sem metricas Prometheus
- sem auditoria detalhada de acoes administrativas

## 13. Como Adicionar Endpoint Novo (Padrao)

1. Definir schema em `app/schemas.py`.
2. Implementar endpoint em router de dominio apropriado.
3. Aplicar dependencias:
   - tenant
   - role
   - modulo/acao quando aplicavel
4. Garantir filtro por `tenant_id` em queries.
5. Tratar erros com `HTTPException` clara.
6. Atualizar documentacao.
