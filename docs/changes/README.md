# Change notes

One file per update, newest last. Each note says what changed, why, which files, who it affects, how it was verified, and what is still open. The running summary lives in [`../PROJECT_OVERVIEW_AND_CHANGES.md`](../PROJECT_OVERVIEW_AND_CHANGES.md).

`docs/` is in `.gitignore`, so new files here need `git add -f`.

| Date | Note | Owner | Commit |
|---|---|---|---|
| 2026-09-24 | [Question sections migration](2026-09-24-question-sections-migration.md) | Nikko | `50ab4ab` |
| 2026-09-24 | [Mobile: pick a question before capture](2026-09-24-mobile-question-linking.md) | Nikko | `24a40aa` |
| 2026-09-24 | [Web: question form, bank, question page, section folders](2026-09-24-web-question-bank-and-folders.md) | Nikko | `a72644d` |
| 2026-09-26 | [Merge pre-extraction and judge0-integration into `feature/question-linking-v2`](2026-09-26-merge-pre-extraction-and-judge0.md) | Nikko (merge), Nombrado + Jayrald (reviewers) | `0e21d5c`, `a727934`, `ffcf908` |
| 2026-09-26 | [Rename the question sections migration](2026-09-26-migration-rename.md) | Nikko | `246cb7e` |
| 2026-09-26 | [Question page: drop marks](2026-09-26-question-page-drop-marks.md) | Nikko | `c6178c6` |
| 2026-09-26 | [Merge Nombrado's latest pre-extraction; restore `AGENTS.md` and `ocr_feature/`](2026-09-26-merge-latest-pre-extraction.md) | Nikko (merge), Nombrado (review) | `60db6ed` |
| 2026-09-26 | Shared docs: `docs/README.md` gets a question-linking block; TEAM_SYNC asks Nombrado about his web guide (docs only, no code) | Nikko | `5d17dff` |
| 2026-09-26 | [Gate verdicts, the validated flag, and catching the cloud up](2026-09-26-gate-result-can-publish-and-cloud-migrations.md) | Jayrald | `018fe7d` |
| 2026-09-26 | [Questions can be edited; edited test cases clear stale grades](2026-09-26-question-updates.md) | Jayrald | `018fe7d` |
| 2026-09-26 | [Nikko's and Nombrado's branches merged into `judge0-integration`](2026-09-26-merges-into-judge0-integration.md) | Jayrald | `138ef02`, `046b88c`, `c893b85` |
| 2026-09-26 | [Pages of one answer share `submissions.batch_id`](2026-09-26-batch-id.md) | Jayrald | `ec5c910` |
| 2026-09-26 | [Every program on a paper is its own row, graded on its own](2026-09-26-submission-programs-and-per-program-grading.md) | Jayrald | `f85d99e`, `f3138c6`, `96eda09` |
| 2026-09-26 | [Merge Jayrald's schema work (`268eb54`) into v2](2026-09-26-merge-judge0-schema.md) | Nikko (merge) | `ce02c06` |
| 2026-09-26 | [Mobile: pages of one answer share a `batch_id`](2026-09-26-mobile-batch-id.md) | Nikko | `49038c1` |
| 2026-09-26 | [End-to-end test against the live database](2026-09-26-end-to-end-test.md) | Nikko | `b1e7728` |
| 2026-09-26 | [Web: edit and re-validate saved questions](2026-09-26-edit-questions.md) | Nikko | `906ad09`, `6156bae` |
| 2026-09-26 | [End-to-end tests for question linking on the web](2026-09-26-e2e-question-bank.md) | Nikko | this commit |
