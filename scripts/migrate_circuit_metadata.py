import os
import json
import shutil

def main():
    base_dir = "/Users/wizards/Sviluppo/F1 Manager AI/python_backend/data"
    old_circuits_dir = os.path.join(base_dir, "circuits")
    new_circuits_dir = os.path.join(old_circuits_dir, "2025")
    backup_dir = os.path.join(base_dir, "circuits_legacy")

    keys_to_transfer = ["tyres", "fuel_mass", "weather", "reliability", "visual"]

    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    print("Iniziando il trasferimento dei metadati...")

    # Recupera i file 2025
    new_files = [f for f in os.listdir(new_circuits_dir) if f.endswith(".json") and f != "manifest.json"]

    for filename in new_files:
        old_path = os.path.join(old_circuits_dir, filename)
        new_path = os.path.join(new_circuits_dir, filename)

        if os.path.exists(old_path):
            # Carica vecchio
            with open(old_path, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
            
            # Carica nuovo
            with open(new_path, 'r', encoding='utf-8') as f:
                new_data = json.load(f)
            
            # Trasferisci i blocchi
            transferred = False
            for key in keys_to_transfer:
                if key in old_data:
                    new_data[key] = old_data[key]
                    transferred = True
            
            # Salva il nuovo file aggiornato
            if transferred:
                with open(new_path, 'w', encoding='utf-8') as f:
                    json.dump(new_data, f, indent=2)
                print(f"✅ Aggiornato {filename}")

            # Sposta il vecchio file nella cartella di backup
            backup_path = os.path.join(backup_dir, filename)
            shutil.move(old_path, backup_path)
        else:
            print(f"⚠️ Vecchio file non trovato per {filename}")

    # Sposta eventuali altri file JSON rimanenti nella vecchia cartella
    for f in os.listdir(old_circuits_dir):
        old_file_path = os.path.join(old_circuits_dir, f)
        if f.endswith(".json") and os.path.isfile(old_file_path):
            shutil.move(old_file_path, os.path.join(backup_dir, f))
            print(f"📦 Spostato file rimanente {f} nel backup.")

    print(f"\nOperazione completata! I vecchi file sono stati spostati in: {backup_dir}")

if __name__ == "__main__":
    main()
