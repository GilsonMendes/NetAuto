from netmiko import (
    ConnectHandler, 
    NetmikoTimeoutException, 
    NetmikoAuthenticationException
    )

class Device:
    
    def send_show_command(self, device_dict: dict, commands: list) -> dict:
        result = {}
        try:
            with ConnectHandler(**device_dict) as ssh:
                ssh.enable()
                for command in commands:
                    output = ssh.send_command(command)
                    result[command] = output
            return result
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as error:
         return {"erro": f"Falha na conexão: {str(error)}"}