import os
import shutil

# Diretório onde o script está sendo executado
current_dir = os.getcwd()

# Caminho do arquivo CSV no diretório atual
csv_path = os.path.join(current_dir, "apks.csv")

# Diretórios fonte e destino
apps_dir = r"C:\Users\dasil\OneDrive\Documentos\droidbot-results-test\apps"
may_25_dir = os.path.join(apps_dir, "may-25-2")

# Lista apenas arquivos .apk na pasta may-25-2
new_files = [
    f for f in os.listdir(may_25_dir)
    if f.endswith(".apk") and os.path.isfile(os.path.join(may_25_dir, f))
]

# Faz a cópia dos arquivos para a pasta apps
for file_name in new_files:
    source_path = os.path.join(may_25_dir, file_name)
    destination_path = os.path.join(apps_dir, file_name)

    if not os.path.exists(destination_path):
        shutil.copy2(source_path, destination_path)  # Mantém metadata (data, etc.)
        print(f"Arquivo copiado: {file_name}")
    else:
        print(f"Arquivo já existe e não foi copiado: {file_name}")

# Gera os caminhos completos para o CSV (baseados na pasta apps)
new_paths = [os.path.join(apps_dir, f) for f in new_files]

# Lê o conteúdo atual do CSV (se existir)
existing_paths = []
if os.path.exists(csv_path):
    with open(csv_path, 'r', encoding='utf-8') as f:
        existing_paths = [line.strip() for line in f.readlines()]

# Filtra os caminhos novos que não estão no CSV
unique_new_paths = [p for p in new_paths if p not in existing_paths]

# Adiciona os novos caminhos ao CSV
with open(csv_path, 'a', encoding='utf-8') as f:
    for path in unique_new_paths:
        f.write(path + '\n')

print(f"\n{len(unique_new_paths)} novos APKs adicionados ao arquivo apks.csv.")
