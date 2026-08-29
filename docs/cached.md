# Using cached models

## Why

By default the worker downloads the model from the Hugging Face Hub every time a worker cold-starts, which is slow for large models. Storing the GGUF on a network volume and pointing `-m` at it is not much better, because network volume read performance is often the bottleneck.

RunPod's [model caching](https://docs.runpod.io/serverless/endpoints/model-caching) solves this by placing the model on fast local worker storage. This worker supports that mechanism out of the box.

## Step-by-step guide

1. In your endpoint settings, enter the Hugging Face URL of the model in RunPod's **Model** field.

    Example: for `unsloth/Qwen3.8-27B-GGUF`, enter `https://huggingface.co/unsloth/Qwen3.8-27B-GGUF`.

2. In the template's environment settings (advanced options), set:

    - **Cached Model** (`LLAMA_CACHED_MODEL`): the model repo ID, e.g. `unsloth/Qwen3.8-27B-GGUF`
    - **Cached Model GGUF Path** (`LLAMA_CACHED_GGUF_PATH`): the path of the GGUF file inside the repo, e.g. `Qwen3.8-27B-UD-Q4_K_XL.gguf` (include the folder if the file is in one, e.g. `models/model-q4_k_m.gguf`)

3. That's it. When Cached Model is set, the worker resolves the cached path at startup and launches `llama-server` with `-m`; the regular Model field of the template (`LLAMA_ARG_HF_REPO`) is ignored, so no download takes place.

## How it works

The worker ships a small helper, `src/find_cached.py`, that locates the GGUF file inside RunPod's Hugging Face cache directory on the worker. You can run it manually for debugging:

```bash
python3 src/find_cached.py unsloth/Qwen3.8-27B-GGUF Qwen3.8-27B-UD-Q4_K_XL.gguf
```

It prints the resolved absolute path, or exits with an error if the model is not (fully) cached.
