# scripts/check_hf_model.py
"""
Accurate HF inference availability checker.
Run with: python scripts/check_hf_model.py
"""
import os
from huggingface_hub import InferenceClient, model_info

api_key = os.getenv("HUGGINGFACE_API_KEY") or input("Enter your HF API key: ").strip()

CANDIDATES = [
    # Chat endpoint candidates
    "mistralai/Mistral-7B-Instruct-v0.3",
    "HuggingFaceH4/zephyr-7b-beta",
    "Qwen/Qwen2.5-7B-Instruct",
    "meta-llama/Llama-3.2-3B-Instruct",
    "microsoft/Phi-3-mini-4k-instruct",
    "google/gemma-2-2b-it",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO",
]

print("=" * 60)
print("Checking HF Hub inference provider mapping...")
print("=" * 60)

for model_id in CANDIDATES:
    try:
        info = model_info(
            model_id,
            expand="inferenceProviderMapping",
            token=api_key,
        )

        # The API returns a LIST of provider objects, not a dict
        raw_mapping = getattr(info, "inference_provider_mapping", None)

        if not raw_mapping:
            print(f"❌ {model_id} — no inference providers")
            continue

        # Handle both list and dict formats
        if isinstance(raw_mapping, list):
            providers = raw_mapping  # list of objects
            provider_info = [
                f"{getattr(p, 'provider_id', getattr(p, 'provider', '?'))} "
                f"(task={getattr(p, 'task', '?')}, "
                f"status={getattr(p, 'status', '?')})"
                for p in providers
            ]
        elif isinstance(raw_mapping, dict):
            provider_info = [
                f"{k} (task={getattr(v, 'task', v)}, status={getattr(v, 'status', '?')})"
                for k, v in raw_mapping.items()
            ]
        else:
            provider_info = [str(raw_mapping)]

        print(f"✅ {model_id}")
        for p in provider_info:
            print(f"   → {p}")

    except Exception as e:
        print(f"⚠️  {model_id} — Error: {e}")
    print()

print("=" * 60)
print("Live generation tests...")
print("=" * 60)

client = InferenceClient(token=api_key)

# Test chat_completion (for instruct/chat models)
CHAT_TEST_MODELS = [
    "mistralai/Mistral-7B-Instruct-v0.3",
    "Qwen/Qwen2.5-7B-Instruct",
    "meta-llama/Llama-3.2-3B-Instruct",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
]

print("\n[A] Testing chat_completion() endpoint:")
for model_id in CHAT_TEST_MODELS:
    try:
        response = client.chat_completion(
            model=model_id,
            messages=[{"role": "user", "content": "Reply with exactly: WORKS"}],
            max_tokens=10,
            temperature=0.01,
        )
        content = response.choices[0].message.content
        print(f"  ✅ {model_id} → '{content}'")
    except Exception as e:
        # Extract just the key part of the error
        msg = str(e)[:120]
        print(f"  ❌ {model_id} → {msg}")

# Test text_generation (for base models)
TEXT_GEN_TEST_MODELS = [
    "mistralai/Mistral-7B-Instruct-v0.3",
    "google/flan-t5-xxl",
    "bigscience/bloom-560m",
    "gpt2",
]

print("\n[B] Testing text_generation() endpoint:")
for model_id in TEXT_GEN_TEST_MODELS:
    try:
        response = client.text_generation(
            model=model_id,
            prompt="The capital of France is",
            max_new_tokens=10,
            temperature=0.01,
        )
        print(f"  ✅ {model_id} → '{response[:50]}'")
    except Exception as e:
        msg = str(e)[:120]
        print(f"  ❌ {model_id} → {msg}")

print("\n[C] Testing with provider=None (fully automatic routing):")
try:
    response = client.chat_completion(
        messages=[{"role": "user", "content": "Reply with exactly: WORKS"}],
        max_tokens=10,
        temperature=0.01,
    )
    content = response.choices[0].message.content
    model_used = getattr(response, "model", "unknown")
    print(f"  ✅ Auto-routed → model='{model_used}' replied '{content}'")
except Exception as e:
    print(f"  ❌ Auto-routing failed: {e}")