import os
import uuid
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

from analisador import AnalisadorDados

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor

# ================= CONFIG =================
UPLOAD_FOLDER = "/tmp/uploads"
ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# ================= APP ====================
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

motor = AnalisadorDados()

# ================= UTILS ==================
def arquivo_permitido(nome):
    return "." in nome and nome.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ================= ROTAS ==================
@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "API online"})

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

    c.setFillColor(fundo)
    c.roundRect(2 * cm, y - 2.2 * cm, largura - 4 * cm, 2 * cm, 10, fill=1)
    c.setFillColor(cinza)
    c.setFont("Helvetica", 11)
    c.drawString(2.5 * cm, y - 0.9 * cm, f"Linhas: {resumo['linhas']}")
    c.drawString(7 * cm, y - 0.9 * cm, f"Colunas: {resumo['colunas']}")

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

# ================= VERCEL HANDLER =================
def handler(environ, start_response):
    return app(environ, start_response)