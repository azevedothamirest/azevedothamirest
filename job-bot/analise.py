"""Análise das vagas com o Claude: compatibilidade, salário e currículo ajustado."""
import json
import re

import anthropic

from fontes import Vaga

client = anthropic.Anthropic()  # lê ANTHROPIC_API_KEY do ambiente

SISTEMA = """Você ajuda uma profissional de QA a encontrar e se candidatar a vagas.
Seja honesto: não infle a compatibilidade e nunca invente experiências que não estão no perfil.
Responda sempre em português do Brasil."""


def _chamar(prompt: str, modelo: str, pesquisar: bool = False, max_tokens: int = 8000) -> str:
    kwargs = dict(
        model=modelo, max_tokens=max_tokens, system=SISTEMA,
        thinking={"type": "adaptive"}, output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
    )
    if pesquisar:
        kwargs["tools"] = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 4}]
    resp = client.beta.messages.create(**kwargs)
    if resp.stop_reason == "refusal":
        raise RuntimeError("O modelo recusou a solicitação")
    return "".join(b.text for b in resp.content if b.type == "text")


def _json(txt: str) -> dict:
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError(f"Resposta sem JSON: {txt[:200]}")
    return json.loads(m.group(0))


def avaliar(v: Vaga, perfil: str, cfg: dict) -> dict:
    sal = cfg["salario"]["senior"]
    prompt = f"""<perfil>
{perfil}
</perfil>

<preferencias>
- Cargos: QA Sênior (prioridade) ou QA Pleno
- Pretensão Sênior: CLT R$ {sal['clt'][0]}–{sal['clt'][1]} | PJ R$ {sal['pj'][0]}–{sal['pj'][1]}
- Local: remoto em qualquer lugar do Brasil; híbrido ou presencial só em Recife/PE
</preferencias>

<vaga>
Título: {v.titulo}
Empresa: {v.empresa}
Local: {v.local} | Modelo: {v.modelo} | Fonte: {v.fonte}
URL: {v.url}
Descrição: {v.descricao or "(sem descrição — pesquise a vaga/empresa se precisar)"}
</vaga>

Tarefas:
1. Avalie a compatibilidade da candidata com a vaga (0–100), considerando requisitos técnicos, senioridade, domínio de negócio e local.
   Se a vaga for presencial/híbrida fora de Recife, ou não for de QA, a nota deve ser no máximo 30.
2. Pesquise na web quanto essa empresa paga para QA nesse nível (Glassdoor, Levels, LinkedIn, notícias, a própria vaga).
   Sugira uma pretensão salarial CLT e PJ. Para Sênior, respeite a faixa da candidata como piso.
   Se não achar dados da empresa, use a média de mercado e diga isso.
3. Faça um resumo curto da empresa (o que faz, porte, reputação se houver).

Responda APENAS com um JSON neste formato:
{{
  "nota": 0,
  "senioridade": "senior|pleno|outra",
  "contrato": "CLT|PJ|ambos|não informado",
  "faixa_anunciada": "texto ou null",
  "resumo_vaga": "2–3 linhas",
  "stack": ["..."],
  "pontos_fortes": ["até 4 itens"],
  "lacunas": ["até 3 itens"],
  "dica": "1 frase do que destacar no CV",
  "empresa_resumo": "1–2 linhas",
  "salario_sugerido": {{"clt": "R$ ...", "pj": "R$ ...", "base": "de onde veio o número"}}
}}"""
    return _json(_chamar(prompt, cfg["modelo_claude"], pesquisar=True))


def ajustar_cv(v: Vaga, perfil: str, analise: dict, cfg: dict) -> dict:
    prompt = f"""<perfil>
{perfil}
</perfil>

<vaga>
{v.titulo} — {v.empresa}
{v.descricao}
</vaga>

<analise>
{json.dumps(analise, ensure_ascii=False)}
</analise>

Reescreva o currículo da candidata ajustado para esta vaga:
- Use SOMENTE fatos do perfil. Pode reordenar, reformular e enfatizar, nunca inventar.
- Use as palavras-chave da vaga onde forem verdadeiras (ajuda nos filtros ATS).
- Coloque no topo o título do cargo da vaga, se condizente.
- Escreva também uma mensagem curta de apresentação (até 120 palavras) para enviar ao recrutador.
- Liste as principais mudanças feitas.

Responda APENAS com JSON:
{{
  "titulo": "linha de título do CV",
  "resumo": "parágrafo",
  "competencias": [["Categoria", "itens"]],
  "experiencias": [{{"cargo": "", "empresa": "", "periodo": "", "bullets": [""]}}],
  "projetos": [{{"nome": "", "descricao": ""}}],
  "formacao": [""],
  "certificacoes": [""],
  "idiomas": "",
  "carta": "mensagem de apresentação",
  "mudancas": ["..."]
}}"""
    return _json(_chamar(prompt, cfg["modelo_claude"], max_tokens=16000))
