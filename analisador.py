import os
import pandas as pd
from typing import Dict, Any, List


class AnalisadorDados:
    """
    Analisa arquivos CSV ou Excel e gera relatório
    com estatísticas, qualidade, score e alertas.
    """

    # ================= TIPO ==================
    def detectar_tipo(self, serie: pd.Series) -> str:
        if pd.api.types.is_numeric_dtype(serie):
            return "inteiro" if pd.api.types.is_integer_dtype(serie) else "decimal"

        valores = serie.dropna()
        if valores.empty:
            return "texto"

        datas = pd.to_datetime(valores, errors="coerce")
        if datas.notna().mean() >= 0.8:
            return "data"

        return "texto"

    # ================= QUALIDADE =============
    def calcular_qualidade(self, serie: pd.Series) -> Dict[str, Any]:
        total = int(len(serie))
        nulos = int(serie.isna().sum())
        unicos = int(serie.nunique(dropna=True))
        duplicados = int(serie.duplicated().sum())

        qualidade = {
            "total_valores": total,
            "nulos": nulos,
            "nulos_pct": round((nulos / total * 100), 1) if total else 0,
            "unicos": unicos,
            "duplicados": duplicados,
            "completude": round(1 - (nulos / total), 2) if total else 0,
            "cardinalidade_pct": round((unicos / total * 100), 1) if total else 0,
        }

        if serie.dtype == object:
            qualidade["strings_vazias"] = int((serie == "").sum())

        if pd.api.types.is_numeric_dtype(serie):
            serie_limpa = serie.dropna()
            if not serie_limpa.empty:
                q1 = serie_limpa.quantile(0.25)
                q3 = serie_limpa.quantile(0.75)
                iqr = q3 - q1

                outliers = serie_limpa[
                    (serie_limpa < q1 - 1.5 * iqr)
                    | (serie_limpa > q3 + 1.5 * iqr)
                ]

                qualidade["outliers"] = int(outliers.count())

        return qualidade

    # ================= STATS =================
    def calcular_stats(self, serie: pd.Series, tipo: str) -> Dict[str, Any]:
        if tipo in {"inteiro", "decimal"}:
            return {
                "Soma": round(float(serie.sum()), 2),
                "Média": round(float(serie.mean()), 2),
                "Máximo": float(serie.max()),
                "Mínimo": float(serie.min()),
            }

        if tipo == "data":
            datas = pd.to_datetime(serie, errors="coerce")
            return {
                "Data Inicial": datas.min().strftime("%d/%m/%Y")
                if not datas.isna().all()
                else "-",
                "Data Final": datas.max().strftime("%d/%m/%Y")
                if not datas.isna().all()
                else "-",
                "Datas Inválidas": int(datas.isna().sum()),
            }

        return {}

    # ================= SCORE (EQUILIBRADO) =================
    def calcular_score(self, qualidade: Dict[str, Any], tipo: str) -> int:
        score = 100
        total = qualidade.get("total_valores", 0)

        if total == 0:
            return 0

        # ❌ NULOS — moderado
        score -= qualidade.get("nulos_pct", 0) * 0.7
        # 20% nulos = -14 pts

        # ❌ DUPLICADOS — moderado
        dup_pct = qualidade["duplicados"] / total * 100
        score -= dup_pct * 0.4

        # ❌ CARDINALIDADE EXTREMA
        card_pct = qualidade.get("cardinalidade_pct", 0)

        # Tudo igual
        if card_pct <= 1:
            score -= 10

        # Tudo único (texto suspeito)
        if card_pct >= 98 and tipo == "texto":
            score -= 5

        # ❌ OUTLIERS — leve e proporcional
        if tipo in {"inteiro", "decimal"}:
            outliers = qualidade.get("outliers", 0)
            out_pct = outliers / total * 100
            score -= out_pct * 0.6

        # ❌ STRINGS VAZIAS — leve
        if tipo == "texto":
            vazias = qualidade.get("strings_vazias", 0)
            score -= (vazias / total) * 100 * 0.3

        return max(0, min(100, int(round(score))))

    # ================= ALERTAS ===============
    def gerar_alertas(self, qualidade: Dict[str, Any], tipo: str) -> List[str]:
        alertas = []

        if qualidade.get("nulos_pct", 0) >= 20:
            alertas.append("Alta taxa de valores nulos")

        if qualidade.get("duplicados", 0) > 0:
            alertas.append("Valores duplicados")

        if qualidade.get("unicos", 0) == qualidade.get("total_valores", 0):
            alertas.append("Possível chave primária")

        if tipo in {"inteiro", "decimal"} and qualidade.get("outliers", 0) > 0:
            alertas.append("Outliers detectados")

        if tipo == "texto" and qualidade.get("strings_vazias", 0) > 0:
            alertas.append("Strings vazias detectadas")

        if tipo == "data" and qualidade.get("nulos", 0) > 0:
            alertas.append("Datas inválidas ou ausentes")

        return alertas

    # ================= LEITURA ===============
    def carregar_arquivo(self, caminho_arquivo: str) -> pd.DataFrame:
        extensao = os.path.splitext(caminho_arquivo)[1].lower()

        if extensao == ".csv":
            return pd.read_csv(
                caminho_arquivo,
                sep=None,
                engine="python",
                encoding="utf-8",
                on_bad_lines="skip",
            )

        if extensao in {".xls", ".xlsx"}:
            return pd.read_excel(caminho_arquivo)

        raise ValueError("Formato de arquivo não suportado")

    # ================= PROCESSAMENTO =========
    def processar(self, caminho_arquivo: str) -> Dict[str, Any]:
        df = self.carregar_arquivo(caminho_arquivo)

        relatorio = {
            "resumo": {
                "linhas": int(len(df)),
                "colunas": int(len(df.columns)),
            },
            "detalhes": {},
            "score_geral": 0,
            "alertas_globais": [],
        }

        scores = []
        alertas_globais = []

        for coluna in df.columns:
            serie = df[coluna]
            tipo = self.detectar_tipo(serie)
            qualidade = self.calcular_qualidade(serie)

            score = self.calcular_score(qualidade, tipo)
            alertas = self.gerar_alertas(qualidade, tipo)

            scores.append(score)

            for alerta in alertas:
                alertas_globais.append(f"{coluna}: {alerta}")

            relatorio["detalhes"][coluna] = {
                "tipo": tipo,
                "stats": self.calcular_stats(serie, tipo),
                "qualidade": qualidade,
                "score": score,
                "alertas": alertas,
            }

        if scores:
            relatorio["score_geral"] = round(sum(scores) / len(scores), 1)

        relatorio["alertas_globais"] = sorted(set(alertas_globais))

        return relatorio