<p align="center">
    <img src="https://raw.githubusercontent.com/ggml-org/llama.cpp/master/media/llama1-icon-transparent.png" alt="llama.cpp logo" width="128">
</p>

# llama.cpp on RunPod Serverless

Serve any GGUF model from Hugging Face as a serverless RunPod endpoint, powered by [llama.cpp](https://github.com/ggml-org/llama.cpp)'s `llama-server`. The worker exposes an OpenAI-compatible API:

- `/v1/models`
- `/v1/chat/completions`
- `/v1/completions`

Streaming responses are supported. The Docker image is built on the official `ghcr.io/ggml-org/llama.cpp:server-cuda` image and rebuilt automatically whenever llama.cpp publishes a new server image — each release of this template is named after the llama.cpp build it ships (e.g. `b10666`). Because the base image tracks a recent CUDA toolkit, workers require hosts with CUDA 12.8 or newer — the template pins this automatically.

## Quick start

1. Deploy the template and pick a **Model** (a Hugging Face GGUF repo, e.g. `unsloth/Qwen3.8-27B-GGUF`) and a **Quantization** (e.g. `UD-Q4_K_XL`, matching a GGUF file in the repo).
2. Choose a GPU with enough VRAM for the GGUF file plus the KV cache (as a rule of thumb: GGUF file size + a few GB).
3. Adjust **Context Size**, **Parallel Slots**, and the advanced options as needed — each field explains what it does.

The model is downloaded when a worker cold-starts. For faster cold starts, use RunPod model caching (see below).

## Configuration

The most important settings, all available in the template UI:

| Setting | Meaning |
|---|---|
| Model | Hugging Face GGUF repo, `<owner>/<repo>` |
| Quantization | Which GGUF quantization to download, e.g. `Q4_K_M` |
| Context Size | Total context window in tokens, shared across parallel slots |
| Parallel Slots | Requests served simultaneously per worker |
| GPU Layers | Layers offloaded to the GPU (999 = all) |
| CPU MoE Layers | Keep expert weights of the first N layers on the CPU (MoE models) |
| Flash Attention / KV Cache Types | Speed and VRAM trade-offs for the KV cache |
| Extra llama-server Arguments | Any other `llama-server` flags, passed verbatim (never set `--port`) |

Settings map directly to `llama-server` options via its native `LLAMA_ARG_*` environment variables, so anything not in the UI can be set as an additional environment variable or through the extra-arguments field.

## Calling the endpoint

Simple prompt or chat input:

```json
{ "input": { "prompt": "Hello, who are you?", "stream": false } }
```

```json
{ "input": { "messages": [{ "role": "user", "content": "Hello!" }], "stream": true } }
```

Or call any supported OpenAI route directly:

```json
{
    "input": {
        "openai_route": "/v1/chat/completions",
        "openai_input": {
            "model": "any",
            "messages": [{ "role": "user", "content": "Hello!" }]
        }
    }
}
```

## Model caching

To avoid re-downloading the model on every cold start, use RunPod's [model caching](https://docs.runpod.io/serverless/endpoints/model-caching): set your model repo in the endpoint's *Model* field and fill in the *Cached Model* and *Cached Model GGUF Path* advanced settings. See [docs/cached.md](./docs/cached.md) for a step-by-step guide.

## License

See the [LICENSE](./LICENSE) file.

[![Runpod](https://api.runpod.io/badge/eniewold/llama-cpp-runpod)](https://console.runpod.io/hub/listing/eniewold/llama-cpp-runpod)
