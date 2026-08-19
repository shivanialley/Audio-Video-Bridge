# Audio-Video Bridge & Studio Localization Console

An enterprise-grade multilingual video/audio transcription, translation, and synchronization pipeline powered by **FastAPI**, **Google Gemini**, and **Docker**. 

This application allows users to upload media files, transcribe audio using AI, translate subtitles into multiple supported languages with accurate timestamp preservation, and export localized outputs.

---

## 🚀 Approach

The core design philosophy behind this project is **modularity, resilience, and asynchronous processing**:
* **Backend Architecture (FastAPI):** Built with a clean separation of concerns (`api`, `services`, `storage`), ensuring clear routing, business logic execution, and database state management.
* **AI-Driven Localization:** Leverages the official `google-genai` SDK (`gemini-2.5-flash`) for high-speed transcription and structured subtitle translation. 
* **Robust Fallback & Validation:** Implements strict JSON parsing and fallback routines during translation to guarantee that subtitle timestamps (`start`/`end` float values) are never dropped or misaligned, especially for complex scripts like Devanagari (Hindi).
* **Containerization:** Packaged completely using Docker to encapsulate complex system dependencies (such as `ffmpeg`) for consistent local execution and seamless cloud deployments.

---

## 🛠️ Key Decisions

1. **Model Selection (`gemini-3.7-flash`):** 
   * Chosen over heavier models for its optimal balance of speed, low latency, and adherence to structured JSON output generation, which is critical for parsing subtitle segment arrays.
2. **Stateless UI/API Integration:** 
   * The backend exposes RESTful endpoints managing temporary storage (`storage/uploads`, `storage/outputs`) and a local database (`jobs.db`) to track processing status cleanly.
3. **Environment Variable Security:** 
   * Strict adherence to removing hardcoded API keys in favor of dynamic environment loading (`os.getenv("GOOGLE_API_KEY")`) to prevent public repository leaks and satisfy cloud security policies (like GitHub Push Protection and Render environment injection).
4. **Cloud Deployment via Render & Docker:** 
   * Utilizing a custom `Dockerfile` pointing to a slim Python runtime with pre-installed `ffmpeg` ensures that audio extraction and media splitting operations succeed uniformly in production.

---

## 💡 Assumptions Made

* **File Format Compliance:** Assumes uploaded media formats adhere to standard web codecs (`.mp4`, `.mov`, `.m4a`, `.mp3`, `.wav`, `.webm`) under a configured size limit (default: 200MB).
* **API Quota Management:** Assumes the user operates within standard Gemini API free-tier or paid rate limits (RPD/RPM), handling concurrency gracefully via structured application error handling.
* **Environment Execution:** Assumes deployment targets (such as Render) have sufficient internal memory/CPU allocation to process standard short-to-medium-length media files via `ffmpeg` without timing out.
