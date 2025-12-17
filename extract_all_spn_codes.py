"""
Extract all SPN codes from PDF and create comprehensive list
"""

import PyPDF2
import re

pdf_path = "Suspect-Parameter-Numbers-SPN-Codes.pdf"

print("=" * 80)
print("📄 EXTRAYENDO TODOS LOS CÓDIGOS SPN DEL PDF (159 páginas)")
print("=" * 80)

spn_database = {}

try:
    with open(pdf_path, "rb") as file:
        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)

        print(f"\n📊 Procesando {total_pages} páginas...\n")

        for page_num in range(total_pages):
            if page_num % 10 == 0:
                print(f"  Procesando página {page_num + 1}/{total_pages}...")

            page = pdf_reader.pages[page_num]
            text = page.extract_text()

            # Buscar líneas que contengan números SPN
            lines = text.split("\n")
            for line in lines:
                # Buscar patrones como: "91 Engine Fuel Filter"
                match = re.match(r"^\s*(\d{2,5})\s+(.+)", line)
                if match:
                    spn = match.group(1)
                    description = match.group(2).strip()

                    # Limpiar descripción
                    description = re.sub(r"[^\x20-\x7E]+", " ", description)
                    description = " ".join(description.split())

                    if len(description) > 5 and len(description) < 200:
                        spn_database[int(spn)] = description

        print(f"\n✅ Extracción completa!")
        print(f"📊 Total de SPNs encontrados: {len(spn_database)}")

        # Mostrar algunos SPNs importantes para DEF/Aftertreatment
        print("\n" + "=" * 80)
        print("🔍 SPNs RELACIONADOS CON DEF/AFTERTREATMENT (5000+)")
        print("=" * 80)

        aftertreatment_spns = {
            k: v for k, v in spn_database.items() if 5000 <= k <= 6000
        }

        for spn in sorted(aftertreatment_spns.keys()):
            print(f"  SPN {spn}: {aftertreatment_spns[spn]}")

        # Buscar el SPN 5444 específicamente
        print("\n" + "=" * 80)
        print("🎯 VERIFICANDO SPN 5444 (del Beyond/Wialon)")
        print("=" * 80)

        if 5444 in spn_database:
            print(f"  ✅ SPN 5444: {spn_database[5444]}")
        else:
            print("  ⚠️ SPN 5444 no encontrado en el PDF")

        # Guardar a archivo
        output_file = "extracted_spn_codes.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("SPN CODES EXTRACTED FROM PDF\n")
            f.write("=" * 80 + "\n\n")
            for spn in sorted(spn_database.keys()):
                f.write(f"SPN {spn}: {spn_database[spn]}\n")

        print(f"\n💾 Lista completa guardada en: {output_file}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
