from fastapi import FastAPI
from fastapi.responses import HTMLResponse


app = FastAPI(
    title="MYAGENT",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "myagent",
    }


@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MYAGENT</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #f5f6f8;
      color: #172033;
      font-family: system-ui, sans-serif;
    }
    main {
      max-width: 800px;
      margin: 12vh auto;
      padding: 32px;
    }
    .label {
      font-size: 13px;
      letter-spacing: .12em;
      font-weight: 700;
      color: #53627a;
    }
    h1 {
      font-size: clamp(36px, 7vw, 56px);
      letter-spacing: -.04em;
      margin: 16px 0;
    }
    p {
      color: #53627a;
      line-height: 1.7;
      max-width: 600px;
    }
    .card {
      background: white;
      border: 1px solid #e1e5ec;
      border-radius: 16px;
      padding: 28px;
      margin-top: 32px;
    }
  </style>
</head>
<body>
  <main>
    <div class="label">MYAGENT</div>
    <h1>Comprendre les règles.<br>Préparer l’examen.</h1>
    <p>
      Un espace pour consulter les connaissances issues des textes
      officiels FIFA et réviser à partir de leurs sources.
    </p>
    <div class="card">
      <strong>Espace en préparation</strong>
      <p>
        La consultation des informations et les fiches de révision
        seront disponibles prochainement.
      </p>
    </div>
  </main>
</body>
</html>
"""
