"""Send one plain-text alert through ERPX's own SMTP settings. Run inside the API container:

    docker exec -i -e ALERT_TO=... -e ALERT_SUBJECT=... -e ALERT_BODY=... erpx_api python - < alert_mail.py

Credentials stay in the container; the host never sees them. Exit code 0 only if the mail was accepted.
"""
import asyncio
import os
import sys

from packages.email.service import EmailService


async def main() -> bool:
    return await EmailService().send(os.environ["ALERT_TO"], os.environ["ALERT_SUBJECT"], os.environ["ALERT_BODY"])


sys.exit(0 if asyncio.run(main()) else 1)
