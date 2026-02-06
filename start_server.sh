#!/bin/bash
# Activate Render's venv and start the server
source /opt/render/project/src/.venv/bin/activate
cd /opt/render/project/src
export PYTHONPATH=/opt/render/project/src:$PYTHONPATH
hypercorn city_guides.src.app:app --bind 0.0.0.0:$PORT
