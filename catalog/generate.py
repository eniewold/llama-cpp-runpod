#!/usr/bin/env python3
"""Render per-model RunPod Hub repositories from catalog/models.json.

The source repo's .runpod/hub.json is the schema source of truth: each
generated listing reuses its full input list, with defaults overridden per
model. Usage:

    python3 catalog/generate.py <base-image-ref> <output-dir>

<base-image-ref> is the worker image the generated Dockerfiles build FROM,
e.g. ghcr.io/eniewold/llama-cpp-runpod@sha256:...
"""

import copy
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

HANDLER_STUB = '"""Marker for RunPod\'s repository scanner; the actual handler ships in the base image (see the Dockerfile)."""\n'

TESTS = {
    "tests": [
        {
            "name": "execute_a_prompt",
            "input": {"prompt": "Hi! Who are you?"},
            "timeout": 60000,
        }
    ],
    "config": {
        "gpuTypeId": "NVIDIA GeForce RTX 4090",
        "gpuCount": 1,
        "env": [
            {"key": "LLAMA_ARG_HF_REPO", "value": "unsloth/gemma-3-270m-it-GGUF"},
            {"key": "LLAMA_HF_QUANT", "value": "Q6_K"},
            {"key": "LLAMA_ARG_CTX_SIZE", "value": "2048"},
            {"key": "LLAMA_ARG_N_GPU_LAYERS", "value": "999"},
        ],
        "allowedCudaVersions": ["12.8", "12.9"],
    },
}


SDK_SNIPPET = """## Using it with an OpenAI SDK

After deploying, point any OpenAI client at your endpoint URL, with your
RunPod API key in place of the OpenAI key:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.runpod.ai/v2/<ENDPOINT_ID>/openai/v1",
    api_key="<YOUR_RUNPOD_API_KEY>",
)

response = client.chat.completions.create(
    model="%MODEL%",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True,
)
for chunk in response:
    print(chunk.choices[0].delta.content or "", end="")
```

`<ENDPOINT_ID>` is shown on your endpoint's page in the RunPod console.
"""


def derive_names(entry):
    """Build the listing title and a short display name.

    Title convention (searchable, mirrors the hand-made public templates):
    "<Model>-<Quant> (<VRAM>GB VRAM, <ctx>k context, OpenAI API, llama.cpp) <keywords>"
    An explicit "title" in the catalog entry overrides the convention.
    """
    base = entry["hf_repo"].split("/")[-1]
    if base.endswith("-GGUF"):
        base = base[: -len("-GGUF")]
    ctx_label = f'{entry["env"]["LLAMA_ARG_CTX_SIZE"] // 1024}k'
    title = entry.get("title") or (
        f'{base}-{entry["quant"]} ({entry["vram_gb"]}GB VRAM, {ctx_label} context, '
        f'OpenAI API, llama.cpp) {entry["keywords"]}'
    )
    return title, f'{base} {entry["quant"]}'


def render_readme(entry):
    ctx = entry["env"]["LLAMA_ARG_CTX_SIZE"]
    _, short_name = derive_names(entry)
    return f"""[![Runpod](https://api.runpod.io/badge/runpod-serverless-templates/{entry["slug"]})](https://console.runpod.io/hub/listing/runpod-serverless-templates/{entry["slug"]})

# {short_name} on RunPod Serverless

{entry["readme_intro"]}

**Drop-in OpenAI API**: the endpoint speaks the OpenAI API directly - point any OpenAI SDK or tool at your endpoint URL and it just works, streaming included. See the snippet below.

Powered by [llama.cpp](https://github.com/ggml-org/llama.cpp). Supported routes:

- `/v1/models`
- `/v1/chat/completions`
- `/v1/completions`

{SDK_SNIPPET.replace("%MODEL%", entry["hf_repo"] + ":" + entry["quant"])}
## Configuration

| Setting | Value |
|---|---|
| Model | [`{entry["hf_repo"]}`]({"https://huggingface.co/" + entry["hf_repo"]}), quantization `{entry["quant"]}` ({entry["weights_gb"]} GB) |
| Context window | {ctx:,} tokens |
| Recommended VRAM | 48 GB or more |

Everything is pre-configured, but every setting stays adjustable at deploy time - model, quantization, context size, KV cache types, and more. The model is downloaded when a worker cold-starts.

## RunPod queue API

The endpoint also accepts RunPod's job format (`POST /v2/<ENDPOINT_ID>/run`):

```json
{{ "input": {{ "messages": [{{ "role": "user", "content": "Hello!" }}], "stream": false }} }}
```

This listing is generated from [eniewold/llama-cpp-runpod](https://github.com/eniewold/llama-cpp-runpod), which also offers a fully configurable any-model template.
"""


def main():
    base_image, out_root = sys.argv[1], pathlib.Path(sys.argv[2])
    base_hub = json.loads((ROOT / ".runpod" / "hub.json").read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "catalog" / "models.json").read_text(encoding="utf-8"))

    meta = {}
    for entry in catalog:
        hub = copy.deepcopy(base_hub)
        hub["title"], _ = derive_names(entry)
        hub["description"] = entry["description"]
        hub["config"]["gpuIds"] = entry["gpuIds"]
        hub["config"]["containerDiskInGb"] = entry["containerDiskInGb"]
        for item in hub["config"]["env"]:
            key = item["key"]
            if key == "LLAMA_ARG_HF_REPO":
                item["input"]["default"] = entry["hf_repo"]
            elif key == "LLAMA_HF_QUANT":
                item["input"]["default"] = entry["quant"]
            elif key in entry["env"]:
                item["input"]["default"] = entry["env"][key]

        out = out_root / entry["slug"]
        out.mkdir(parents=True, exist_ok=True)
        (out / ".runpod").mkdir(exist_ok=True)
        (out / ".runpod" / "hub.json").write_text(
            json.dumps(hub, indent=4) + "\n", encoding="utf-8"
        )
        (out / ".runpod" / "tests.json").write_text(
            json.dumps(TESTS, indent=4) + "\n", encoding="utf-8"
        )
        (out / "Dockerfile").write_text(
            "# Generated by eniewold/llama-cpp-runpod catalog sync - do not edit by hand.\n"
            f"FROM {base_image}\n",
            encoding="utf-8",
        )
        (out / "handler.py").write_text(HANDLER_STUB, encoding="utf-8")
        (out / "README.md").write_text(render_readme(entry), encoding="utf-8")
        meta[entry["slug"]] = entry["description"]

    (out_root / "meta.json").write_text(json.dumps(meta, indent=4), encoding="utf-8")
    print(f"Generated {len(catalog)} listing(s) in {out_root}")


if __name__ == "__main__":
    main()
