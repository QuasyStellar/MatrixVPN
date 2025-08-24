import os
import pathlib
import asyncio
import aiosqlite
import re
import shutil
from datetime import datetime
import json
import sqlite3
from xtlsapi import XrayClient, utils
from contextlib import asynccontextmanager
import aiofiles
from collections import defaultdict


# --- Configuration Class ---
class Config:
    """Handles loading and accessing configuration from the setup file."""

    def __init__(self, setup_file_path="/root/antizapret/setup"):
        self.config = {}
        self.load_config(setup_file_path)

        # Define paths with defaults, overridden by the setup file
        self.ROOT_DIR = self.get("ROOT_DIR", "/root/antizapret")
        self.EASYRSA_DIR = self.get("EASYRSA_DIR", "/etc/openvpn/easyrsa3")
        self.OPENVPN_DIR = self.get("OPENVPN_DIR", "/etc/openvpn")
        self.WIREGUARD_DIR = self.get("WIREGUARD_DIR", "/etc/wireguard")
        self.XRAY_DB_PATH = self.get("XRAY_DB_PATH",
                                     "/root/antizapret/xray.db")
        self.XRAY_API_HOST = self.get("XRAY_API_HOST", "127.0.0.1")
        self.XRAY_API_PORT = int(self.get("XRAY_API_PORT", 10085))
        self.IP = "172" if self.get("ALTERNATIVE_IP",
                                    "n").lower() == "y" else "10"
        self.CLIENT_BASE_DIR = os.path.join(self.ROOT_DIR, "client")
        self.BACKUP_BASE_DIR = os.path.join(self.ROOT_DIR, "backup")
        self.SERVER_CONFIG_PATH = os.path.join(self.ROOT_DIR, "setup")

    def load_config(self, setup_file_path):
        if not os.path.exists(setup_file_path):
            raise FileNotFoundError(f"Setup file not found: {setup_file_path}")
        with open(setup_file_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, value = line.split("=", 1)
                        self.config[key.strip()] = value.strip()

    def get(self, key, default=None):
        return self.config.get(key, default)


# Global config instance and lock management
config = Config()
SERVER_IP = None
openvpn_lock = asyncio.Lock()  # Global lock for all OpenVPN/easyrsa operations
user_locks = defaultdict(asyncio.Lock)  # Per-user locks for WG and VLESS


# --- Helper Functions ---
async def handle_error(lineno, command, message=""):
    print(f"Error at line {lineno}: {command}")
    print(f"Message: {message}")


async def run_command(command_args, input_data=None, cwd=None, env=None):
    print(f"Running: {" ".join(command_args)}")
    process = await asyncio.create_subprocess_exec(
        *command_args,
        stdin=asyncio.subprocess.PIPE if input_data else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=env)
    stdout, stderr = await process.communicate(
        input=input_data.encode() if input_data else None)

    if process.returncode != 0:
        await handle_error(
            "N/A",
            " ".join(command_args),
            f"Command failed with exit code {process.returncode}:\n{stderr.decode()}",
        )
        return None, None

    return stdout.decode(), stderr.decode()


@asynccontextmanager
async def file_lock(lock_file_path):
    lock_file = f"{lock_file_path}.lock"
    if await asyncio.to_thread(os.path.exists, lock_file):
        raise IOError(
            f"Lock file {lock_file} already exists. Another instance may be running."
        )
    try:
        async with aiofiles.open(lock_file, "w") as f:
            await f.write(str(os.getpid()))
        yield
    finally:
        if await asyncio.to_thread(os.path.exists, lock_file):
            await asyncio.to_thread(os.remove, lock_file)


async def extract_cert_content(cert_path):
    try:
        async with aiofiles.open(cert_path, "r") as f:
            content = await f.read()
        start_marker = "-----BEGIN CERTIFICATE-----"
        end_marker = "-----END CERTIFICATE-----"
        start_index = content.find(start_marker)
        end_index = content.find(end_marker)
        if start_index != -1 and end_index != -1:
            return content[start_index:end_index + len(end_marker)]
    except IOError as e:
        print(f"Could not read certificate file {cert_path}: {e}")
    return ""


async def modify_wg_config(config_path, client_name, new_peer_block=None):
    if not await asyncio.to_thread(os.path.exists, config_path):
        return False

    async with aiofiles.open(config_path, "r") as f:
        lines = await f.readlines()

    new_lines = []
    client_found = False
    in_client_block = False

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == f"# Client = {client_name}":
            client_found = True
            i += 1
            while i < len(lines) and lines[i].strip() != "":
                i += 1
            if i < len(lines) and lines[i].strip() == "":
                i += 1
            continue
        new_lines.append(line)
        i += 1

    while new_lines and new_lines[-1].strip() == "":
        new_lines.pop()

    if new_peer_block:
        new_lines.append("\n\n")
        new_lines.append(new_peer_block)
        new_lines.append("\n")

    async with aiofiles.open(config_path, "w") as f:
        await f.writelines(new_lines)

    return client_found


async def sync_wireguard_config(interface_name):
    stdout, stderr = await run_command(
        ["systemctl", "is-active", "--quiet", f"wg-quick@{interface_name}"])
    if stdout is None:  # Error occurred
        return

    print(f"Syncing active WireGuard interface: {interface_name}")
    try:
        stripped_config, _ = await run_command(
            ["wg-quick", "strip", interface_name])
        if stripped_config:
            await run_command(["wg", "syncconf", interface_name, "/dev/stdin"],
                              input_data=stripped_config)
    except Exception as e:
        print(
            f"An error occurred during wg syncconf for {interface_name}: {e}")


async def set_server_host_file_name(client_name, server_host_override=""):
    global SERVER_HOST, FILE_NAME
    SERVER_HOST = server_host_override or SERVER_IP
    FILE_NAME = client_name.replace("antizapret-", "").replace("vpn-", "")
    FILE_NAME = f"{FILE_NAME}-({SERVER_HOST})"
    return SERVER_HOST, FILE_NAME


async def render(template_file_path, variables):
    async with aiofiles.open(template_file_path, "r") as f:
        content = await f.read()
    for var_name, value in variables.items():
        content = content.replace(f"${{{var_name}}}", str(value))
    content = re.sub(r"\$\{[a-zA-Z_][a-zA-Z_0-9]*}", "", content)
    return content


# --- OpenVPN Functions ---
async def init_openvpn():
    print("\nInitializing OpenVPN EasyRSA PKI...")
    pki_dir = os.path.join(config.EASYRSA_DIR, "pki")
    server_keys_dir = os.path.join(config.OPENVPN_DIR, "server/keys")
    client_keys_dir = os.path.join(config.OPENVPN_DIR, "client/keys")

    await asyncio.to_thread(os.makedirs, config.EASYRSA_DIR, exist_ok=True)

    if not all([
            await asyncio.to_thread(os.path.exists, p) for p in [
                os.path.join(pki_dir, "ca.crt"),
                os.path.join(pki_dir, "issued/antizapret-server.crt"),
            ]
    ]):
        print("PKI not found or incomplete. Initializing new PKI...")
        if await asyncio.to_thread(os.path.exists, pki_dir):
            await asyncio.to_thread(shutil.rmtree, pki_dir)
        if await asyncio.to_thread(os.path.exists, server_keys_dir):
            await asyncio.to_thread(shutil.rmtree, server_keys_dir)
        if await asyncio.to_thread(os.path.exists, client_keys_dir):
            await asyncio.to_thread(shutil.rmtree, client_keys_dir)

        await run_command(["/usr/share/easy-rsa/easyrsa", "init-pki"],
                          cwd=config.EASYRSA_DIR)
        await run_command([
            "/usr/share/easy-rsa/easyrsa",
            "--batch",
            "--req-cn=AntiZapret CA",
            "build-ca",
            "nopass",
        ],
                          cwd=config.EASYRSA_DIR,
                          env={
                              "EASYRSA_CA_EXPIRE": "3650",
                              **os.environ
                          })
        await run_command([
            "/usr/share/easy-rsa/easyrsa",
            "--batch",
            "build-server-full",
            "antizapret-server",
            "nopass",
        ],
                          cwd=config.EASYRSA_DIR,
                          env={
                              "EASYRSA_CERT_EXPIRE": "3650",
                              **os.environ
                          })
    else:
        print("OpenVPN PKI already initialized.")

    await asyncio.to_thread(os.makedirs, server_keys_dir, exist_ok=True)
    await asyncio.to_thread(os.makedirs, client_keys_dir, exist_ok=True)

    for f in ["ca.crt", "antizapret-server.crt", "antizapret-server.key"]:
        src_path = os.path.join(
            pki_dir,
            ("issued" if ".crt" in f and f != "ca.crt" else
             ("private" if ".key" in f else "")),
            f,
        )
        dest_path = os.path.join(server_keys_dir, f)
        if not await asyncio.to_thread(os.path.exists, dest_path):
            await asyncio.to_thread(shutil.copy, src_path, dest_path)

    crl_path = os.path.join(server_keys_dir, "crl.pem")
    if not await asyncio.to_thread(os.path.exists, crl_path):
        print("Generating CRL...")
        await run_command(["/usr/share/easy-rsa/easyrsa", "gen-crl"],
                          cwd=config.EASYRSA_DIR,
                          env={
                              "EASYRSA_CRL_DAYS": "3650",
                              **os.environ
                          })
        await asyncio.to_thread(shutil.copy, os.path.join(pki_dir, "crl.pem"),
                                crl_path)
        await asyncio.to_thread(os.chmod, crl_path, 0o644)


async def add_openvpn(client_name, client_cert_expire_days=3650):
    print(f"\nAdding/Renewing OpenVPN client: {client_name}")
    await set_server_host_file_name(client_name, config.get("OPENVPN_HOST"))
    pki_dir = os.path.join(config.EASYRSA_DIR, "pki")

    client_crt_path = os.path.join(pki_dir, "issued", f"{client_name}.crt")
    client_key_path = os.path.join(pki_dir, "private", f"{client_name}.key")

    if await asyncio.to_thread(os.path.exists,
                               client_crt_path) or await asyncio.to_thread(
                                   os.path.exists, client_key_path):
        print(f"Client '{client_name}' already exists. Forcing renewal...")
        for p in [
                client_crt_path, client_key_path,
                os.path.join(pki_dir, "reqs", f"{client_name}.req")
        ]:
            if await asyncio.to_thread(os.path.exists, p):
                await asyncio.to_thread(os.remove, p)
    else:
        print("Client does not exist. Building new client certificate.")

    await run_command([
        "/usr/share/easy-rsa/easyrsa",
        "--batch",
        "build-client-full",
        client_name,
        "nopass",
    ],
                      cwd=config.EASYRSA_DIR,
                      env={
                          "EASYRSA_CERT_EXPIRE": str(client_cert_expire_days),
                          **os.environ
                      })

    client_keys_dir = os.path.join(config.OPENVPN_DIR, "client/keys")
    await asyncio.to_thread(
        shutil.copy, client_crt_path,
        os.path.join(client_keys_dir, f"{client_name}.crt"))
    await asyncio.to_thread(
        shutil.copy, client_key_path,
        os.path.join(client_keys_dir, f"{client_name}.key"))

    ca_cert_content = await extract_cert_content(
        os.path.join(config.OPENVPN_DIR, "server/keys/ca.crt"))
    client_cert_content = await extract_cert_content(
        os.path.join(client_keys_dir, f"{client_name}.crt"))
    async with aiofiles.open(
            os.path.join(client_keys_dir, f"{client_name}.key"), "r") as f:
        client_key_content = await f.read()

    if not all([ca_cert_content, client_cert_content, client_key_content]):
        await handle_error("N/A", "Key loading", "Cannot load client keys!")

    client_dir = os.path.join(config.CLIENT_BASE_DIR, client_name)
    await asyncio.to_thread(os.makedirs, client_dir, exist_ok=True)
    current_date = datetime.now().strftime("%y-%m-%d")

    render_vars = {
        "SERVER_HOST": SERVER_HOST,
        "CA_CERT": ca_cert_content,
        "CLIENT_CERT": client_cert_content,
        "CLIENT_KEY": client_key_content,
        "SERVER_IP": SERVER_IP,
        **config.config,
    }

    templates_dir = os.path.join(config.OPENVPN_DIR, "client/templates")
    templates = {
        "antizapret-udp.conf": f"AZ-UDP-{current_date}.ovpn",
        "antizapret-tcp.conf": f"AZ-TCP-{current_date}.ovpn",
        "antizapret.conf": f"AZ-U+T-{current_date}.ovpn",
        "vpn-udp.conf": f"GL-UDP-{current_date}.ovpn",
        "vpn-tcp.conf": f"GL-TCP-{current_date}.ovpn",
        "vpn.conf": f"GL-U+T-{current_date}.ovpn",
    }

    for template, output_filename in templates.items():
        template_path = os.path.join(templates_dir, template)
        if await asyncio.to_thread(os.path.exists, template_path):
            output_path = os.path.join(client_dir, output_filename)
            rendered_content = await render(template_path, render_vars)
            async with aiofiles.open(output_path, "w") as f:
                await f.write(rendered_content)

    print(
        f"OpenVPN profile files (re)created for client '{client_name}' at {client_dir}"
    )


async def delete_openvpn(client_name):
    print(f"\nDeleting OpenVPN client: {client_name}")
    await run_command(
        ["/usr/share/easy-rsa/easyrsa", "--batch", "revoke", client_name],
        cwd=config.EASYRSA_DIR)
    await run_command(["/usr/share/easy-rsa/easyrsa", "gen-crl"],
                      cwd=config.EASYRSA_DIR,
                      env={
                          "EASYRSA_CRL_DAYS": "3650",
                          **os.environ
                      })
    pki_dir = os.path.join(config.EASYRSA_DIR, "pki")
    crl_src = os.path.join(pki_dir, "crl.pem")
    crl_dest = os.path.join(config.OPENVPN_DIR, "server/keys/crl.pem")
    await asyncio.to_thread(shutil.copy, crl_src, crl_dest)
    await asyncio.to_thread(os.chmod, crl_dest, 0o644)

    if await asyncio.to_thread(
            os.path.exists, os.path.join(config.CLIENT_BASE_DIR, client_name)):
        await asyncio.to_thread(
            shutil.rmtree, os.path.join(config.CLIENT_BASE_DIR, client_name))
    for ext in [".crt", ".key"]:
        p = os.path.join(config.OPENVPN_DIR, f"client/keys/{client_name}{ext}")
        if await asyncio.to_thread(os.path.exists, p):
            await asyncio.to_thread(os.remove, p)

    print(f"OpenVPN client '{client_name}' successfully deleted")


# --- WireGuard Functions ---
async def init_wireguard():
    print("\nInitializing WireGuard/AmneziaWG server keys...")
    await asyncio.to_thread(os.makedirs, config.WIREGUARD_DIR, exist_ok=True)
    key_path = os.path.join(config.WIREGUARD_DIR, "key")

    if not await asyncio.to_thread(os.path.exists, key_path):
        private_key, _ = await run_command(["wg", "genkey"])
        public_key, _ = await run_command(["wg", "pubkey"],
                                          input_data=private_key)

        async with aiofiles.open(key_path, "w") as f:
            await f.write(
                f"PRIVATE_KEY={private_key.strip()}\nPUBLIC_KEY={public_key.strip()}\n"
            )

        render_vars = {
            "PRIVATE_KEY": private_key.strip(),
            "PUBLIC_KEY": public_key.strip(),
            "SERVER_IP": SERVER_IP,
            **config.config,
        }

        templates_dir = os.path.join(config.WIREGUARD_DIR, "templates")
        for conf_name in ["antizapret.conf", "vpn.conf"]:
            template_path = os.path.join(templates_dir, conf_name)
            if await asyncio.to_thread(os.path.exists, template_path):
                rendered_conf = await render(template_path, render_vars)
                async with aiofiles.open(
                        os.path.join(config.WIREGUARD_DIR, conf_name),
                        "w") as f:
                    await f.write(rendered_conf)
        print("WireGuard/AmneziaWG server keys and configs generated.")
    else:
        print("WireGuard/AmneziaWG server keys already exist.")


async def add_wireguard(client_name):
    print(f"\nAdding WireGuard/AmneziaWG client: {client_name}")
    await set_server_host_file_name(client_name, config.get("WIREGUARD_HOST"))

    key_path = os.path.join(config.WIREGUARD_DIR, "key")
    if not await asyncio.to_thread(os.path.exists, key_path):
        await handle_error(
            "N/A",
            "WireGuard key loading",
            "WireGuard server keys not found. Run init_wireguard first.",
        )

    async with aiofiles.open(key_path, "r") as f:
        content = await f.read()
        server_public_key = re.search(r"PUBLIC_KEY=(.*)", content).group(1)

    ips_path = os.path.join(config.WIREGUARD_DIR, "ips")
    ips_content = ""
    if await asyncio.to_thread(os.path.exists, ips_path):
        async with aiofiles.open(ips_path, "r") as f:
            ips_content = await f.read()

    client_dir = os.path.join(config.CLIENT_BASE_DIR, client_name)
    await asyncio.to_thread(os.makedirs, client_dir, exist_ok=True)
    current_date = datetime.now().strftime("%y-%m-%d")

    for wg_type in ["antizapret", "vpn"]:
        print(f"Processing {wg_type.capitalize()} WireGuard configuration...")
        conf_path = os.path.join(config.WIREGUARD_DIR, f"{wg_type}.conf")
        lock_path = f"{conf_path}.lock"

        async with file_lock(lock_path):
            if await modify_wg_config(conf_path, client_name):
                print(
                    f"Client '{client_name}' exists in {wg_type}.conf. Recreating..."
                )

            client_private_key, _ = await run_command(["wg", "genkey"])
            client_public_key, _ = await run_command(
                ["wg", "pubkey"], input_data=client_private_key)
            client_preshared_key, _ = await run_command(["wg", "genpsk"])

            async with aiofiles.open(conf_path, "r") as f:
                conf_content = await f.read()
                base_ip_match = re.search(
                    r"Address = (\d{1,3}\.\d{1,3}\.\d{1,3})", conf_content)
                base_client_ip = base_ip_match.group(1)

                existing_ips = set(
                    re.findall(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})",
                               conf_content))

            client_ip = ""
            for i in range(2, 255):
                potential_ip = f"{base_client_ip}.{i}"
                if potential_ip not in existing_ips:
                    client_ip = potential_ip
                    break

            if not client_ip:
                await handle_error(
                    "N/A", "IP assignment",
                    f"No available IPs in the {wg_type} subnet!")

            new_peer_block = (
                f"# Client = {client_name}\n# PrivateKey = {client_private_key.strip()}\n[Peer]\n"
                f"PublicKey = {client_public_key.strip()}\nPresharedKey = {client_preshared_key.strip()}\n"
                f"AllowedIPs = {client_ip}/32")
            await modify_wg_config(conf_path, client_name, new_peer_block)

        await sync_wireguard_config(wg_type)

        render_vars = {
            "SERVER_HOST": SERVER_HOST,
            "PUBLIC_KEY": server_public_key,
            "CLIENT_PRIVATE_KEY": client_private_key.strip(),
            "CLIENT_PUBLIC_KEY": client_public_key.strip(),
            "CLIENT_PRESHARED_KEY": client_preshared_key.strip(),
            "CLIENT_IP": client_ip,
            "IPS": ips_content,
            **config.config,
        }

        templates_dir = os.path.join(config.WIREGUARD_DIR, "templates")
        prefix = "AZ" if wg_type == "antizapret" else "GL"

        for suffix in ["wg", "am"]:
            template_name = f"{wg_type}-client-{suffix}.conf"
            output_name = f"{prefix}-{suffix.upper()}-{current_date}.conf"
            template_path = os.path.join(templates_dir, template_name)
            if await asyncio.to_thread(os.path.exists, template_path):
                rendered_conf = await render(template_path, render_vars)
                async with aiofiles.open(os.path.join(client_dir, output_name),
                                         "w") as f:
                    await f.write(rendered_conf)

    print(
        f"WireGuard/AmneziaWG profile files (re)created for client '{client_name}' at {client_dir}"
    )


async def delete_wireguard(client_name):
    print(f"\nDeleting WireGuard/AmneziaWG client: {client_name}")

    client_found = False
    for wg_type in ["antizapret", "vpn"]:
        conf_path = os.path.join(config.WIREGUARD_DIR, f"{wg_type}.conf")
        if await modify_wg_config(conf_path, client_name, new_peer_block=None):
            print(f"Removed client '{client_name}' from {wg_type}.conf")
            client_found = True
            await sync_wireguard_config(wg_type)

    if not client_found:
        print(
            f"Failed to delete client '{client_name}'! Client not found in any config."
        )
        return

    if await asyncio.to_thread(
            os.path.exists, os.path.join(config.CLIENT_BASE_DIR, client_name)):
        await asyncio.to_thread(
            shutil.rmtree, os.path.join(config.CLIENT_BASE_DIR, client_name))
    print(f"WireGuard/AmneziaWG client '{client_name}' successfully deleted")


# --- Xray Functions ---
def get_xray_client(host, port):
    try:
        return XrayClient(host, port)
    except Exception as e:
        raise ConnectionError(
            f"Error connecting to Xray API on {host}:{port}: {e}")


async def create_table():
    if not await asyncio.to_thread(os.path.exists,
                                   os.path.dirname(config.XRAY_DB_PATH)):
        await asyncio.to_thread(os.makedirs,
                                os.path.dirname(config.XRAY_DB_PATH))
    async with aiosqlite.connect(config.XRAY_DB_PATH) as conn:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS users (uuid TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_email ON users (email)")
        await conn.commit()


async def add_user_to_db(uuid, identifier):
    try:
        async with aiosqlite.connect(config.XRAY_DB_PATH) as conn:
            await conn.execute("INSERT INTO users (uuid, email) VALUES (?, ?)",
                               (uuid, identifier))
            await conn.commit()
            return True
    except sqlite3.IntegrityError:
        print(f"Error: User with identifier '{identifier}' already exists.")
        return False


async def get_user_by_identifier_from_db(identifier):
    async with aiosqlite.connect(config.XRAY_DB_PATH) as conn:
        async with conn.execute("SELECT * FROM users WHERE email = ?",
                                (identifier, )) as cursor:
            return await cursor.fetchone()


async def remove_user_from_db(email):
    async with aiosqlite.connect(config.XRAY_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("DELETE FROM users WHERE email = ?", (email, ))
        await conn.commit()


def generate_vless_link(user_id, server_host, public_key, server_names,
                        vless_port, short_id, identifier):
    """Generates a VLESS configuration link."""
    params = {
        "type": "tcp",
        "security": "reality",
        "flow": "xtls-rprx-vision",
        "fp": "chrome",
        "pbk": public_key,
        "sni": server_names,
        "sid": short_id,
    }
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return f"vless://{user_id}@{server_host}:{vless_port}?{query_string}#{identifier}"


def generate_client_config(user_id, server_host, public_key, server_names,
                           vless_port, short_id):
    """Generates the client-side VLESS configuration dictionary."""
    # This function remains largely the same, just ensure variables are passed correctly.
    return {
        "dns": {
            "servers": [f"{config.IP}.29.12.1"]
        },
        "fakedns": [
            {
                "ipPool": "198.20.0.0/15",
                "poolSize": 128
            },
            {
                "ipPool": "fc00::/64",
                "poolSize": 128
            },
        ],
        "inbounds": [{
            "listen": "127.0.0.1",
            "port": 1080,
            "protocol": "socks",
            "settings": {
                "auth": "noauth",
                "udp": True
            },
            "sniffing": {
                "destOverride": ["http", "tls", "quic"],
                "enabled": True,
                "routeOnly": True,
            },
            "tag": "in-vless",
        }],
        "outbounds": [
            {
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address":
                        server_host,
                        "port":
                        int(vless_port),
                        "users": [{
                            "id": user_id,
                            "encryption": "none",
                            "flow": "xtls-rprx-vision",
                        }],
                    }]
                },
                "streamSettings": {
                    "network": "tcp",
                    "realitySettings": {
                        "fingerprint": "chrome",
                        "publicKey": public_key,
                        "serverName": server_names,
                        "shortId": short_id,
                    },
                    "security": "reality",
                    "tcpSettings": {
                        "header": {
                            "type": "none",
                            "request": {
                                "headers": {}
                            }
                        }
                    },
                },
                "tag": "proxy",
            },
            {
                "protocol": "freedom",
                "tag": "direct"
            },
            {
                "protocol": "blackhole",
                "tag": "block"
            },
        ],
        "routing": {
            "domainStrategy":
            "IPOnDemand",
            "rules": [
                {
                    "ip": ["10.30.0.0/15", f"{config.IP}.29.12.1"],
                    "outboundTag": "proxy",
                    "type": "field",
                },
                {
                    "domain": ["geosite:private"],
                    "outboundTag": "direct",
                    "type": "field",
                },
                {
                    "ip": ["0.0.0.0/0"],
                    "outboundTag": "direct",
                    "type": "field"
                },
            ],
        },
    }


async def handle_add_user(identifier, xray_client):
    user = await get_user_by_identifier_from_db(identifier)
    if user:
        user_id = user[0]
        print(
            f"User '{identifier}' exists. Recreating Xray client and configs..."
        )
        await handle_remove_user(user_id, xray_client)
    else:
        user_id = utils.generate_random_user_id()
        if not await add_user_to_db(user_id, identifier):
            return
        print(
            f"User '{identifier}' not found. Created new user with ID {user_id}."
        )

    try:
        add_client_result = await asyncio.to_thread(xray_client.add_client,
                                                    "in-vless",
                                                    user_id,
                                                    identifier,
                                                    flow="xtls-rprx-vision")
        if not add_client_result:
            print(
                f"Failed to add user '{identifier}' to Xray. The user may already exist."
            )
            return
        print(f"User '{identifier}' successfully added to Xray.")
    except Exception as e:
        print(f"An exception occurred while adding user to Xray: {e}")
        return

    # Generate AZ-XR JSON config
    az_server_host = config.get("SERVER_HOST")
    az_public_key = config.get("VLESS_PUBLIC_KEY")
    az_server_names = config.get("VLESS_SERVER_NAMES")
    az_short_id = config.get("VLESS_SHORT_ID")

    if all([az_server_host, az_public_key, az_server_names, az_short_id]):
        az_client_config = generate_client_config(user_id, az_server_host,
                                                  az_public_key,
                                                  az_server_names, 443,
                                                  az_short_id)
        client_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", identifier)
        dir_path = os.path.join(config.CLIENT_BASE_DIR, client_name)
        await asyncio.to_thread(os.makedirs, dir_path, exist_ok=True)
        file_path = os.path.join(
            dir_path, f"AZ-XR-{datetime.now().strftime('%y-%m-%d')}.json")
        async with aiofiles.open(file_path, "w") as f:
            await f.write(json.dumps(az_client_config, indent=4))
        print(f"AZ-XR JSON config saved to: {file_path}")
    else:
        print(
            f"Warning: Missing AZ VLESS config in {config.SERVER_CONFIG_PATH}. Skipping AZ-XR JSON generation."
        )

    # Generate GL-XR VLESS link
    gb_server_host = config.get("SERVER_HOST")
    gb_public_key = config.get("VLESS_PUBLIC_KEY")
    gb_server_names = config.get("VLESS_SERVER_NAMES")
    gb_short_id = config.get("VLESS_SHORT_ID")

    if all([gb_server_host, gb_public_key, gb_server_names, gb_short_id]):
        gb_vless_link = generate_vless_link(user_id, gb_server_host,
                                            gb_public_key, gb_server_names,
                                            443, gb_short_id,
                                            identifier + "-GL")
        client_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", identifier)
        dir_path = os.path.join(config.CLIENT_BASE_DIR, client_name)
        await asyncio.to_thread(os.makedirs, dir_path, exist_ok=True)
        file_path = os.path.join(
            dir_path, f"GL-XR-{datetime.now().strftime('%y-%m-%d')}.txt")
        async with aiofiles.open(file_path, "w") as f:
            await f.write(gb_vless_link)
        print(f"GL-XR VLESS link saved to: {file_path}")
    else:
        print(
            f"Warning: Missing GL VLESS config in {config.SERVER_CONFIG_PATH}. Skipping GL-XR link generation."
        )


async def handle_remove_user(identifier, xray_client):
    user = await get_user_by_identifier_from_db(identifier)
    if not user:
        print(f"Error: User with identifier '{identifier}' not found.")
        return
    try:
        await asyncio.to_thread(xray_client.remove_client, "in-vless",
                                identifier)
        print(f"User '{identifier}' removed from Xray.")
    except Exception as e:
        print(
            f"Warning: Could not remove user from Xray (user might not exist there): {e}"
        )

    await remove_user_from_db(identifier)
    print(f"User '{identifier}' removed from database.")
    if await asyncio.to_thread(
            os.path.exists,
            os.path.join(config.CLIENT_BASE_DIR,
                         re.sub(r"[^a-zA-Z0-9_.-]", "_", identifier))):
        await asyncio.to_thread(
            shutil.rmtree,
            os.path.join(config.CLIENT_BASE_DIR,
                         re.sub(r"[^a-zA-Z0-9_.-]", "_", identifier)))


# --- Main Integration Functions ---
async def create_user(user_id):
    client_name = f"n{user_id}"
    print(f"--- Creating user {client_name} ---")

    async with openvpn_lock:
        await init_openvpn()
        await add_openvpn(client_name)

    async with user_locks[user_id]:
        await init_wireguard()
        await add_wireguard(client_name)

        await create_table()
        try:
            xray_client = await asyncio.to_thread(get_xray_client,
                                                  config.XRAY_API_HOST,
                                                  config.XRAY_API_PORT)
            await handle_add_user(
                client_name,
                xray_client,
            )
        except ConnectionError as e:
            print(
                f"Could not connect to Xray, skipping VLESS user creation: {e}"
            )

    print(f"--- User {client_name} created ---")


async def delete_user(user_id):
    client_name = f"n{user_id}"
    print(f"--- Deleting user {client_name} ---")

    async with openvpn_lock:
        await delete_openvpn(client_name)

    async with user_locks[user_id]:
        await delete_wireguard(client_name)
        try:
            xray_client = await asyncio.to_thread(get_xray_client,
                                                  config.XRAY_API_HOST,
                                                  config.XRAY_API_PORT)
            await handle_remove_user(client_name, xray_client)
        except ConnectionError as e:
            print(
                f"Could not connect to Xray, skipping VLESS user deletion: {e}"
            )


async def set_server_ip_async():
    global SERVER_IP
    path = pathlib.Path("/root/antizapret/setup")
    async with aiofiles.open(path, encoding="utf-8") as f:
        async for line in f:
            line = line.strip()
            if line.startswith("SERVER_HOST="):
                SERVER_IP = line.split("=", 1)[1].strip().strip("\"'")
                return SERVER_IP
    raise RuntimeError("SERVER_HOST не найден в setup")
