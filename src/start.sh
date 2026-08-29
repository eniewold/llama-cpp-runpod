#!/bin/bash

# fail on error:
set -e -o pipefail

# This script starts llama-server and, once it is healthy, the RunPod handler.
#
# Configuration is passed almost entirely through llama-server's native
# LLAMA_ARG_* environment variables (set from the template UI), which
# llama-server reads by itself. This script only:
#   - resolves the model path when RunPod model caching is used,
#   - appends any extra arguments from LLAMA_SERVER_CMD_ARGS,
#   - forces the server port to 3098 (CLI arguments override env vars).

PORT=3098

cleanup() {
    echo "start.sh: Cleaning up..."
    pkill -P $$ # kill all child processes of the current script
    exit 0
}

CACHED_LLAMA_ARGS=""

find_cached_path() {
    local model_path
    model_path=$(python ./find_cached.py "$LLAMA_CACHED_MODEL" "$LLAMA_CACHED_GGUF_PATH")
    if [ $? -ne 0 ] || [ -z "$model_path" ]; then
        echo "start.sh: Error: Could not resolve cached model path. Check that LLAMA_CACHED_MODEL and LLAMA_CACHED_GGUF_PATH are correct and the model is fully cached."
        exit 1
    fi
    CACHED_LLAMA_ARGS="-m $model_path"
}

# When RunPod model caching is used, load the model from the cache and ignore
# any Hugging Face download settings so llama-server does not try to download.
if [ -n "$LLAMA_CACHED_MODEL" ]; then
    echo "start.sh: Model caching is enabled. Resolving cached model path..."
    find_cached_path
    echo "start.sh: Using cached model: $CACHED_LLAMA_ARGS"
    unset LLAMA_ARG_HF_REPO LLAMA_ARG_HF_FILE LLAMA_ARG_MODEL
fi

# The template asks for the model repo and the quantization as separate
# fields (the console validates the repo name, which llama.cpp's repo:quant
# syntax would break). Combine them here for llama-server, unless the repo
# already carries a :quant tag or an explicit GGUF file is configured.
if [ -n "$LLAMA_HF_QUANT" ] && [ -n "$LLAMA_ARG_HF_REPO" ] \
    && [[ "$LLAMA_ARG_HF_REPO" != *:* ]] && [ -z "$LLAMA_ARG_HF_FILE" ]; then
    export LLAMA_ARG_HF_REPO="${LLAMA_ARG_HF_REPO}:${LLAMA_HF_QUANT}"
    echo "start.sh: Using model: $LLAMA_ARG_HF_REPO"
fi

# Require some model source to be configured.
if [ -z "$CACHED_LLAMA_ARGS" ] && [ -z "$LLAMA_ARG_HF_REPO" ] && [ -z "$LLAMA_ARG_MODEL" ] \
    && [[ "$LLAMA_SERVER_CMD_ARGS" != *"-hf"* ]] && [[ "$LLAMA_SERVER_CMD_ARGS" != *"-m "* ]]; then
    echo "start.sh: Error: No model configured. Set LLAMA_ARG_HF_REPO (the Model field in the template), or configure model caching with LLAMA_CACHED_MODEL and LLAMA_CACHED_GGUF_PATH."
    exit 1
fi

# The worker requires llama-server to listen on port $PORT.
if [[ "$LLAMA_SERVER_CMD_ARGS" == *"--port"* ]]; then
    echo "start.sh: Error: You must not define --port in LLAMA_SERVER_CMD_ARGS, as port $PORT is required."
    exit 1
fi

# trap exit signals and call the cleanup function
trap cleanup SIGINT SIGTERM

# kill any existing llama-server processes
echo "start.sh: Stopping existing llama-server instances (if any)..."
{
    pkill llama-server 2>/dev/null
} || {
    echo "start.sh: No llama-server running"
}

echo "start.sh: Running /app/llama-server $CACHED_LLAMA_ARGS $LLAMA_SERVER_CMD_ARGS --port $PORT"

touch llama.server.log

# Extra arguments must be passed to llama-server verbatim (unquoted on purpose).
LD_LIBRARY_PATH=/app /app/llama-server $CACHED_LLAMA_ARGS $LLAMA_SERVER_CMD_ARGS --port $PORT 2>&1 | tee llama.server.log &

LLAMA_SERVER_PID=$! # store the process ID (PID) of the background command

echo "start.sh: Waiting for llama-server to become healthy (downloading/loading the model can take a while)..."

# Wait until the /health endpoint reports ready. No fixed timeout here: large
# models legitimately take minutes to download and load, and RunPod enforces
# its own worker timeouts.
until curl -sf "http://127.0.0.1:${PORT}/health" > /dev/null 2>&1; do
    if ! kill -0 "$LLAMA_SERVER_PID" 2>/dev/null; then
        echo "start.sh: Error: llama-server exited unexpectedly. Last log lines:"
        tail -n 40 llama.server.log
        exit 1
    fi
    sleep 1
done

echo "start.sh: llama-server is up and running, delegating to the handler script."

python -u handler.py $1
