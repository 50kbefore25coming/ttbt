"""Bước 3: chuyển văn bản thành giọng nói bằng edge-tts (miễn phí)."""
import asyncio
import edge_tts


async def _synth_one(text, voice, rate, pitch, retries=3):
    for attempt in range(retries):
        try:
            buf = bytearray()
            comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            async for part in comm.stream():
                if part["type"] == "audio":
                    buf.extend(part["data"])
            if buf:
                return bytes(buf)
        except Exception as e:
            print(f"    ! TTS lỗi ({e.__class__.__name__}), thử lại {attempt + 1}/{retries}")
            await asyncio.sleep(3 * (attempt + 1))
    raise RuntimeError("TTS thất bại sau nhiều lần thử")


async def _run(chunks, out_path, voice, rate, pitch):
    with open(out_path, "wb") as f:
        for i, c in enumerate(chunks, 1):
            print(f"    đọc đoạn {i}/{len(chunks)}...")
            f.write(await _synth_one(c, voice, rate, pitch))
            await asyncio.sleep(1)


def synthesize(chunks, out_path, voice="vi-VN-HoaiMyNeural", rate="+0%", pitch="+0Hz"):
    asyncio.run(_run(chunks, out_path, voice, rate, pitch))
