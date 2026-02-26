# Roksell SaaS â€” Pontos de AtenÃ§Ã£o (seguranÃ§a, escala, confiabilidade)

## SeguranÃ§a / Auth
- Tokens em `localStorage` (risco XSS). Mover para cookies httpOnly + refresh, ou storage com nonce e rotinas de rotate/kill.
- Sem refresh tokens/MFA/rate limiting. Implementar para mitigar brute-force e sequestro de sessÃ£o.
- CORS aberto a localhost; revisar para ambientes prod. Segredos/env expostos localmente; adotar rotation.
- RBAC ainda coarse (owner/manager/operator); falta polÃ­tica por mÃ³dulo/feature e auditoria de aÃ§Ãµes admin.

## Multi-tenant / Isolamento
- Single DB compartilhado; nÃ£o hÃ¡ limites por tenant (quotas, throttling) nem opÃ§Ã£o de isolamento (schema/db dedicado) para premium.
- Imports/mÃ³dulos nÃ£o respeitam feature flags no front; menus â€œem breveâ€ aparecem mesmo sem mÃ³dulo contratado.

## Billing / Revenue
- IntegraÃ§Ã£o real com gateway nÃ£o feita; ausÃªncia de reconciliaÃ§Ã£o, suspensÃ£o automÃ¡tica, retries/idempotÃªncia em webhooks.
- Falta emissÃ£o de notas/faturas, trials e controle de inadimplÃªncia.

## Observabilidade / OperaÃ§Ã£o
- Sem logs estruturados com `tenant_id`/`user_id`, sem tracing (OTel) ou mÃ©tricas Prometheus/alertas.
- Sem auditoria de aÃ§Ãµes sensÃ­veis (login, troca de plano, CRUD produtos, mudanÃ§as de SLA).

## Dados / ConsistÃªncia
- ImportaÃ§Ãµes ignoram itens sem produto; nÃ£o hÃ¡ relatÃ³rios de erros. Produtos/categorias/endereÃ§os devem ser validados por tenant.
- Insights somam pagamentos pendentes e confirmados; se precisar separar receita reconhecida vs. registrada, criar colunas/estados especÃ­ficos.
- Ãndices e unicidades compostas por tenant presentes, mas revisar FK cascatas e performance em cargas grandes.

## Disponibilidade / Infra
- Sem fila para jobs pesados (agregaÃ§Ãµes de insights, webhooks, emails). Sem cache/CDN para assets ou responses quentes.
- Backups/restore nÃ£o descritos; sem testes de DR. Sem limites de conexÃ£o nem pool configurado explicitamente.
- Deploy: falta estratÃ©gia blue/green/rollback; falta healthcheck e readiness/liveness robustos.

## Frontend / UX
- Guardas apenas por token; nÃ£o hÃ¡ bloqueio por mÃ³dulo/plano. Menus placeholders podem confundir; ideal ocultar conforme assinatura.
- KPIs/widgets usam placeholders; conectar a APIs reais e padronizar loading/error states.
- Tokens em localStorage (risco XSS) e sem CSRF; rever estratÃ©gia.

## Roadmap curto sugerido
1) SeguranÃ§a: refresh + httpOnly cookies, rate limiting, audit log, MFA opcional, CORS endurecido; RBAC por mÃ³dulo.  
2) Observabilidade: logs estruturados, tracing, mÃ©tricas/alertas.  
3) Billing real + suspensÃ£o automÃ¡tica.  
4) Infra: backups/restore testados, fila de jobs, caching/CDN, estratÃ©gia de deploy.  
5) Dados: pipeline de import com relatÃ³rios e validaÃ§Ã£o; corrigir itens Ã³rfÃ£os.  
6) UX: ocultar menus por plano/mÃ³dulo, ligar KPIs/insights, estados de loading/erro.  

