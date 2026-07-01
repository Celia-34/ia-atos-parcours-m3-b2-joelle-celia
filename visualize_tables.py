"""Visualise les deux tables produits et capteurs_iot en HTML."""
import pandas as pd
from pathlib import Path

# Charger les données
data_dir = Path(__file__).parent / "data"
produits_df = pd.read_csv(data_dir / "produits.csv")
capteurs_df = pd.read_csv(data_dir / "capteurs_iot.csv")

# Créer le HTML
html = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tables Acerox</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #2196F3;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th {{
            background-color: #2196F3;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background-color: #f9f9f9;
        }}
        .stats {{
            background-color: #e3f2fd;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Tables Acerox</h1>
        
        <h2>1️⃣ Table PRODUITS</h2>
        <div class="stats">
            <strong>Nombre de produits:</strong> {len(produits_df)} | 
            <strong>Catégories:</strong> {', '.join(produits_df['categorie'].unique())}
        </div>
        {produits_df.to_html(index=False, classes='table')}
        
        <h2>2️⃣ Table MESURES_IOT</h2>
        <div class="stats">
            <strong>Nombre de mesures:</strong> {len(capteurs_df)} | 
            <strong>Sites:</strong> {', '.join(capteurs_df['site'].unique())} | 
            <strong>Lignes:</strong> {', '.join(map(str, sorted(capteurs_df['line_id'].unique())))}
        </div>
        {capteurs_df.head(50).to_html(index=False, classes='table')}
        <p><em>Affichage des 50 premières mesures ({len(capteurs_df)} au total)</em></p>
    </div>
</body>
</html>
"""

# Sauvegarder et ouvrir
output_path = data_dir.parent / "tables_acerox.html"
output_path.write_text(html, encoding='utf-8')
print(f"✅ Rapport généré: {output_path}")
print(f"📌 Ouvrez-le dans le navigateur pour voir les tables")
