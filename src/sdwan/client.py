"""Cliente mínimo e SOMENTE LEITURA da API REST do Catalyst SD-WAN Manager.

Faz apenas requisições GET em /dataservice. O único POST é o login
(/j_security_check), que não altera nada na rede.
"""

import requests
import urllib3


class ManagerError(Exception):
    """Falha de autenticação ou de consulta ao Manager."""


class ManagerClient:
    def __init__(self, host: str, username: str, password: str,
                 port: int = 443, verify_ssl: bool = False, timeout: int = 30):
        self.base = f"https://{host}:{port}"
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = verify_ssl
        if not verify_ssl:
            # Lab com certificado autoassinado no Manager
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # ---------- sessão ----------
    def login(self) -> None:
        try:
            resp = self.session.post(
                f"{self.base}/j_security_check",
                data={"j_username": self.username, "j_password": self.password},
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise ManagerError(f"Manager inacessível em {self.base}: {error}") from error

        # Login inválido: o Manager devolve 200 com a página HTML de login
        if resp.status_code != 200 or "<html" in resp.text.lower():
            raise ManagerError("Falha no login: verifique usuário e senha do Manager.")

        token = self.session.get(f"{self.base}/dataservice/client/token", timeout=self.timeout)
        if token.status_code == 200 and token.text:
            self.session.headers["X-XSRF-TOKEN"] = token.text

    def logout(self) -> None:
        try:
            self.session.get(f"{self.base}/logout", params={"nocache": "1"}, timeout=10)
        except requests.RequestException:
            pass
        finally:
            self.session.close()

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, *exc):
        self.logout()

    # ---------- consultas ----------
    def get(self, path: str, **params) -> list:
        """GET em /dataservice<path>; devolve sempre a lista 'data'."""
        url = f"{self.base}/dataservice{path}"
        try:
            resp = self.session.get(url, params=params or None, timeout=self.timeout)
        except requests.RequestException as error:
            raise ManagerError(f"Erro ao consultar {path}: {error}") from error
        if resp.status_code != 200:
            raise ManagerError(f"{path} retornou HTTP {resp.status_code}")
        body = resp.json()
        data = body.get("data", body) if isinstance(body, dict) else body
        return data if isinstance(data, list) else [data]

    def get_safe(self, path: str, **params) -> list:
        """Como get(), mas devolve [] em caso de erro (o relatório segue)."""
        try:
            return self.get(path, **params)
        except (ManagerError, ValueError):
            return []

    # Atalhos usados pelo relatório
    def devices(self):
        return self.get("/device")

    def edge_inventory(self):
        return self.get_safe("/system/device/vedges")

    def controller_inventory(self):
        return self.get_safe("/system/device/controllers")

    def control_connections(self, system_ip):
        return self.get_safe("/device/control/connections", deviceId=system_ip)

    def local_properties(self, system_ip):
        return self.get_safe("/device/control/localproperties", deviceId=system_ip)

    def bfd_sessions(self, system_ip):
        return self.get_safe("/device/bfd/sessions", deviceId=system_ip)

    def app_route_stats(self, system_ip):
        return self.get_safe("/device/app-route/statistics", deviceId=system_ip)

    def sla_classes(self, system_ip):
        return self.get_safe("/device/app-route/sla-class", deviceId=system_ip)
