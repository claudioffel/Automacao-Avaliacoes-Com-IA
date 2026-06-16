import re

import pandas as pd

from classificacao_ia import classificar_com_hibrido, gerar_resumos_ia
from relatorio_pdf import gerar_relatorio_pdf

ARQUIVO_SAIDA = "Avaliacoes_Nubank_Tratadas.xlsx"

ARQUIVO_RELATORIO = "Relatorio_Executivo_Nubank.pdf"

TOTAL_DESEJADO = 2000

# ETAPA DE COLETA DAS AVALIAÇÕES DA PLAY STORE, UTILIZANDO A BIBLIOTECA GOOGLE_PLAY_SCRAPER

def coletar_avaliacoes(total_desejado=TOTAL_DESEJADO):
 
    from google_play_scraper import reviews

    todas_avaliacoes = []
    continuation_token = None

    while len(todas_avaliacoes) < total_desejado:
        resultado, continuation_token = reviews(
            "com.nu.production",
            lang="pt",
            country="br",
            count=200,
            continuation_token=continuation_token,
        )
        todas_avaliacoes.extend(resultado)

        print(f"{len(todas_avaliacoes)} avaliacoes coletadas")

        if continuation_token is None:
            break

    return todas_avaliacoes[:total_desejado]


# ETAPA DE LIMPEZA E TRATAMENTO DOS COMENTARIOS E DA TABELA GERADA NO EXCEL

def remover_emojis(texto):

    if pd.isna(texto):

        return ""

    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002700-\U000027BF"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )

    return emoji_pattern.sub("", str(texto))


def classificar_tamanho(comentario):

    qtd_palavras = len(str(comentario).split())

    if qtd_palavras <= 4:
        return "Comentario Curto"

    return "Comentario Longo"


def classificar_satisfacao(nota):

    if nota == 1:
        return "Pessimo"
    if nota == 2:
        return "Ruim"
    if nota == 3:
        return "Neutro"
    if nota == 4:
        return "Bom"
    if nota == 5:
        return "Otimo"

    return "Nao Classificado"


def montar_dataframe(avaliacoes):

    df = pd.DataFrame(avaliacoes)

    df = df[
        [
            "reviewId",
            "content",
            "score",
            "thumbsUpCount",
            "at",
            "appVersion",
        ]
    ]

    df.columns = [
        "ID",
        "COMENTARIO",
        "NOTA",
        "LIKES",
        "DATA",
        "VERSAO_APP",
    ]

    df["COMENTARIO"] = (
        df["COMENTARIO"]
        .apply(remover_emojis)
        .fillna("")
        .str.strip()
    )

    df = df[df["COMENTARIO"] != ""].copy()

    df["DATA"] = pd.to_datetime(df["DATA"])
    df["DATA"] = df["DATA"].dt.strftime("%d/%m/%Y")

    df["TAMANHO"] = df["COMENTARIO"].apply(classificar_tamanho)
    df["SATISFACAO"] = df["NOTA"].apply(classificar_satisfacao)

    return df

# ETAPA PARA MONTAR A ESTRUTURA DA CLASSIFICAÇÃO HIBRIDA, QUE VAI SER DE REGRA + IA

def aplicar_classificacao(df):
    
    setores = []
    categorias = []
    chamadas_ia = 0

    for indice, comentario in enumerate(df["COMENTARIO"], start=1):
        
        setor, categoria, _metodo, _confianca, ia_chamada, _resultado_ia = classificar_com_hibrido(comentario)

        setores.append(setor)
        categorias.append(categoria)
        chamadas_ia += int(ia_chamada)

        if indice % 100 == 0:
            print(f"{indice} comentarios classificados")

    df["SETOR"] = setores
    df["CATEGORIA"] = categorias
    print(f"Chamadas para IA na classificacao: {chamadas_ia}")

    return df

# ETAPA PARA EXPORTAR A PLANILHA EM EXCEL

def gerar_aba_resumos(df):

    registros = df.to_dict(orient="records")
    return pd.DataFrame(
        gerar_resumos_ia(registros),
        columns=["Categoria", "Sentimento", "Qtde Comentarios", "Resumo IA"],
    )

def exportar_excel(df, arquivo_saida=ARQUIVO_SAIDA):

    df_resumos = gerar_aba_resumos(df)

    colunas_comentarios = [
        "ID",
        "COMENTARIO",
        "SETOR",
        "CATEGORIA",
        "NOTA",
        "LIKES",
        "DATA",
        "VERSAO_APP",
        "TAMANHO",
        "SATISFACAO",
    ]

    with pd.ExcelWriter(arquivo_saida, engine="openpyxl") as writer:
        df[colunas_comentarios].to_excel(writer, sheet_name="comentarios", index=False)
        df_resumos.to_excel(writer, sheet_name="resumos_ia", index=False)

        ws_comentarios = writer.book["comentarios"]
        ws_resumos = writer.book["resumos_ia"]

        ws_comentarios.freeze_panes = "A2"
        ws_resumos.freeze_panes = "A2"

        larguras_comentarios = {
            "A": 38,
            "B": 85,
            "C": 24,
            "D": 24,
            "E": 10,
            "F": 10,
            "G": 14,
            "H": 16,
            "I": 18,
            "J": 16,
        }
        larguras_resumos = {
            "A": 24,
            "B": 14,
            "C": 18,
            "D": 90,
        }

        for coluna, largura in larguras_comentarios.items():
            ws_comentarios.column_dimensions[coluna].width = largura

        for coluna, largura in larguras_resumos.items():
            ws_resumos.column_dimensions[coluna].width = largura

# ETAPA PARA ORGANIZAR E EXECUTAR O FLUXO COMPLETO DO PROJETO

def main():
    
    avaliacoes = coletar_avaliacoes()
    df = montar_dataframe(avaliacoes)
    df = aplicar_classificacao(df)
    exportar_excel(df)
    caminho_pdf = gerar_relatorio_pdf(df, ARQUIVO_RELATORIO)

    print("\nArquivo gerado com sucesso!")
    print(ARQUIVO_SAIDA)

    if caminho_pdf:
        print("Relatorio PDF gerado com sucesso!")
        print(caminho_pdf)

if __name__ == "__main__":
    main()
