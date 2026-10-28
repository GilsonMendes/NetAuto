# NetAuto

API FastAPI que executa comandos `show` em roteadores via SSH (Netmiko) e exibe a saída em uma página HTML.

## Requisitos
- Python 3.10+
- Acesso SSH a um dispositivo de rede

## Instalação
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
# opcional: cp .env.example .env para sobrescrever os valores do laboratório
```

## Execução
```bash
cd src
python main.py
```
Acesse `http://localhost:8000/show-comands`.

## Endpoints
| Rota | Descrição |
|------|-----------|
| `GET /` | Health check |
| `GET /show-comands` | Executa `sh clock` e `sh ip int br` e renderiza o resultado |

## Laboratório de teste (PNETLab)

![Topologia do laboratório](docs/topologia.png)

Para reproduzir o laboratório, importe [docs/LAB-AUTOMATION-pnetlab.zip](docs/LAB-AUTOMATION-pnetlab.zip) no PNETLab (imagens: IOL L3 e vIOS-L2). O export contém apenas a topologia; o endereçamento das interfaces deve ser configurado nos equipamentos.

| Link | Rede |
|------|------|
| PE-1 (AS 300) ↔ P1 | `100.10.11.0/30` |
| P1 ↔ P2 | `10.10.12.0/30` |
| P1 ↔ P3 | `10.10.13.0/30` |
| P2 ↔ P4 | `10.10.24.0/30` |
| P3 ↔ P4 | `10.10.34.0/30` |
| P4 ↔ PE-2 (AS 500) | `200.10.24.0/30` |

### Rede de gerência (out-of-band)

Todos os roteadores possuem uma **VRF MGMT** com OSPF 100 (área 0), isolada do plano de dados. O P2 recebe a rede de gerência pela `e0/2` (DHCP, nuvem **MGMT AUTOMATION**) e propaga as Loopbacks de gerência aos demais pelas subinterfaces `.3999` (dot1Q 3999) das `e0/0` e `e0/1`.

A API acessa o P2 via SSH em `10.255.0.2` (Loopback100, VRF MGMT). Configuração de referência: [docs/configs/P2.cfg](docs/configs/P2.cfg). Usuário `cisco` (privilégio 15), SSH v2 e `login local` nas linhas VTY.

## Configuração
Os padrões (`10.255.0.2`, `cisco/cisco`) são de um laboratório. Para outro dispositivo, copie `.env.example` para `.env` e ajuste.
