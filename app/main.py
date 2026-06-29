from pms_client import PMSClient

pms = PMSClient()

print(pms.login())

pms.close()