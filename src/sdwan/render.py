"""Saídas do relatório: resumo no terminal e página HTML autocontida."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def render_html(report: dict) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES),
                      autoescape=select_autoescape(["html"]))
    return env.get_template("sdwan_report.html").render(r=report)


def _table(headers, rows) -> str:
    widths = [max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows else len(str(h))
              for i, h in enumerate(headers)]
    line = "  ".join(f"{{:<{w}}}" for w in widths)
    out = [line.format(*headers), "  ".join("-" * w for w in widths)]
    out += [line.format(*[str(c) for c in r]) for r in rows]
    return "\n".join(out)


def render_terminal(report: dict) -> str:
    rows = [(d["status"], d["hostname"], d["type"], d["system_ip"], d["site"],
             f'{d["control_up"]}/{len(d["control"])}',
             f'{d["bfd_up"]}/{len(d["bfd"])}' if d["is_edge"] else "-",
             (f'{sum(t["ok"] for t in d["tunnels"])}/{len(d["tunnels"])}'
              if d["is_edge"] and d["tunnels"] else "-"),
             d["sync"])
            for d in report["devices"]]
    text = [
        f'Relatório SD-WAN Day 2  |  {report["manager"]}  |  {report["collected_at"]}',
        f'Estado geral: {report["overall"]}   '
        f'(OK {report["totals"]["OK"]} · ATENÇÃO {report["totals"]["ATENÇÃO"]} · '
        f'FALHA {report["totals"]["FALHA"]})',
        "",
        _table(("STATUS", "HOSTNAME", "TIPO", "SYSTEM-IP", "SITE",
                "CONTROLE", "BFD", "TÚNEIS NA SLA", "CONFIG"), rows),
    ]
    problems = [(d["hostname"], i) for d in report["devices"] for i in d["issues"]]
    if problems:
        text += ["", "Pontos de atenção:"] + [f"  - {h}: {i}" for h, i in problems]
    return "\n".join(text)
