#!/bin/bash
# Start Zhihu Profiler Web UI
# Usage: ./start_web.sh [port]

cd "$(dirname "$0")"
PORT=${1:-8765}

echo "Starting Zhihu Profiler Web UI..."
echo "Open http://127.0.0.1:${PORT} in your browser"
echo ""

./venv/bin/python -c "
from zhihu_profiler.web.server import app
import uvicorn
uvicorn.run(app, host='0.0.0.0', port=${PORT}, log_level='warning')
"
