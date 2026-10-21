"""Small "About & support" page for the DynaFrame plugin page.

Serves one page on loopback and registers it as the plugin's advanced
settings page. Name, version and description come from manifest.json.
"""
import html
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_FOOTER = '  <footer class="support">\n    <p class="support-text"><span>Problems, questions or feature requests?</span> <a id="issueLink" href="https://github.com/Archonw/Jans-DynaframePro-Store/issues/new?title=__ISSUE__" target="_blank" rel="noopener">Open an issue on GitHub</a><span> with the plugin name and version.</span></p>\n    <div class="support-row">\n      <a class="bmc" href="https://www.buymeacoffee.com/Archonw" target="_blank" rel="noopener"><svg class="bmc-cup" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14l-1.6 13.2a1 1 0 0 1-1 .8H7.6a1 1 0 0 1-1-.8z" fill="#fff" stroke="#000" stroke-width="1.6" stroke-linejoin="round"/><rect x="3.5" y="4" width="17" height="3.4" rx="1" fill="#000"/><path d="M6.4 11h11.2" stroke="#FFDD00" stroke-width="3"/></svg><span>Buy me a coffee</span></a>\n      <a class="qr-link" href="https://www.buymeacoffee.com/Archonw" target="_blank" rel="noopener"><svg class="qr" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 41 41" role="img" aria-label="QR code: buymeacoffee.com/Archonw" shape-rendering="crispEdges"><rect width="41" height="41" rx="2" fill="#fff"/><path d="M2 2h1v1h-1zM3 2h1v1h-1zM4 2h1v1h-1zM5 2h1v1h-1zM6 2h1v1h-1zM7 2h1v1h-1zM8 2h1v1h-1zM13 2h1v1h-1zM14 2h1v1h-1zM15 2h1v1h-1zM16 2h1v1h-1zM18 2h1v1h-1zM20 2h1v1h-1zM25 2h1v1h-1zM28 2h1v1h-1zM29 2h1v1h-1zM30 2h1v1h-1zM32 2h1v1h-1zM33 2h1v1h-1zM34 2h1v1h-1zM35 2h1v1h-1zM36 2h1v1h-1zM37 2h1v1h-1zM38 2h1v1h-1zM2 3h1v1h-1zM8 3h1v1h-1zM10 3h1v1h-1zM14 3h1v1h-1zM15 3h1v1h-1zM17 3h1v1h-1zM18 3h1v1h-1zM19 3h1v1h-1zM21 3h1v1h-1zM22 3h1v1h-1zM24 3h1v1h-1zM25 3h1v1h-1zM30 3h1v1h-1zM32 3h1v1h-1zM38 3h1v1h-1zM2 4h1v1h-1zM4 4h1v1h-1zM5 4h1v1h-1zM6 4h1v1h-1zM8 4h1v1h-1zM12 4h1v1h-1zM14 4h1v1h-1zM15 4h1v1h-1zM19 4h1v1h-1zM21 4h1v1h-1zM22 4h1v1h-1zM23 4h1v1h-1zM25 4h1v1h-1zM28 4h1v1h-1zM29 4h1v1h-1zM30 4h1v1h-1zM32 4h1v1h-1zM34 4h1v1h-1zM35 4h1v1h-1zM36 4h1v1h-1zM38 4h1v1h-1zM2 5h1v1h-1zM4 5h1v1h-1zM5 5h1v1h-1zM6 5h1v1h-1zM8 5h1v1h-1zM11 5h1v1h-1zM15 5h1v1h-1zM16 5h1v1h-1zM17 5h1v1h-1zM19 5h1v1h-1zM20 5h1v1h-1zM21 5h1v1h-1zM28 5h1v1h-1zM29 5h1v1h-1zM30 5h1v1h-1zM32 5h1v1h-1zM34 5h1v1h-1zM35 5h1v1h-1zM36 5h1v1h-1zM38 5h1v1h-1zM2 6h1v1h-1zM4 6h1v1h-1zM5 6h1v1h-1zM6 6h1v1h-1zM8 6h1v1h-1zM12 6h1v1h-1zM17 6h1v1h-1zM28 6h1v1h-1zM29 6h1v1h-1zM32 6h1v1h-1zM34 6h1v1h-1zM35 6h1v1h-1zM36 6h1v1h-1zM38 6h1v1h-1zM2 7h1v1h-1zM8 7h1v1h-1zM10 7h1v1h-1zM11 7h1v1h-1zM13 7h1v1h-1zM14 7h1v1h-1zM15 7h1v1h-1zM17 7h1v1h-1zM18 7h1v1h-1zM20 7h1v1h-1zM21 7h1v1h-1zM22 7h1v1h-1zM24 7h1v1h-1zM25 7h1v1h-1zM30 7h1v1h-1zM32 7h1v1h-1zM38 7h1v1h-1zM2 8h1v1h-1zM3 8h1v1h-1zM4 8h1v1h-1zM5 8h1v1h-1zM6 8h1v1h-1zM7 8h1v1h-1zM8 8h1v1h-1zM10 8h1v1h-1zM12 8h1v1h-1zM14 8h1v1h-1zM16 8h1v1h-1zM18 8h1v1h-1zM20 8h1v1h-1zM22 8h1v1h-1zM24 8h1v1h-1zM26 8h1v1h-1zM28 8h1v1h-1zM30 8h1v1h-1zM32 8h1v1h-1zM33 8h1v1h-1zM34 8h1v1h-1zM35 8h1v1h-1zM36 8h1v1h-1zM37 8h1v1h-1zM38 8h1v1h-1zM10 9h1v1h-1zM11 9h1v1h-1zM12 9h1v1h-1zM14 9h1v1h-1zM15 9h1v1h-1zM16 9h1v1h-1zM18 9h1v1h-1zM19 9h1v1h-1zM20 9h1v1h-1zM21 9h1v1h-1zM26 9h1v1h-1zM27 9h1v1h-1zM6 10h1v1h-1zM7 10h1v1h-1zM8 10h1v1h-1zM9 10h1v1h-1zM11 10h1v1h-1zM14 10h1v1h-1zM19 10h1v1h-1zM23 10h1v1h-1zM26 10h1v1h-1zM27 10h1v1h-1zM29 10h1v1h-1zM30 10h1v1h-1zM32 10h1v1h-1zM33 10h1v1h-1zM37 10h1v1h-1zM2 11h1v1h-1zM5 11h1v1h-1zM7 11h1v1h-1zM10 11h1v1h-1zM12 11h1v1h-1zM13 11h1v1h-1zM14 11h1v1h-1zM16 11h1v1h-1zM19 11h1v1h-1zM21 11h1v1h-1zM22 11h1v1h-1zM25 11h1v1h-1zM28 11h1v1h-1zM32 11h1v1h-1zM35 11h1v1h-1zM36 11h1v1h-1zM3 12h1v1h-1zM4 12h1v1h-1zM8 12h1v1h-1zM9 12h1v1h-1zM11 12h1v1h-1zM12 12h1v1h-1zM14 12h1v1h-1zM15 12h1v1h-1zM16 12h1v1h-1zM20 12h1v1h-1zM21 12h1v1h-1zM23 12h1v1h-1zM24 12h1v1h-1zM27 12h1v1h-1zM28 12h1v1h-1zM29 12h1v1h-1zM31 12h1v1h-1zM34 12h1v1h-1zM3 13h1v1h-1zM5 13h1v1h-1zM7 13h1v1h-1zM9 13h1v1h-1zM11 13h1v1h-1zM12 13h1v1h-1zM13 13h1v1h-1zM15 13h1v1h-1zM17 13h1v1h-1zM19 13h1v1h-1zM20 13h1v1h-1zM21 13h1v1h-1zM22 13h1v1h-1zM25 13h1v1h-1zM26 13h1v1h-1zM28 13h1v1h-1zM29 13h1v1h-1zM30 13h1v1h-1zM31 13h1v1h-1zM33 13h1v1h-1zM34 13h1v1h-1zM36 13h1v1h-1zM37 13h1v1h-1zM38 13h1v1h-1zM2 14h1v1h-1zM5 14h1v1h-1zM6 14h1v1h-1zM8 14h1v1h-1zM9 14h1v1h-1zM10 14h1v1h-1zM11 14h1v1h-1zM12 14h1v1h-1zM13 14h1v1h-1zM14 14h1v1h-1zM21 14h1v1h-1zM23 14h1v1h-1zM25 14h1v1h-1zM26 14h1v1h-1zM31 14h1v1h-1zM32 14h1v1h-1zM33 14h1v1h-1zM36 14h1v1h-1zM37 14h1v1h-1zM38 14h1v1h-1zM2 15h1v1h-1zM3 15h1v1h-1zM6 15h1v1h-1zM7 15h1v1h-1zM9 15h1v1h-1zM10 15h1v1h-1zM12 15h1v1h-1zM14 15h1v1h-1zM19 15h1v1h-1zM20 15h1v1h-1zM21 15h1v1h-1zM23 15h1v1h-1zM24 15h1v1h-1zM25 15h1v1h-1zM27 15h1v1h-1zM29 15h1v1h-1zM31 15h1v1h-1zM34 15h1v1h-1zM36 15h1v1h-1zM2 16h1v1h-1zM4 16h1v1h-1zM5 16h1v1h-1zM7 16h1v1h-1zM8 16h1v1h-1zM9 16h1v1h-1zM10 16h1v1h-1zM12 16h1v1h-1zM19 16h1v1h-1zM20 16h1v1h-1zM22 16h1v1h-1zM23 16h1v1h-1zM24 16h1v1h-1zM25 16h1v1h-1zM26 16h1v1h-1zM27 16h1v1h-1zM29 16h1v1h-1zM31 16h1v1h-1zM32 16h1v1h-1zM34 16h1v1h-1zM35 16h1v1h-1zM36 16h1v1h-1zM37 16h1v1h-1zM2 17h1v1h-1zM3 17h1v1h-1zM4 17h1v1h-1zM6 17h1v1h-1zM15 17h1v1h-1zM16 17h1v1h-1zM17 17h1v1h-1zM19 17h1v1h-1zM21 17h1v1h-1zM23 17h1v1h-1zM25 17h1v1h-1zM28 17h1v1h-1zM29 17h1v1h-1zM33 17h1v1h-1zM34 17h1v1h-1zM36 17h1v1h-1zM38 17h1v1h-1zM4 18h1v1h-1zM6 18h1v1h-1zM7 18h1v1h-1zM8 18h1v1h-1zM11 18h1v1h-1zM12 18h1v1h-1zM13 18h1v1h-1zM14 18h1v1h-1zM16 18h1v1h-1zM17 18h1v1h-1zM19 18h1v1h-1zM23 18h1v1h-1zM26 18h1v1h-1zM29 18h1v1h-1zM31 18h1v1h-1zM32 18h1v1h-1zM35 18h1v1h-1zM36 18h1v1h-1zM37 18h1v1h-1zM38 18h1v1h-1zM5 19h1v1h-1zM6 19h1v1h-1zM7 19h1v1h-1zM9 19h1v1h-1zM10 19h1v1h-1zM14 19h1v1h-1zM15 19h1v1h-1zM16 19h1v1h-1zM17 19h1v1h-1zM18 19h1v1h-1zM20 19h1v1h-1zM23 19h1v1h-1zM25 19h1v1h-1zM27 19h1v1h-1zM28 19h1v1h-1zM29 19h1v1h-1zM30 19h1v1h-1zM34 19h1v1h-1zM35 19h1v1h-1zM36 19h1v1h-1zM2 20h1v1h-1zM7 20h1v1h-1zM8 20h1v1h-1zM10 20h1v1h-1zM11 20h1v1h-1zM12 20h1v1h-1zM14 20h1v1h-1zM20 20h1v1h-1zM21 20h1v1h-1zM23 20h1v1h-1zM24 20h1v1h-1zM29 20h1v1h-1zM31 20h1v1h-1zM33 20h1v1h-1zM35 20h1v1h-1zM3 21h1v1h-1zM4 21h1v1h-1zM6 21h1v1h-1zM10 21h1v1h-1zM13 21h1v1h-1zM14 21h1v1h-1zM16 21h1v1h-1zM17 21h1v1h-1zM19 21h1v1h-1zM20 21h1v1h-1zM21 21h1v1h-1zM22 21h1v1h-1zM23 21h1v1h-1zM28 21h1v1h-1zM29 21h1v1h-1zM32 21h1v1h-1zM33 21h1v1h-1zM36 21h1v1h-1zM37 21h1v1h-1zM3 22h1v1h-1zM4 22h1v1h-1zM5 22h1v1h-1zM7 22h1v1h-1zM8 22h1v1h-1zM11 22h1v1h-1zM12 22h1v1h-1zM14 22h1v1h-1zM15 22h1v1h-1zM16 22h1v1h-1zM18 22h1v1h-1zM22 22h1v1h-1zM23 22h1v1h-1zM26 22h1v1h-1zM31 22h1v1h-1zM32 22h1v1h-1zM36 22h1v1h-1zM37 22h1v1h-1zM38 22h1v1h-1zM2 23h1v1h-1zM3 23h1v1h-1zM6 23h1v1h-1zM9 23h1v1h-1zM10 23h1v1h-1zM11 23h1v1h-1zM13 23h1v1h-1zM15 23h1v1h-1zM16 23h1v1h-1zM17 23h1v1h-1zM19 23h1v1h-1zM20 23h1v1h-1zM25 23h1v1h-1zM27 23h1v1h-1zM29 23h1v1h-1zM34 23h1v1h-1zM35 23h1v1h-1zM4 24h1v1h-1zM5 24h1v1h-1zM6 24h1v1h-1zM7 24h1v1h-1zM8 24h1v1h-1zM10 24h1v1h-1zM12 24h1v1h-1zM13 24h1v1h-1zM15 24h1v1h-1zM20 24h1v1h-1zM21 24h1v1h-1zM22 24h1v1h-1zM24 24h1v1h-1zM25 24h1v1h-1zM29 24h1v1h-1zM30 24h1v1h-1zM31 24h1v1h-1zM36 24h1v1h-1zM2 25h1v1h-1zM3 25h1v1h-1zM4 25h1v1h-1zM5 25h1v1h-1zM9 25h1v1h-1zM10 25h1v1h-1zM14 25h1v1h-1zM16 25h1v1h-1zM17 25h1v1h-1zM19 25h1v1h-1zM21 25h1v1h-1zM22 25h1v1h-1zM23 25h1v1h-1zM24 25h1v1h-1zM28 25h1v1h-1zM30 25h1v1h-1zM33 25h1v1h-1zM36 25h1v1h-1zM37 25h1v1h-1zM2 26h1v1h-1zM3 26h1v1h-1zM4 26h1v1h-1zM6 26h1v1h-1zM8 26h1v1h-1zM9 26h1v1h-1zM10 26h1v1h-1zM11 26h1v1h-1zM12 26h1v1h-1zM16 26h1v1h-1zM17 26h1v1h-1zM18 26h1v1h-1zM20 26h1v1h-1zM23 26h1v1h-1zM27 26h1v1h-1zM28 26h1v1h-1zM29 26h1v1h-1zM32 26h1v1h-1zM33 26h1v1h-1zM34 26h1v1h-1zM36 26h1v1h-1zM2 27h1v1h-1zM4 27h1v1h-1zM5 27h1v1h-1zM6 27h1v1h-1zM7 27h1v1h-1zM11 27h1v1h-1zM14 27h1v1h-1zM16 27h1v1h-1zM21 27h1v1h-1zM26 27h1v1h-1zM27 27h1v1h-1zM30 27h1v1h-1zM31 27h1v1h-1zM32 27h1v1h-1zM33 27h1v1h-1zM34 27h1v1h-1zM35 27h1v1h-1zM36 27h1v1h-1zM5 28h1v1h-1zM8 28h1v1h-1zM19 28h1v1h-1zM25 28h1v1h-1zM26 28h1v1h-1zM27 28h1v1h-1zM28 28h1v1h-1zM30 28h1v1h-1zM31 28h1v1h-1zM33 28h1v1h-1zM34 28h1v1h-1zM35 28h1v1h-1zM4 29h1v1h-1zM6 29h1v1h-1zM10 29h1v1h-1zM11 29h1v1h-1zM12 29h1v1h-1zM13 29h1v1h-1zM15 29h1v1h-1zM19 29h1v1h-1zM20 29h1v1h-1zM22 29h1v1h-1zM25 29h1v1h-1zM28 29h1v1h-1zM32 29h1v1h-1zM33 29h1v1h-1zM36 29h1v1h-1zM37 29h1v1h-1zM38 29h1v1h-1zM2 30h1v1h-1zM3 30h1v1h-1zM6 30h1v1h-1zM7 30h1v1h-1zM8 30h1v1h-1zM9 30h1v1h-1zM10 30h1v1h-1zM11 30h1v1h-1zM12 30h1v1h-1zM13 30h1v1h-1zM14 30h1v1h-1zM15 30h1v1h-1zM16 30h1v1h-1zM20 30h1v1h-1zM21 30h1v1h-1zM26 30h1v1h-1zM29 30h1v1h-1zM30 30h1v1h-1zM31 30h1v1h-1zM32 30h1v1h-1zM33 30h1v1h-1zM34 30h1v1h-1zM35 30h1v1h-1zM36 30h1v1h-1zM37 30h1v1h-1zM38 30h1v1h-1zM10 31h1v1h-1zM11 31h1v1h-1zM12 31h1v1h-1zM13 31h1v1h-1zM15 31h1v1h-1zM16 31h1v1h-1zM17 31h1v1h-1zM18 31h1v1h-1zM19 31h1v1h-1zM25 31h1v1h-1zM30 31h1v1h-1zM34 31h1v1h-1zM35 31h1v1h-1zM37 31h1v1h-1zM2 32h1v1h-1zM3 32h1v1h-1zM4 32h1v1h-1zM5 32h1v1h-1zM6 32h1v1h-1zM7 32h1v1h-1zM8 32h1v1h-1zM10 32h1v1h-1zM12 32h1v1h-1zM13 32h1v1h-1zM14 32h1v1h-1zM15 32h1v1h-1zM16 32h1v1h-1zM20 32h1v1h-1zM21 32h1v1h-1zM23 32h1v1h-1zM25 32h1v1h-1zM26 32h1v1h-1zM27 32h1v1h-1zM28 32h1v1h-1zM30 32h1v1h-1zM32 32h1v1h-1zM34 32h1v1h-1zM35 32h1v1h-1zM36 32h1v1h-1zM2 33h1v1h-1zM8 33h1v1h-1zM10 33h1v1h-1zM11 33h1v1h-1zM12 33h1v1h-1zM13 33h1v1h-1zM14 33h1v1h-1zM15 33h1v1h-1zM16 33h1v1h-1zM20 33h1v1h-1zM22 33h1v1h-1zM28 33h1v1h-1zM30 33h1v1h-1zM34 33h1v1h-1zM36 33h1v1h-1zM38 33h1v1h-1zM2 34h1v1h-1zM4 34h1v1h-1zM5 34h1v1h-1zM6 34h1v1h-1zM8 34h1v1h-1zM10 34h1v1h-1zM12 34h1v1h-1zM14 34h1v1h-1zM18 34h1v1h-1zM21 34h1v1h-1zM24 34h1v1h-1zM26 34h1v1h-1zM30 34h1v1h-1zM31 34h1v1h-1zM32 34h1v1h-1zM33 34h1v1h-1zM34 34h1v1h-1zM35 34h1v1h-1zM36 34h1v1h-1zM37 34h1v1h-1zM38 34h1v1h-1zM2 35h1v1h-1zM4 35h1v1h-1zM5 35h1v1h-1zM6 35h1v1h-1zM8 35h1v1h-1zM12 35h1v1h-1zM16 35h1v1h-1zM19 35h1v1h-1zM23 35h1v1h-1zM24 35h1v1h-1zM27 35h1v1h-1zM28 35h1v1h-1zM29 35h1v1h-1zM30 35h1v1h-1zM32 35h1v1h-1zM33 35h1v1h-1zM2 36h1v1h-1zM4 36h1v1h-1zM5 36h1v1h-1zM6 36h1v1h-1zM8 36h1v1h-1zM11 36h1v1h-1zM12 36h1v1h-1zM13 36h1v1h-1zM14 36h1v1h-1zM16 36h1v1h-1zM17 36h1v1h-1zM18 36h1v1h-1zM19 36h1v1h-1zM21 36h1v1h-1zM22 36h1v1h-1zM23 36h1v1h-1zM24 36h1v1h-1zM27 36h1v1h-1zM32 36h1v1h-1zM35 36h1v1h-1zM37 36h1v1h-1zM2 37h1v1h-1zM8 37h1v1h-1zM16 37h1v1h-1zM17 37h1v1h-1zM18 37h1v1h-1zM19 37h1v1h-1zM20 37h1v1h-1zM21 37h1v1h-1zM26 37h1v1h-1zM29 37h1v1h-1zM32 37h1v1h-1zM33 37h1v1h-1zM36 37h1v1h-1zM37 37h1v1h-1zM2 38h1v1h-1zM3 38h1v1h-1zM4 38h1v1h-1zM5 38h1v1h-1zM6 38h1v1h-1zM7 38h1v1h-1zM8 38h1v1h-1zM11 38h1v1h-1zM16 38h1v1h-1zM19 38h1v1h-1zM25 38h1v1h-1zM26 38h1v1h-1zM29 38h1v1h-1zM31 38h1v1h-1zM32 38h1v1h-1zM34 38h1v1h-1zM35 38h1v1h-1zM36 38h1v1h-1zM37 38h1v1h-1zM38 38h1v1h-1z" fill="#000"/><rect x="15.58" y="15.58" width="9.84" height="9.84" rx="2.16" fill="#FFDD00" stroke="#fff" stroke-width="1.18"/><path d="M17.94 18.14h5.12l-0.69 4.92h-3.74z" fill="#fff" stroke="#000" stroke-width="0.59" stroke-linejoin="round"/><rect x="17.55" y="17.35" width="5.90" height="0.98" rx="0.30" fill="#000"/></svg></a>\n    </div>\n    <a class="back" href="/Plugins">← Back to DynaFrame</a>\n  </footer>\n'

_CSS = '\n/* Fußzeile: Kontakt über GitHub und Buy me a coffee */\n.support { margin: 28px auto 0; padding-top: 22px; border-top: 1px solid var(--line); text-align: center; max-width: 940px; }\n.support-text { margin: 0 0 18px; color: var(--muted); }\n.support-text a { color: var(--accent); }\n.support-row { display: flex; flex-wrap: wrap; gap: 24px; align-items: center; justify-content: center; margin-bottom: 22px; }\n.bmc { display: inline-flex; align-items: center; gap: 10px; height: 54px; padding: 0 22px; border-radius: 12px;\n       background: #FFDD00; color: #000; border: 2px solid #000; text-decoration: none;\n       font-size: 21px; font-weight: 700; line-height: 1; }\n.bmc:hover { filter: brightness(1.05); }\n.bmc-cup { width: 30px; height: 30px; flex: none; }\n.qr-link { display: block; line-height: 0; }\n.qr { width: 150px; height: 150px; border-radius: 10px; }\n.back { display: inline-block; padding: 12px 26px; border: 1px solid var(--accent); border-radius: 999px;\n        color: var(--ink); text-decoration: none; font-weight: 600; }\n.back:hover { background: color-mix(in srgb, var(--accent) 15%, transparent); }\n'

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name}</title>
<style>
:root {{ --bg:#11151c; --panel:#1a202a; --ink:#e9edf3; --muted:#9aa5b4; --line:#2a3240; --accent:#4fa3ff; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }}
main {{ max-width:940px; margin:0 auto; padding:32px 16px 40px; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:24px 26px; }}
h1 {{ margin:0 0 4px; font-size:28px; }}
.ver {{ color:var(--muted); margin:0 0 16px; }}
.desc {{ margin:0 0 14px; }}
.hint {{ margin:0; color:var(--muted); }}
{css}
</style></head>
<body><main>
<section class="card">
<h1>{name}</h1>
<p class="ver">Version {version} &middot; by Jan</p>
<p class="desc">{desc}</p>
<p class="hint">All settings for this plugin are on the normal plugin page.</p>
</section>
{footer}
</main></body></html>
"""

_server = None


def _render():
    try:
        m = json.loads((Path(__file__).resolve().parent / "manifest.json").read_text(encoding="utf-8"))
    except Exception:
        m = {}
    name = str(m.get("DisplayName") or m.get("Name") or "Plugin")
    version = str(m.get("Version") or "")
    issue = urllib.parse.quote(f"[{name} {version}] ")
    return _PAGE.format(
        name=html.escape(name), version=html.escape(version),
        desc=html.escape(str(m.get("Description") or "")), css=_CSS,
        footer=_FOOTER.replace("__ISSUE__", issue),
    ).encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urllib.parse.urlsplit(self.path).path not in ("/", "/index.html"):
            self.send_error(404)
            return
        body = _render()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def start(plugin):
    """Start the page and register it. Never raises: the plugin works without it."""
    global _server
    try:
        _server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=_server.serve_forever, name="support-page", daemon=True).start()
        plugin.register_advanced_settings_page(f"http://127.0.0.1:{_server.server_address[1]}/")
    except Exception as exc:
        try:
            plugin.log(f"Support page not available: {exc}", level="warning")
        except Exception:
            pass


def stop(plugin):
    global _server
    try:
        plugin.unregister_advanced_settings_page()
    except Exception:
        pass
    if _server is not None:
        try:
            _server.shutdown()
            _server.server_close()
        except Exception:
            pass
        _server = None
