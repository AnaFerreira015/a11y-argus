# coding: utf-8
import os
import json
import pandas as pd
from collections import defaultdict

# Caminho base onde estão as pastas output_dir_<app>
BASE_DIR = "."

# Inicializa estruturas
falhas_por_tela = []
frequencia_falhas_app = defaultdict(lambda: defaultdict(int))
ranking_falhas = defaultdict(lambda: {"apps": set(), "total": 0})
wcag_distribution = defaultdict(int)

def process_errors(app_name, screen_id, error_list):
    for error in error_list:
        tipo = error["type"]
        criterio = error.get("Success Criterion", "")
        nivel = error.get("Level", "")

        falhas_por_tela.append({
            "App": app_name,
            "Tela (screen_id)": screen_id,
            "Tipo de Falha": tipo,
            "Critério WCAG": criterio,
            "Nível": nivel,
            "Contagem": 1
        })

        chave = (tipo, criterio, nivel)
        frequencia_falhas_app[app_name][chave] += 1
        ranking_falhas[tipo]["apps"].add(app_name)
        ranking_falhas[tipo]["total"] += 1
        wcag_distribution[nivel] += 1

# Percorre os diretórios de cada app
for pasta_app in os.listdir(BASE_DIR):
    if not pasta_app.startswith("output_dir_"):
        continue

    app_path = os.path.join(BASE_DIR, pasta_app)
    app_name = pasta_app.replace("output_dir_", "")
    results_path = os.path.join(app_path, "results")

    if not os.path.isdir(results_path):
        continue

    for pasta_result in os.listdir(results_path):
        result_path = os.path.join(results_path, pasta_result)
        if not os.path.isdir(result_path):
            continue

        for nome_arquivo in ["errors.json", "overlapping_errors.json"]:
            caminho = os.path.join(result_path, nome_arquivo)
            if os.path.exists(caminho):
                with open(caminho, encoding="utf-8") as f:
                    data = json.load(f)
                    screen_id = data.get("screen_id")
                    errors = data.get("errors", [])
                    process_errors(app_name, screen_id, errors)

# Cria DataFrame principal
df_falhas_por_tela = pd.DataFrame(falhas_por_tela)
df_falhas_por_tela.to_csv("falhas_por_tela.csv", index=False)

# RQ1 - Frequência de falhas por app
rq1_rows = []
for app, erros in frequencia_falhas_app.items():
    total = sum(erros.values())
    for (tipo, criterio, nivel), qtd in erros.items():
        rq1_rows.append({
            "Aplicativo": app,
            "Tipo de Falha": tipo,
            "Critério WCAG": criterio,
            "Nível": nivel,
            "Número de Ocorrências": qtd,
            "Percentual (%)": round((qtd / total) * 100, 2) if total > 0 else 0.0
        })
df_rq1 = pd.DataFrame(rq1_rows)
df_rq1.to_csv("frequencia_falhas.csv", index=False)

# RQ2 - Ranking de falhas
df_rq2 = pd.DataFrame([
    {
        "Tipo de Falha": tipo,
        "Total Ocorrências": dados["total"],
        "Aplicativos Afetados": len(dados["apps"])
    }
    for tipo, dados in ranking_falhas.items()
]).sort_values(by="Total Ocorrências", ascending=False)
df_rq2.insert(0, "Rank", range(1, len(df_rq2) + 1))
df_rq2.to_csv("ranking_falhas.csv", index=False)

# RQ3 - Distribuição por nível WCAG (combinando Advisory em AA)
# Primeiro: cria uma cópia do wcag_distribution para poder manipular
wcag_adjusted = defaultdict(int, wcag_distribution)

# Soma o Advisory dentro de AA, se existir
if "Advisory" in wcag_adjusted:
    wcag_adjusted["AA"] += wcag_adjusted["Advisory"]
    del wcag_adjusted["Advisory"]

# Agora gera a planilha com os dados já ajustados
total_falhas = sum(wcag_adjusted.values())

df_rq3 = pd.DataFrame([
    {
        "Nível WCAG": nivel,
        "Total de Falhas": total,
        "Percentual (%)": round((total / total_falhas) * 100, 2)
    }
    for nivel, total in wcag_adjusted.items()
])

df_rq3.to_csv("distribuicao_wcag.csv", index=False)

# RQ1 - Versão pivotada por app
pivot_dict = defaultdict(dict)
total_por_app = {app: sum(erros.values()) for app, erros in frequencia_falhas_app.items()}

for app, erros in frequencia_falhas_app.items():
    for (tipo, criterio, nivel), qtd in erros.items():
        chave = (tipo, criterio, nivel)
        pivot_dict[chave][f"{app} - Nº Ocorrências"] = int(qtd)
        percentual = (qtd / total_por_app[app]) * 100 if total_por_app[app] > 0 else 0.0
        pivot_dict[chave][f"{app} - %"] = round(percentual, 2)

pivot_rows = []
for (tipo, criterio, nivel), valores in pivot_dict.items():
    base = {
        "Tipo de Falha": tipo,
        "Critério WCAG": criterio,
        "Nível": nivel
    }
    base.update(valores)
    pivot_rows.append(base)

df_rq1_pivot = pd.DataFrame(pivot_rows)
df_rq1_pivot.to_csv("frequencia_falhas_pivotada.csv", index=False)

print("Planilhas geradas com sucesso!")
