import os
import posix
from shellescape import quote
import asyncio
import asyncio.streams

MUSIC_PATH = "/var/jellyfin/media/music"
MXLRC_PATH = "/home/pauel/MxLRC"

DONE_FOLDERS_LIST = f"{MXLRC_PATH}/done.txt"

def colour_text(text: str, colour: int) -> str:
    return f"\033[38;5;{colour}m{text}\033[0m"

def make_command(music_folder: posix.DirEntry, token: str) -> str:
    return f'{MXLRC_PATH}/.venv/bin/python3 {quote(f"{MXLRC_PATH}/mxlrc.py")} -s {quote(music_folder.path)} --token {token} -t 60 -q'

class Token:
    def __init__(self, value: str, color: int):
        self.value:str = value
        self.colour: int = color

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
            async def monitor(stream: asyncio.streams.StreamReader, stream_name:str):
                nonlocal restart
                async for line in stream:
                    text = line.decode().rstrip()
                    print(f"[{stream_name}] {text}")

                    if text.startswith("[o] Timed out."):
                        restart = True
                        process.kill()
                        break

            await asyncio.gather(
                monitor(process.stdout, colour_text(f"...{token.value[-4:]}-stdout", token.colour)),
                monitor(process.stderr, colour_text(f"...{token.value[-4:]}-stderr", token.colour)),
            )

            await process.wait()

            if restart:
                print(colour_text(f"[...{token.value[-4:]}-prcmgr] Timeout detected, restarting in 10 minutes...", token.colour))
                await asyncio.sleep(600)
                continue  # restart loop

            break  # normal exit → done

        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

    queue.put_nowait(token)
    print(f"[...{token.value[-4:]}-prcmgr] Finished processing {cur_folder.path}")
    os.system(f"echo {quote(cur_folder.path)} >> {DONE_FOLDERS_LIST}")


async def main(tokens: list[Token]):

    done_folders_file = open(DONE_FOLDERS_LIST, "r")
    done_folders = done_folders_file.readlines()
    for i, folder in enumerate(done_folders):
        done_folders[i] = folder.strip()

    tasks: list[asyncio.Task] = []
    token_queue = asyncio.Queue()

    for t in tokens:
        token_queue.put_nowait(t)

    for folder in os.scandir(MUSIC_PATH):
        if not os.path.isdir(folder) or folder.path in done_folders:
            continue
        task = asyncio.create_task(run_command(folder, token_queue))
        tasks.append(task)

    await asyncio.gather(*tasks)



if __name__ == "__main__":
    tokens_file = open("TOKENS", "r")
    text_tokens = tokens_file.readlines()
    tokens_file.close()
    list_tokens: list[Token | None] = [None] * len(text_tokens)
    colour_index = 0
    for (index, temp_token) in enumerate(text_tokens):
        list_tokens[index] = Token(temp_token.strip(), 9 + colour_index)
        colour_index = (colour_index + 1) % 6

    asyncio.run(main(list_tokens))





