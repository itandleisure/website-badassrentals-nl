#!/usr/bin/env python3
"""
Lokale test-mailserver: vangt alle mail van PHP mail() op en slaat die op in dev-mail/*.eml.
Er wordt niets echt verstuurd.

    python tools/mailcatcher.py        # luistert op 127.0.0.1:2525

php.ini (lokaal): SMTP = 127.0.0.1, smtp_port = 2525
"""
import asyncio
from datetime import datetime
from email import message_from_bytes, policy
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "dev-mail"
HOST, PORT = "127.0.0.1", 2525


async def handle(reader, writer):
    try:
        await session(reader, writer)
    except (ConnectionResetError, BrokenPipeError):
        pass


async def session(reader, writer):
    async def send(line):
        writer.write((line + "\r\n").encode())
        await writer.drain()

    await send("220 mailcatcher ready")
    rcpt, data_mode, buf = [], False, []
    while True:
        line = await reader.readline()
        if not line:
            break
        if data_mode:
            if line in (b".\r\n", b".\n"):
                data_mode = False
                raw = b"".join(buf)
                OUT.mkdir(exist_ok=True)
                name = OUT / f"{datetime.now():%Y%m%d-%H%M%S-%f}.eml"
                name.write_bytes(raw)
                msg = message_from_bytes(raw, policy=policy.default)
                print(f"[mail] aan {', '.join(rcpt)} | {msg['subject']} -> {name.name}", flush=True)
                buf, rcpt = [], []
                await send("250 OK")
            else:
                buf.append(line[1:] if line.startswith(b"..") else line)
            continue
        cmd = line.decode(errors="replace").strip()
        upper = cmd.upper()
        if upper.startswith(("HELO", "EHLO")):
            await send("250 mailcatcher")
        elif upper.startswith("MAIL FROM"):
            await send("250 OK")
        elif upper.startswith("RCPT TO"):
            rcpt.append(cmd.split(":", 1)[1].strip(" <>"))
            await send("250 OK")
        elif upper == "DATA":
            data_mode = True
            await send("354 End data with <CR><LF>.<CR><LF>")
        elif upper == "QUIT":
            await send("221 Bye")
            break
        else:
            await send("250 OK")
    writer.close()


async def main():
    loop = asyncio.get_running_loop()
    # Poortcontroles die direct de verbinding verbreken niet als fout loggen
    loop.set_exception_handler(
        lambda lp, ctx: None if isinstance(ctx.get("exception"), ConnectionResetError)
        else lp.default_exception_handler(ctx))
    server = await asyncio.start_server(handle, HOST, PORT)
    print(f"Mailcatcher luistert op {HOST}:{PORT}, mails in {OUT}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
