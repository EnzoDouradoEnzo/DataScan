import os
import uuid
import sys
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

from analisador import AnalisadorDados

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor


# ================= FUNÇÃO PARA PYINSTALLER =================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


# ================= CONFIG =================
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}
MAX_FILE_SIZE = 20 * 1024 * 1024

# ================= APP ====================
app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static"),
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

motor = AnalisadorDados()


# ================= UTILS ==================
def arquivo_permitido(nome):
    return "." in nome and nome.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ================= ROTAS ==================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "arquivo" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files["arquivo"]

    if file.filename == "":
        return jsonify({"error": "Arquivo vazio"}), 400

    if not arquivo_permitido(file.filename):
        return jsonify({"error": "Formato não permitido"}), 400

    nome_original = secure_filename(file.filename)
    nome_unico = f"{uuid.uuid4().hex}_{nome_original}"
    caminho = os.path.join(app.config["UPLOAD_FOLDER"], nome_unico)

    try:
        file.save(caminho)

        relatorio = motor.processar(caminho)
        relatorio["nome_arquivo"] = nome_original
        relatorio["arquivo_servidor"] = nome_unico

        return jsonify(relatorio)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= PDF ====================

def quebrar_texto(texto, max_chars=60):
    """
    Divide texto longo em várias linhas automaticamente
    """
    palavras = texto.split()
    linhas = []
    linha_atual = ""

    for palavra in palavras:
        if len(linha_atual) + len(palavra) < max_chars:
            linha_atual += palavra + " "
        else:
            linhas.append(linha_atual.strip())
            linha_atual = palavra + " "

    if linha_atual:
        linhas.append(linha_atual.strip())

    return linhas


def gerar_pdf(relatorio: dict, caminho_pdf: str):
    c = canvas.Canvas(caminho_pdf, pagesize=A4)
    largura, altura = A4

    # ===== CORES =====
    verde = HexColor("#22c55e")
    azul = HexColor("#3b82f6")
    amarelo = HexColor("#f59e0b")
    vermelho = HexColor("#ef4444")
    cinza = HexColor("#64748b")
    fundo = HexColor("#f8fafc")

    # ================= HEADER =================
    def desenhar_header():
        c.setFillColor(azul)
        c.rect(0, altura - 2.5 * cm, largura, 2.5 * cm, fill=1, stroke=0)

        c.setFillColor(HexColor("#ffffff"))
        c.setFont("Helvetica-Bold", 18)
        c.drawString(2 * cm, altura - 1.6 * cm, "Relatório DataScan")

        c.setFont("Helvetica", 10)
        c.drawString(
            2 * cm,
            altura - 2.2 * cm,
            f"Arquivo: {relatorio['nome_arquivo']}",
        )

    def nova_pagina():
        c.showPage()
        desenhar_header()
        return altura - 3.5 * cm

    desenhar_header()
    y = altura - 3.5 * cm

    resumo = relatorio["resumo"]

    # ================= CARD RESUMO =================
    c.setFillColor(fundo)
    c.roundRect(2 * cm, y - 2.2 * cm, largura - 4 * cm, 2 * cm, 10, fill=1)

    c.setFillColor(cinza)
    c.setFont("Helvetica", 11)
    c.drawString(2.5 * cm, y - 0.9 * cm, f"Linhas: {resumo['linhas']}")
    c.drawString(7 * cm, y - 0.9 * cm, f"Colunas: {resumo['colunas']}")

    # ================= SCORE =================
    score = relatorio.get("score_geral", 0)

    if score >= 80:
        cor = verde
        status = "Excelente"
    elif score >= 60:
        cor = azul
        status = "Bom"
    elif score >= 40:
        cor = amarelo
        status = "Atenção"
    else:
        cor = vermelho
        status = "Crítico"

    c.setFillColor(cor)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(largura - 6 * cm, y - 1.6 * cm, f"{score}/100")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(largura - 6 * cm, y - 2.1 * cm, status)

    y -= 3 * cm

    # ================= COLUNAS =================
    for coluna, info in relatorio["detalhes"].items():

        alertas = info.get("alertas", [])

        # altura dinâmica do card
        altura_card = 3.5 * cm + (len(alertas) * 0.6 * cm)

        if y < altura_card + 3 * cm:
            y = nova_pagina()

        # CARD FUNDO
        c.setFillColor(fundo)
        c.roundRect(2 * cm, y - altura_card, largura - 4 * cm, altura_card, 10, fill=1)

        # TITULO
        c.setFillColor(HexColor("#000000"))
        c.setFont("Helvetica-Bold", 12)
        c.drawString(2.5 * cm, y - 0.6 * cm, coluna)

        # TIPO E SCORE
        c.setFont("Helvetica", 10)
        c.setFillColor(cinza)
        c.drawString(
            2.5 * cm,
            y - 1.1 * cm,
            f"Tipo: {info['tipo']} | Score: {info['score']}/100"
        )

        # STATS
        stats = info["stats"]
        y_cursor = y - 1.6 * cm

        for k, v in stats.items():
            c.drawString(2.5 * cm, y_cursor, f"{k}: {v}")
            y_cursor -= 0.45 * cm

        # QUALIDADE
        q = info["qualidade"]
        texto_q = (
            f"Nulos: {q['nulos']} ({q['nulos_pct']}%) | "
            f"Duplicados: {q['duplicados']} | "
            f"Únicos: {q['unicos']}"
        )

        c.drawString(2.5 * cm, y_cursor, texto_q)
        y_cursor -= 0.6 * cm

        # ================= ALERTAS (CORRIGIDO) =================
        if alertas:
            c.setFont("Helvetica", 9)
            c.setFillColor(amarelo)

            for alerta in alertas:
                linhas = quebrar_texto("⚠ " + alerta, max_chars=65)

                for linha in linhas:
                    c.drawString(2.8 * cm, y_cursor, linha)
                    y_cursor -= 0.45 * cm

        y = y - altura_card - 0.8 * cm

    c.save()


@app.route("/exportar-pdf", methods=["POST"])
def exportar_pdf():
    dados = request.json

    if not dados:
        return jsonify({"error": "Dados inválidos"}), 400

    nome_pdf = f"relatorio_{dados['nome_arquivo']}.pdf"
    caminho_pdf = os.path.join(app.config["UPLOAD_FOLDER"], nome_pdf)

    gerar_pdf(dados, caminho_pdf)

    return send_file(
        caminho_pdf,
        as_attachment=True,
        download_name=nome_pdf,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
