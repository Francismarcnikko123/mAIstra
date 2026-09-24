# Self-host Judge0 CE on an Ubuntu VM with Docker

This guide installs a private Judge0 CE server on an Ubuntu 22.04 Linux virtual machine or server, following the [official Judge0 v1.13.1 deployment instructions](https://github.com/judge0/judge0/releases/tag/v1.13.1). Judge0 listens on port `2358`; mAIstra's `judge0_api` FastAPI service sends code-execution requests to it.

> Judge0 executes untrusted code. Use a dedicated VM, set strong database and Redis passwords, and do not expose port `2358` directly to the public internet.

## 1. Prepare the VM

Recommended minimum for development:

- Ubuntu Server 22.04 LTS (64-bit)
- 2 CPU cores
- 4 GB RAM
- 20 GB free disk space
- Internet access
- A VM network mode that gives the host access to the guest, such as bridged networking or NAT with port forwarding

Update the server and install the basic tools:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y ca-certificates curl gnupg unzip wget openssl openssh-server
```

## 2. Connect to the VM through SSH

Use SSH from the host computer for the rest of the setup. Copying and pasting multiline commands is often unavailable or unreliable in a VM's built-in console, while an SSH terminal supports normal host clipboard shortcuts.

Enable the SSH server inside the VM:

```bash
sudo systemctl enable --now ssh
sudo systemctl status ssh
```

Find the VM's IP address:

```bash
hostname -I
```

Note the VM's LAN address, such as `192.168.1.50`. From PowerShell, Windows Terminal, macOS Terminal, or a Linux terminal on the host computer, connect using the Ubuntu account created during installation:

```bash
ssh YOUR_UBUNTU_USERNAME@VM_IP_ADDRESS
```

For example:

```bash
ssh jayrald@192.168.1.50
```

Accept the host fingerprint when prompted, then enter the Ubuntu user's password. After connecting, copy and paste the remaining commands into this SSH terminal.

If SSH cannot connect:

- Make sure the VM is running and `sudo systemctl status ssh` reports `active (running)`.
- With bridged networking, connect directly to the VM's LAN IP.
- With NAT networking, configure SSH port forwarding in the hypervisor, such as host port `2222` to guest port `22`, and connect with `ssh -p 2222 YOUR_UBUNTU_USERNAME@127.0.0.1`.
- If UFW is enabled, run `sudo ufw allow OpenSSH` inside the VM.

## 3. Configure cgroup v1

Judge0 v1.13.1 recommends Ubuntu 22.04 with the legacy cgroup hierarchy enabled. Open GRUB's configuration:

```bash
sudo nano /etc/default/grub
```

Find `GRUB_CMDLINE_LINUX` and add `systemd.unified_cgroup_hierarchy=0` inside its quotes. For example:

```text
GRUB_CMDLINE_LINUX="systemd.unified_cgroup_hierarchy=0"
```

If the variable already contains options, keep them and add the new option separated by a space. Apply the change and reboot:

```bash
sudo update-grub
sudo reboot
```

After reconnecting to the server, verify that cgroup v1 is active. The following command should print `tmpfs`:

```bash
stat -fc %T /sys/fs/cgroup
```

## 4. Install Docker Engine and Compose

Add Docker's official Ubuntu repository:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
```

```bash
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

Install Docker and enable it at boot:

```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Log out and back in so the Docker group change takes effect, then verify the installation:

```bash
docker --version
docker compose version
docker run --rm hello-world
```

## 5. Download Judge0 CE

Download the official v1.13.1 release archive rather than cloning the development branch:

```bash
mkdir -p "$HOME/judge0"
cd "$HOME/judge0"
wget https://github.com/judge0/judge0/releases/download/v1.13.1/judge0-v1.13.1.zip
unzip judge0-v1.13.1.zip
cd judge0-v1.13.1
```

The extracted directory contains `docker-compose.yml` and `judge0.conf`.

## 6. Set passwords and Judge0 API tokens

Generate four different secrets—one each for Redis, PostgreSQL, Judge0 authentication, and Judge0 authorization:

```bash
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 32
```

Open the configuration:

```bash
nano judge0.conf
```

Replace the existing values for these variables with the four generated secrets:

```env
REDIS_PASSWORD=first-generated-secret
POSTGRES_PASSWORD=second-generated-secret
AUTHN_HEADER=X-Auth-Token
AUTHN_TOKEN=third-generated-secret
AUTHZ_HEADER=X-Auth-User
AUTHZ_TOKEN=fourth-generated-secret
```

`AUTHN_TOKEN` protects every Judge0 API request. Clients send its value in the `X-Auth-Token` header. `AUTHZ_TOKEN` permits protected administrative operations, such as listing all submissions, and clients send its value in the `X-Auth-User` header. Despite the default header name, `X-Auth-User` contains the authorization token—not an Ubuntu username.

Keep authentication enabled for a network-accessible installation. Do not commit or share `judge0.conf` after adding these secrets. The examples below use these placeholders:

```text
YOUR_AUTHN_TOKEN = value assigned to AUTHN_TOKEN
YOUR_AUTHZ_TOKEN = value assigned to AUTHZ_TOKEN
```

## 7. Start Judge0

Start PostgreSQL and Redis first, allow them to initialize, and then start the remaining services:

```bash
docker compose up -d db redis
sleep 10
docker compose up -d
sleep 5
```

Confirm that the containers are running:

```bash
docker compose ps
docker compose logs --tail=100
```

Judge0 should now be available inside the VM at:

```text
http://localhost:2358
http://localhost:2358/docs
```

Verify the API:

```bash
curl -H "X-Auth-Token: YOUR_AUTHN_TOKEN" http://localhost:2358/about
curl -H "X-Auth-Token: YOUR_AUTHN_TOKEN" http://localhost:2358/languages
```

Verify both tokens explicitly:

```bash
curl -i -X POST \
  -H "X-Auth-Token: YOUR_AUTHN_TOKEN" \
  http://localhost:2358/authenticate

curl -i -X POST \
  -H "X-Auth-Token: YOUR_AUTHN_TOKEN" \
  -H "X-Auth-User: YOUR_AUTHZ_TOKEN" \
  http://localhost:2358/authorize
```

Both commands should return HTTP `200`. A missing or incorrect authentication token returns HTTP `401`.

## 8. Allow access from the host or application server

Find the VM's IP address:

```bash
hostname -I
```

From the host machine, test it with the first relevant address returned above:

```bash
curl -H "X-Auth-Token: YOUR_AUTHN_TOKEN" \
  http://VM_IP_ADDRESS:2358/about
```

If UFW is enabled, allow only the host or application server to reach Judge0. Replace `CLIENT_IP_ADDRESS` with that machine's IP:

```bash
sudo ufw allow from CLIENT_IP_ADDRESS to any port 2358 proto tcp
sudo ufw status
```

For a NAT-only VM, configure a port-forwarding rule in the hypervisor, such as host port `2358` to guest port `2358`. With bridged networking, use the VM's LAN address directly.

## 9. Connect mAIstra to the self-hosted Judge0 server

On the machine that runs this repository, clone it and enter its directory if needed:

```bash
git clone YOUR_REPOSITORY_URL mAIstra
cd mAIstra
```

Set the Judge0 URL before starting the FastAPI wrapper:

```bash
export JUDGE0_BASE_URL=http://VM_IP_ADDRESS:2358
export JUDGE0_API_KEY=YOUR_AUTHN_TOKEN
```

The wrapper reads `JUDGE0_API_KEY` and sends it to Judge0 as `X-Auth-Token`. Its current submission and language endpoints do not perform Judge0's authorization-protected administrative operations, so it does not need `AUTHZ_TOKEN` or send `X-Auth-User`. Keep the authorization token available only to trusted administration tools.

Run the wrapper locally:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r judge0_api/requirements.txt
cd judge0_api
uvicorn main:app --host 0.0.0.0 --port 8001
```

In another terminal, verify the wrapper:

```bash
curl http://localhost:8001/
```

Expected response:

```json
{"status":"ok"}
```

Test a C submission through mAIstra's wrapper:

```bash
curl -X POST http://localhost:8001/api/judge0/run \
  -H "Content-Type: application/json" \
  -d '{
    "source_code": "#include <stdio.h>\nint main(void){ printf(\"Hello Judge0\"); return 0; }",
    "language_id": 50,
    "stdin": ""
  }'
```

The response should contain `Hello Judge0` in `stdout`.

The Angular application currently expects the wrapper at `http://127.0.0.1:8001/api/judge0`. If the wrapper runs on another machine, update the URLs in:

- `maistra_web/src/app/services/judge0.service.ts`
- `maistra_web/src/app/components/judge0/judge0.ts`

## Routine administration

Run these commands from `$HOME/judge0/judge0-v1.13.1`:

```bash
# View status
docker compose ps

# Follow logs
docker compose logs -f

# Restart all services
docker compose restart

# Stop services without deleting their data
docker compose down

# Start services again
docker compose up -d
```

Avoid `docker compose down -v` unless you intentionally want to delete Judge0's PostgreSQL and Redis volumes.

## Troubleshooting

- **`Cannot write ... /sys/fs/cgroup/...` or submissions end in Internal Error:** verify Step 3 and confirm `stat -fc %T /sys/fs/cgroup` prints `tmpfs`, not `cgroup2fs`.
- **Port `2358` is unreachable:** check `docker compose ps`, the VM network mode, port forwarding, the cloud firewall/security group, and UFW.
- **Database or Redis is unhealthy:** confirm the passwords in `judge0.conf` were changed without spaces or quotes, then inspect `docker compose logs db redis`.
- **Judge0 returns HTTP 401:** make sure the request includes `X-Auth-Token` with the exact `AUTHN_TOKEN` value from `judge0.conf`.
- **Judge0 rejects a protected operation:** include both `X-Auth-Token: YOUR_AUTHN_TOKEN` and `X-Auth-User: YOUR_AUTHZ_TOKEN`.
- **Wrapper cannot connect:** test `/about` with the authentication header from the same machine or container as the wrapper, confirm `JUDGE0_API_KEY` matches `AUTHN_TOKEN`, and verify `JUDGE0_BASE_URL` has no trailing path.
- **Browser reports a CORS error:** add the frontend's exact origin to `allow_origins` in `judge0_api/main.py`.
- **After a reboot:** Docker and Judge0 containers should restart automatically. If they do not, run `docker compose up -d` from the Judge0 directory.

## Official references

- [Judge0 GitHub repository](https://github.com/judge0/judge0)
- [Judge0 CE v1.13.1 release and deployment procedure](https://github.com/judge0/judge0/releases/tag/v1.13.1)
- [Docker Engine installation on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
