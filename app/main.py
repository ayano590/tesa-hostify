from pms_client import PMSClient

pms = PMSClient()

pms.login()
print(pms.test_session())

pms.close()