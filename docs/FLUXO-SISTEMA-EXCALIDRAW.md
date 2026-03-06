# Fluxo do Sistema – Documento Excalidraw

Este diretório contém o diagrama **fluxo-sistema-roksell.excalidraw** com a visão completa do sistema Roksell.

## Conteúdo do diagrama

1. **Visão geral da topologia**  
   Browser → Next.js (BFF) → FastAPI → PostgreSQL, incluindo Redis, Storage, Maps, WhatsApp, Telegram, Web Push.

2. **Pontos de segurança**  
   - Resolução de tenant (`X-Tenant-Id` / `X-Tenant`).  
   - Auth: JWT + cookie `admin_token` (HttpOnly, SameSite=lax).  
   - Sessão server-side (`user_sessions`), revogação no logout.  
   - RBAC (owner, manager, operator) + módulo e ação (view/edit).  
   - Rate limit (login, signup, checkout, shipping/quote).  
   - Webhooks: HMAC (billing), challenge (WhatsApp).  
   - Headers de segurança (HSTS, X-Content-Type-Options, etc.).  
   - Upload: whitelist MIME + assinatura binária + limite de tamanho.

3. **Chamadas de requisições (Front → Back)**  
   - **Auth:** `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`.  
   - **Proxy admin:** `/api/admin/[...path]` (repassa para FastAPI com cookie).  
   - **Público:** `/api/catalog`, `/api/stores`, `/api/shipping`, `/api/checkout`, `/api/checkout/preview`.  
   - Next.js nunca expõe o backend direto ao browser nas rotas admin; o BFF usa o cookie e repassa.

4. **Comunicação Back–Front**  
   - Front chama apenas o próprio host (Next.js).  
   - Next.js route handlers fazem `fetch` ao backend (`API_URL` em server).  
   - Browser usa `NEXT_PUBLIC_API_URL` apenas para rotas públicas (ex.: vitrine/checkout) quando aplicável.  
   - Admin/portal: sempre `adminFetch`/`adminUpload` → `/api/admin/*` (credentials: include).  
   - Respostas JSON; erros tratados com mensagem e status HTTP.

5. **Fluxos por área**  
   - **Vitrine:** páginas estáticas/SSR + `GET /api/catalog`, `GET /api/stores`.  
   - **Checkout:** catalog + stores → preview → shipping/quote → `POST /checkout` (pedido + notificações).  
   - **Portal:** login → auth/me + guards → módulos (pedidos, catálogo, lojas, etc.) via `/api/admin/*`.  
   - **Admin central:** super admin → `/api/admin/central/*` (tenants, planos, dashboard).  
   - **Rastreio:** `/pedido/[id]?token=...` → `GET /orders/{id}` com validação HMAC.

## Como abrir

- Instale a extensão **Excalidraw** no Cursor/VS Code (ou use [excalidraw.com](https://excalidraw.com) e importe o arquivo).  
- Abra o arquivo **fluxo-sistema-roksell.excalidraw** neste diretório.

## Manutenção

- Ao alterar arquitetura, segurança ou rotas, atualize o diagrama e este README.  
- Consulte `ARCHITECTURE.md`, `docs/backend.md`, `docs/frontend.md` e `docs/security.md` para detalhes técnicos.
