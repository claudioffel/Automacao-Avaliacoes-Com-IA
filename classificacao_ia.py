import json
import re
import unicodedata
from collections import Counter
from urllib import request

try:
    import ollama
except ImportError:
    ollama = None

# ETAPA DE DEFINIÇÃO DE REGRAS DE CONFIANÇA NUMÉRICA DOS RESULTADOS E DE QUANDO USAR A IA (OLLAMA)

MODELO_OLLAMA = "llama3:latest"

USAR_OLLAMA_FALLBACK = True

CONFIANCA_MINIMA = 0.45

CONFIANCA_VALIDACAO_IA = 0.40

MARGEM_EMPATE_TECNICO = 0.35

# ETAPA PARA DEFINIR SETORES E CATEGORIAS PRÉ DEFINIDOS PARA O MAPEAMENTO DOS COMENTÁRIOS

categorias_por_setor = {
    "Acesso e Login": [
        "Login",
        "Senha",
        "Autenticacao",
        "Conta Bloqueada",
        "Biometria",
    ],
    "Cartoes e Credito": [
        "Cartoes",
        "Emprestimo",
    ],
    "Operacoes Financeiras": [
        "Pix",
        "Transferencias",
        "Pagamentos",
    ],
    "Conta e Saldo": [
        "Saldo",
        "Extrato",
    ],
    "Aplicativo e Erros": [
        "App/Bugs",
    ],
    "Atendimento": [
        "Atendimento",
    ],
    "Cobranca": [
        "Cobranca Indevida",
    ],
}

categoria_para_setor = {
    categoria: setor
    for setor, categorias in categorias_por_setor.items()
    for categoria in categorias
}

# ETAPA PARA DEFINIR PRIORIDADES E PALAVRAS CHAFEs E ASSIM FACILITAR A CLASSIFICAÇÃO DOS COMENTARIOS

regras_categoria = {
    "Senha": [
        "senha", "redefinir senha", "esqueci minha senha", "senha invalida",
        "recuperar senha", "trocar senha",
    ],
    "Autenticacao": [
        "codigo", "autenticacao", "2fa", "token", "sms", "codigo nao chega",
        "validacao", "verificacao",
    ],
    "Conta Bloqueada": [
        "bloqueada", "bloqueado", "bloquearam", "conta bloqueada",
        "acesso bloqueado",
    ],
    "Biometria": [
        "biometria", "digital", "face id", "reconhecimento facial",
        "rosto", "camera", "foto", "reconhecimento",
    ],
    "Login": [
        "login", "acessar", "entrar", "acesso", "abrir minha conta",
        "nao consigo acessar",
    ],
    "Emprestimo": [
        "emprestimo", "emprestimos", "contratar emprestimo", "credito pessoal",
    ],
    "Cartoes": [
        "cartao", "cartao de credito", "cartao de debito", "credito", "debito",
        "limite", "compra recusada", "recusado", "nao passa", "cartao fisico",
    ],
    "Pix": [
        "pix", "chave pix", "pix indisponivel", "qr code", "copia e cola",
    ],
    "Transferencias": [
        "transferencia", "transferir", "ted", "doc", "envio falhou",
        "processamento", "falha",
    ],
    "Pagamentos": [
        "boleto", "boletos", "pagar", "pagamento", "deposito", "depositar",
        "fatura", "conta paga", "nao caiu",
    ],
    "Extrato": [
        "extrato", "lancamento", "lancamentos", "historico", "movimentacao",
    ],
    "Saldo": [
        "saldo", "sumiu", "desapareceu", "rendimento", "rendimentos",
        "caixinha", "conta pj", "conta corrente", "valor incorreto",
        "valores incorretos",
    ],
    "Atendimento": [
        "chat", "atendente", "atendimento", "responde", "demora", "sem solucao",
        "suporte", "resolver problema", "falar com uma pessoa",
        "respostas automaticas", "sem retorno", "protocolo", "reclamacao",
    ],
    "App/Bugs": [
        "aplicativo", "app", "trava", "travando", "lento", "lentidao",
        "atualizacao", "erro", "erros", "notificacao", "notificacoes",
        "interface", "bug", "falha no app", "congela", "fecha sozinho",
        "menus", "erro inesperado", "cache",
    ],
    "Cobranca Indevida": [
        "cobranca indevida", "cobranca", "cobrado", "cobraram", "indevida",
        "valor cobrado", "fatura errada", "compra duplicada", "contestar",
    ],
}

prioridade_desempate = [
    "Cobranca Indevida",
    "Senha",
    "Autenticacao",
    "Conta Bloqueada",
    "Biometria",
    "Emprestimo",
    "Cartoes",
    "Pix",
    "Transferencias",
    "Pagamentos",
    "Extrato",
    "Saldo",
    "Atendimento",
    "App/Bugs",
    "Login",
]

stopwords = {
    "a", "o", "os", "as", "um", "uma", "de", "do", "da", "dos", "das",
    "e", "em", "no", "na", "nos", "nas", "meu", "minha", "meus", "minhas",
    "nao", "nunca", "sem", "com", "por", "para", "pra", "que", "esta",
    "estao", "foi", "veio", "apos", "toda", "todo", "varios", "varias",
}


# ETAPA PARA NORMALIZAR E LIMPAR OS COMENTARIOS ANTES DE JOGAR PRA PLANILHA

def normalizar(texto):
   
    texto = str(texto).lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    texto = re.sub(r"[^a-z0-9\s/]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def tokenizar(texto):
   
    texto = normalizar(texto)
    return {
        token
        for token in texto.split()
        if len(token) > 2 and token not in stopwords
    }

prototipos_categoria = {
    categoria: tokenizar(" ".join(termos))
    for categoria, termos in regras_categoria.items()
}


def pontuar_por_regras(comentario):

    texto = normalizar(comentario)
    scores = Counter()

    for categoria, termos in regras_categoria.items():
        for termo in termos:
            termo_normalizado = normalizar(termo)
            if termo_normalizado in texto:
                peso = 3 if " " in termo_normalizado else 1
                scores[categoria] += peso

    return scores


def pontuar_por_similaridade(comentario):

    tokens_comentario = tokenizar(comentario)
    scores = Counter()

    if not tokens_comentario:
        return scores

    for categoria, tokens_prototipo in prototipos_categoria.items():
        intersecao = tokens_comentario & tokens_prototipo
        uniao = tokens_comentario | tokens_prototipo
        if uniao:
            scores[categoria] = len(intersecao) / len(uniao)

    return scores

# ETAPA PARA REFINAR A LOGICA DA REGRA APLICADA, DIMINUINDO OS ERROS DNA DEFINIÇÃO DE CATEGORIAS

def rerank_validacao(comentario, categoria, score):

    texto = normalizar(comentario)

    if "conta pj" in texto:
        categoria = "Saldo"
        score += 4

    if categoria == "Login" and any(p in texto for p in ["senha", "codigo", "bloquead", "biometria"]):
        score -= 2

    if any(p in texto for p in ["codigo", "sms", "token", "confirmacao", "verificacao"]):
        if any(p in texto for p in ["nao chega", "nunca chega", "nao recebo", "nao aparece", "enviado"]):
            categoria = "Autenticacao"
            score += 4

    if "senha" in texto and any(p in texto for p in ["redefinir", "incorreta", "nova senha"]):
        categoria = "Senha"
        score += 4

    if any(p in texto for p in ["rosto", "camera", "foto", "reconhecimento"]):
        if any(p in texto for p in ["validacao", "biometria", "funciona", "rejeita"]):
            categoria = "Biometria"
            score += 4

    if "fatura" in texto and "errada" in texto:
        categoria = "Cobranca Indevida"
        score += 4

    if "cobranca" in texto or "cobrado" in texto or "cobraram" in texto:
        if any(p in texto for p in ["indevida", "duplicada", "errada", "contestar"]):
            categoria = "Cobranca Indevida"
            score += 4

    if "transferencia" in texto and any(p in texto for p in ["falha", "processamento"]):
        categoria = "Transferencias"
        score += 4

    if "extrato" in texto:
        categoria = "Extrato"
        score += 4

    if categoria == "Cartoes" and "emprestimo" in texto:
        categoria = "Emprestimo"
        score += 3

    if categoria == "App/Bugs" and any(p in texto for p in ["chat", "atendente", "atendimento"]):
        categoria = "Atendimento"
        score += 3

    if any(p in texto for p in ["falar com uma pessoa", "respostas automaticas", "suporte", "protocolo", "sem retorno"]):
        categoria = "Atendimento"
        score += 4

    if any(p in texto for p in ["interface", "menus", "congela", "fecha sozinho", "erro inesperado"]):
        categoria = "App/Bugs"
        score += 4

    return categoria, score

# ETAPA PARA DEFINIR QUANDO CHAMAR A IA, SÓ EM CASOS EM QUE A REGRA REPRESENTA UMA CONFIANÇA BAIXA OU EMPATE TECNICO

def deve_validar_com_ia(confianca, scores_finais):

    ordenados = sorted(scores_finais.items(), key=lambda item: item[1], reverse=True)
    categorias_com_sinal = [item for item in ordenados if item[1] > 0]

    if confianca < CONFIANCA_VALIDACAO_IA:
        return True

    if len(categorias_com_sinal) >= 2:
        diferenca_top_2 = categorias_com_sinal[0][1] - categorias_com_sinal[1][1]
        if diferenca_top_2 <= MARGEM_EMPATE_TECNICO:
            return True

    if len(categorias_com_sinal) >= 3 and confianca < CONFIANCA_MINIMA:
        return True

    return False


def escolher_candidatas_para_ia(scores_finais):

    ordenados = sorted(scores_finais.items(), key=lambda item: item[1], reverse=True)
    candidatas = [categoria for categoria, score in ordenados if score > 0][:5]
    return candidatas or list(categoria_para_setor.keys())

def chamar_ollama_texto(prompt, timeout=120):

    if ollama is not None:
        resposta = ollama.chat(
            model=MODELO_OLLAMA,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0},
        )
        return resposta["message"]["content"]

    payload = {
        "model": MODELO_OLLAMA,
        "messages": [{"role": "user", "content": prompt}],
        "options": {"temperature": 0},
        "stream": False,
    }
    dados = json.dumps(payload).encode("utf-8")
    req = request.Request(
        "http://localhost:11434/api/chat",
        data=dados,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as resp:
        resposta = json.loads(resp.read().decode("utf-8"))
    return resposta["message"]["content"]

# ETAPA ONDE ESTOU DIZENDO PARA A IA O QUE ELA DEVE FAZER 

def classificar_com_ollama(comentario, categorias_candidatas=None):

    if not USAR_OLLAMA_FALLBACK:
        return None, None

    categorias = categorias_candidatas or list(categoria_para_setor.keys())
    opcoes = "\n".join(
        f"{i + 1} = {categoria} ({categoria_para_setor[categoria]})"
        for i, categoria in enumerate(categorias)
    )

    prompt = f"""
Voce e um classificador de comentarios de app bancario.

Escolha APENAS UMA categoria da lista abaixo.
Priorize o problema principal relatado pelo usuario.
Ignore palavras secundarias quando elas apenas aparecem como contexto.
Responda somente com o numero.

Categorias:
{opcoes}

Comentario:
{comentario}
"""

    try:
        conteudo = chamar_ollama_texto(prompt, timeout=60)

        match = re.search(r"\d+", conteudo)
        if not match:
            return None, None

        indice = int(match.group()) - 1
        if indice < 0 or indice >= len(categorias):
            return None, None

        categoria = categorias[indice]
        return categoria_para_setor[categoria], categoria
    except Exception:

        return None, None

# ETAPA DO CLASSIFICADOR PRINCIPAL, ONDE V=CLASSIFICA OS COMENTARIOS USANDO REGRAS, SIMILARIDADES E IA

def classificar_com_hibrido(comentario):

    scores_regras = pontuar_por_regras(comentario)
    scores_similaridade = pontuar_por_similaridade(comentario)
    scores_finais = Counter()

    for categoria in regras_categoria:

        scores_finais[categoria] = scores_regras[categoria] + scores_similaridade[categoria] * 2

    categorias_candidatas_ia = escolher_candidatas_para_ia(scores_finais)

    categoria, score = max(
        scores_finais.items(),
        key=lambda item: (item[1], -prioridade_desempate.index(item[0])),
    )

    categoria, score = rerank_validacao(comentario, categoria, score)
    setor = categoria_para_setor[categoria]
    metodo = "regras/similaridade"

    confianca = min(score / 6, 1)
    tem_regra_util = scores_regras[categoria] > 0

    precisa_ia = (
        (not tem_regra_util and confianca < CONFIANCA_MINIMA)
        or deve_validar_com_ia(confianca, scores_finais)
    )

    if precisa_ia:
        setor_ia, categoria_ia = classificar_com_ollama(comentario, categorias_candidatas_ia)
        if setor_ia and categoria_ia:
            resultado_ia = (setor_ia, categoria_ia)

            if not tem_regra_util:
                return setor_ia, categoria_ia, "ollama fallback", confianca, True, resultado_ia

            if categoria_ia == categoria:
                return setor, categoria, "regras + ia confirmou", confianca, True, resultado_ia

            return setor, categoria, "regras + ia consultada", confianca, True, resultado_ia

    return setor, categoria, metodo, confianca, False, None


# ETAPA QUE VAI CRIAR A SEGUNDA ABA DO EXCEL, PARA CRIAR OS REUMOS DOS COMENTARIOS POSITIVOS E NEGATIVOS DIVIDO PELOS CATEGORIAS

def sentimento_por_nota(nota):

    try:
        nota = int(nota)
    except (TypeError, ValueError):
        return None

    if nota in (1, 2, 3):
        return "Negativo"
    if nota in (4, 5):
        return "Positivo"
    return None


def limitar_amostra_comentarios(comentarios_grupo, limite_comentarios=80, limite_caracteres=6000):

    linhas = []
    tamanho = 0

    for comentario in comentarios_grupo[:limite_comentarios]:
        linha = f"- {str(comentario).strip()}"
        if tamanho + len(linha) > limite_caracteres:
            break
        linhas.append(linha)
        tamanho += len(linha)

    return "\n".join(linhas)


def resumir_grupo_com_ia(categoria, sentimento, comentarios_grupo):

    if not USAR_OLLAMA_FALLBACK or not comentarios_grupo:
        return ""

    amostra = limitar_amostra_comentarios(comentarios_grupo)
    prompt = f"""
Voce esta analisando comentarios da Play Store de um app bancario.

Categoria: {categoria}
Sentimento: {sentimento}
Quantidade total de comentarios neste grupo: {len(comentarios_grupo)}

Escreva um resumo curto, em portugues, com 1 ou 2 frases.
Foque nos temas mais recorrentes.
Nao invente numeros, causas, produtos ou detalhes que nao aparecam nos comentarios.
Nao use lista. Responda apenas o texto do resumo.

Comentarios:
{amostra}
"""

    try:
        resumo = chamar_ollama_texto(prompt, timeout=120).strip()
        return re.sub(r"\s+", " ", resumo)
    except Exception:
        return ""


def gerar_resumos_ia(registros_classificados):

    grupos = {}

    for registro in registros_classificados:
        categoria = registro.get("CATEGORIA") or registro.get("categoria")
        comentario = registro.get("COMENTARIO") or registro.get("comentario")
        sentimento = (
            registro.get("SENTIMENTO_IA")
            or registro.get("sentimento")
            or sentimento_por_nota(registro.get("NOTA") or registro.get("nota"))
        )

        if not categoria or not comentario or not sentimento:
            continue

        chave = (categoria, sentimento)
        grupos.setdefault(chave, []).append(comentario)

    linhas = []
    for (categoria, sentimento), comentarios_grupo in sorted(grupos.items()):
        linhas.append({
            "Categoria": categoria,
            "Sentimento": sentimento,
            "Qtde Comentarios": len(comentarios_grupo),
            "Resumo IA": resumir_grupo_com_ia(categoria, sentimento, comentarios_grupo),
        })

    return linhas
