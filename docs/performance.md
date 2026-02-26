# Performance - Diagnostico e Plano de Melhoria

Documento orientado a capacidade, latencia e escalabilidade.
Atualizado em 2026-02-25.

## 1. Estado Atual

Arquitetura funcional para carga inicial, com alguns gargalos previsiveis em crescimento:

- processamento sincrono em partes criticas (checkout + integracoes)
- ausencia de fila dedicada para jobs externos
- ausencia de camada de cache estruturada para leitura quente
- ausencia de pre-agregacao para analytics

## 2. Hot Paths do Sistema

## 2.1 Checkout (`POST /checkout`)

Passos custosos:

- validacao de itens/campanhas
- calculo de frete com chamada externa
- lock e baixa de estoque
- persistencia de pedido + itens + pagamento + entrega
- notificacoes externas

Risco: aumento de latencia em horario de pico.

## 2.2 Shipping quote (`POST /shipping/quote`)

- depende de servicos externos para distancia
- fallback Haversine reduz disponibilidade de precisao mas mantem operacao

Risco: oscilacao de latencia por terceiros.

## 2.3 Insights (`GET /admin/insights`)

- agregacoes em tempo real sobre pedidos/itens/pagamentos

Risco: consultas pesadas conforme volume historico cresce.

## 2.4 Mensagens WhatsApp (`/admin/whatsapp/*`)

- leitura de threads e conversas com joins e consolidacao em memoria

Risco: payload grande e custo crescente por tenant com alta mensagem.

## 2.5 Frontend portal (paginas client-heavy)

- varias telas carregam tudo via client component
- potencial de carga inicial grande e re-render custo alto

Risco: UX degradada em dispositivos modestos e conexoes lentas.

## 3. Controles de Performance Ja Existentes

- rate limit em rotas sensiveis
- fallback local para rate limit quando Redis indisponivel
- validacoes de upload para evitar arquivos excessivos
- alguns limites de pagina (`limit`, `page`) em endpoints de listagem

## 4. Gaps Relevantes

1. Sem cache dedicado para leitura quente (catalogo, stores, config leve).
2. Sem fila para desacoplar chamadas externas de request critico.
3. Sem metricas formais de p95/p99 e throughput.
4. Sem testes de carga recorrentes.

## 5. Metricas Recomendadas (SLI/SLO)

## 5.1 API

- `p95` de `/checkout` < 1200 ms
- `p95` de `/shipping/quote` < 800 ms
- `p95` de `/catalog` < 300 ms
- erro 5xx < 0.5%

## 5.2 Frontend

- TTFB paginas publicas < 500 ms (target)
- Largest Contentful Paint < 2.5 s (target)
- taxa de erro JS < 1%

## 5.3 Jobs/Integracoes

- tempo medio de envio WhatsApp/Telegram
- taxa de falha por provider
- backlog de notificacoes pendentes (quando fila existir)

## 6. Plano de Melhoria por Fase

## 6.1 Fase 1 - Quick wins (0-15 dias)

1. Garantir paginacao consistente em todos endpoints de listagem.
2. Revisar queries de insights e threads para reduzir varredura desnecessaria.
3. Evitar chamadas externas duplicadas em checkout quando dados ja estao disponiveis.
4. Instrumentar metricas basicas de tempo por endpoint (request middleware + export).

## 6.2 Fase 2 - Escala controlada (15-45 dias)

1. Introduzir cache de leitura para:
   - catalogo por tenant/loja
   - stores ativas por tenant
2. Introduzir fila para:
   - envio Telegram
   - envio WhatsApp outbound
   - push web
3. Criar tabela/materializacao para agregados de insights.

## 6.3 Fase 3 - Escala avancada (45-90 dias)

1. Replica de leitura para consultas analiticas.
2. Politica de arquivamento para tabelas de alto volume (mensagens/logs).
3. Teste de carga automatizado no CI/CD de release.

## 7. Recomendacoes de Indice (A validar em ambiente)

Prioridade de analise:

- `orders(tenant_id, created_at)`
- `orders(tenant_id, status, created_at)`
- `whatsapp_inbound_messages(tenant_id, from_phone, received_at)`
- `whatsapp_message_logs(tenant_id, to_phone, created_at)`
- `store_inventory(tenant_id, store_id, product_id)` (ja possui unique)

Nota: aplicar indice sem benchmark pode degradar escrita; medir antes/depois.

## 8. Diretrizes para Feature Nova (Performance)

- endpoint novo deve definir limites de pagina claros
- evitar `SELECT *` em colecoes volumosas
- evitar N+1 (usar join/selectinload quando necessario)
- chamadas externas devem ter timeout e retry controlado
- avaliar se operacao pode ser async/eventual em vez de bloquear request

## 9. Checklist de Revisao de Performance

- [ ] latencia endpoint principal medida
- [ ] payload de resposta proporcional ao uso
- [ ] consulta principal analisada (filtros + indices)
- [ ] sem loops de request no frontend
- [ ] sem bloqueio desnecessario do caminho critico
