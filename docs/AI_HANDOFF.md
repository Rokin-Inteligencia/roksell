# AI Handoff Guide

Este documento foi feito para agentes de IA que chegam sem contexto.
Use este roteiro antes de qualquer alteracao relevante.

## 1. Contexto de Negocio

Plataforma SaaS multi-tenant para restaurantes com:

- vitrine publica (`/vitrine/[slug]`)
- checkout com frete
- portal de operacao (`/portal/*`)
- admin central SaaS (`/admin/*`)

## 2. Mapa Rapido do Workspace

- `roksell-backend`: API FastAPI
- `roksell-frontend`: front Next.js
- `ARCHITECTURE.md`: visao macro
- `docs/`: documentacao detalhada

## 3. Fonte de Verdade por Tema

- Arquitetura geral: `../ARCHITECTURE.md`
- API e regras: `backend.md`
- Modelo de dados: `database.md`
- UI e fluxo front: `frontend.md`
- Padroes de codigo: `development-standards.md`
- Hardening e riscos: `security.md`
- Escala e gargalos: `performance.md`

## 4. Regras de Ouro para Alteracoes

1. Nunca quebrar isolamento por tenant.
2. Toda query de dominio deve considerar `tenant_id`.
3. Endpoint admin novo deve usar role + modulo/acao quando aplicavel.
4. Front admin deve usar `adminFetch`/`adminUpload` (proxy `/api/admin/*`).
5. Mudanca de schema exige migracao Alembic.
6. Nao acoplar regra de negocio complexa em componente de UI.

## 5. Fluxo Minimo para Nova Feature

1. Ler documentos relevantes.
2. Mapear impacto em tenancy, auth, schema e UI.
3. Implementar backend (router + schema + service).
4. Implementar frontend usando padrao existente.
5. Atualizar documentacao afetada.
6. Validar build/lint localmente.

## 6. Checklist de Revisao Antes de Entregar

- [ ] Query com escopo de tenant
- [ ] Endpoint protegido com dependencia correta
- [ ] Validacao de payload com Pydantic
- [ ] Tratamento de erro consistente
- [ ] Nao exposicao de segredo em logs/resposta
- [ ] Compatibilidade com fluxo atual de login por cookie
- [ ] Documento atualizado quando houver alteracao estrutural

## 7. Pontos Sensiveis Atuais

- Nao ha suite de testes automatizados formal.
- Nao ha trilha de auditoria completa de acoes administrativas.
- Nao ha fila dedicada para jobs externos (mensageria/insights).
- Parte das paginas de portal e altamente client-side (payload grande no browser).

Sempre consultar `security.md` e `performance.md` antes de introduzir novas integracoes ou pontos de carga.

