import os
import posix
from shellescape import quote
import asyncio

MUSIC_PATH = "/var/jellyfin/media/music"
MXLRC_PATH = "/home/pauel/MxLRC"

DONE_FOLDERS_LIST = f"{MXLRC_PATH}/done.txt"

def make_command(music_folder: posix.DirEntry, token: str) -> str:
    return f'{MXLRC_PATH}/.venv/bin/python3 {quote(f"{MXLRC_PATH}/mxlrc.py")} -s {quote(music_folder.path)} --token {token} -t 60 -q'

class Token:
    def __init__(self, value: str):
        self.value:str = value

async def run_command(cur_folder: posix.DirEntry, queue: asyncio.Queue[Token]):
    token = await queue.get()

    command = make_command(cur_folder, token.value)

    while True:  # restart loop
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            restart = False
            async def monitor(stream, stream_name:str):
                nonlocal restart
                async for line in stream:
                    text = line.decode().rstrip()
                    print(f"[{stream_name}] {text}")

                    if text.startswith("[o] Timed out."):
                        restart = True
                        process.kill()
                        break

            await asyncio.gather(
                monitor(process.stdout, f"...{token.value[-4:]}-stdout"),
                monitor(process.stderr, f"...{token.value[-4:]}-stderr"),
            )

            await process.wait()

            if restart:
                print("Timeout detected, restarting in 10 minutes...")
                await asyncio.sleep(600)
                continue  # restart loop

            break  # normal exit → done

        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
            queue.put_nowait(token)

    os.system(f"echo {quote(cur_folder.path)} >> {DONE_FOLDERS_LIST}")


async def main(tokens: list[Token]):

    tasks: list[asyncio.Task] = []
    token_queue = asyncio.Queue()

    for t in tokens:
        token_queue.put_nowait(t)

    for folder in os.scandir(MUSIC_PATH):
        if not os.path.isdir(folder):
            continue
        task = asyncio.create_task(run_command(folder, token_queue))
        tasks.append(task)

    await asyncio.gather(*tasks)



if __name__ == "__main__":
    tokens_file = open("TOKENS", "r")
    text_tokens = tokens_file.readlines()
    tokens_file.close()
    tokens: list[Token | None] = [None]*len(text_tokens)
    for i, t in enumerate(text_tokens):
        tokens[i] = Token(t.strip())

    asyncio.run(main(tokens))





