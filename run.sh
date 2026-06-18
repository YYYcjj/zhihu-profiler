#!/bin/bash
# Start Zhihu Profiler with auto-captured public URL

cd "$(dirname "$0")"

# Start uvicorn in background
./venv/bin/uvicorn zhihu_profiler.web.server:app --host 0.0.0.0 --port 8765 --log-level warning &
UVI_PID=$!
sleep 3

# Start bore tunnel and capture port
/tmp/bore local 8765 --to bore.pub 2>&1 | while read line; do
    echo "$line"
    if [[ "$line" == *"listening at"* ]]; then
        # Extract URL and save it
        port=$(echo "$line" | grep -oE '[0-9]+$')
        echo "bore.pub:$port" > .public_url
        curl -s "http://localhost:8765/api/public-url" > /dev/null 2>&1 || true
    fi
done &
BORE_PID=$!

echo "Server PID: $UVI_PID, Bore PID: $BORE_PID"
echo "Public URL file: .public_url"
wait
