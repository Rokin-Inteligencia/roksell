# Relatório de Gaps Arquiteturais — Revisão 2026

Este documento resume os **5 principais riscos arquiteturais** identificados na auditoria do repositório Roksell e como o novo `.cursorrules` ajuda a mitigá-los.

---

## 1. Lógica de negócio e persistência na camada de transporte (routers) — **PILOTO IMPLEMENTADO (CHECKOUT)**

**Risco:** Vários routers (ex.: `checkout.py`, `admin.py`, `insights.py`, `catalog_admin.py`, `whatsapp_webhook.py`, `admin_central.py`) concentram centenas de linhas com `db.query`/`db.add`/`db.commit` e regras de domínio diretamente nos endpoints. Isso:

- Dificulta testes unitários e reuso da lógica.
- Aumenta o acoplamento entre HTTP e domínio.
- Viola o princípio de responsabilidade única e dificulta evolução (ex.: fila assíncrona, cache).

**Piloto aplicado (checkout):** Toda a lógica de negócio e persistência do fluxo de checkout foi extraída para `app/services/checkout.py`. O router `app/routers/checkout.py` passou a fazer apenas orquestração e notificações em background.

**Refatoração adicional (insights):** A lógica de agregações do endpoint `GET /admin/insights` foi extraída para `app/services/insights.py`. O router chama `get_insights(db, tenant.id, start_date, end_date)` e devolve o resultado.

**Refatoração adicional (catalog_admin):** Toda a lógica de CRUD de product masters, categorias, adicionais e produtos foi extraída para `app/services/catalog_admin.py`. O router `app/routers/catalog_admin.py` faz apenas orquestração HTTP (Depends, Query, File/UploadFile), validação de upload de imagem/vídeo e chamadas ao serviço; uploads de mídia salvam no storage no router e atualizam a URL via `update_product_media_url`.

**Refatoração adicional (admin onboarding):** O fluxo de onboarding do admin (estado, conclusão, modo teste) foi extraído para `app/services/admin_onboarding.py`. Os schemas de request/response de onboarding foram movidos para `app/schemas.py`. O router `app/routers/admin.py` mantém apenas orquestração para os endpoints `/onboarding/state`, `/onboarding/complete` e `/onboarding/test-enable`.

Os demais routers (`admin.py` — endpoints de pedidos/dashboard e módulos —, `whatsapp_webhook.py`, `admin_central.py`) podem seguir o mesmo padrão de forma incremental: extrair funções de serviço por fluxo e manter o router apenas orquestrando.

**Mitigação via `.cursorrules`:**  
A seção **2.1** exige que routers façam apenas orquestração e que fluxos com múltiplas entidades ou regras não triviais sejam implementados em `app/services/` (ou domínio) e apenas invocados pelo router. O checklist (**§8**) reforça que payloads sejam validados e que a estrutura de camadas seja respeitada. Assim, novas features e refatorações tendem a seguir o padrão de serviço em vez de inflar ainda mais os routers.

---

## 2. Webhook WhatsApp sem validação de assinatura no POST — **CORRIGIDO**

**Risco (mitigado):** Os endpoints `POST /webhooks/whatsapp` e `POST /webhooks/whatsapp/{tenant_slug}` processavam o body sem validar o header `X-Hub-Signature-256`.

**Correção aplicada:** Foi implementada a validação HMAC-SHA256 com o App Secret da Meta (`WHATSAPP_APP_SECRET`). O body é lido em bruto, a assinatura é verificada com `hmac.compare_digest` e, se o secret não estiver configurado, o POST retorna 503. Documentação em `docs/README.md` e `docs/security.md` atualizada.

**Mitigação via `.cursorrules`:**  
A seção **3.2** torna explícito que webhooks que recebem payloads de terceiros **devem** validar assinatura antes de processar o body. A correção acima implementa isso; o `.cursorrules` mantém o padrão para futuros webhooks.

---

## 3. Schemas de entrada pouco restritivos e exposição de sensíveis — **PARCIALMENTE CORRIGIDO**

**Risco:**  
- `PaymentIn` usava `method: str` em vez de `Literal["pix", "cash"]`. **Correção:** schema atualizado para `Literal["pix", "cash"]`.  
- Endpoints de admin central devolviam `whatsapp_token` e `telegram_bot_token` em claro. **Correção:** respostas GET e PATCH de mensageria passam a retornar valor mascarado (`••••••••`) quando o token está configurado; no PATCH, enviar o valor mascarado é tratado como “não alterar”.
- Outros campos de entrada ainda podem se beneficiar de `Literal`/Enum ou `Field(ge=..., le=...)` conforme evolução.

**Mitigação via `.cursorrules`:**  
As seções **3.1** e **3.3** exigem:  
- Uso de tipos restritos (Literal/Enum) para domínios finitos e `Field` para limites.  
- Não expor em schemas de resposta tokens de integração em formato utilizável (podem ser mascarados ou omitidos).  
Isso direciona correções nos schemas existentes e impede que novos endpoints repitam o padrão inseguro.

---

## 4. Ausência de camada de serviço consistente e risco de dependências circulares

**Risco:**  
- Não há convenção clara de “um fluxo = um serviço”; parte da orquestração e da persistência está nos routers e parte em `app/services/`.  
- O arquivo `app/models.py` importa vários `app.domain.*`; routers importam `domain` e `services`. Se no futuro um módulo de domínio passar a depender de algo em `routers` ou em um `service` que importe outro router, surgem ciclos difíceis de resolver.

**Mitigação via `.cursorrules`:**  
A seção **2.1** define o sentido permitido de dependências (routers → services/domain; services → domain; domain sem depender de routers/services de forma cíclica) e exige que fluxos não triviais vivam em serviços. O **checklist (§8)** e a regra de **documentação (§7)** mantêm a consistência e a visibilidade das decisões, reduzindo a chance de introduzir ciclos ou lógica no lugar errado.

---

## 5. Falta de testes automatizados e de critério claro para TDD

**Risco:** A base não possui suite formal de testes (mencionado em `ARCHITECTURE.md`, `docs/README.md`, `AI_HANDOFF.md`). Isso aumenta o risco de regressão em fluxos críticos (checkout, auth, tenancy, webhooks) e dificulta refatorações seguras (ex.: extrair lógica dos routers para serviços).

**Mitigação via `.cursorrules`:**  
A seção **5** estabelece que:  
- Novas features devem preferir implementação orientada a testes quando o escopo for estável.  
- Alterações em fluxos críticos devem ser cobertas por testes ou validação manual explícita no PR.  
- Não quebrar compile/lint/build no CI.  
Isso cria um critério mínimo de qualidade e um caminho para introduzir testes de forma gradual (serviços e rotas críticas primeiro), sem bloquear o trabalho atual.

---

## Resumo

| # | Risco principal | Como o `.cursorrules` ajuda |
|---|------------------|-----------------------------|
| 1 | Lógica e persistência nos routers | §2.1: routers só orquestram; fluxos em services/domain; checklist §8. |
| 2 | Webhook WhatsApp sem assinatura no POST | §3.2: webhooks de terceiros devem validar assinatura. |
| 3 | Schemas fracos e exposição de sensíveis | §3.1 e §3.3: Literal/Enum, Field, e não expor tokens em respostas. |
| 4 | Camada de serviço inconsistente e ciclos | §2.1: direção de dependências e fluxos em serviços; §7 docs. |
| 5 | Ausência de testes e critério TDD | §5: preferir TDD em features novas; cobrir fluxos críticos; CI verde. |

O `.cursorrules` funciona como contrato impositivo para as próximas interações: ao seguir suas regras, o código tende a reduzir esses cinco riscos e a manter padrão de qualidade, segurança e TDD alinhado a 2026.
