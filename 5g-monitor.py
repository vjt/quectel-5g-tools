#!/usr/bin/env python3
import subprocess
import time
import os
import sys
from collections import defaultdict

# --- CONFIGURAZIONE ---
BUS_ID = "1-1.2"

# --- MAPPE DI CONVERSIONE ---

# QENG LTE DL Bandwidth Index
LTE_QENG_BW_MAP = {
    '0': '1MHz', '1': '3MHz', '2': '5MHz',
    '3': '10MHz',  '4': '15MHz', '5': '20MHz'
}

# QCAINFO LTE Bandwidth (RB)
LTE_QCA_BW_MAP = {
    '6': '1MHz', '15': '3MHz', '25': '5MHz',
    '50': '10MHz', '75': '15MHz', '100': '20MHz'
}

# NR5G Bandwidth Index (SCS 30kHz)
NR_BW_INDEX_MAP = {
    '0': '5MHz',   '1': '10MHz',  '2': '15MHz',  '3': '20MHz',
    '4': '25MHz',  '5': '30MHz',  '6': '40MHz',  '7': '50MHz',
    '8': '60MHz',  '9': '70MHz',  '10': '80MHz', '11': '90MHz',
    '12': '100MHz'
}

class C:
    G = '\033[92m' # Verde
    Y = '\033[93m' # Giallo
    R = '\033[91m' # Rosso
    B = '\033[94m' # Blu
    C = '\033[96m' # Ciano
    W = '\033[97m' # Bianco
    M = '\033[95m' # Magenta
    N = '\033[0m'  # Reset

def run_at(command):
    cmd = f"gl_modem -B {BUS_ID} AT '{command}'"
    try:
        res = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        return res.decode('utf-8').replace('\r', '').strip()
    except:
        return None

def clean_split(line):
    parts = line.split(',')
    return [p.strip().replace('"', '') for p in parts]

def get_color(val_str, mode='sinr'):
    try:
        v = float(val_str)
        if mode == '4gsinr':
            if v >= 15: return C.G
            if v >= 8: return C.Y
            return C.R
        if mode == '5gsinr':
            if v >= 16: return C.G
            if v >= 10: return C.Y
            return C.R
        if mode == 'rsrq':
            if v >= -10: return C.G
            if v >= -15: return C.Y
            return C.R
        if mode == 'rsrp':
            if v >= -99: return C.G
            if v >= -110: return C.Y
            return C.R
    except:
        return C.W

def calc_freq(code):
    """
    Converte EARFCN (LTE) o NR-ARFCN (5G) in MHz.
    Restituisce una stringa tipo "1845.0 MHz (B3)"
    """
    try:
        if not code or code == '-' or code == 'N/D': return "N/D"
        c = int(code)
    except:
        return code # Se non è un numero, ridallo indietro

    # --- 5G NR (N78) ---
    # Range N78: 620000 - 653333 (3300-3800 MHz)
    # Formula: F = 3000 + 0.015 * (N - 600000)
    if 620000 <= c <= 653333:
        freq = 3000 + 0.015 * (c - 600000)
        return f"{freq:.1f} MHz"

    # --- LTE BANDS (Italia/Europa) ---
    # Tupla: (Band, Start, End, F_Low, N_Off)
    lte_table = [
        (1, 0, 599, 2110, 0),        # B1 (2100)
        (3, 1200, 1949, 1805, 1200), # B3 (1800)
        (7, 2750, 3449, 2620, 2750), # B7 (2600)
        (20, 6150, 6449, 791, 6150), # B20 (800)
        (28, 9210, 9659, 758, 9210), # B28 (700)
        (32, 9920, 10359, 1452, 9920), # B32 (1500 SDL)
        (38, 37750, 38249, 2570, 37750), # B38 (2600 TDD)
        (40, 38650, 39649, 2300, 38650)  # B40 (2300 TDD)
    ]

    for b, start, end, flow, noff in lte_table:
        if start <= c <= end:
            # Formula LTE: F = F_low + 0.1 * (N - N_off)
            freq = flow + 0.1 * (c - noff)
            return f"{freq:.1f} MHz"

    return f"Freq? ({c})"

def pcell_state(state):
  return {
      '0': 'Idle',
      '1': 'Registered',
      '2': 'Searching',
      '3': 'Denied',
      '4': 'Unknown',
      '5': 'Roaming',
  }.get(state, 'N/A')

def scell_state(state):
  return {
      '0': 'Deconfigured',
      '1': 'Inactive',
      '2': 'Active',
  }.get(state, 'N/A')

def beep_sequence(sinr):
    try:
        val = float(sinr)
    except:
        return 0

    if val >= 19: return 6
    if val == 18: return 5
    if val == 17: return 4
    if val == 16: return 3
    if val >= 14: return 2
    if val >= 12: return 1

    return 0

def play_beeps(count):
    if count > 0:
        sys.stdout.flush()
        for _ in range(count):
            print('\a', end='', flush=True)
            time.sleep(0.6) # Ritmo da tachicardia come richiesto

def main():
    while True:
        os.system('clear')

        cache = defaultdict(dict)
        lte_found = False
        nr_found = False
        beeps = 0

        qspn_raw = run_at('AT+QSPN')
        network_name = None
        for line in qspn_raw.splitlines():
          parts = clean_split(line)
          if len(parts) != 5:
            continue

          network_name = parts[0].replace('+QSPN: ', '')

        if not network_name:
          network_name = "N/A"

        print(f"{C.Y}--===================================================--")
        print(f"{C.Y}--======== MONITOR QUECTEL RM520N !DIO LUPO! ========--{C.N}")
        print(f"{C.Y}--===================================================--")
        print(f"{C.M}Network: {network_name} {C.N}")

        # --- PARSING QENG ---
        # +QENG: "servingcell","NOCONN"
        # +QENG: "LTE","FDD",222,01,4940206,427,1350,3,5,5,BFF,-94,-15,-58,9,5,100,-
        # +QENG: "NR5G-NSA",222,01,920,-96,18,-10,648768,78,10,1
        qeng_raw = run_at('AT+QENG="servingcell"')
        if qeng_raw:
            lines = qeng_raw.splitlines()
            for line in lines:
                parts = clean_split(line)
                
                # [LTE] +QENG: "LTE","FDD",222,01,4940206,427,1350,3,5,5,BFF,-94,-14,-59,9,6,-120,-
                if len(parts) > 10 and "LTE" == parts[0].replace('+QENG: ', ''):
                    try:
                        mode = parts[1]
                        cell_id_hex = parts[4]
                        pci = parts[5]
                        earfcn = parts[6]
                        band = parts[7]
                        ul_bw_idx = parts[8]
                        dl_bw_idx = parts[9]
                        tac_hex = parts[10]
                        rsrp = parts[11]
                        rsrq = parts[12]
                        rssi = parts[13]
                        sinr = parts[14]
                        cqi = parts[15]
                        txpower = parts[16]
                        
                        try:
                            cid_dec = int(cell_id_hex, 16)
                            enodeb = cid_dec >> 8
                        except:
                            enodeb = "ERR"
                        
                        try:
                            tac_dec = int(tac_hex, 16)
                        except:
                            tac_dec = "ERR"

                        dl_bw = LTE_QENG_BW_MAP.get(dl_bw_idx, f"?{dl_bw_idx}?")
                        ul_bw = LTE_QENG_BW_MAP.get(ul_bw_idx, f"?{dl_bw_idx}?")
                        
                        c_rsrp = get_color(rsrp, 'rsrp')
                        c_rsrq = get_color(rsrq, 'rsrq')
                        c_sinr = get_color(sinr, '4gsinr')

                        freq = calc_freq(earfcn)

                        pwr = f"{float(txpower) / 10:.1f}dBm"

                        print(f"{C.B}[4G - B{band}]{C.N} mode:{C.C}{mode}{C.N} eNodeB:{C.C}{enodeb}{C.N} PCI:{C.C}{pci}{C.N} TAC:{C.C}{tac_dec}{C.N}")
                        print(f"Bandwidth: DL: {C.W}{dl_bw}{C.N} UL: {C.W}{ul_bw}{C.N} | Freq: {C.W}{freq}{C.N}")
                        print(f"Signal   : RSRP:{c_rsrp}{rsrp}{C.N} | RSRQ:{c_rsrq}{rsrq}{C.N} | SINR:{c_sinr}{sinr}{C.N} | PWR:{C.W}{pwr}{C.N}")
                        lte_found = True
                    except Exception as e:
                        print(f"{C.R}LTE PARSING ERROR: {e}{C.N}")

                # [NR5G] +QENG: "NR5G-NSA",222,01,920,-96,18,-10,648768,78,10,1
                if len(parts) > 8 and "NR5G-NSA" in parts[0].replace('+QENG: ', ''):
                    try:
                        pci = parts[3]
                        rsrp = parts[4]
                        sinr = parts[5]
                        rsrq = parts[6]
                        arfcn = parts[7]
                        band = parts[8]
                        bw_idx = parts[9]
                        
                        cache[pci]['rsrp'] = rsrp
                        cache[pci]['sinr'] = sinr
                        
                        bw_str = NR_BW_INDEX_MAP.get(bw_idx, f"?{bw_idx}?")
                        freq = calc_freq(arfcn)
                        
                        beeps = beep_sequence(sinr)

                        c_rsrp = get_color(rsrp, 'rsrp')
                        c_rsrq = get_color(rsrq, 'rsrq')
                        c_sinr = get_color(sinr, '5gsinr')

                        print(f"{C.W}" + "-"*80 + f"{C.N}")
                        print(f"{C.G}[5G - n{band}]{C.N} PCI:{C.C}{pci}{C.N}")
                        print(f"Bandwidth: DL: {C.W}{bw_str}{C.N} | Freq: {C.W}{freq}{C.N}")
                        print(f"Signal   : RSRP:{c_rsrp}{rsrp}{C.N} | RSRQ:{c_rsrq}{rsrq}{C.N} | SINR:{c_sinr}{sinr}{C.N} | Beeps:{C.C}{beeps}{C.N}")
                        nr_found = True
                    except Exception as e:
                        print(f"{C.R}NR PARSING ERROR: {e}{C.N}")

        if not lte_found: print(f"{C.R}[4G] NO LOCK{C.N}")
        if not nr_found: print(f"{C.R}[5G] NO SIGNAL{C.N}")

        print(f"{C.W}" + "-"*80 + f"{C.N}")

        # --- PARSING QCAINFO ---
        # +QCAINFO: "PCC",1350,100,"LTE BAND 3",1,427,-94,-15,-58,-3
        # +QCAINFO: "SCC",275,75,"LTE BAND 1",1,406,-104,-20,-74,-10,0,-,-
        # +QCAINFO: "SCC",648768,10,"NR5G BAND 78",920
        qca_raw = run_at('AT+QCAINFO')
        print(f"{C.W}CARRIER AGGREGATION:{C.N}")
        if qca_raw:
            lines = qca_raw.splitlines()
            for line in lines:
                if "+QCAINFO:" not in line: continue

                parts = clean_split(line.replace('+QCAINFO: ', ''))

                c_type = parts[0]
                earfcn = parts[1]
                bw_val = parts[2]
                band_name = parts[3]

                if c_type == "PCC":
                  state = pcell_state(parts[4])
                  pci = parts[5]
                  rsrp = parts[6]
                  rsrq = parts[7]
                  sinr = parts[9]
                else:
                  if len(parts) == 13:
                    state = scell_state(parts[4])
                    pci = parts[5]
                    rsrp = parts[6]
                    rsrq = parts[7]
                    sinr = parts[9]
                    ul_configured = parts[10]
                    ul_band = parts[11]
                    ul_earfcn = parts[12]

                  elif len(parts) == 12:
                    state = scell_state(parts[4])
                    pci = parts[5]
                    ul_configured = parts[6]
                    ul_band = parts[7]
                    ul_earfcn = parts[8]
                    rsrp = parts[9]
                    rsrq = parts[10]
                    sinr = parts[11]

                  elif len(parts) == 9:
                    state = scell_state(parts[4])
                    pci = parts[5]
                    ul_configured = parts[6]
                    ul_band = parts[7]
                    ul_earfcn = parts[8]
                    rsrp = None
                    rsrq = None
                    sinr = None

                  elif len(parts) == 5:
                    state = 'N/A'
                    pci = parts[4]
                    rsrp = None
                    rsrq = None
                    sinr = None

                freq = calc_freq(earfcn)
                col = C.B if "PCC" in c_type else C.C

                if not rsrp and cache.get(pci) and 'rsrp' in cache[pci]:
                  rsrp = cache[pci]['rsrp']
                if rsrp:
                  c_rsrp = get_color(rsrp, 'rsrp')
                else:
                  c_rsrp = C.W
                
                if not sinr and cache.get(pci) and 'sinr' in cache[pci]:
                  sinr = cache[pci]['sinr']
                if sinr:
                  thresholds = '5gsinr' if '5G' in band_name else '4gsinr'
                  c_sinr = get_color(sinr, thresholds)
                else:
                  c_sinr = C.W
                
                if "NR5G" in band_name:
                    bw_mhz = NR_BW_INDEX_MAP.get(bw_val, f"Idx {bw_val}")
                else:
                    bw_mhz = LTE_QCA_BW_MAP.get(bw_val, f"Idx {bw_val}")

                print(f" -> {col}{c_type}{C.N} {band_name:<12} | PCI:{C.C}{pci:<3}{C.N} | SINR:{c_sinr}{sinr:<3}{C.N} | RSRP:{c_rsrp}{rsrp:<4}{C.N} | {C.W}{bw_mhz:<5}{C.N} | {C.W}{freq}{C.N} | {state}")

        print(f"{C.W}" + "-"*80 + f"{C.N}")
        
        play_beeps(beeps)
        #sys.exit()

        time.sleep(5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit()
