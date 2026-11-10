"""Relatório Day 2 (somente leitura) do Catalyst SD-WAN.

Uso:
    python sdwan_report.py                         # coleta no Manager e gera HTML
    python sdwan_report.py --dump snapshot.json    # salva também os JSON brutos
    python sdwan_report.py --from-json ../docs/sdwan/exemplo-snapshot.json
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from sdwan.client import ManagerClient, ManagerError
from sdwan.collector import analyze, collect
from sdwan.render import render_html, render_terminal


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Relatório Day 2 do Catalyst SD-WAN (somente leitura)")
    parser.add_argument("--output", help="arquivo HTML (padrão: reports/sdwan-AAAAMMDD-HHMM.html)")
    parser.add_argument("--dump", help="salva o snapshot bruto (JSON) neste arquivo")
    parser.add_argument("--from-json", help="gera o relatório a partir de um snapshot salvo, sem acessar o Manager")
    args = parser.parse_args()

    if args.from_json:
        snapshot = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    else:
        client = ManagerClient(
            host=os.getenv("VMANAGE_HOST", "199.1.1.2"),
            port=int(os.getenv("VMANAGE_PORT", "443")),
            username=os.getenv("VMANAGE_USERNAME", "admin"),
            password=os.getenv("VMANAGE_PASSWORD", "admin"),
            verify_ssl=os.getenv("VMANAGE_VERIFY_SSL", "false").lower() == "true",
        )
        try:
            with client:
                snapshot = collect(client)
        except ManagerError as error:
            print(f"ERRO: {error}", file=sys.stderr)
            return 2

    if args.dump:
        Path(args.dump).write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")

    report = analyze(snapshot)
    print(render_terminal(report))

    output = Path(args.output or f"reports/sdwan-{datetime.now():%Y%m%d-%H%M}.html")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html(report), encoding="utf-8")
    print(f"\nHTML: {output.resolve()}")

    # código de saída útil para agendamento (cron) ou CI
    return {"OK": 0, "ATENÇÃO": 1, "FALHA": 2}[report["overall"]]


if __name__ == "__main__":
    sys.exit(main())
