"""Mac manager (AI Manager): system stats, apps, Homebrew, storage and duplicate clean-up.

Imported by server.py; routes are served under /api/mgr/ (see route_get / route_post).
Deletes go to the Trash through Finder. File access is limited to the home folder.
"""
from collections import deque
import hashlib, json, os, plistlib, re, shlex, shutil, signal, stat, subprocess, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs

HOME = Path.home()
APP_DIRS = [Path("/Applications"), HOME / "Applications"]
_cache = {"apps": None}


def run(cmd, timeout=20):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def memory():
    total = int(run(["sysctl", "-n", "hw.memsize"]).strip() or 0)
    out = run(["vm_stat"])
    page = int(re.search(r"page size of (\d+)", out).group(1)) if out else 16384
    pages = {k.strip(): int(v.strip(" .")) for k, v in
             (l.split(":") for l in out.splitlines() if ":" in l and "Mach" not in l)}
    g = lambda k: pages.get(k, 0) * page
    free, inactive, spec = g("Pages free"), g("Pages inactive"), g("Pages speculative")
    wired, comp, active = g("Pages wired down"), g("Pages occupied by compressor"), g("Pages active")
    swap = run(["sysctl", "-n", "vm.swapusage"]).strip()
    return {"total": total, "free": free + spec, "inactive": inactive, "active": active,
            "wired": wired, "compressed": comp,
            "used": max(total - free - inactive - spec, 0), "swap": swap}


def processes():
    out = run(["ps", "-axo", "pid=,rss=,pcpu=,user=,comm="]).splitlines()
    rows = []
    for l in out:
        p = l.split(None, 4)
        if len(p) == 5:
            rows.append({"pid": int(p[0]), "rss": int(p[1]) * 1024, "cpu": float(p[2]),
                         "user": p[3], "name": os.path.basename(p[4]), "path": p[4]})
    rows.sort(key=lambda r: r["rss"], reverse=True)
    return rows[:25]


def system():
    d = shutil.disk_usage("/")
    return {"memory": memory(), "disk": {"total": d.total, "used": d.used, "free": d.free},
            "load": os.getloadavg(), "cpus": os.cpu_count(), "procs": processes(),
            "me": os.environ.get("USER", "")}


HIST = deque(maxlen=360)  # one reading per 5 s, about 30 minutes


def sampler():
    while True:
        try:
            mem = memory()
            sw = re.search(r"total = ([\d.]+)M\s+used = ([\d.]+)M", mem["swap"])
            HIST.append({"t": int(time.time()), "mem": mem["used"] / mem["total"],
                         "swap": float(sw.group(2)) / float(sw.group(1)) if sw and float(sw.group(1)) else 0,
                         "cpu": min(os.getloadavg()[0] / (os.cpu_count() or 1), 1)})
        except Exception:
            pass
        time.sleep(5)


def app_info(path):
    info = {"path": str(path), "name": path.stem, "version": "", "bundle": "", "size": 0, "lastUsed": ""}
    try:
        with open(path / "Contents" / "Info.plist", "rb") as f:
            pl = plistlib.load(f)
        info["version"] = str(pl.get("CFBundleShortVersionString", ""))
        info["bundle"] = pl.get("CFBundleIdentifier", "")
    except Exception:
        pass
    kb = run(["du", "-sk", str(path)], 60).split()
    info["size"] = int(kb[0]) * 1024 if kb and kb[0].isdigit() else 0
    lu = run(["mdls", "-raw", "-name", "kMDItemLastUsedDate", str(path)]).strip()
    info["lastUsed"] = "" if lu.startswith("(null)") else lu[:10]
    info["appStore"] = (path / "Contents" / "_MASReceipt").exists()
    return info


def apps(refresh=False):
    if _cache["apps"] is None or refresh:
        paths = [p for d in APP_DIRS if d.is_dir() for p in sorted(d.glob("*.app"))]
        with ThreadPoolExecutor(8) as ex:
            _cache["apps"] = list(ex.map(app_info, paths))
        _cache["apps"].sort(key=lambda a: a["size"], reverse=True)
    return _cache["apps"]


def brew_bin():
    return shutil.which("brew") or next((p for p in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew") if os.path.exists(p)), None)


_brew_cache = {"t": 0, "v": None}


def brew():
    if _brew_cache["v"] and time.time() - _brew_cache["t"] < 300:
        return _brew_cache["v"]
    b = brew_bin()
    if not b:
        return {"installed": False, "items": [], "outdated": []}
    items = []
    for l in run([b, "list", "--versions"], 60).splitlines():
        p = l.split()
        if p:
            items.append({"name": p[0], "version": " ".join(p[1:]), "kind": "formula"})
    for l in run([b, "list", "--cask", "--versions"], 60).splitlines():
        p = l.split()
        if p:
            items.append({"name": p[0], "version": " ".join(p[1:]), "kind": "cask"})
    _brew_cache.update(t=time.time(), v={"installed": True, "items": items, "outdated": []})
    return _brew_cache["v"]


_outdated = {"t": 0, "v": []}


def brew_outdated():
    """`brew outdated` talks to the network and is slow, so it is fetched after the list is shown."""
    b = brew_bin()
    if b and time.time() - _outdated["t"] > 300:
        _outdated.update(t=time.time(), v=run([b, "outdated", "--quiet"], 90).split())
    return {"outdated": _outdated["v"]}


def trash_app(path):
    p = Path(path).resolve()
    if not p.exists():
        return False, "That app no longer exists."
    if p.suffix != ".app" or p.parent not in [d.resolve() for d in APP_DIRS if d.exists()]:
        return False, "Only .app bundles directly in /Applications or ~/Applications are allowed."
    if p.name in ("Safari.app", "Finder.app"):
        return False, "Protected system app."
    stopped = stop_app_processes(p)
    script = f'tell application "Finder" to delete POSIX file "{p}"'
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=60)
    if r.returncode:
        return False, r.stderr.strip() or "Finder refused."
    _cache["apps"] = None
    msg = f"Moved {p.name} to the Trash. Restore it from the Trash if you change your mind."
    if stopped:
        msg += f" Stopped {stopped} running process(es) first."
    helpers = leftover_helpers(p)
    if helpers:
        msg += (" Still running: " + ", ".join(helpers) + ". The app may have its own uninstaller window "
                "(check for it), or a root helper that needs your admin password to remove.")
    return True, msg


def stop_app_processes(app):
    """Quit the user's processes running from inside the app bundle, repeating because
    apps with login agents tend to respawn."""
    me, total = os.environ.get("USER", ""), 0
    for _ in range(3):
        out = run(["ps", "-axo", "pid=,user=,command="]).splitlines()
        pids = [int(l.split(None, 2)[0]) for l in out
                if len(l.split(None, 2)) == 3 and l.split(None, 2)[1] == me and str(app) + "/" in l.split(None, 2)[2]]
        if not pids:
            break
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
                total += 1
            except OSError:
                pass
        time.sleep(1.5)
    return total


def leftover_helpers(app):
    """Processes from the app's vendor that survive removal (e.g. root helpers)."""
    try:
        with open(app / "Contents" / "Info.plist", "rb") as f:
            bundle = plistlib.load(f).get("CFBundleIdentifier", "")
    except Exception:
        return []
    vendor = ".".join(bundle.split(".")[:2]).lower()
    if vendor.count(".") != 1 or vendor in ("com.apple", "com.microsoft", "com.google"):
        return []
    time.sleep(1)
    return sorted({l.split(None, 1)[1].split("/")[-1].split(" ")[0] for l in run(["ps", "-axo", "pid=,command="]).splitlines()
                   if vendor in l.lower() and "manager.py" not in l and "ps -axo" not in l and len(l.split(None, 1)) == 2})


PROTECTED = {"Desktop", "Documents", "Downloads", "Library", "Pictures", "Music", "Movies", "Applications", "Public", ".Trash"}


def safe_path(raw, allow_root=False):
    """Resolve a path and require it to live inside the home folder."""
    p = Path(raw).expanduser().resolve()
    if p != HOME and HOME not in p.parents:
        raise ValueError("Only files inside your home folder can be managed here.")
    if p == HOME and not allow_root:
        raise ValueError("Your home folder itself is protected.")
    return p


_sizes = {}  # path -> (time, bytes); folder sizes are slow, so they are cached and fetched one at a time


def dir_size(p, ttl=600):
    hit = _sizes.get(str(p))
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    kb = run(["du", "-sk", str(p)], 120).split()
    size = int(kb[0]) * 1024 if kb and kb[0].isdigit() else None
    if size is not None:
        _sizes[str(p)] = (time.time(), size)
    return size


def folder_size(raw):
    p = safe_path(raw)
    if not p.is_dir():
        raise ValueError("Not a folder.")
    return {"path": str(p), "size": dir_size(p)}


def list_dir(raw):
    p = safe_path(raw or str(HOME), allow_root=True)
    if not p.is_dir():
        raise ValueError("Not a folder.")
    rows = []
    for e in sorted(p.iterdir(), key=lambda x: x.name.lower()):
        try:
            st = e.lstat()
        except OSError:
            continue
        rows.append({"name": e.name, "path": str(e), "dir": e.is_dir() and not e.is_symlink(),
                     "size": None if e.is_dir() and not e.is_symlink() else st.st_size, "mtime": int(st.st_mtime),
                     "protected": (p == HOME and e.name in PROTECTED)})
    for r in rows:                      # sizes for folders arrive later, one request each (see folder_size)
        if r["dir"]:
            hit = _sizes.get(r["path"])
            r["size"] = hit[1] if hit and time.time() - hit[0] < 600 else None
    return {"path": str(p), "parent": str(p.parent) if p != HOME else None, "home": str(HOME), "entries": rows}


def large_files(min_mb):
    min_mb = max(int(min_mb), 1)
    out = run(["find", str(HOME), "-type", "f", "-size", f"+{min_mb}M", "-not", "-path", str(HOME / "Library") + "/*",
               "-not", "-path", "*/.Trash/*", "-print0"], 150)
    rows = []
    for f in out.split("\0"):
        if not f:
            continue
        try:
            st = os.lstat(f)
            rows.append({"name": os.path.basename(f), "path": f, "dir": False, "size": st.st_size,
                         "mtime": int(st.st_mtime), "protected": False})
        except OSError:
            pass
    rows.sort(key=lambda r: r["size"], reverse=True)
    return {"path": f"Files over {min_mb} MB (excluding Library)", "parent": None, "home": str(HOME), "entries": rows[:300]}


def trash_paths(paths):
    done, failed = 0, []
    for raw in paths[:200]:
        try:
            p = safe_path(raw)
            if p.parent == HOME and p.name in PROTECTED:
                raise ValueError(f"{p.name} is a protected folder.")
            finder_trash(p)
            done += 1
        except Exception as e:
            failed.append(f"{os.path.basename(raw)}: {e}")
    msg = f"Moved {done} item(s) to the Trash (restorable)."
    if failed:
        msg += " Failed: " + "; ".join(failed[:3])
    return done > 0 or not failed, msg


def trash_info():
    r = subprocess.run(["osascript", "-e", 'tell application "Finder" to count items of trash'],
                       capture_output=True, text=True, timeout=30)
    count = int(r.stdout.strip()) if r.stdout.strip().isdigit() else None
    kb = run(["du", "-sk", str(HOME / ".Trash")], 60).split()
    size = int(kb[0]) * 1024 if kb and kb[0].isdigit() else None
    return {"count": count, "size": size}


def empty_trash():
    before = trash_info()
    r = subprocess.run(["osascript", "-e", 'tell application "Finder" to empty trash'],
                       capture_output=True, text=True, timeout=300)
    if r.returncode:
        return False, r.stderr.strip() or "Finder refused."
    return True, f"Trash emptied ({before['count']} item(s) permanently deleted)."


def brew_uninstall(name, kind):
    b = brew_bin()
    if not b or not re.fullmatch(r"[A-Za-z0-9@._+\-/]+", name):
        return False, "Invalid package or Homebrew missing."
    cmd = [b, "uninstall"] + (["--cask"] if kind == "cask" else []) + [name]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    _brew_cache["v"] = None
    _outdated["t"] = 0
    return r.returncode == 0, (r.stdout + r.stderr).strip()[-600:]


def quit_proc(pid):
    me = os.environ.get("USER", "")
    row = next((p for p in processes() if p["pid"] == pid), None)
    if not row or row["user"] != me or pid <= 1:
        return False, "Can only quit your own processes from the top-25 list."
    os.kill(pid, signal.SIGTERM)
    return True, f"Asked {row['name']} (pid {pid}) to quit."


def finder_trash(p):
    r = subprocess.run(["osascript", "-e", "on run argv", "-e", "set f to POSIX file (item 1 of argv)",
                        "-e", 'tell application "Finder" to delete f', "-e", "end run", str(p)],
                       capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise ValueError(r.stderr.strip()[:120] or "Finder refused.")


def file_hash(p, limit=None):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        left = limit
        while True:
            chunk = f.read(1 << 20 if left is None else min(1 << 20, left))
            if not chunk:
                break
            h.update(chunk)
            if left is not None:
                left -= len(chunk)
                if left <= 0:
                    break
    return h.hexdigest()


_jobs = {}
SKIP_DIRS = {".Trash", "node_modules", ".git", "Library"}


def dupe_scan(job, root, min_bytes):
    try:
        by_size, seen = {}, 0
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.endswith((".app", ".photoslibrary", ".sparsebundle"))]
            for fn in fns:
                p = os.path.join(dp, fn)
                try:
                    st = os.lstat(p)
                except OSError:
                    continue
                if stat.S_ISREG(st.st_mode) and st.st_size >= min_bytes:
                    by_size.setdefault(st.st_size, []).append((p, st))
                seen += 1
            job["stage"], job["scanned"] = "Scanning files", seen
        cands = []
        for size, items in by_size.items():
            inodes = {}
            for p, st in items:
                inodes.setdefault((st.st_dev, st.st_ino), []).append((p, st))
            if len(inodes) > 1:
                cands.append((size, list(inodes.values())))
        total = sum(len(v) for _, v in cands) or 1
        done, groups = 0, []
        for size, inode_lists in cands:
            by_hash = {}
            for lst in inode_lists:
                p, st = lst[0]
                try:
                    key = (file_hash(p, 1 << 20), file_hash(p))
                except OSError:
                    continue
                by_hash.setdefault(key, []).append(lst)
                done += 1
                job["stage"], job["progress"] = "Comparing contents", round(done / total * 100)
            for key, lsts in by_hash.items():
                if len(lsts) > 1:
                    files = [{"path": l[0][0], "mtime": int(l[0][1].st_mtime),
                              "links": [x[0] for x in l[1:]]} for l in lsts]
                    files.sort(key=lambda f: (f["mtime"], len(f["path"])))
                    groups.append({"size": size, "files": files})
        groups.sort(key=lambda g: g["size"] * (len(g["files"]) - 1), reverse=True)
        job["result"] = {"groups": groups[:300], "truncated": len(groups) > 300,
                         "reclaimable": sum(g["size"] * (len(g["files"]) - 1) for g in groups)}
        job["stage"] = "done"
    except Exception as e:
        job["error"] = str(e)
        job["stage"] = "done"


def dupes_start(root, min_mb):
    p = safe_path(root or str(HOME), allow_root=True)
    if not p.is_dir():
        raise ValueError("Not a folder.")
    jid = uuid.uuid4().hex[:10]
    _jobs[jid] = {"stage": "Starting", "scanned": 0, "progress": 0}
    threading.Thread(target=dupe_scan, args=(_jobs[jid], str(p), int(float(min_mb) * 1e6)), daemon=True).start()
    return {"id": jid}


def trash_dupes(items):
    keeps = {it.get("keep") for it in items}
    done, saved, failed = 0, 0, []
    for it in items[:400]:
        name = os.path.basename(str(it.get("path")))
        try:
            p, k = safe_path(it["path"]), safe_path(it["keep"])
            if str(p) in keeps:
                raise ValueError("is also a file being kept")
            if not (p.is_file() and k.is_file()):
                raise ValueError("file is missing")
            sp, sk = p.stat(), k.stat()
            if (sp.st_dev, sp.st_ino) == (sk.st_dev, sk.st_ino):
                raise ValueError("same file (hard link); nothing to free")
            if sp.st_size != sk.st_size or file_hash(p) != file_hash(k):
                raise ValueError("no longer identical to the kept copy")
            finder_trash(p)
            done += 1
            saved += sp.st_size
        except Exception as e:
            failed.append(f"{name}: {e}")
    msg = f"Moved {done} duplicate(s) to the Trash ({saved / 1e6:.0f} MB, restorable). One copy of each was kept."
    if failed:
        msg += " Skipped: " + "; ".join(failed[:3])
    return done > 0 or not failed, msg


def reveal(path):
    p = safe_path(path)
    subprocess.run(["open", "-R", str(p)], timeout=20)
    return True, "Opened in Finder."


def _plist(cmd):
    try:
        return plistlib.loads(subprocess.run(cmd, capture_output=True, timeout=8).stdout)
    except Exception:
        return {}


def drives():
    """Every mounted volume under /Volumes (the boot disk is flagged internal) with size and free space."""
    out = []
    try:
        names = sorted(os.listdir("/Volumes"))
    except OSError:
        return out
    for n in names:
        mp = "/Volumes/" + n
        d = _plist(["diskutil", "info", "-plist", mp])
        if not d:
            continue
        try:
            u = shutil.disk_usage(mp)
        except OSError:
            continue
        internal = bool(d.get("Internal"))
        out.append({"name": d.get("VolumeName") or n, "mount": mp, "device": d.get("DeviceIdentifier"),
                    "fs": d.get("FilesystemName") or d.get("FilesystemType"), "total": u.total, "free": u.free,
                    "internal": internal, "external": not internal, "protocol": d.get("BusProtocol"),
                    "model": d.get("MediaName"), "ejectable": bool(d.get("Ejectable")),
                    "writable": os.access(mp, os.W_OK), "ssd": d.get("SolidState")})
    return out


def _sp(dtype):
    try:
        raw = subprocess.run(["system_profiler", dtype, "-json"], capture_output=True, text=True, timeout=15).stdout
        return json.loads(raw).get(dtype, [])
    except Exception:
        return []


_wifi_state = {"v": {}, "t": 0, "busy": False}


def _wifi_refresh():
    """system_profiler needs ~13 s for Wi-Fi details, so it runs in the background and is cached for a minute."""
    if _wifi_state["busy"] or time.time() - _wifi_state["t"] < 60:
        return
    _wifi_state["busy"] = True

    def work():
        try:
            wifi = {}
            for sec in _sp("SPAirPortDataType"):
                for i in sec.get("spairport_airport_interfaces", []):
                    c = i.get("spairport_current_network_information")
                    if c and c.get("spairport_network_channel"):
                        sn = (c.get("spairport_signal_noise") or "").split("/")
                        wifi = {"device": i.get("_name"), "channel": c.get("spairport_network_channel"),
                                "mode": c.get("spairport_network_phymode"), "rate": c.get("spairport_network_rate"),
                                "signal": sn[0].strip(), "security": (c.get("spairport_security_mode") or "").replace("spairport_security_mode_", "")}
            _wifi_state.update(v=wifi, t=time.time())
        finally:
            _wifi_state["busy"] = False
    threading.Thread(target=work, daemon=True).start()


def network():
    ports, cur = [], {}
    for line in run(["networksetup", "-listallhardwareports"]).splitlines():
        if line.startswith("Hardware Port:"):
            cur = {"port": line.split(":", 1)[1].strip()}
        elif line.startswith("Device:") and cur:
            cur["device"] = line.split(":", 1)[1].strip()
            ports.append(cur)
    for p in ports:
        p["ip"] = run(["ipconfig", "getifaddr", p["device"]]).strip() or None
    route = run(["route", "-n", "get", "default"])
    gw = re.search(r"gateway: (\S+)", route)
    iface = re.search(r"interface: (\S+)", route)
    dns = []
    for l in run(["scutil", "--dns"]).splitlines():
        m = re.search(r"nameserver\[\d+\] : (\S+)", l)
        if m and m.group(1) not in dns:
            dns.append(m.group(1))
    ping = run(["ping", "-c", "1", "-t", "2", "1.1.1.1"], timeout=4)
    ms = re.search(r"time=([\d.]+) ms", ping)
    wifi = _wifi_state["v"]
    _wifi_refresh()
    return {"ports": [p for p in ports if p["ip"] or p["port"] in ("Wi-Fi", "Ethernet")],
            "gateway": gw.group(1) if gw else None, "interface": iface.group(1) if iface else None,
            "dns": dns[:3], "online": bool(ms), "latency_ms": float(ms.group(1)) if ms else None, "wifi": wifi}


def bluetooth():
    on, devs = None, []
    for sec in _sp("SPBluetoothDataType"):
        on = (sec.get("controller_properties", {}).get("controller_state") == "attrib_on")
        for group in sec.get("device_connected", []):
            for name, info in group.items():
                devs.append({"name": name, "type": info.get("device_minorType"), "address": info.get("device_address"),
                             "battery": info.get("device_batteryLevelMain")})
    return {"on": on, "connected": devs}


def usb():
    found = []
    def walk(items):
        for it in items:
            if "_items" in it:
                walk(it["_items"])
            if "vendor_id" in it or "product_id" in it:
                found.append({"name": it.get("_name"), "vendor": it.get("manufacturer"), "speed": it.get("device_speed")})
    walk(_sp("SPUSBDataType"))
    return found


_dev_cache = {"t": 0, "v": None}


def devices():
    """Drives, network, Bluetooth and USB for the Devices tab (cached for a few seconds)."""
    if _dev_cache["v"] and time.time() - _dev_cache["t"] < 4:
        return _dev_cache["v"]
    with ThreadPoolExecutor(4) as ex:
        f = {k: ex.submit(fn) for k, fn in (("drives", drives), ("network", network), ("bluetooth", bluetooth), ("usb", usb))}
        v = {k: x.result() for k, x in f.items()}
    _dev_cache.update(t=time.time(), v=v)
    return v


def eject(mount):
    if not mount.startswith("/Volumes/") or ".." in mount:
        return {"ok": False, "message": "Not an external volume."}
    d = _plist(["diskutil", "info", "-plist", mount])
    if d.get("Internal"):
        return {"ok": False, "message": "That is an internal disk."}
    r = subprocess.run(["diskutil", "eject", mount], capture_output=True, text=True, timeout=30)
    _dev_cache["v"] = None
    return {"ok": r.returncode == 0, "message": (r.stdout or r.stderr).strip()[:200]}


def live():
    """Small, cheap payload for the always-on panel on the main screen."""
    m = memory()
    d = shutil.disk_usage("/")
    return {"hist": list(HIST)[-120:], "mem": {"used": m["used"], "total": m["total"]},
            "disk": {"free": d.free, "total": d.total}, "cpus": os.cpu_count()}


def start_background():
    """Warm the app cache and begin the memory history sampler."""
    threading.Thread(target=apps, daemon=True).start()
    threading.Thread(target=_wifi_refresh, daemon=True).start()
    threading.Thread(target=sampler, daemon=True).start()


def route_get(path, query):
    q = parse_qs(query)
    one = lambda k, d="": q.get(k, [d])[0]
    try:
        if path == "/api/mgr/info": return 200, {"home": str(HOME)}
        if path == "/api/mgr/system": return 200, system()
        if path == "/api/mgr/history": return 200, list(HIST)
        if path == "/api/mgr/apps": return 200, apps(bool(one("refresh")))
        if path == "/api/mgr/brew": return 200, brew()
        if path == "/api/mgr/brew-outdated": return 200, brew_outdated()
        if path == "/api/mgr/live": return 200, live()
        if path == "/api/mgr/devices": return 200, devices()
        if path == "/api/mgr/dirsize": return 200, folder_size(one("path"))
        if path == "/api/mgr/trash-info": return 200, trash_info()
        if path == "/api/mgr/dupes-status":
            job = _jobs.get(one("id"))
            return (200, job) if job else (404, {"error": "unknown job"})
        if path == "/api/mgr/dir":
            return 200, (large_files(one("large")) if one("large") else list_dir(one("path")))
    except Exception as e:
        return 400, {"error": str(e)}
    return 404, {"error": "not found"}


def route_post(path, body):
    try:
        if path == "/api/mgr/dupes-start": return 200, dupes_start(body.get("path", ""), body.get("min_mb", 1))
        actions = {"/api/mgr/trash": lambda: trash_app(body.get("path", "")),
                   "/api/mgr/brew-uninstall": lambda: brew_uninstall(body.get("name", ""), body.get("kind", "")),
                   "/api/mgr/quit": lambda: quit_proc(int(body.get("pid", 0))),
                   "/api/mgr/empty-trash": empty_trash,
                   "/api/mgr/eject": lambda: eject(body.get("mount", "")),
                   "/api/mgr/trash-paths": lambda: trash_paths(body.get("paths", [])),
                   "/api/mgr/trash-dupes": lambda: trash_dupes(body.get("items", [])),
                   "/api/mgr/reveal": lambda: reveal(body.get("path", ""))}
        if path in actions:
            ok, msg = actions[path]()
            return 200, {"ok": ok, "message": msg}
    except Exception as e:
        return 200, {"ok": False, "message": str(e)}
    return 404, {"error": "not found"}


# --- helpers for spoken answers (spoken-style summaries; unused by AI Manager) ---

def spoken_memory():
    m = memory()
    g = lambda b: f"{b / 1e9:.1f}"
    return f"You are using {g(m['used'])} of {g(m['total'])} gigabytes of memory, with {g(m['compressed'])} compressed."


def spoken_disk():
    d = shutil.disk_usage("/")
    return f"You have {d.free / 1e9:.0f} gigabytes free out of {d.total / 1e9:.0f}."
