# Banco de Dados - Modelo, Tenancy e Migracoes

## 1. Visao Geral

- Banco principal: PostgreSQL
- ORM: SQLAlchemy 2.x
- Migracoes: Alembic
- Estrategia de tenancy: shared database com isolamento por `tenant_id`

## 2. Estrategia Multi-tenant

Modelo atual:

- um unico schema/banco
- isolamento logico via coluna `tenant_id`
- constraints e queries sempre com escopo de tenant

Implicacoes:

- operacao simples e custo inicial menor
- exige disciplina rigorosa em todas as queries
- risco de vazamento logico se filtros de tenant forem esquecidos

## 3. Entidades por Dominio

## 3.1 Tenancy e acesso

- `tenants`
  - identidade do tenant (slug unico)
  - limites (`users_limit`, `stores_limit`)
  - dados cadastrais, faturamento e onboarding
- `tenant_modules`
  - modulos ativos por tenant
  - `UNIQUE (tenant_id, module)`
- `users`
  - usuario interno por tenant
  - `UNIQUE (tenant_id, email)`
- `user_groups`
  - grupo de permissao e escopo de lojas
  - `UNIQUE (tenant_id, name)`
- `user_sessions`
  - sessao revogavel por usuario/tenant

## 3.2 Billing

- `modules`
  - catalogo de modulos SaaS
- `plans`
  - plano comercial
- `plan_modules`
  - relacionamento plano x modulos
  - `UNIQUE (plan_id, module_id)`
- `subscriptions`
  - assinatura atual do tenant (1 para 1)
  - `tenant_id` unico

## 3.3 Catalogo e produto

- `product_masters`
  - base canonica para produtos
- `categories`
  - categoria global ou por loja
  - `UNIQUE (tenant_id, store_id, name)`
- `additionals`
  - adicionais de produto
  - `UNIQUE (tenant_id, store_id, name)`
- `products`
  - produto vendavel
  - flags: ativo, custom, availability, block_sale
- `product_additionals`
  - relacionamento N:N produto x adicional

## 3.4 Cliente e pedido

- `customers`
  - cliente por tenant
  - `UNIQUE (tenant_id, phone)`
- `customer_addresses`
  - enderecos do cliente
- `orders`
  - cabecalho de pedido
  - status armazenado em texto
- `order_items`
  - itens do pedido
- `payments`
  - pagamento por pedido (`order_id` unico)
- `deliveries`
  - entrega por pedido (`order_id` unico)

## 3.5 Loja, frete e estoque

- `stores`
  - loja fisica/logica por tenant
  - `UNIQUE (tenant_id, slug)`
- `store_inventory`
  - saldo por loja e produto
  - `UNIQUE (tenant_id, store_id, product_id)`
- `shipping_distance_tiers`
  - faixas de frete por km
  - `UNIQUE (tenant_id, store_id, km_min, km_max)`
- `shipping_overrides`
  - excecao por CEP
  - `UNIQUE (tenant_id, postal_code)`
- `geocode_cache`
  - cache de geocoding por CEP

## 3.6 Configuracao operacional

- `operations_config`
  - config global do tenant (1:1 por tenant)
  - inclui mensageria, pix, status de pedido, horarios, shipping method
- `blocked_days`
  - dias bloqueados por tenant

## 3.7 Campanhas

- `campaigns`
  - desconto por percentual/cupom/regra
  - indices:
    - `(tenant_id, coupon_code)`
    - `(tenant_id, is_active, starts_at, ends_at)`
- `campaign_stores`
  - relacionamento campanha x loja

## 3.8 WhatsApp e notificacao

- `whatsapp_message_logs`
  - historico outbound
- `whatsapp_conversations`
  - estado por telefone (last_inbound/read)
- `whatsapp_inbound_messages`
  - inbox por tenant
- `whatsapp_push_subscriptions`
  - inscricoes push web

## 4. Integridade e Constraints

Padroes relevantes:

- chaves estrangeiras com `ondelete` para manter limpeza de dados
- multiplas constraints unicas em escopo de tenant
- tabelas de relacao com chaves compostas em alguns casos
- `user_sessions` usada para revogacao de token no servidor

## 5. Campos de Configuracao em JSON/Text

Hoje alguns campos estruturados ficam em `Text` com JSON serializado:

- `operations_config.order_statuses`
- `operations_config.order_status_colors`
- `operations_config.payment_methods`
- `stores.operating_hours`
- `stores.closed_dates`
- `campaigns.rule_config`
- `user_groups.permissions_json`
- `user_groups.store_ids_json`

Vantagem:

- flexibilidade evolutiva rapida

Custo:

- validacao e indexacao limitadas
- maior risco de inconsistencias se parser falhar

## 6. Migracoes Alembic

Diretorio: `roksell-backend/alembic/versions`

Historico cobre:

- base inicial
- auth e billing
- campanhas e regras
- configuracoes operacionais
- lojas/estoque/frete
- WhatsApp inbound/outbound/push
- sessoes de usuario com multi-login

Boas praticas adotadas:

- comparacao de tipo habilitada no Alembic
- evolucao incremental por dominio

## 7. Fluxos de Dado Sensiveis

- login grava sessao em `user_sessions`
- checkout escreve em `orders`, `order_items`, `payments`, `deliveries`
- alteracao de status pedido afeta indicadores de receita e operacao
- webhook billing altera assinatura e modulos do tenant

## 8. Backup e Recuperacao

Referencia: `../BACKUP_DR.md`

Scripts:

- `scripts/backup_db.py`
- `scripts/restore_db.py`

Objetivos no documento atual:

- RPO alvo: 24h
- RTO alvo: 4h

## 9. Riscos Estruturais Atuais

- ausencia de particionamento para tabelas de alto volume (ex: mensagens)
- sem replica de leitura declarada na arquitetura atual
- sem mecanica automatica de arquivamento historico

## 10. Checklist para Mudanca de Schema

1. Criar migration Alembic.
2. Garantir compatibilidade com tenancy (`tenant_id` quando necessario).
3. Avaliar indices para filtros principais.
4. Garantir downgrade minimamente seguro.
5. Atualizar docs de backend/database.
6. Planejar backfill se coluna nova exigir dados iniciais.

