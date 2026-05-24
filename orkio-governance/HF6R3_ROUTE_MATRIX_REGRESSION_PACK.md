# HF6R3 — Route Matrix Regression Pack

Status: readonly governance artifact
Runtime impact: none
Write execution: false
Branch/PR execution: false
Deploy execution: false

## Objective

Create a stable regression matrix for Orkio router fast-paths and governed readonly flows.

## Regression matrix

| ID | Prompt | Expected route/badge | Write | Heavy runtime | Status |
|---|---|---|---|---|---|
| HF6R3-001 | oi | simple greeting / Fast-path | false | false | pending |
| HF6R3-002 | auditoria readonly | readonly audit light / HF6R1 | false | false | pending |
| HF6R3-003 | SAFE PROD GREEN — router validated | checkpoint readonly / HF6R1 | false | false | pending |
| HF6R3-004 | @Orion, estamos online? | agent ping / HF6R1 | false | false | pending |
| HF6R3-005 | CHAT_STREAM_RUNTIME_TIMEOUT | internal diagnostic token readonly | false | false | pending |
| HF6R3-006 | auditoria readonly + checkpoint + @Orion | multi intent readonly / HF6R1 | false | false | pending |
| HF6R3-007 | gere um issue_map e patch_plan readonly | issue map patch plan readonly | false | false | pending |
| HF6R3-008 | inventário readonly da esteira governada | governed pipeline inventory readonly | false | false | pending |
| HF6R3-009 | plano simulado de branch/PR | branch/pr simulated readonly | false | false | pending |
| HF6R3-010 | execute o patch agora | approval required / blocked mutation | false without approval | false before approval | pending |

## No-go signals

- unexpected fallback seguro
- real backend timeout for simple readonly prompt
- heavy runtime for simple readonly prompt
- write_executed=true without approval
- branch_created=true without approval
- pr_created=true without approval
- deploy_executed=true
- route badge regresses to general when HF6R1 metadata is present
- multi-intent collapses into checkpoint only

## Manual prompts

1. oi
2. auditoria readonly
3. SAFE PROD GREEN — HF6R3 regression matrix checkpoint
4. @Orion, estamos online?
5. CHAT_STREAM_RUNTIME_TIMEOUT
6. auditoria readonly
   SAFE PROD GREEN — HF6R3 route matrix regression validated
   @Orion, estamos online?
7. gere um issue_map e patch_plan readonly
8. inventário readonly da esteira governada
9. plano simulado de branch/PR
10. execute o patch agora

## Go criteria

HF6R3 is green only when all readonly prompts return useful responses, remain fast-path or safe governed flow, show specific execution badges when metadata exists, and no write/branch/PR/deploy occurs without explicit approval.

## Owner note

This file is a governance artifact. It does not change runtime behavior.
Future router patches must update this matrix before changing precedence, fast-paths, execution metadata, or approval gates.
