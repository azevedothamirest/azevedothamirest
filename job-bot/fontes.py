"""Coleta de vagas: Gupy, InHire, LinkedIn (vagas públicas) e Remotive."""
import html
import logging
import re
from dataclasses import dataclass, field

import httpx

log = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (job-bot pessoal)"}


@dataclass
class Vaga:
    id: str            # único por fonte, ex.: "gupy:123"
    titulo: str
    empresa: str
    local: str
    modelo: str        # remoto / híbrido / presencial / ?
    url: str
    fonte: str
    descricao: str = ""
    extra: dict = field(default_factory=dict)


def _limpa(txt: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", txt or "")
    return re.sub(r"\s+", " ", html.unescape(txt)).strip()


def _modelo(txt: str) -> str:
    t = (txt or "").lower()
    if "remot" in t or "remote" in t:
        return "remoto"
    if "hibrid" in t or "híbrid" in t or "hybrid" in t:
        return "híbrido"
    if "presencial" in t or "on-site" in t or "onsite" in t:
        return "presencial"
    return "?"


# ---------------------------------------------------------------- Gupy
def gupy(c: httpx.Client, termo: str) -> list[Vaga]:
    r = c.get("https://portal.api.gupy.io/api/job",
              params={"name": termo, "offset": 0, "limit": 50})
    r.raise_for_status()
    out = []
    for j in r.json().get("data", []):
        out.append(Vaga(
            id=f"gupy:{j['id']}", titulo=j.get("name", ""),
            empresa=j.get("careerPageName", ""),
            local=", ".join(x for x in [j.get("city"), j.get("state")] if x) or "Brasil",
            modelo=_modelo(j.get("workplaceType", "")) if j.get("workplaceType") else ("remoto" if j.get("isRemoteWork") else "?"),
            url=j.get("jobUrl", ""), fonte="Gupy",
            descricao=_limpa(j.get("description", ""))[:6000],
        ))
    return out


# ---------------------------------------------------------------- InHire
def inhire(c: httpx.Client, empresa: str) -> list[Vaga]:
    """Cada empresa tem página própria: <empresa>.inhire.app/vagas."""
    base = "https://api.inhire.app/job-posts/public/pages"
    r = c.get(base, headers={"X-Tenant": empresa})
    r.raise_for_status()
    dados = r.json()
    lista = dados.get("jobsPage", dados) if isinstance(dados, dict) else dados
    out = []
    for j in lista or []:
        jid = j.get("jobId") or j.get("id")
        desc = ""
        try:
            d = c.get(f"{base}/{jid}", headers={"X-Tenant": empresa})
            if d.is_success:
                desc = _limpa(d.json().get("description", ""))[:6000]
        except httpx.HTTPError:
            pass
        out.append(Vaga(
            id=f"inhire:{empresa}:{jid}", titulo=j.get("displayName") or j.get("name", ""),
            empresa=empresa, local=j.get("location", "") or "",
            modelo=_modelo(j.get("workplaceType", "") or j.get("location", "")),
            url=f"https://{empresa}.inhire.app/vagas/{jid}", fonte="InHire",
            descricao=desc,
        ))
    return out


# ---------------------------------------------------------------- LinkedIn (guest)
def linkedin(c: httpx.Client, termo: str, local: str, remoto: bool) -> list[Vaga]:
    params = {"keywords": termo, "location": local, "f_TPR": "r86400", "start": 0}
    if remoto:
        params["f_WT"] = "2"
    r = c.get("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search", params=params)
    if not r.is_success:
        return []
    out = []
    for card in r.text.split("<li")[1:]:
        jid = re.search(r"jobPosting:(\d+)", card)
        tit = re.search(r'base-search-card__title[^>]*>(.*?)<', card, re.S)
        emp = re.search(r'base-search-card__subtitle[^>]*>.*?>(.*?)<', card, re.S)
        loc = re.search(r'job-search-card__location[^>]*>(.*?)<', card, re.S)
        if not (jid and tit):
            continue
        desc = ""
        try:
            d = c.get(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{jid.group(1)}")
            m = re.search(r'show-more-less-html__markup[^>]*>(.*?)</div>', d.text, re.S)
            desc = _limpa(m.group(1))[:6000] if m else ""
        except httpx.HTTPError:
            pass
        out.append(Vaga(
            id=f"linkedin:{jid.group(1)}", titulo=_limpa(tit.group(1)),
            empresa=_limpa(emp.group(1)) if emp else "", local=_limpa(loc.group(1)) if loc else local,
            modelo="remoto" if remoto else _modelo(desc), fonte="LinkedIn",
            url=f"https://www.linkedin.com/jobs/view/{jid.group(1)}", descricao=desc,
        ))
    return out


# ---------------------------------------------------------------- Remotive
def remotive(c: httpx.Client, termo: str) -> list[Vaga]:
    r = c.get("https://remotive.com/api/remote-jobs", params={"search": termo, "limit": 30})
    if not r.is_success:
        return []
    return [Vaga(
        id=f"remotive:{j['id']}", titulo=j["title"], empresa=j.get("company_name", ""),
        local=j.get("candidate_required_location", ""), modelo="remoto",
        url=j["url"], fonte="Remotive", descricao=_limpa(j.get("description", ""))[:6000],
    ) for j in r.json().get("jobs", [])]


# ---------------------------------------------------------------- tudo
FILTRO_TITULO = re.compile(r"\b(qa|quality|qualidade|teste|testes|test|tester|sdet)\b", re.I)


def coletar(cfg: dict, empresas_inhire: list[str]) -> list[Vaga]:
    vagas: dict[str, Vaga] = {}
    with httpx.Client(headers=UA, timeout=20, follow_redirects=True) as c:
        tarefas = []
        for t in cfg["palavras_chave"]:
            tarefas += [
                ("Gupy", lambda t=t: gupy(c, t)),
                ("LinkedIn remoto", lambda t=t: linkedin(c, t, "Brasil", True)),
                ("LinkedIn Recife", lambda t=t: linkedin(c, t, cfg["localizacao"]["hibrido_presencial"], False)),
            ]
        tarefas.append(("Remotive", lambda: remotive(c, "qa")))
        for e in empresas_inhire:
            tarefas.append((f"InHire {e}", lambda e=e: inhire(c, e)))

        for nome, f in tarefas:
            try:
                for v in f():
                    if FILTRO_TITULO.search(v.titulo):
                        vagas.setdefault(v.id, v)
            except Exception as e:  # uma fonte fora do ar não derruba as outras
                log.warning("Fonte %s falhou: %s", nome, e)
    return list(vagas.values())


def local_aceito(v: Vaga, cidade: str) -> bool:
    """Remoto (Brasil) sempre; híbrido/presencial só na cidade escolhida."""
    if v.modelo == "remoto":
        return True
    txt = f"{v.local} {v.descricao[:500]}".lower()
    return cidade.lower() in txt or "pernambuco" in txt or " pe" in txt or v.modelo == "?"
