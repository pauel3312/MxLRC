import os
import posix
from shellescape import quote
import asyncio

MUSIC_PATH = "/home/pauel/MxLRC/test_files/Colette Magny"
MXLRC_PATH = "/home/pauel/MxLRC"

DONE_FOLDERS_LIST = "/home/pauel/MxLRC/done.txt"

def make_command(music_folder: posix.DirEntry, token: str) -> str:
    return f'{MXLRC_PATH}/.venv/bin/python3 {quote(f"{MXLRC_PATH}/mxlrc.py")} -s {quote(music_folder.path)} --token {token} -t 60'

class Token:
    def __init__(self, value: str):
        self.value:str = value
        self.sem = asyncio.Semaphore(1)

async def run_command(cur_folder: posix.DirEntry, token: Token):
    await token.sem.acquire()

    command = make_command(cur_folder, token.value)

    while True:  # restart loop
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            restart = False
            async def monitor(stream):
                nonlocal restart
                async for line in stream:
                    text = line.decode().rstrip()
                    print(text)

                    if text.startswith("[o] Timed out."):
                        restart = True
                        process.kill()
                        break

            await asyncio.gather(
                monitor(process.stdout),
                monitor(process.stderr),
            )

            await process.wait()

            if restart:
                print("Timeout detected, restarting in 60 seconds...")
                await asyncio.sleep(60)
                continue  # restart loop

            break  # normal exit → done

        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
    os.system(f"echo {quote(cur_folder.path)}\n >> {DONE_FOLDERS_LIST}")
    token.sem.release()


async def main(tokens: list[Token]):
    async def token_selector():
        while True:
            for token in tokens:
                if not token.sem.locked():
                    return token
            await asyncio.sleep(1)

    tasks: list[asyncio.Task] = []

    for folder in os.scandir(MUSIC_PATH):
        if not os.path.isdir(folder):
            continue
        token = await token_selector()
        task = asyncio.create_task(run_command(folder, token))
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





