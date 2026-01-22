#!/usr/bin/env python3
"""Simple port/HTTP monitor.

Usage: python scripts/port_monitor.py --ports 5174 --interval 5

Polls the given HTTP ports on localhost and logs timestamped status to stdout and a log file.
"""
import argparse
import time
import socket
import sys
import subprocess
from datetime import datetime
import urllib.request


def is_port_open(host: str, port: int, timeout=1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def http_check(url: str, timeout=2.0) -> (bool, int):
    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, getattr(resp, 'status', 200)
    except Exception:
        return False, None


def monitor(ports, interval, logfile=None, restart_cmd=None, max_restarts=3, cooldown=60, dry_run=False):
    host = '127.0.0.1'
    if logfile:
        f = open(logfile, 'a')
    else:
        f = None

    # track restart attempts per port
    restarts = {p: {'count': 0, 'last': 0} for p in ports}

    try:
        while True:
            now = datetime.utcnow().isoformat() + 'Z'
            lines = []
            for p in ports:
                up = is_port_open(host, p, timeout=1.0)
                url = f'http://{host}:{p}/'
                http_ok, status = http_check(url, timeout=2.0) if up else (False, None)
                state = 'UP' if up and http_ok else 'DOWN'
                line = f"{now} port={p} socket_open={up} http_ok={http_ok} http_status={status} state={state}"
                lines.append(line)
            out = '\n'.join(lines)
            print(out)
            if f:
                f.write(out + '\n')
                f.flush()
            # attempt restart if configured and port is DOWN
            if restart_cmd or monitor.use_builtins:
                for p in ports:
                    up = is_port_open(host, p, timeout=1.0)
                    url = f'http://{host}:{p}/'
                    http_ok, status = http_check(url, timeout=2.0) if up else (False, None)
                    is_down = not (up and http_ok)
                    now_ts = time.time()
                    rec = restarts[p]
                    # only attempt if down and cooldown passed and under max_restarts
                    if is_down and (now_ts - rec['last'] > cooldown) and rec['count'] < max_restarts:
                        if monitor.use_builtins:
                            # call built-in handlers for known ports
                            try:
                                if p == 5174:
                                    cmd_desc = 'builtin:restart_frontend'
                                    if not dry_run:
                                        restart_frontend(f)
                                else:
                                    cmd_desc = f'builtin:unknown_port_{p}'
                            except Exception as e:
                                err = f"{now} builtin restart failed for port={p}: {e}"
                                print(err)
                                if f:
                                    f.write(err + '\n')
                                    f.flush()
                        else:
                            cmd = restart_cmd.format(port=p)
                            cmd_desc = cmd
                            print(f"{now} attempting restart for port={p} cmd={cmd}")
                            if f:
                                f.write(f"{now} attempting restart for port={p} cmd={cmd}\n")
                                f.flush()
                            if not dry_run:
                                try:
                                    subprocess.Popen(cmd, shell=True, stdout=(f or subprocess.DEVNULL), stderr=(f or subprocess.DEVNULL))
                                except Exception as e:
                                    err = f"{now} restart command failed for port={p}: {e}"
                                    print(err)
                                    if f:
                                        f.write(err + '\n')
                                        f.flush()
                        rec['count'] += 1
                        rec['last'] = now_ts
                        # notification on new down event (respect cooldown)
                        if hasattr(monitor, 'notify_methods') and monitor.notify_methods:
                            # only notify if last_notify older than cooldown_notify
                            last_n = rec.get('last_notify', 0)
                            if now_ts - last_n > getattr(monitor, 'cooldown_notify', 300):
                                msg = f"{now} ALERT: port={p} state=DOWN attempt={rec['count']}"
                                send_notification(msg, methods=monitor.notify_methods, webhook_url=getattr(monitor, 'webhook_url', None), logfile_handle=f)
                                rec['last_notify'] = now_ts
            # short sleep loop with responsive exit
            for _ in range(int(interval)):
                time.sleep(1)
    except KeyboardInterrupt:
        print('Monitor stopped')
    finally:
        if f:
            f.close()


def restart_frontend(logfile_handle=None):
    """Kill ALL existing frontend processes on port 5174 and start a fresh one.

    Writes logs to the provided logfile handle if present.
    """
    now = datetime.utcnow().isoformat() + 'Z'
    import subprocess

    # Kill ALL existing vite/node processes that might be serving port 5174
    try:
        # Find all processes that might be using port 5174
        ssout = subprocess.check_output("ss -ltnp | grep ':5174' || true", shell=True, text=True).strip()
        if ssout:
            # Extract PIDs from ss output
            import re
            pids = re.findall(r'pid=(\d+)', ssout)
            if pids:
                msg = f"{now} restart_frontend: killing existing processes on port 5174: {pids}"
                print(msg)
                if logfile_handle:
                    logfile_handle.write(msg + '\n')
                    logfile_handle.flush()
                for pid in pids:
                    try:
                        subprocess.run(["kill", "-9", pid], timeout=5)
                    except Exception:
                        pass
                time.sleep(2)  # Wait for processes to die

        # Also kill any remaining vite/npm processes
        out = subprocess.check_output("pgrep -f 'node .*vite\|npm.*dev' || true", shell=True, text=True).strip()
        pids = [int(x) for x in out.split()] if out else []
        if pids:
            msg = f"{now} restart_frontend: killing remaining vite/npm processes: {pids}"
            print(msg)
            if logfile_handle:
                logfile_handle.write(msg + '\n')
                logfile_handle.flush()
            for pid in pids:
                try:
                    subprocess.run(["kill", "-9", str(pid)], timeout=5)
                except Exception:
                    pass
            time.sleep(1)
    except Exception as e:
        msg = f"{now} restart_frontend: error killing existing processes: {e}"
        print(msg)
        if logfile_handle:
            logfile_handle.write(msg + '\n')
            logfile_handle.flush()

    # Start fresh frontend process
    try:
        cmd = "cd /home/markm/TravelLand/frontend && nohup npm run dev > /home/markm/TravelLand/frontend.log 2>&1 & echo $! > /home/markm/TravelLand/frontend.pid"
        subprocess.Popen(cmd, shell=True)
        msg = f"{now} restart_frontend: started fresh frontend process"
        print(msg)
        if logfile_handle:
            logfile_handle.write(msg + '\n')
            logfile_handle.flush()
    except Exception as e:
        err = f"{now} restart_frontend failed: {e}"
        print(err)
        if logfile_handle:
            logfile_handle.write(err + '\n')
            logfile_handle.flush()


def restart_backend(logfile_handle=None):
    """Restart the Python backend by killing existing app process and starting it via venv python -m city_guides.app.

    Writes logs to the provided logfile handle if present.
    """
    now = datetime.utcnow().isoformat() + 'Z'
    import subprocess
    # attempt to find PIDs running city_guides.app or hypercorn
    import subprocess
    # find existing backend processes
    try:
        out = subprocess.check_output("pgrep -f 'city_guides.app|hypercorn|python .*city_guides.app' || true", shell=True, text=True).strip()
        pids = [int(x) for x in out.split()] if out else []
    except Exception:
        pids = []

    if pids:
        # keep first, kill extras
        primary = pids[0]
        extras = pids[1:]
        if extras:
            msg = f"{now} restart_backend: killing extra PIDs: {extras}"
            print(msg)
            if logfile_handle:
                logfile_handle.write(msg + '\n')
                logfile_handle.flush()
            for pid in extras:
                try:
                    subprocess.run(["kill", str(pid)])
                except Exception:
                    pass
            time.sleep(1)
        # verify primary listens on 5010
        try:
            ssout = subprocess.check_output("ss -ltnp | grep ':5010' || true", shell=True, text=True).strip()
        except Exception:
            ssout = ''
        if ssout and str(primary) in ssout:
            msg = f"{now} restart_backend: primary PID {primary} already serving 5010; nothing to do"
            print(msg)
            if logfile_handle:
                logfile_handle.write(msg + '\n')
                logfile_handle.flush()
            return

    # start backend and write pid file
    try:
        cmd = "nohup /home/markm/TravelLand/city_guides/.venv/bin/python -m city_guides.app > /home/markm/TravelLand/app.log 2>&1 & echo $! > /home/markm/TravelLand/city_guides_backend.pid"
        subprocess.Popen(cmd, shell=True)
        msg = f"{now} restart_backend: started backend with cmd"
        print(msg)
        if logfile_handle:
            logfile_handle.write(msg + '\n')
            logfile_handle.flush()
    except Exception as e:
        err = f"{now} restart_backend failed: {e}"
        print(err)
        if logfile_handle:
            logfile_handle.write(err + '\n')
            logfile_handle.flush()


def send_notification(message: str, methods=None, webhook_url: str | None = None, logfile_handle=None):
    """Send notification via configured methods. Methods: 'log', 'desktop', 'webhook'.

    Desktop notifications use `notify-send` if available. Webhook does a POST with JSON {text: message}.
    """
    if not methods:
        return
    # always write to logfile_handle if provided
    if logfile_handle:
        try:
            logfile_handle.write(message + '\n')
            logfile_handle.flush()
        except Exception:
            pass

    for m in methods:
        try:
            if m == 'log':
                # already written above
                continue
            if m == 'desktop':
                # use notify-send if present
                import shutil, subprocess
                if shutil.which('notify-send'):
                    subprocess.Popen(["notify-send", "Port Monitor", message])
            if m == 'webhook' and webhook_url:
                try:
                    import json, urllib.request
                    req = urllib.request.Request(webhook_url, data=json.dumps({'text': message}).encode('utf-8'), headers={'Content-Type': 'application/json'})
                    urllib.request.urlopen(req, timeout=5)
                except Exception:
                    pass
        except Exception:
            # ignore notification errors
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ports', nargs='+', type=int, default=[5174], help='Ports to check')
    parser.add_argument('--interval', type=int, default=5, help='Polling interval seconds')
    parser.add_argument('--log', type=str, default='/home/markm/TravelLand/port_monitor.log', help='Log file path')
    parser.add_argument('--restart-cmd', type=str, default=None, help='Shell command to run when a port is down. Use {port} as placeholder')
    parser.add_argument('--use-builtins', action='store_true', help='Use built-in restart handlers for known services (frontend/backend)')
    parser.add_argument('--notify-methods', type=str, default=None, help='Comma-separated notification methods: log,desktop,webhook')
    parser.add_argument('--webhook-url', type=str, default=None, help='Webhook URL to POST notifications to (if using webhook method)')
    parser.add_argument('--cooldown-notify', type=int, default=300, help='Cooldown seconds between notifications for the same port')
    parser.add_argument('--max-restarts', type=int, default=3, help='Maximum restarts per port')
    parser.add_argument('--cooldown', type=int, default=60, help='Cooldown between restart attempts (seconds)')
    parser.add_argument('--dry-run', action='store_true', help='Log restart attempts but do not execute commands')
    args = parser.parse_args()
    print('Starting port monitor for ports', args.ports, 'interval', args.interval)
    # attach use_builtins flag to monitor function for access inside
    monitor.use_builtins = args.use_builtins
    # parse notify methods
    if args.notify_methods:
        methods = [m.strip().lower() for m in args.notify_methods.split(',') if m.strip()]
    else:
        methods = []
    monitor.notify_methods = methods
    monitor.webhook_url = args.webhook_url
    monitor.cooldown_notify = args.cooldown_notify
    monitor(args.ports, args.interval, logfile=args.log, restart_cmd=args.restart_cmd, max_restarts=args.max_restarts, cooldown=args.cooldown, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
