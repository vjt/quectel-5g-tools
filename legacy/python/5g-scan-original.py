#!/usr/bin/env python3
import subprocess
import os
import sys
import time

# --- CONFIGURAZIONE ---
BUS_ID = "1-1.2"
REFRESH_SEC = 5

# --- COLORI ANSI PER LA GLORIA DI DIO ---
class C:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def run_at_cmd():
    # Comando AT per vicini
    cmd = f"gl_modem -B {BUS_ID} AT 'AT+QENG=\"neighbourcell\"'"
    try:
        # Timeout per evitare che si pianti se il modem sta bestemmiando
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=4)
        return result.decode('utf-8').strip()
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        print(f"porco dio! errore estraendo la lista delle torri: {e}")
        return None

def parse_and_print(raw_data):
    os.system('clear')
    print(f"{C.HEADER}{C.BOLD}--- RADAR TORRI 5G/4G [LIVE MONITOR] ---{C.ENDC}")
    print(f"{C.HEADER}Target ideale: PCI 280 (B1) | Aggiornamento ogni {REFRESH_SEC}s{C.ENDC}")
    print(f"{C.OKCYAN}" + "-"*70 + f"{C.ENDC}")
    # Intestazione corretta in base al tuo output: Prima RSRQ, poi RSRP
    print(f"{C.BOLD}{'BANDA':<8} | {'PCI':<6} | {'RSRP (Potenza)':<15} | {'RSRQ (Qualità)':<15} | {'DISTANZA?'}{C.ENDC}")
    print(f"{C.OKCYAN}" + "-"*70 + f"{C.ENDC}")

    if not raw_data or "TIMEOUT" in raw_data:
        print(f"{C.FAIL}Nessun dato o Modem Occupato... Riprovo...{C.ENDC}")
        return

    lines = raw_data.splitlines()
    found = False

    for line in lines:
        if "neighbourcell" not in line:
            continue
        
        # Pulizia della stringa infame
        # Esempio: +QENG: "neighbourcell intra","LTE",1350,427,-12,-93,-61...
        clean_line = line.replace('"', '').replace('+QENG: neighbourcell ', '')
        # Rimuove intra/inter per uniformare
        clean_line = clean_line.replace('intra,', '').replace('inter,', '')
        
        parts = clean_line.split(',')
        
        # Parsing Robustezza v2.0
        try:
            # Format atteso dopo pulizia: LTE, EARFCN, PCI, RSRQ, RSRP, RSSI...
            tech = parts[0] # LTE
            earfcn = int(parts[1])
            pci = parts[2]
            rsrq = int(parts[3]) # Nel tuo output -12 viene prima di -93
            rsrp = int(parts[4]) # Potenza vera

            # Traduzione Bande (EARFCN)
            band_name = "UNK"
            if earfcn == 1350: band_name = "B3 (1800)"
            elif earfcn == 275: band_name = "B1 (2100)"
            elif earfcn == 6300: band_name = "B20 (800)"
            elif earfcn == 3000: band_name = "B7 (2600)"
            else: band_name = f"Freq {earfcn}"

            # Colori in base alla Potenza (RSRP)
            color = C.FAIL # Rosso merda
            if rsrp > -95: color = C.OKGREEN # Ottimo
            elif rsrp > -105: color = C.WARNING # Medio
            
            # Highlight speciale per il TARGET (PCI 280)
            status_icon = ""
            if pci == "280":
                status_icon = " <--- TARGET"
                color = C.OKCYAN + C.BOLD # Blu elettrico per il target

            print(f"{color}{band_name:<8} | {pci:<6} | {str(rsrp) + ' dBm':<15} | {str(rsrq) + ' dB':<15} | {status_icon}{C.ENDC}")
            found = True

        except Exception as e:
            # Ignora righe malformate o vuote
            print(f"porco dio! riga: {clean_line}, errore: {e}")
            continue

    if not found:
        print(f"{C.FAIL}Nessuna cella vicina rilevata al momento.{C.ENDC}")
        print("Il modem popola questa lista solo durante trasferimento dati attivo.")

    print(f"{C.OKCYAN}" + "-"*70 + f"{C.ENDC}")
    print(f"Premi CTRL+C per bestemmiare e uscire.")

def main():
    try:
        while True:
            data = run_at_cmd()
            parse_and_print(data)
            time.sleep(REFRESH_SEC)
    except KeyboardInterrupt:
        print(f"\n{C.FAIL}Monitoraggio interrotto. Amen.{C.ENDC}")
        sys.exit(0)

if __name__ == "__main__":
    main()
