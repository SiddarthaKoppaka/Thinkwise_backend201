import io
import json
import datetime
import pandas as pd

def parse_ideas_file(filename, content):
    def safe_str(val):
        if pd.isna(val):
            return ""
        return str(val)

    ideas = {}
    if filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(content))
        print("🧾 CSV Headers:", df.columns.tolist())
        print("🧾 First 5 Rows:\n", df.head())

        df.columns = [col.strip().lower() for col in df.columns]

        for i, row in df.iterrows():
            idea_id = str(i + 1)
            ideas[idea_id] = {
                "title": safe_str(row.get("idea title", row.get("title", ""))),
                "description": safe_str(row.get("description", "")),
                "author": safe_str(row.get("name", row.get("author", ""))),
                "category": safe_str(row.get("domain", row.get("category", "Uncategorized"))),
                "timestamp": safe_str(row.get("timestamp", datetime.datetime.utcnow()))
            }

    elif filename.endswith(".json"):
        raw = json.loads(content.decode())
        for i, idea in enumerate(raw):
            idea_id = str(i + 1)
            ideas[idea_id] = {
                "title": safe_str(idea.get("title", "")),
                "description": safe_str(idea.get("description", "")),
                "author": safe_str(idea.get("author", "")),
                "category": safe_str(idea.get("category", "Uncategorized")),
                "timestamp": safe_str(idea.get("timestamp", datetime.datetime.utcnow()))
            }
    else:
        raise ValueError("Unsupported file format")

    return ideas
