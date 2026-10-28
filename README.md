# Pro_API

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

## Configuração
Os padrões (`10.255.0.2`, `cisco/cisco`) são de um laboratório. Para outro dispositivo, copie `.env.example` para `.env` e ajuste.
