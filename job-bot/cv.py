"""Gera o currículo ajustado em .docx (editável e aceito por qualquer site)."""
from docx import Document
from docx.shared import Pt, RGBColor

CABECALHO = ("Recife, PE · +55 (81) 98909-8222 · azevedothamirest@gmail.com · "
             "linkedin.com/in/qathamiresazevedo · azevedothamirest.github.io")
VERDE = RGBColor(0x1E, 0x8E, 0x3E)


def _secao(doc, nome):
    p = doc.add_paragraph()
    r = p.add_run(nome.upper())
    r.bold, r.font.size, r.font.color.rgb = True, Pt(11), VERDE


def gerar(cv: dict, caminho: str) -> str:
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(10)

    t = doc.add_paragraph()
    r = t.add_run("Thamires Azevedo")
    r.bold, r.font.size = True, Pt(20)
    sub = doc.add_paragraph().add_run(cv.get("titulo", "QA Sênior | QA Engineer"))
    sub.bold, sub.font.color.rgb = True, VERDE
    doc.add_paragraph(CABECALHO)

    _secao(doc, "Resumo profissional")
    doc.add_paragraph(cv.get("resumo", ""))

    _secao(doc, "Competências")
    for cat, itens in cv.get("competencias", []):
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(f"{cat}: ").bold = True
        p.add_run(itens)

    _secao(doc, "Experiência profissional")
    for e in cv.get("experiencias", []):
        p = doc.add_paragraph()
        p.add_run(f"{e['cargo']} | {e['empresa']}").bold = True
        p.add_run(f"   {e['periodo']}")
        for b in e.get("bullets", []):
            doc.add_paragraph(b, style="List Bullet")

    if cv.get("projetos"):
        _secao(doc, "Projetos")
        for pr in cv["projetos"]:
            p = doc.add_paragraph()
            p.add_run(pr["nome"] + ": ").bold = True
            p.add_run(pr["descricao"])

    _secao(doc, "Formação acadêmica")
    for f in cv.get("formacao", []):
        doc.add_paragraph(f, style="List Bullet")
    _secao(doc, "Certificações")
    for c in cv.get("certificacoes", []):
        doc.add_paragraph(c, style="List Bullet")
    _secao(doc, "Idiomas")
    doc.add_paragraph(cv.get("idiomas", ""))

    doc.save(caminho)
    return caminho
