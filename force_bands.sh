#!/bin/sh

# vim: syn=bash

# Aspettiamo che il modem si svegli e finisca di caricare i driver di merda
if [ "$1" != "now" ]; then
  sleep 30
fi

BUS="1-1.2"
LTE_BANDS="1:3:7:20"
NR5_BANDS="78"

# LOG INIZIALE
logger -t BAND_LOCK "DIO CANE: Inizio blocco bande 4G:${LTE_BANDS} 5G:${NR5_BANDS}"

gl_modem -B $BUS AT "AT+QNWPREFCFG=\"lte_band\",$LTE_BANDS" >/dev/null
gl_modem -B $BUS AT "AT+QNWPREFCFG=\"nsa_nr5g_band\",$NR5_BANDS" >/dev/null

RES=$(gl_modem -B $BUS AT 'AT+QNWPREFCFG="lte_band"' | tr '\r' ' ' | grep QNW)
logger -t BAND_LOCK "Risultato applicazione bande LTE: $RES"

RES=$(gl_modem -B $BUS AT 'AT+QNWPREFCFG="nsa_nr5g_band"' | tr '\r' ' ' | grep QNW)
logger -t BAND_LOCK "Risultato applicazione bande 5G: $RES"
