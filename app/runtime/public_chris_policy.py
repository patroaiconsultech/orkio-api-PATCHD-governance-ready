AO47 — Chris + Orion Public Policy Modules

Objetivo:
- Criar módulos externos para Chris e Orion.
- Evitar inflar app/main.py.
- Corrigir Chris pública negativa.
- Dar ao Orion uma camada técnica premium conservadora.
- Preservar GitHub readonly, auditoria readonly e memória factual existentes.

Arquivos:
1. app/runtime/public_chris_policy.py
2. app/runtime/public_orion_policy.py
3. patch manual pequeno em app/main.py conforme AO47_MAIN_IMPORT_AND_HOOK_SNIPPET.txt

Validação backend:
python -m py_compile app/runtime/public_chris_policy.py
python -m py_compile app/runtime/public_orion_policy.py
python -m py_compile app/main.py

Testes:
1. @Chris me dê uma leitura executiva em uma frase.
   Esperado: Chris positiva, executiva e investidor-ready.

2. @Chris estruture os blocos iniciais do business plan da PatroAI.
   Esperado: visão, mercado, receita, go-to-market, financeiro e roadmap.

3. @Orion explique tecnicamente o que é o ORKIO OS.
   Esperado: Orion técnico, premium, sem auditoria pesada.

4. @Orion faça uma auditoria readonly da plataforma.
   Esperado: NÃO cair neste módulo; seguir auditoria readonly existente.

5. @Orion leia o status do repositório backend no GitHub em modo readonly.
   Esperado: NÃO cair neste módulo; seguir GitHub readonly existente.

6. @Orion qual foi a palavra-chave desta conversa?
   Esperado: NÃO cair neste módulo; seguir memória factual existente.

7. Orkio, precisamos criar o business plan...
   Esperado: Orkio público continua funcionando.

Rollback:
- Remover imports de public_chris_policy/public_orion_policy no app/main.py.
- Remover hook CHRIS_ORION_PUBLIC_POLICY_MODULE_FASTPATH.
- Manter ou remover os arquivos novos; sem hook eles ficam inativos.
