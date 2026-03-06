# Seguranca - Avaliacao Tecnica e Roadmap

Documento de referencia para postura de seguranca do sistema.
Atualizado em 2026-02-25.

## 1. Escopo Avaliado

- autenticacao e autorizacao
- isolamento multi-tenant
- exposicao de API e webhooks
- upload de arquivos
- tratamento de segredos
- protecoes de aplicacao (headers, rate limit, CORS)

## 2. Controles Ja Implementados

## 2.1 Auth e sessao

- hash de senha com `bcrypt_sha256`
- JWT assinado com segredo forte validado
- suporte a rotacao de segredo (`AUTH_SECRET_PREVIOUS`, `AUTH_SECRETS`)
- sessao server-side (`user_sessions`) com revogacao
- cookie `admin_token` HttpOnly e `SameSite=lax`

## 2.2 Autorizacao

- RBAC por role (`owner`, `manager`, `operator`)
- controle por modulo e acao (`view`/`edit`)
- escopo de loja por grupo/usuario

## 2.3 Protecao HTTP

- headers de seguranca:
  - `Strict-Transport-Security` (quando HTTPS)
  - `X-Content-Type-Options`
  - `X-Frame-Options`
  - `Referrer-Policy`
  - `Permissions-Policy`
  - CSP minima (`frame-ancestors 'none'`)
- request id por requisicao
- rate limit em rotas sensiveis (`/auth/login`, `/auth/signup`, `/checkout`, `/shipping/quote`)

## 2.4 Webhooks e integracoes

- webhook billing com verificacao HMAC em `X-Signature`
- WhatsApp: challenge token para GET (verificacao de webhook); POST exige validacao de `X-Hub-Signature-256` com `WHATSAPP_APP_SECRET` (App Secret do app Meta)

## 2.5 Upload de midia

- whitelist de tipos por MIME/extensao
- validacao por assinatura binaria (magic bytes)
- limite de tamanho (imagem/video)

## 3. Matriz de Risco Atual

## 3.1 Alto

1. Ausencia de auditoria completa de acoes sensiveis
   - impacto: baixa rastreabilidade forense e compliance
   - recomendacao: trilha de auditoria por usuario/tenant/acao/recurso

2. Ausencia de MFA para acessos administrativos
   - impacto: risco aumentado em caso de credencial comprometida
   - recomendacao: MFA opcional no curto prazo, obrigatoria por tenant no medio prazo

3. ~~Verificacao de integridade de payload do webhook WhatsApp nao formalizada~~ **Implementado:** POST do webhook WhatsApp valida `X-Hub-Signature-256` quando `WHATSAPP_APP_SECRET` esta configurado.

## 3.2 Medio

1. Protecao anti-automacao parcial
   - rate limit cobre algumas rotas, mas nao todas de alto risco

2. Sem validacao de origem para mutacoes autenticadas por cookie
   - `SameSite=lax` ajuda, mas validacao de `Origin/Referer` e recomendada

3. Sem refresh token com rotacao e deteccao de reuse
   - sessao existe, mas estrategia de token pode evoluir

4. CORS depende de lista estatica/env sem politica dinamica central
   - requer governanca em deploys multi-ambiente

5. Logs sem enriquecimento completo de usuario/recurso para operacoes de negocio
   - request log atual e bom para HTTP, incompleto para trilha funcional

## 3.3 Baixo

1. CSP ainda minima
   - recomendacao: evoluir para `default-src`, `script-src`, `img-src` etc por ambiente

2. Nao ha baseline formal de SAST/DAST no pipeline
   - recomendacao: adicionar etapas automatizadas no CI

## 4. Recomendacoes Priorizadas

## 4.1 Curto prazo (0-15 dias)

1. Implementar validacao de assinatura no webhook WhatsApp.
2. Adicionar check de `Origin` para mutacoes autenticadas por cookie.
3. Expandir rate limit para endpoints admin de alto impacto.
4. Definir politica de rotacao de segredos e checklist de deploy.

## 4.2 Medio prazo (15-45 dias)

1. Introduzir auditoria de acoes:
   - login/logout
   - alteracao de usuario/grupo
   - alteracao de plano/modulo/tenant
   - alteracao de pedido/status/estoque
2. Implementar MFA para perfis administrativos.
3. Adotar refresh token rotativo.

## 4.3 Longo prazo (45-90 dias)

1. Integrar SAST e dependencia scanning no CI.
2. Definir baseline de pentest recorrente.
3. Avaliar isolamento de dados premium (schema/database por tenant).

## 5. Checklist de Seguranca para Nova Feature

- [ ] endpoint protegido por role/modulo correto
- [ ] query restrita por tenant
- [ ] payload validado por schema
- [ ] erro sem vazamento de informacao sensivel
- [ ] logs sem segredos
- [ ] impacto em upload/webhook avaliado
- [ ] documentacao de seguranca atualizada quando relevante

## 6. Procedimento Minimo de Incidente

1. Isolar vetor (desabilitar endpoint/integracao impactada se necessario).
2. Coletar request ids, tenant, usuario e janela temporal.
3. Revogar sessoes/segredos comprometidos.
4. Aplicar correcoes e validar em ambiente controlado.
5. Registrar postmortem tecnico com acao corretiva e preventiva.
