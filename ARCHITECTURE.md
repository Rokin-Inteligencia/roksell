# Sistema Restaurante - Arquitetura Tecnica

Documento atualizado em 2026-02-25.
Objetivo: servir como base de handoff tecnico para qualquer pessoa ou IA continuar evolucoes sem contexto previo.

## 1. Visao Geral

O sistema e um SaaS multi-tenant para operacao digital de restaurantes, com:

- vitrine publica por tenant e por loja
- checkout com calculo de frete e criacao de pedidos
- portal operacional para time do restaurante
- admin central para operacao SaaS (tenants, planos, modulos e usuarios)
- integracoes de mensageria (WhatsApp, Telegram, push web)

Workspace:

- `roksell-backend`: backend FastAPI + SQLAlchemy + Alembic
- `roksell-frontend`: frontend Next.js App Router + TypeScript

## 2. Topologia de Execucao

```text
[Browser]
   |\
   | \-- paginas Next.js (SSR/CSR)
   |
   +----> route handlers Next.js (/api/*) ----> FastAPI

[FastAPI]
   +---- PostgreSQL (core transacional)
   +---- Redis opcional (rate limit distribuido)
   +---- Storage local ou S3/OCI (midia)
   +---- Google Maps + Nominatim (frete por distancia)
   +---- WhatsApp Cloud API
   +---- Telegram Bot API
   +---- Web Push (VAPID)
```

## 3. Decisoes Arquiteturais Principais

### 3.1 Multi-tenant por chave de aplicacao

- Tenant resolvido por `X-Tenant-Id` ou `X-Tenant`.
- Quase todas as tabelas de dominio possuem `tenant_id`.
- `TenantContext` injeta tenant, status de assinatura, limites e modulos ativos.
- Existe fallback para tenant legado.

### 3.2 Seguranca de acesso em 2 niveis

- Nivel 1: role (`owner`, `manager`, `operator`).
- Nivel 2: modulo e acao (`view`/`edit`) com permissao por grupo.

### 3.3 Sessao revogavel em banco

- JWT inclui `sid`.
- Validade de sessao consultada em `user_sessions`.
- Logout revoga sessao no servidor.

### 3.4 BFF leve no frontend

- Next.js route handlers concentram autenticacao por cookie e proxy para backend.
- Browser nao precisa conhecer detalhes de auth do backend para rotas admin.

## 4. Fluxos Criticos

### 4.1 Login portal/admin

1. Front chama `/api/auth/login`.
2. Next encaminha para `/auth/login` no backend.
3. Backend valida credenciais, cria sessao, gera JWT.
4. Next grava cookies `admin_token` (HttpOnly) e `tenant_slug`.
5. Paginas protegidas usam `/api/auth/me` + hooks de guard.

### 4.2 Checkout

1. Front carrega catalogo e lojas.
2. Front calcula preview (`/checkout/preview`) e frete (`/shipping/quote`).
3. Front cria pedido (`/checkout`).
4. Backend valida tenant/loja/estoque/frete/campanha e grava pedido.
5. Backend dispara notificacoes (push + Telegram) e devolve token de rastreio.

### 4.3 Rastreio publico de pedido

1. Cliente abre `/pedido/{id}?tenant=...&token=...`.
2. Front chama `/orders/{id}`.
3. Backend valida HMAC (`order_id + phone`) do tracking token.
4. Retorna status, entrega, pagamento e itens.

### 4.4 Mensageria WhatsApp inbound

1. Meta chama `/webhooks/whatsapp`.
2. Backend resolve tenant por slug ou `phone_number_id`.
3. Mensagens inbound e conversas sao persistidas.
4. Tela de mensagens no portal e alimentada por `/admin/whatsapp/*`.

### 4.5 Admin central SaaS

1. Usuario owner do tenant super admin acessa `/admin`.
2. Front chama `/admin/central/*`.
3. Backend permite criar tenant, editar limites, plano, modulos e usuarios.

## 5. Estrutura do Codigo

### Backend (`roksell-backend`)

- `app/main.py`: bootstrap FastAPI e middlewares
- `app/routers/`: endpoints por dominio
- `app/domain/`: modelos e regras de dominio
- `app/services/`: integracoes externas e casos de uso
- `alembic/`: migracoes de banco
- `scripts/`: seed, importacoes e backup/restore

### Frontend (`roksell-frontend`)

- `src/app/`: paginas App Router e APIs internas (`/api/*`)
- `src/components/`: componentes compartilhados
- `src/lib/`: clientes HTTP, auth helper e hooks
- `src/store/`: estado global (carrinho)
- `src/config/`: configuracoes de menu e navegacao

## 6. Qualidade Arquitetural Atual

Fortes:

- separacao clara frontend/backend
- tenancy consistente no backend
- RBAC + modulo por assinatura
- sessao server-side revogavel
- upload com validacao de assinatura de arquivo

Pontos de melhoria:

- ausencia de fila dedicada para jobs assincronos
- ausencia de trilha de auditoria de alto detalhe
- ausencia de suite de testes automatizados
- potencial de carga alta em insights sem pre-agregacao

## 7. Mapa de Documentacao

- `docs/README.md`: indice principal
- `docs/AI_HANDOFF.md`: guia de handoff para IA
- `docs/backend.md`: arquitetura de backend e APIs
- `docs/database.md`: dados, relacionamento e migracoes
- `docs/frontend.md`: arquitetura frontend e padroes de UI
- `docs/development-standards.md`: padroes oficiais de desenvolvimento
- `docs/security.md`: analise de seguranca e roadmap
- `docs/performance.md`: analise de performance e melhorias
- `docs/ARCHITECTURAL_GAPS_REPORT.md`: relatorio de gaps da revisao arquitetural e mitigacao via .cursorrules

