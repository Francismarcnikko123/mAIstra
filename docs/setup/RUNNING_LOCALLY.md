# Running mAIstra locally (Angular + OCR + Judge0)

## Test continuation without starting services — 2026-09-14

The association experiment can be tested directly in the OCR terminal; Angular,
FastAPI and Judge0 do not need to be running. Use the normal OCR virtual environment
and downloaded fine-tuned model. From the repository root:

```sh
cd ocr_feature
PYTHONPATH=. .venv/bin/python -m tests.manual_continuation "/path/to/photo.jpg"
```

The command prints production text and prototype ordering, plus reasons and the
saved comparison path. It does not enable a web feature. Full guide: [session handoff](../../ocr_feature/reports/2026-09-14-continuation-session-handoff.md).

Full local dev setup: three services, three terminals. Judge0 itself runs on
a teammate's Ubuntu VM (VirtualBox), reached over the LAN via SSH/port
forwarding; the Angular app and the OCR backend run directly on your own
machine.

## The three terminals

| # | Service | Command | Port | Notes |
|---|---|---|---|---|
| 1 | Judge0 wrapper (`judge0_api`) | see below | 8001 | Talks to the remote Judge0 VM over the network |
| 2 | OCR backend (`ocr_feature`) | see below | 8000 | PaddleOCR pipeline, runs locally |
| 3 | Angular app (`maistra_web`) | `npm start` | 4200 | The UI |

The Angular code hardcodes these exact local ports — no config to change,
just get all three running:
- `maistra_web/src/app/services/judge0.service.ts` / `judge0.ts` →
  `http://127.0.0.1:8001/api/judge0/*`
- `maistra_web/src/app/components/submissions-list/submissions-list.ts` →
  `http://localhost:8000/api/ocr/extract-from-url`

### Terminal 1 — Judge0 wrapper

Prerequisite: the Judge0 server itself must already be reachable (see
"Connecting to a teammate's Judge0 VM" below). Then, from the repo root:

```bash
cd judge0_api
source .venv/bin/activate   # first time: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001
```

Needs a `judge0_api/.env` (gitignored, not committed) pointing at the VM:

```env
JUDGE0_BASE_URL=http://<VM_IP_ADDRESS>:2358
JUDGE0_API_KEY=<AUTHN_TOKEN from the VM's judge0.conf>
```

Verify:

```bash
curl http://localhost:8001/
# {"status":"ok"}
```

### Terminal 2 — OCR backend

```bash
cd ocr_feature
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Pre-extraction on arrival (optional, 2026-09-24, branch `feature/pre-extraction`).**
The same server can read new papers by itself, so teachers open them already
extracted. It's off unless `ocr_feature/.env` says so (copy `.env.example`):

```
SUPABASE_URL=...            # same as the web app
SUPABASE_KEY=...            # the web's publishable key for now; a secret key from Jayrald once RLS is on
AUTO_EXTRACT=true
AUTO_EXTRACT_INTERVAL_SECONDS=10
AUTO_EXTRACT_SINCE=         # empty = only papers captured after the server starts
```

- **Startup:** it logs `[auto-extract] started: checking every 10s for papers captured since …`.
- **Each paper:** it logs `saved` / `skipped: already filled in` / `failed (n/3)` with timings. Timings (ids and seconds only) go to `outputs/auto_extract_timings.csv`.
- **Old papers stay untouched:** it only reads papers captured after the start date. On 2026-09-24 the shared database had 204 unread old papers, so don't set an early `AUTO_EXTRACT_SINCE` against the cloud without agreeing it with Jayrald.
- **List badge:** `GET http://localhost:8000/` reports `auto_extract.enabled`, `since` and ids in `failed`. The web checks it on load, every 30 seconds and after list reloads. A new unread paper after `since` shows **Extracting…** while the worker runs, then **Needs review** when its `extracted_text` arrives by realtime UPDATE. It remains under the **Needs OCR** filter until then. An old paper, one given up after three failures, or a new paper while the server is off shows **Needs OCR**; **Extract now** remains available.
- **Restart catch-up check:** the default `AUTO_EXTRACT_SINCE` is the server start, so papers captured while it was stopped are intentionally outside the new worker's range. To test catch-up, set `AUTO_EXTRACT_SINCE` to a recent time before the test photo, then restart the server. Do this only in the agreed test environment; don't set an early date against the shared cloud backlog.

Requires the fine-tuned model at `ocr_feature/models/fine_tuned_rec/inference/`
(see `ocr_feature/models/README.md` if it's missing — distributed via GitHub
Release, not committed to git).

### OCR defense demos and evaluation

For OCR defense demos, run either command from the repository root:

```bash
ocr_feature/.venv/bin/python ocr_feature/try_config.py
ocr_feature/.venv/bin/python ocr_feature/compare_config.py
ocr_feature/.venv/bin/python ocr_feature/compare_config.py ocr_feature/samples/bond/bond_writer1_1.jpg
```

Both tools default to the real two-column `green_writer10_B2_1.jpg` sample.
The default image, recognizer, and comparison CSV references resolve from
their source-file locations. Explicit image paths (and an explicit
`MAISTRA_REC_MODEL_DIR`) retain their caller-relative semantics. The comparison
uses an adjacent `.txt` first, then `samples/labels.csv` and
`datasets/verified/labels.csv` by image basename, and prints CER when found.
Preprocessed demo images are written to `outputs/` in the working directory.

For the 20-image sample evaluator, run from `ocr_feature/`:

```bash
.venv/bin/python -m evaluators.evaluate_cer
.venv/bin/python -m unittest discover -s tests
```

To show the synthetic brace-depth reassembly cases without running live OCR,
run from `ocr_feature/`:

```bash
.venv/bin/python -m tests.test_ocr_pipeline --demo-reassembly rbnode
.venv/bin/python -m tests.test_ocr_pipeline --demo-reassembly compressor
.venv/bin/python -m tests.test_ocr_pipeline --demo-reassembly small
.venv/bin/python -m tests.test_ocr_pipeline --demo-reassembly all
.venv/bin/python -m tests.test_ocr_pipeline --demo-two-column
```

`--demo-two-column` prints the real `green_writer10_B2_1.jpg` two-column split
(the detected gutter, then the left column in full followed by the right) from
the committed detection fixture — no models needed. The `--demo-reassembly`
demos print the synthetic detected order first, then the reassembled
continuation. They reuse the same RBNode and Compressor fixtures covered by
`ReassembleDisplacedRegionsTests`, plus the small end-to-end displaced-closer
example. This bypasses live PaddleOCR recognition, which is intentional: the
brace-depth path depends on reliable `{` / `}` text, while real handwriting
still misreads enough braces that this path usually no-ops.

The current end-to-end baseline after two-column reading-order handling is
clean_ws CER **0.099**, clean WER **0.328**, and clean token accuracy **0.716**.
The historical recognition-only fine-tune comparison remains CER
**0.274 → 0.126**, with fine-tuned WER **0.359**, before the column split.
Do not present 0.126 as the current end-to-end evaluator result.

### Local-gutter reading-order checks

From `ocr_feature/`, run `.venv/bin/python run_tests.py` and
`.venv/bin/python -m evaluators.evaluate_cer` after changing reading order.
The held-out pins remain clean_ws CER **0.099**, clean WER **0.328**, and clean
token accuracy **0.716**. `RealSampleTwoColumnTests` must retain the real
green_writer10 24-left / 23-right split.

For margin continuations, use the real extraction function on
`datasets/verified/images/greenbook/green_writer18_B2_2.jpg` and
`green_writer27_B1_3.jpg`. Compare `cleaned_text` against each row's
`verified_text` in `datasets/verified/labels.csv`, keyed by `submission_id`,
using `evaluators.evaluation.evaluate_text_pair(...)["clean_ws"]`.
The feature's real-pipeline before/after measurement is **0.515044 → 0.146903**
for writer18 and **0.342105 → 0.342105** for writer27. Do not substitute the
spec's earlier simplified-row-grouper A/B figures for these live results.
The pass changes grouping and order only; OCR mistakes in the returned text
remain for teacher verification.

### Real handwriting margin calibration

From `ocr_feature/`, run the three-photo geometric replay without loading models:

```bash
.venv/bin/python -m unittest tests.test_real_margin_layout -v
```

The committed `writerX_marginA/B/C_detections.json` fixtures preserve every
text/score/box, including fabric false positives. The 2026-09-13 calibration
keeps the region seed at 0.75 and reduces only the band gutter multiplier
from 1.5 to 0.5, retaining the 60px floor and three-row/uncrossed-band guards.
A uses two-column detection; B/C use banded detection. Braces survived 16/16,
but brace reassembly made no move. The full suite now passes 157 tests and
the live evaluator retains 0.099 / 0.328 / 0.716 with writer10 at 0.061.

See the [complete measurement and live instrumentation recipe](../../ocr_feature/reports/2026-09-13-real-margin-validation.md).
Patch helpers in `core.layout`, not their `ocr_pipeline` re-exports (only
`_group_detection_records` / `line_member_bounds` remain re-exported after the
2026-09-18 dead-export cleanup; `core/layout/reorder.py` was removed). Original
photos and debug artifacts stay under ignored `outputs/real_margin_validation/`;
the fixtures and report are tracked. Re-run full tests and `evaluate_cer` after
any threshold change. Do not treat full-page gaps as band-only gutter values.

### Terminal 3 — Angular app

```bash
cd maistra_web
npm start
```

Opens on `http://localhost:4200` once it finishes compiling.

**Program tabs (2026-09-26):** Multi-program papers now use
`submission_programs`; the old `submissions.answers` column is gone. The table
migration is `supabase/migrations/20260926000600_add_submission_programs.sql`
(applied to the cloud by Jayrald). On a database still missing this table,
Program 1 can save, but extra tabs remain preview-only. The message under the
editor names the missing table and asks Jayrald to apply the migrations.

**Save feedback (`feature/review-save-followups`, 2026-09-26):** the label beside
Save is the only save-status message. Red means a failure or revision conflict;
amber means program edits remain unsaved; green confirms saved programs.
Pending extra tabs take priority over the Program 1-only confirmation. The
older duplicate paragraph is removed; extraction and program-rule errors stay
below the editor. The save operation and conflict protections are unchanged.

## Connecting to a teammate's Judge0 VM

Judge0 needs a Linux host (cgroup-based sandboxing), so it runs inside a
VirtualBox Ubuntu VM on whoever's machine hosts it — not natively on macOS.
Full VM provisioning: [`JUDGE0_UBUNTU_DOCKER_SETUP.md`](JUDGE0_UBUNTU_DOCKER_SETUP.md).
The rest of this section is what actually goes wrong reaching an *already
set up* VM from a different machine on the same network.

### Step 1 — same network

Both machines (yours and the VM host's) must be on the same LAN/Wi-Fi.
Check your own IP:

```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

Ask the VM owner for their machine's IP too (Windows: `ipconfig`, or
`(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notmatch "Loopback|vEthernet"}).IPAddress`
in PowerShell). Match subnets by netmask — e.g. a `/16` (`255.255.0.0`)
means anything sharing the first two octets is reachable; a VPN or
Hyper-V/WSL virtual adapter IP in the list is usually a red herring.

### Step 2 — SSH into the VM

```bash
ssh <VM_USERNAME>@<HOST_IP> -p <FORWARDED_SSH_PORT>
```

(the port is whatever the VirtualBox NAT rule forwards to guest port 22 —
commonly `2222`; if the VM uses bridged networking instead of NAT, connect
directly to the VM's own IP on port 22, no `-p` needed).

**If this hangs or refuses, check on the VM host machine, in order:**

1. **VirtualBox port-forwarding rule exists and has the right guest IP.**
   VM Settings → Network → Advanced → Port Forwarding. Needs an entry like
   `Guest Port 22` → `Host Port 2222`, TCP.
2. **Host IP field must be blank, not `127.0.0.1`.** ⚠️ This is the actual
   bug that bit us: VirtualBox's default port-forward rules pin `Host IP`
   to `127.0.0.1`, which only accepts connections from the VM host's own
   machine — it silently refuses everyone else on the network, which looks
   like a hang (not an immediate refusal) from the connecting side. Fix:
   double-click the `Host IP` cell for each rule, delete the value, leave
   it blank, click OK, **then fully power off and restart the VM** (a
   guest-side reboot doesn't reload the NAT engine). Confirm the fix by
   checking the port is listening on all interfaces, not just localhost:
   - **Windows** (PowerShell or cmd): `netstat -an | findstr <PORT>` — want
     `0.0.0.0:<PORT> ... LISTENING`, not `127.0.0.1:<PORT>`.
   - **macOS**: `netstat -an | grep <PORT>` — want `*.{PORT}` or
     `0.0.0.0.{PORT}` in `LISTEN` state, not `127.0.0.1.{PORT}`. `lsof -nP -i
     :<PORT>` also works and is easier to read.
   - **Linux**: `ss -tlnp | grep <PORT>` — want `0.0.0.0:<PORT>`, not
     `127.0.0.1:<PORT>`.
3. **A firewall on the VM host is blocking the port.**
   - **Windows** (PowerShell, as Administrator):
     ```powershell
     Get-NetFirewallRule -DisplayName "*<PORT>*"     # check
     New-NetFirewallRule -DisplayName "<name>" -Direction Inbound -LocalPort <PORT> -Protocol TCP -Action Allow   # fix
     ```
   - **macOS**: the built-in Application Firewall (System Settings →
     Network → Firewall) blocks by application, not by port, so it's
     rarely the culprit for a VirtualBox port-forward — VirtualBox itself
     is what would need to be allowed if the firewall is on at all. More
     likely on Mac: nothing extra to configure, but if you're unsure it's
     enabled, check System Settings → Network → Firewall.
   - **Linux** (if `ufw` is active):
     ```bash
     sudo ufw status                          # check
     sudo ufw allow <PORT>/tcp                # fix
     ```

Do the same Host-IP and firewall check for Judge0's own port (`2358`), not
just SSH's (`2222`) — they're separate port-forward rules and each needs
its own fix.

### Step 3 — verify Judge0 itself

Once SSH works, from inside the VM:

```bash
cd ~/judge0-v1.13.1        # find it with: find / -iname "docker-compose.yml" 2>/dev/null
sudo docker compose ps     # or: sudo usermod -aG docker $USER && newgrp docker
```

All four containers (`db`, `redis`, `server`, `workers`) should be `Up`, and
`server` should show `0.0.0.0:2358->2358/tcp` in its ports column.

Get the API token:

```bash
grep AUTHN_TOKEN judge0.conf
```

Then, from your **own** machine (not the SSH session — a common mix-up,
since `curl` run inside the SSH session only proves the VM can reach
itself):

```bash
curl -H "X-Auth-Token: <TOKEN>" http://<HOST_IP>:2358/about
```

A JSON response with `"version":"1.13.1"` confirms full reachability — put
that token in `judge0_api/.env` as shown above and start Terminal 1.

**Security note:** the `AUTHN_TOKEN` is a real secret — don't paste it into
chat logs, commits, or anywhere outside `.env` files. Rotate it
(`openssl rand -hex 32`, update `judge0.conf`, `docker compose restart`) if
it's ever been exposed.

## If it stops connecting later

The port-forward and firewall fixes in the section above are saved settings
— they persist across VM/laptop restarts, so you shouldn't need to redo
them every session. When the wrapper suddenly can't reach Judge0, check
things in this order, cheapest first, **before** re-touching any
firewall/port-forward settings:

1. **Is the VM host's IP still the same?** `172.28.38.164` (or whatever
   you're using) was assigned by DHCP for that network session — it can
   change if the laptop reconnects to Wi-Fi, restarts, or joins a different
   network. Have the VM owner re-check their IP — **Windows:** `ipconfig`;
   **macOS:** `ifconfig | grep "inet " | grep -v 127.0.0.1` or `ipconfig
   getifaddr en0` (swap `en0` for the active interface); **Linux:** `ip
   addr` or `hostname -I` — and compare against what's in your
   `judge0_api/.env`'s `JUDGE0_BASE_URL`. This is the single most common
   reason a previously-working setup stops working.
2. **Is the VM actually running, and is Judge0 up inside it?** SSH in
   (`ssh <user>@<host_ip> -p <port>`) and run `sudo docker compose ps` from
   `~/judge0-v1.13.1` (or wherever `find / -iname "docker-compose.yml"
   2>/dev/null` locates it). All four containers need to show `Up`. A
   laptop that slept, or a VM that wasn't started this session, is the
   second most common cause — nothing wrong with the network at all.
3. **Are you still on the same network?** Re-check both machines' IPs are
   in the same subnet (see "Step 1 — same network" above) — this changes
   if either of you switches Wi-Fi networks (e.g. moving between campus
   buildings with separate APs, or one of you tethering to mobile data).
4. **Only if 1–3 all check out**, re-verify the port-forward/firewall
   layers didn't get reset — e.g. a VirtualBox update or VM re-import can
   sometimes wipe custom NAT rules. Re-check the port is still listening on
   all interfaces (see the OS-specific commands in Step 2's troubleshooting
   list above — `netstat`/`findstr` on Windows, `netstat`/`lsof` on macOS,
   `ss` on Linux) and shows `0.0.0.0:<PORT>`, not `127.0.0.1:<PORT>` — if
   it's back to `127.0.0.1`, redo the Host-IP-blank fix from Step 2 above.
5. Once the IP/VM/network layer is confirmed fine, re-run the actual
   verification test from your own machine (not inside the SSH session):
   ```bash
   curl -H "X-Auth-Token: <TOKEN>" http://<CURRENT_HOST_IP>:2358/about
   ```
   A JSON response means you're good — go start Terminal 1 as usual. If
   `JUDGE0_BASE_URL` in `.env` needs updating because the IP changed,
   update it before starting `uvicorn`.

### End-to-end browser tests (Playwright, added by Jayrald; installed locally 2026-09-27)

Playwright drives the real Angular app in a browser (open a paper, edit, save,
grade) against a **fake backend**: every Supabase, Judge0 and OCR request is
intercepted (`maistra_web/tests/e2e/support/fake-backend.ts`), so a run never
writes to the cloud. It starts its own dev server on port 4300.

```bash
cd maistra_web
npm ci                              # once, or after package.json changes
npx playwright install chromium     # once per machine (about 95 MB browser)
npm run e2e
```

9/9 passed on `judge0-integration` on 2026-09-27.

## Common local mistakes (not VM-related)

- **Running an old branch against the cloud (2026-09-27).** Only run the web
  app from `judge0-integration` (or a branch made from it). Older branches are
  kept for diffs only; their Save writes `submissions.verified_text` directly
  and leaves Program 1 in `submission_programs` stale.
- **Committing local lockfile changes.** `npm install` or Flutter commands can
  rewrite `maistra_web/package-lock.json` or `maistra_mobile/pubspec.lock` for
  your local tool versions. Don't commit those; restore with
  `git checkout -- <file>`. Prefer `npm ci`, which never edits the lockfile.
- **Mobile analyzer errors in `maistra_mobile/packages/`.** The bundled scanner
  plugins (`cunning_document_scanner`, `edge_detection`) show
  `permission_handler` errors until `flutter pub get` is run inside them. They
  are unused (Nikko is removing them); the app in `lib/` is unaffected.

- **Wrong working directory.** `pip install -r judge0_api/requirements.txt`
  fails silently-ish ("No such file or directory") if you're not in the
  repo root, or double-fails if you're in your home directory instead —
  always `cd` into the actual repo first, and double check with `pwd`
  before creating a venv (a `.venv` created from the wrong directory ends
  up in the wrong place entirely).
- **Testing "from the wrong side."** Running `curl` inside an SSH session
  only proves the *remote* machine can reach the target — it says nothing
  about whether *your* machine can. Always open a **separate** local
  terminal for any check that's supposed to validate your own machine's
  connectivity.
