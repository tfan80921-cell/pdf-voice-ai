# Completar el código fuente

Este repositorio ya tiene la estructura base (proveedores IA, config, run.py).

El proyecto completo (24 archivos) está en el commit local. Para subir todo:

```bash
# Con GitHub CLI autenticado:
cd pdf-voice-ai
git remote add origin https://github.com/tfan80921-cell/pdf-voice-ai.git  # si falta
git push -u origin main --force
```

Archivos que deben quedar en el repo:
- app/main.py, app/schemas.py
- app/documents/manager.py, app/racks/manager.py
- app/templates/catalog.py, app/templates/generator.py
- static/index.html, static/css/styles.css, static/js/app.js

Arranque:
```bash
pip install -r requirements.txt
python run.py
```
