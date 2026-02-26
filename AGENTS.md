# AGENTS

Este arquivo define o protocolo padrao para qualquer agente/IA que atuar neste repositorio.

## 1. Objetivo

Garantir que toda interacao comece com contexto tecnico minimo, reduzindo erros e retrabalho.

## 2. Onboarding Obrigatorio (antes de qualquer alteracao)

Todo agente deve ler, nesta ordem:

1. `ARCHITECTURE.md`
2. `docs/README.md`
3. `docs/AI_HANDOFF.md`

Depois, deve ler os documentos especificos conforme o tipo de tarefa:

- Backend/API: `docs/backend.md`
- Banco/migracoes/modelagem: `docs/database.md`
- Frontend/UI/Next.js: `docs/frontend.md`
- Convencoes de implementacao: `docs/development-standards.md`
- Seguranca: `docs/security.md`
- Performance/escalabilidade: `docs/performance.md`

## 3. Confirmacao obrigatoria na primeira resposta

Antes de implementar, o agente deve declarar explicitamente:

- quais documentos leu
- quais documentos aplicam para a tarefa atual

Formato sugerido:

`Onboarding lido: ARCHITECTURE.md, docs/README.md, docs/AI_HANDOFF.md, ...`

## 4. Regra de execucao

- Nao iniciar mudancas de codigo sem concluir o onboarding, exceto se o usuario pedir explicitamente para pular.
- Se houver conflito entre docs e codigo atual, o codigo e a fonte de verdade tecnica imediata.
- Em caso de conflito, o agente deve:
  1. apontar a divergencia
  2. corrigir os docs no mesmo trabalho (quando solicitado ou quando fizer sentido)

## 5. Regra de continuidade

- Toda mudanca estrutural relevante deve atualizar ao menos um documento em `docs/`.
- Se a mudanca afetar arquitetura geral, atualizar tambem `ARCHITECTURE.md`.
