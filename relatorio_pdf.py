from pathlib import Path

import pandas as pd

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError:
    colors = None
    TA_CENTER = None
    A4 = None
    ParagraphStyle = None
    getSampleStyleSheet = None
    cm = None
    PageBreak = None
    Paragraph = None
    SimpleDocTemplate = None
    Spacer = None
    Table = None
    TableStyle = None

ARQUIVO_RELATORIO_PADRAO = "Relatorio_Executivo_Nubank.pdf"

# ETAPA PARA TRANSFORMAR CATEGORIAS DO EXCEL EM TEMAS EXECUTIVOS NO PDF

TEMA_POR_CATEGORIA = {
    "Login": "Falhas de acesso/login",
    "Senha": "Problemas com senha",
    "Autenticacao": "Falhas de autenticacao",
    "Conta Bloqueada": "Bloqueio de conta",
    "Biometria": "Problemas com biometria",
    "Cartoes": "Problemas com cartoes e limite",
    "Emprestimo": "Dificuldades com emprestimo",
    "Pix": "Instabilidade no Pix",
    "Transferencias": "Falhas em transferencias",
    "Pagamentos": "Problemas em pagamentos",
    "Saldo": "Divergencias de saldo",
    "Extrato": "Problemas no extrato",
    "App/Bugs": "Erros e instabilidade do aplicativo",
    "Atendimento": "Experiencia com atendimento",
    "Cobranca Indevida": "Cobrancas indevidas",
}


def preparar_datas(df):

    df_relatorio = df.copy()
    df_relatorio["DATA_RELATORIO"] = pd.to_datetime(
        df_relatorio["DATA"],
        dayfirst=True,
        errors="coerce",
    )

    df_relatorio = df_relatorio.dropna(subset=["DATA_RELATORIO"]).copy()

    df_relatorio["MES_PERIODO"] = df_relatorio["DATA_RELATORIO"].dt.to_period("M")
    return df_relatorio


def nome_mes_portugues(periodo):

    nomes_meses = {
        1: "Janeiro",
        2: "Fevereiro",
        3: "Marco",
        4: "Abril",
        5: "Maio",
        6: "Junho",
        7: "Julho",
        8: "Agosto",
        9: "Setembro",
        10: "Outubro",
        11: "Novembro",
        12: "Dezembro",
    }
    return f"{nomes_meses[periodo.month]}/{periodo.year}"

def formatar_numero(valor):

    return f"{int(valor):,}".replace(",", ".")


def formatar_nota(valor):

    return f"{float(valor):.1f}".replace(".", ",")


def top_categorias(df, notas, limite=3):

    filtrado = df[df["NOTA"].isin(notas)]

    if filtrado.empty:
        return []

    return filtrado["CATEGORIA"].value_counts().head(limite).index.tolist()


def temas_das_categorias(categorias):

    return [TEMA_POR_CATEGORIA.get(categoria, categoria) for categoria in categorias]


def distribuicao_notas(df):

    contagem = df["NOTA"].value_counts().to_dict()
    return [[f"{nota} estrela(s)", formatar_numero(contagem.get(nota, 0))] for nota in range(1, 6)]

# ETAPA PARA CRIAR A PARTE VISUAL E DE ESTILOS DO PDF, DEIXANDO COM UM DESIGN MAIS AGRADAVEL

def criar_estilos():

    estilos_base = getSampleStyleSheet()

    estilos = {
        "titulo": ParagraphStyle(
            "TituloRelatorio",
            parent=estilos_base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#4B0082"),
            alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "subtitulo": ParagraphStyle(
            "SubtituloRelatorio",
            parent=estilos_base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#4B0082"),
            spaceBefore=8,
            spaceAfter=8,
        ),
        "texto": ParagraphStyle(
            "TextoRelatorio",
            parent=estilos_base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            spaceAfter=6,
        ),
        "observacao": ParagraphStyle(
            "ObservacaoRelatorio",
            parent=estilos_base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#555555"),
            spaceAfter=8,
        ),
    }

    return estilos


def tabela_simples(dados, larguras=None):

    tabela = Table(dados, colWidths=larguras)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4B0082")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F2FA")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return tabela

# ETAPA PARA CRIAR PAGINAS DE RESUMOS E LISTAS PARA COMPLETAR A APRESENTAÇÃO MAIS OBJETIVA NO PDF

def adicionar_lista(elementos, titulo, itens, estilos):

    elementos.append(Paragraph(titulo, estilos["subtitulo"]))

    if not itens:
        elementos.append(Paragraph("Nao houve dados suficientes para este indicador.", estilos["texto"]))
        return

    for item in itens:
        elementos.append(Paragraph(f"- {item}", estilos["texto"]))


def criar_pagina_mes(elementos, df_mes, periodo, estilos):

    periodo_texto = nome_mes_portugues(periodo)
    total_avaliacoes = len(df_mes)
    nota_media = df_mes["NOTA"].mean()

    categorias_negativas = top_categorias(df_mes, notas=[1, 2, 3])
    categorias_positivas = top_categorias(df_mes, notas=[4, 5])
    temas_negativos = temas_das_categorias(categorias_negativas)

    elementos.append(Paragraph(f"Periodo analisado: {periodo_texto}", estilos["titulo"]))

    indicadores = [
        ["Indicador", "Valor"],
        ["Total de avaliacoes", formatar_numero(total_avaliacoes)],
        ["Nota media", formatar_nota(nota_media)],
    ]
    elementos.append(tabela_simples(indicadores, larguras=[7 * cm, 7 * cm]))
    elementos.append(Spacer(1, 0.35 * cm))

    elementos.append(Paragraph("Distribuicao das notas", estilos["subtitulo"]))
    elementos.append(tabela_simples(
        [["Nota", "Quantidade"]] + distribuicao_notas(df_mes),
        larguras=[7 * cm, 7 * cm],
    ))
    elementos.append(Spacer(1, 0.25 * cm))

    adicionar_lista(
        elementos,
        "Principais categorias negativas",
        categorias_negativas,
        estilos,
    )
    adicionar_lista(
        elementos,
        "Principais temas identificados",
        temas_negativos,
        estilos,
    )
    adicionar_lista(
        elementos,
        "Categorias mais elogiadas",
        categorias_positivas,
        estilos,
    )

    elementos.append(Paragraph(
        "Observacao: categorias negativas usam notas 1, 2 e 3; categorias "
        "elogiadas usam notas 4 e 5.",
        estilos["observacao"],
    ))


def criar_pagina_resumo_geral(elementos, df, estilos):

    total_avaliacoes = len(df)
    nota_media = df["NOTA"].mean()
    meses = sorted(df["MES_PERIODO"].unique())
    periodo_inicial = nome_mes_portugues(meses[0])
    periodo_final = nome_mes_portugues(meses[-1])

    categorias_negativas = top_categorias(df, notas=[1, 2, 3])
    categorias_positivas = top_categorias(df, notas=[4, 5])
    temas_negativos = temas_das_categorias(categorias_negativas)

    elementos.append(Paragraph("Relatorio Executivo - Avaliacoes Nubank", estilos["titulo"]))
    elementos.append(Paragraph(
        f"Periodo geral analisado: {periodo_inicial} a {periodo_final}",
        estilos["texto"],
    ))

    indicadores = [
        ["Indicador", "Valor"],
        ["Total de avaliacoes", formatar_numero(total_avaliacoes)],
        ["Nota media", formatar_nota(nota_media)],
        ["Meses analisados", formatar_numero(len(meses))],
    ]
    elementos.append(tabela_simples(indicadores, larguras=[7 * cm, 7 * cm]))
    elementos.append(Spacer(1, 0.35 * cm))

    adicionar_lista(elementos, "Principais categorias negativas", categorias_negativas, estilos)
    adicionar_lista(elementos, "Principais temas identificados", temas_negativos, estilos)
    adicionar_lista(elementos, "Categorias mais elogiadas", categorias_positivas, estilos)

    elementos.append(Paragraph(
        "As paginas seguintes detalham os indicadores mes a mes.",
        estilos["observacao"],
    ))

# ETAPA QUE ENFIM VAI GERAR O RELATORIO EM PDF

def gerar_relatorio_pdf(df, arquivo_saida=ARQUIVO_RELATORIO_PADRAO):

    if SimpleDocTemplate is None:
        print(
            "reportlab nao esta instalado. O PDF executivo nao foi gerado. "
            "Instale as dependencias com: python -m pip install -r requirements.txt"
        )
        return None

    df_relatorio = preparar_datas(df)

    if df_relatorio.empty:
        print("Nao ha datas validas para gerar o PDF executivo.")
        return None

    caminho_saida = Path(arquivo_saida)
    estilos = criar_estilos()

    documento = SimpleDocTemplate(
        str(caminho_saida),
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title="Relatorio Executivo - Avaliacoes Nubank",
        author="Projeto Avaliacoes Nubank",
    )

    elementos = []
    criar_pagina_resumo_geral(elementos, df_relatorio, estilos)

    for periodo in sorted(df_relatorio["MES_PERIODO"].unique()):
        elementos.append(PageBreak())
        df_mes = df_relatorio[df_relatorio["MES_PERIODO"] == periodo]
        criar_pagina_mes(elementos, df_mes, periodo, estilos)

    documento.build(elementos)
    return str(caminho_saida.resolve())
