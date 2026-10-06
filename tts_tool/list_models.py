"""Liệt kê các model Gemini mà API key của bạn dùng được:  python list_models.py"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from google import genai

client = genai.Client()
for m in client.models.list():
    if "generateContent" in (m.supported_actions or []):
        print(m.name.replace("models/", ""))
