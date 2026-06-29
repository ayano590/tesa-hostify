from pms_client import PMSClient

pms = PMSClient()

pms.login()

data = pms.get_common_pins()

print(data)

pms.close()