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
    """
    Corrige caminhos quando o app roda empacotado no .exe
    """
    try:
        base_path = sys._MEIPASS  # PyInstaller temp folder
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


# ================= CONFIG =================
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# ================= APP ====================
app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static"),
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

# Cria pasta uploads sempre que iniciar
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

    def nova_pagina():
        c.showPage()
        desenhar_header()
        return altura - 3.5 * cm

    def desenhar_header():
        # Faixa superior
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

    desenhar_header()
    y = altura - 3.5 * cm

    resumo = relatorio["resumo"]

    # ===== CARD RESUMO =====
    c.setFillColor(fundo)
    c.roundRect(2 * cm, y - 2.2 * cm, largura - 4 * cm, 2 * cm, 10, fill=1)
    c.setFillColor(cinza)
    c.setFont("Helvetica", 11)
    c.drawString(2.5 * cm, y - 0.9 * cm, f"Linhas: {resumo['linhas']}")
    c.drawString(7 * cm, y - 0.9 * cm, f"Colunas: {resumo['colunas']}")

    # ===== SCORE GERAL =====
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

    # ===== ALERTAS GLOBAIS =====
    alertas = relatorio.get("alertas_globais", [])
    if alertas:
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(HexColor("#000000"))
        c.drawString(2 * cm, y, "Alertas Globais")
        y -= 0.6 * cm

        c.setFont("Helvetica", 10)
        c.setFillColor(cinza)
        for alerta in alertas:
            if y < 3 * cm:
                y = nova_pagina()
            c.drawString(2.5 * cm, y, f"• {alerta}")
            y -= 0.45 * cm

        y -= 0.6 * cm

    # ===== COLUNAS =====
    for coluna, info in relatorio["detalhes"].items():
        if y < 6 * cm:
            y = nova_pagina()

        c.setFillColor(fundo)
        altura_card = 4.2 * cm if info["tipo"] in ["inteiro", "decimal", "data"] else 3.5 * cm
        c.roundRect(2 * cm, y - altura_card, largura - 4 * cm, altura_card, 10, fill=1)

        c.setFillColor(HexColor("#000000"))
        c.setFont("Helvetica-Bold", 12)
        c.drawString(2.5 * cm, y - 0.6 * cm, coluna)

        c.setFont("Helvetica", 10)
        c.setFillColor(cinza)
        c.drawString(
            2.5 * cm,
            y - 1.1 * cm,
            f"Tipo: {info['tipo']} | Score: {info['score']}/100"
        )

        stats = info["stats"]
        y_cursor = y - 1.6 * cm
        for k, v in stats.items():
            if y_cursor < 3 * cm:
                y_cursor = nova_pagina() - 1.6 * cm
            c.drawString(2.5 * cm, y_cursor, f"{k}: {v}")
            y_cursor -= 0.45 * cm

        q = info["qualidade"]
        linha_qualidade = y_cursor

        q_texto = (
            f"Nulos: {q['nulos']} ({q['nulos_pct']}%) | "
            f"Duplicados: {q['duplicados']} | "
            f"Únicos: {q['unicos']}"
        )

        if "strings_vazias" in q:
            q_texto += f" | Strings vazias: {q['strings_vazias']}"
        if "outliers" in q:
            q_texto += f" | Outliers: {q['outliers']}"

        c.drawString(2.5 * cm, linha_qualidade, q_texto)
        y = linha_qualidade - 1.2 * cm

        if info.get("alertas"):
            for alerta in info["alertas"]:
                if y < 3 * cm:
                    y = nova_pagina()
                c.setFont("Helvetica", 9)
                c.setFillColor(amarelo)
                c.drawString(2.8 * cm, y, f"⚠ {alerta}")
                y -= 0.4 * cm

        y -= 0.6 * cm

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
