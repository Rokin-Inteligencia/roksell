# Roksell SaaS â€” Contexto Atual

## Objetivo
- Plataforma SaaS multi-tenant para restaurantes; mÃ³dulos: online orders, delivery, financeiro, estoque, insights, fidelidade. Painel admin e portal do cliente por tenant.

## Backend (FastAPI + SQLAlchemy + Alembic)
- DomÃ­nios: tenancy (Tenant, TenantModule, User), catalog (Category, Product), customer, order (Order/OrderItem/Payment/Delivery), shipping, config, billing (Module/Plan/Subscription), core enums (OrderStatus, PaymentMethod/Status, DeliveryStatus, TenantStatus, UserRole), insights.
- Tenancy via headers `X-Tenant-Id`/`X-Tenant`; fallback legado. `TenantContext` injeta assinatura e mÃ³dulos ativos.
- Auth/RBAC: JWT+bcrypt; deps `get_current_user`, `require_roles` (owner/manager/operator); rotas `/auth/signup` (primeiro usuÃ¡rio), `/auth/login`.
- Billing/feature flags: `services/subscriptions.py`, webhook `/billing/webhook/status`.
- Rotas admin: `/admin`, `/admin/users`, `/admin/catalog`, `/admin/config`, `/admin/billing`, `/admin/insights`. PÃºblico: `/catalog`, `/checkout`, `/shipping/quote`, `/health`.
- Insights: `/admin/insights` soma pagamentos pendentes+confirmados (faturamento dia/semana/mÃªs) e quebra por categoria/produto.
- Migrations em inglÃªs; seed cria tenant legado, plano Starter, mÃ³dulos `online_orders`/`delivery`, produtos demo e admin opcional (`DEFAULT_ADMIN_EMAIL/PASSWORD`). Scripts de import: `import_customers.py`, `import_products.py`, `import_orders.py`.

## Frontend (Next.js + TS)
- Paleta â€œcactusâ€: PrimÃ¡rias `#4D774E`, `#9DC88D`; SecundÃ¡rias `#164A41`, `#F1B24A`, `#FFFFFF`.
- PÃºblico: `/` catÃ¡logo; `/checkout` com proxies `/api/shipping` -> backend `/shipping/quote`; `/api/checkout` -> backend `/checkout`.
- Admin:
  - Login `/admin/login`, token em `localStorage` (`admin_token`), redireciona para `/admin`; guardas `useAdminGuard`.
  - Layout desktop com sidebar flutuante (menus: Insights, Pedidos, Clientes, Produtos, Campanhas, Estoque, Loja, UsuÃ¡rios â€” mÃ³dulos nÃ£o implementados marcados â€œEm breveâ€).
  - KPIs principais no topo (faturamento/pedidos/ticket), central operacional com widgets (pedidos em atraso, entregas, estoque crÃ­tico, campanhas) placeholders.
  - MÃ³dulos ativos: `/admin/insights`, `/admin/catalog` (CRUD/ediÃ§Ã£o), `/admin/config` (SLA/delivery), `/admin/billing`.

## Estado do Banco
- Schema multi-tenant aplicado; tabelas `users`, `subscriptions`, `tenant_modules` ativas; imports de clientes, produtos e pedidos realizados para o tenant legado.

## PrÃ³ximos Passos (prioridade)
1) SeguranÃ§a/Auth: refresh tokens, MFA opcional, rate limiting, audit log, tokens fora do localStorage (cookies httpOnly).  
2) RBAC/mÃ³dulos: expor mÃ³dulos/roles no JWT, esconder menus pelo plano; implementar Pedidos/Clientes/UsuÃ¡rios/Campanhas/Estoque/Loja.  
3) Billing real: integrar provedor (Stripe/Iugu), suspensÃ£o automÃ¡tica, reconciliaÃ§Ã£o.  
4) Observabilidade: logs estruturados com tenant/user, tracing (OTel), mÃ©tricas/alertas.  
5) Dados/import: validar categorias/produtos ao importar, reprocessar itens pulados, relatÃ³rios de inconsistÃªncia.  
6) Infra: backups testados, fila para jobs pesados, CDN/caching.  
7) UX: ligar KPIs/insights a APIs reais; i18n (PT padrÃ£o, EN opcional).  

