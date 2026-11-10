"""Coleta (snapshot bruto) e análise do estado do SD-WAN.

A coleta grava os JSON exatamente como o Manager devolve. A análise
transforma esse snapshot no relatório. Separar as duas etapas permite
reprocessar um snapshot salvo (--from-json) sem tocar na rede.
"""

from datetime import datetime, timezone

CERT_WARN_DAYS = 30


# ===================== coleta =====================
def collect(client) -> dict:
    devices = client.devices()
    inventory = client.edge_inventory() + client.controller_inventory()

    per_device = {}
    for dev in devices:
        sip = dev.get("system-ip")
        if not sip or dev.get("reachability") != "reachable":
            continue
        entry = {
            "control": client.control_connections(sip),
            "local": client.local_properties(sip),
        }
        if dev.get("device-type") == "vedge":
            entry["bfd"] = client.bfd_sessions(sip)
            entry["approute"] = client.app_route_stats(sip)
            entry["sla_classes"] = client.sla_classes(sip)
        per_device[sip] = entry

    return {
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manager": client.base,
        "devices": devices,
        "inventory": inventory,
        "per_device": per_device,
    }


# ===================== análise =====================
TYPE_LABEL = {"vmanage": "Manager", "vsmart": "Controller",
              "vbond": "Validator", "vedge": "Edge"}
TYPE_ORDER = {"vmanage": 0, "vsmart": 1, "vbond": 2, "vedge": 3}


def _cert_days(local: dict):
    raw = local.get("certificate-not-valid-after")
    if not raw:
        return None, None
    try:
        expires = datetime.strptime(" ".join(raw.split()), "%b %d %H:%M:%S %Y %Z")
    except ValueError:
        return raw, None
    days = (expires.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).days
    return expires.strftime("%d/%m/%Y"), days


def _split_index(value) -> list:
    if value in (None, "", "None"):
        return []
    return [int(v) for v in str(value).replace(" ", "").split(",") if v.isdigit()]


def _tunnels(approute: list, sla_names: dict, custom: set) -> list:
    """Um registro por túnel (src->dst). A API pode repetir por intervalo."""
    seen, tunnels = set(), []
    for row in approute:
        key = (row.get("src-ip"), row.get("dst-ip"), row.get("local-color"), row.get("remote-color"))
        if key in seen:
            continue
        seen.add(key)
        indexes = _split_index(row.get("sla-class-index"))
        met = [sla_names.get(i, f"#{i}") for i in indexes if i in custom]
        missing = [sla_names[i] for i in sorted(custom) if i not in indexes]
        tunnels.append({
            "local_color": row.get("local-color", "-"),
            "remote_color": row.get("remote-color", "-"),
            "remote": row.get("remote-system-ip", row.get("dst-ip", "-")),
            "src": row.get("src-ip", "-"),
            "dst": row.get("dst-ip", "-"),
            "loss": row.get("mean-loss", "-"),
            "latency": row.get("mean-latency", "-"),
            "jitter": row.get("mean-jitter", "-"),
            "sla_met": met,
            "sla_missing": missing,
            "ok": not missing,
        })
    return tunnels


def analyze(snapshot: dict) -> dict:
    inventory = {i.get("system-ip"): i for i in snapshot.get("inventory", []) if i.get("system-ip")}
    rows = []

    for dev in sorted(snapshot["devices"],
                      key=lambda d: (TYPE_ORDER.get(d.get("device-type"), 9), d.get("host-name", ""))):
        sip = dev.get("system-ip", "-")
        dtype = dev.get("device-type", "")
        data = snapshot["per_device"].get(sip, {})
        inv = inventory.get(sip, {})
        local = (data.get("local") or [{}])[0]
        issues = []

        reachable = dev.get("reachability") == "reachable"
        if not reachable:
            issues.append("Dispositivo inalcançável pelo Manager")

        # sincronismo de configuração
        sync = inv.get("configStatusMessage") or "-"
        mode = inv.get("configOperationMode") or "-"
        if dtype == "vedge" and sync not in ("-", "In Sync"):
            issues.append(f"Configuração: {sync}")

        # conexões de controle
        control = [{
            "peer": TYPE_LABEL.get(c.get("peer-type"), c.get("peer-type", "-")),
            "peer_ip": c.get("system-ip", "-"),
            "color": c.get("local-color", "-"),
            "state": c.get("state", "-"),
            "uptime": c.get("uptime", "-"),
        } for c in data.get("control", [])]
        ctrl_up = sum(1 for c in control if c["state"] == "up")
        if reachable and control and ctrl_up < len(control):
            issues.append(f"Conexões de controle: {ctrl_up}/{len(control)} up")
        if dtype == "vedge" and reachable:
            peers = {c["peer"] for c in control if c["state"] == "up"}
            for needed in ("Controller", "Manager"):
                if needed not in peers:
                    issues.append(f"Sem conexão com o {needed}")

        # BFD
        bfd = [{
            "remote": b.get("system-ip", "-"),
            "site": b.get("site-id", "-"),
            "local_color": b.get("local-color", "-"),
            "remote_color": b.get("color", "-"),
            "state": b.get("state", "-"),
            "uptime": b.get("uptime", "-"),
            "transitions": b.get("transitions", "-"),
        } for b in data.get("bfd", [])]
        bfd_up = sum(1 for b in bfd if b["state"] == "up")
        if dtype == "vedge" and reachable and bfd_up < len(bfd):
            issues.append(f"BFD: {bfd_up}/{len(bfd)} sessões up")

        # SLA (App-Aware Routing)
        sla_list = data.get("sla_classes", [])
        sla_names = {int(s["index"]): s.get("name", f"#{s['index']}")
                     for s in sla_list if str(s.get("index", "")).isdigit()}
        custom = {i for i in sla_names if i != 0}
        tunnels = _tunnels(data.get("approute", []), sla_names, custom)
        out_of_sla = [t for t in tunnels if not t["ok"]]
        if out_of_sla:
            issues.append(f"{len(out_of_sla)} túnel(is) fora de SLA")

        # certificado
        cert_exp, cert_days = _cert_days(local)
        if cert_days is not None and cert_days < CERT_WARN_DAYS:
            issues.append(f"Certificado vence em {cert_days} dias")

        if not reachable:
            status = "FALHA"
        elif issues:
            status = "ATENÇÃO"
        else:
            status = "OK"

        rows.append({
            "hostname": dev.get("host-name", "-"),
            "type": TYPE_LABEL.get(dtype, dtype or "-"),
            "is_edge": dtype == "vedge",
            "system_ip": sip,
            "site": dev.get("site-id", "-"),
            "version": dev.get("version", "-"),
            "reachable": reachable,
            "sync": sync,
            "mode": mode,
            "control": control, "control_up": ctrl_up,
            "bfd": bfd, "bfd_up": bfd_up,
            "sla_classes": [{"index": s.get("index"), "name": s.get("name", "-"),
                             "loss": s.get("loss", "-"), "latency": s.get("latency", "-"),
                             "jitter": s.get("jitter", "-")}
                            for s in sla_list if str(s.get("index")) != "0"],
            "tunnels": tunnels,
            "cert_expires": cert_exp or "-",
            "cert_days": cert_days,
            "issues": issues,
            "status": status,
        })

    totals = {s: sum(1 for r in rows if r["status"] == s) for s in ("OK", "ATENÇÃO", "FALHA")}
    overall = "FALHA" if totals["FALHA"] else "ATENÇÃO" if totals["ATENÇÃO"] else "OK"
    collected = datetime.fromisoformat(snapshot["collected_at"])

    return {
        "manager": snapshot.get("manager", "-"),
        "collected_at": collected.astimezone().strftime("%d/%m/%Y %H:%M:%S"),
        "devices": rows,
        "totals": totals,
        "overall": overall,
        "edges": [r for r in rows if r["is_edge"]],
    }
