"""Met à jour le sommaire, la liste des figures et la liste des tableaux du mémoire, puis
exporte le PDF (et une version DOCX aux index à jour) avec LibreOffice en mode sans interface.

Usage : python3 finalize_memoire.py  (après node build_memoire.js)
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import uno  # fourni par LibreOffice (paquet python3-uno)
from com.sun.star.beans import PropertyValue

HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / "memoire.json").read_text(encoding="utf-8"))
SOURCE = (HERE / ".." / CONFIG["output_docx"]).resolve()
PDF = SOURCE.with_suffix(".pdf")
PORT = 2099


def prop(name: str, value) -> PropertyValue:
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def main() -> None:
    office = subprocess.Popen(["soffice", "--headless", "--invisible", "--nologo", "--norestore",
                               f"--accept=socket,host=127.0.0.1,port={PORT};urp;"])
    try:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        for _ in range(60):
            try:
                ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={PORT};urp;StarOffice.ComponentContext")
                break
            except Exception:  # LibreOffice démarre
                time.sleep(0.5)
        else:
            sys.exit("LibreOffice ne répond pas")
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.loadComponentFromURL(SOURCE.as_uri(), "_blank", 0, (prop("Hidden", True),))
        # Deux passes : la seconde intègre les numéros de page décalés par la première.
        for _ in range(2):
            indexes = doc.getDocumentIndexes()
            for i in range(indexes.getCount()):
                indexes.getByIndex(i).update()
            doc.refresh()
        doc.storeToURL(PDF.as_uri(), (prop("FilterName", "writer_pdf_Export"),))
        doc.storeToURL(SOURCE.as_uri(), (prop("FilterName", "MS Word 2007 XML"),))
        doc.close(True)
        print(f"PDF : {PDF}\nDOCX (index à jour) : {SOURCE}")
    finally:
        office.terminate()
        office.wait(timeout=30)


if __name__ == "__main__":
    main()
