import subprocess
import time

def get_active_vpn_connection():
    result = subprocess.run(
        ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"],
        capture_output=True,
        text=True
    )
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        name, conn_type = line.split(":", 1)
        if conn_type == "vpn":
            return name
    return None

def disconnect_vpn():
    vpn_name = get_active_vpn_connection()
    if not vpn_name:
        print("No active VPN connection found — nothing to disconnect.")
        return True  # not an error, just already disconnected

    result = subprocess.run(
        ["nmcli", "connection", "down", vpn_name],
        capture_output=True,
        text=True
    )
    print(f"Disconnecting '{vpn_name}':", result.stdout, result.stderr)
    return result.returncode == 0