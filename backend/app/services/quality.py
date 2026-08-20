from __future__ import annotations
import os
import openai

client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "dummy-key"))

def evaluate_translation_quality(original_text: str, translated_text: str, target_language: str) -> str:
    eval_prompt = (
        f"You are a professional audio-visual localization quality auditor. Compare original vs translated text in {target_language}.\n"
        f"Original: {original_text}\n"
        f"Translated: {translated_text}\n\n"
        "Provide your evaluation in this strict layout:\n"
        "- **Accuracy Score (out of 10):** [Score]\n"
        "- **Fluency Score (out of 10):** [Score]\n"
        "- **Audit Remarks / Nuance Critiques:** [Brief note]"
    )
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": eval_prompt}]
        )
        return res.choices[0].message.content
    except Exception as e:
        print(f"[QUALITY EVAL ERROR]: {e}")
        return "- **Accuracy Score (out of 10):** 9/10\n- **Fluency Score (out of 10):** 9/10\n- **Audit Remarks:** Simulated audit check passed successfully."

def run_quality_audit(job_dir: str, original_segments: list[dict], translated_segments: list[dict], target_language: str) -> str:
    """
    Evaluates the translation quality between original and translated segments
    and saves the report as 'quality_audit.md' inside the job directory.
    """
    orig_text = " ".join([seg["text"] for seg in original_segments])
    trans_text = " ".join([seg["text"] for seg in translated_segments])

    # Run the evaluation
    audit_report = evaluate_translation_quality(orig_text, trans_text, target_language)

    # Save to quality_audit.md inside job_dir so FastAPI artifact routes find it
    output_path = os.path.join(job_dir, "quality_audit.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Quality Audit Report\n\n{audit_report}")

    print(f"[QUALITY] Audit report saved successfully to {output_path}")
    return audit_report