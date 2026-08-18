# mAIstra

Vision-based Handwritten Assessment Grading and Feedback for C Programming Subjects.

mAIstra captures handwritten C programming submissions, extracts code through OCR, allows teacher verification, executes code with Judge0, and presents test-case and grading feedback.

## Applications

- `maistra_mobile` — Flutter application for capturing and uploading submissions
- `maistra_web` — Angular teacher application for questions, OCR review, and grading
- `ocr_feature` — Python FastAPI and PaddleOCR service
- `judge0_api` — Python FastAPI wrapper around Judge0
- `supabase` — Local configuration, migrations, and seed data

## Documentation

- [Project overview and changes](docs/PROJECT_OVERVIEW_AND_CHANGES.md)
- [Judge0 Ubuntu Docker setup](docs/setup/JUDGE0_UBUNTU_DOCKER_SETUP.md)
- [Supabase local setup](docs/setup/SUPABASE_LOCAL_SETUP.md)
- [Switching between local and cloud Supabase](docs/setup/SUPABASE_CLOUD_LOCAL_SWITCHING.md)

Project-specific Codex instructions are defined in [AGENTS.md](AGENTS.md).
