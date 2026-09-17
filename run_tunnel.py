import os
import sys
import re
import time
import subprocess
import signal
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def update_backend_env(domain: str):
    env_file = Path(__file__).resolve().parent / "backend" / ".env"
    if not env_file.exists():
        print(f"[Warning] {env_file} does not exist.")
        return
    
    content = env_file.read_text(encoding="utf-8")
    if re.search(r"^APP_HOST=.*$", content, flags=re.MULTILINE):
        new_content = re.sub(r"^APP_HOST=.*$", f"APP_HOST={domain}", content, flags=re.MULTILINE)
    else:
        new_content = content + f"\nAPP_HOST={domain}\n"
    
    env_file.write_text(new_content, encoding="utf-8")
    print(f"[OK] Updated backend/.env with APP_HOST={domain}")

def start_ssh_tunnel(port: int = 5000):
    print("Connecting zero-setup secure public tunnel via localhost.run...")
    null_dest = "NUL" if sys.platform == "win32" else "/dev/null"
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", f"UserKnownHostsFile={null_dest}",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-R", f"80:127.0.0.1:{port}",
        "nokey@localhost.run"
    ]
    
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace"
    )
    
    domain = None
    public_url = None
    start_time = time.time()

    # Read lines to capture the tunnel domain
    for line in proc.stdout:
        # Match URL like https://xyz.lhr.life or xyz.lhr.life
        m = re.search(r"https?://([a-zA-Z0-9.\-]+\.lhr\.life)", line)
        if m:
            domain = m.group(1).strip()
            public_url = f"https://{domain}"
            break
        m_alt = re.search(r"([a-zA-Z0-9.\-]+\.lhr\.life)\s+tunneled", line)
        if m_alt:
            domain = m_alt.group(1).strip()
            public_url = f"https://{domain}"
            break
        if time.time() - start_time > 20:
            break
            
    if not domain:
        proc.kill()
        raise RuntimeError("Could not establish SSH tunnel to localhost.run within 20s.")
        
    return proc, domain, public_url

def start_ngrok_tunnel(port: int = 5000, token: str = None):
    from pyngrok import ngrok
    if token:
        ngrok.set_auth_token(token)
    tunnel = ngrok.connect(port)
    public_url = tunnel.public_url
    domain = re.sub(r"^https?://", "", public_url).rstrip("/")
    return tunnel, domain, public_url

def main():
    while True:
        try:
            print("=" * 65)
            print("🚀 VOCALIS AI - TWILIO PUBLIC STREAM TUNNEL LAUNCHER")
            print("=" * 65)

            from dotenv import load_dotenv
            env_file = Path(__file__).resolve().parent / "backend" / ".env"
            if env_file.exists():
                load_dotenv(dotenv_path=env_file)

            token = None
            if len(sys.argv) > 1:
                token = sys.argv[1].strip()
            if not token:
                token = os.getenv("NGROK_AUTHTOKEN")

            proc = None
            domain = None
            public_url = None

            if token:
                try:
                    print("Found ngrok authtoken. Starting ngrok tunnel...")
                    tunnel_obj, domain, public_url = start_ngrok_tunnel(5000, token)
                except Exception as e:
                    print(f"ngrok failed: {e}. Falling back to zero-setup SSH tunnel...")

            if not domain:
                try:
                    proc, domain, public_url = start_ssh_tunnel(5000)
                except Exception as e:
                    print(f"❌ Tunnel creation failed: {e}. Retrying in 5 seconds...")
                    time.sleep(5)
                    continue

            print("\n" + "=" * 65)
            print("✅ PUBLIC TUNNEL ONLINE & ROUTING TWILIO CALLS")
            print("=" * 65)
            print(f"Public URL    : {public_url}")
            print(f"Domain        : {domain}")
            print(f"Twilio Voice  : {public_url}/api/twilio/voice")
            print(f"Twilio Stream : wss://{domain}/twilio-stream")
            print("=" * 65)

            update_backend_env(domain)

            print("\n🎉 Backend is now fully reachable by Twilio PSTN!")
            print("👉 Outbound calls will stream bidirectional audio through this tunnel.")
            print("Press Ctrl+C to disconnect tunnel.\n")

            if proc:
                while proc.poll() is None:
                    time.sleep(2)
                print(f"\n[Tunnel] Connection closed (code {proc.poll()}). Auto-reconnecting in 3s...")
                time.sleep(3)
            else:
                while True:
                    time.sleep(2)

        except KeyboardInterrupt:
            print("\nStopping tunnel...")
            if proc:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except Exception:
                    proc.kill()
            print("Tunnel closed.")
            break
        except Exception as err:
            print(f"[Tunnel Error] {err}. Reconnecting in 3s...")
            time.sleep(3)

if __name__ == "__main__":
    main()

