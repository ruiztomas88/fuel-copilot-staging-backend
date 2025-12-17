"""
Extract SPN codes from PDF document
"""

import PyPDF2
import re

pdf_path = "Suspect-Parameter-Numbers-SPN-Codes.pdf"

print("=" * 80)
print("📄 EXTRAYENDO CÓDIGOS SPN DEL PDF")
print("=" * 80)

try:
    with open(pdf_path, "rb") as file:
        pdf_reader = PyPDF2.PdfReader(file)

        print(f"\n📊 Total de páginas: {len(pdf_reader.pages)}")
        print("\nExtrayendo texto de las primeras 5 páginas...\n")

        for page_num in range(min(5, len(pdf_reader.pages))):
            print(f"\n{'=' * 80}")
            print(f"PÁGINA {page_num + 1}")
            print(f"{'=' * 80}\n")

            page = pdf_reader.pages[page_num]
            text = page.extract_text()

            # Buscar patrones de SPN
            # Formato típico: "SPN 5444" o "5444 - Description"
            spn_matches = re.findall(
                r"\b(?:SPN\s+)?(\d{3,5})\b.*?([A-Za-z][\w\s-]+)", text
            )

            if spn_matches:
                print(f"SPNs encontrados en página {page_num + 1}:")
                for spn, desc in spn_matches[:10]:  # Primeros 10
                    print(f"  SPN {spn}: {desc[:60]}")

            # Mostrar primeros 1000 caracteres de la página
            print(f"\nTexto de la página (primeros 1000 chars):")
            print(text[:1000])

except FileNotFoundError:
    print(f"❌ Archivo no encontrado: {pdf_path}")
except Exception as e:
    print(f"❌ Error leyendo PDF: {e}")
