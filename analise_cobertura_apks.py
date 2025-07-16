import os
import cereja as cj
import pandas as pd

apks = cj.FileIO.load(r'C:\Users\dasil\PycharmProjects\ocr-test\apks.csv', cols=('apk_path',)).data

total_apks = len(apks)

BASE_DIR = r"C:\Users\dasil\PycharmProjects\ocr-test"

total_analisados = 0

for pasta in os.listdir(BASE_DIR):
    if pasta.startswith("output_dir_"):
        caminho_results = os.path.join(BASE_DIR, pasta, "results")

        if os.path.exists(caminho_results) and os.path.isdir(caminho_results):
            subpastas = [p for p in os.listdir(caminho_results) if os.path.isdir(os.path.join(caminho_results, p))]

            if subpastas:
                total_analisados += 1
                print(f"✔️ {pasta} → {len(subpastas)} tela(s)")

print(f"\nTotal de aplicativos avaliados (com pasta 'results' não vazia): {total_analisados}")

total_nao_analisados = total_apks - total_analisados
percentual_cobertura = round((total_analisados / total_apks) * 100, 2)

# Criando a tabela de cobertura
tabela_cobertura = pd.DataFrame({
    'Métrica': [
        'Total de APKs coletados',
        'Total de APKs analisados pela ferramenta',
        'Total de APKs não analisados',
        'Percentual de cobertura (%)'
    ],
    'Valor': [
        total_apks,
        total_analisados,
        total_nao_analisados,
        percentual_cobertura
    ]
})

tabela_cobertura.loc[0:2, 'Valor'] = tabela_cobertura.loc[0:2, 'Valor'].astype(int)

print("\nTabela de Cobertura:")
print(f'{"Métrica":<40} | {"Valor":>10}')
print("-" * 55)
for _, row in tabela_cobertura.iterrows():
    metrica = row['Métrica']
    valor = row['Valor']
    if isinstance(valor, float) and not 'Percentual' in metrica:
        valor = int(valor)
    print(f'{metrica:<40} | {valor:>10}')

tabela_cobertura.to_csv('tabela_cobertura.csv', index=False)
