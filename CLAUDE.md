# Overview

This is a set of scripts I wrote to extract information from a device i own running the Quectel RM520 modem, the GL.INET X-3000, connected to a directional antenna (poynting xpol-24).

My goal is to extract as much information as possible from the modem on the currently serving cell and also aggregated bands, to be used as a tool to aid accurate pointing of the directional antenna. The '5g-monitor.py' script, written in python, queries the network name, serving cell and carrier aggregated cells to print a summary of the signal strength, quality and signal-to-noise ratio.

The script also emits beeps driven by the 5G SINR value, so to be useful to be used while moving the antenna without needing to look at the screen.

# Goals of this project

The script is written in python and thus requires a user to add python packages to their installation, that may not be exactly desirable. Considering that on OpenWRT on which the GL-X3000 is built already has lua pre-installed, we should first consider whether it makes sense to rewrite it all in Lua. However, we must also consider all the other goals.

I want to create a re-usable library to parse the Quectel modem strings. Currently the python script does brutal string splits and replaces to obtain the goal, and it just does a set of print() followed by a system("clear") that a bit ugly. In the rewrite, I'd like to establish:

- An ergonomic wrapper to parse the output of the AT commands. This wrapper should be composed of multiple classes, one for each data type, and should have methods that invoke modem commands and return lists of appropriate hydrated instances, for easy decoding

- A CLI interface, that just prints the information once in a list and maybe a JSON format

- A TUI interface, that does what currently the python script does (printing the information nicely every X seconds) but using ncurses and possibly 256-color output. The choice of the colors and thresholds should be dicated by the ranges described in the official Quectel documentation

- An HTTP JSON interface, to be integrated in LuCI, so that I can then poll for this data from an external service and collect it and store it for statistics purposes.

- A couple of utilities to query the modem, such as the "at" one to send custom AT commands to the modem and the `force_bands.sh` to lock the modem on specific bands.

- If possible, a very tiny wrapper that interacts directly with the modem without forking to `gl_modem`. But if this becomes too complicated or relies on too much undocumented interfaces, let's just use `gl_modem` that's not a big deal.

- A configuration file e.g. for the modem BUS that should be shared by all of these components, integrated in the UCI framework but with sane defaults for the X-3000. We will start using this on the X-3000 but I don't want to scope this project only to this specific device.

All of this should be written in Lua as I guess it's the easier path forward to integrate it nicely in the OpenWRT ecosystem.

# Engineering

This must be well coded, well understandable, modular and extensible. We should follow closely the documentation in the quectel-rm520n-excerpt.pdf file. That explains what the commands do and what the output means. 

I don't want a quick hack, I want production-grade code that's coded by a veteran. On the other hand, I don't want too layered, over-engineered java style code. It has to be as simple as possible, but not simpler. It must be understandable and not filled with comments. We should use comments only in the most compllicated parts (if ever).

It should follow the principle of the least surprise, and it has to be DRY - Don't Repeat Yourself. Lower-level parsing, common functions, higher level abstractions and wrappers, well formed library and the CLI, TUI and WEB API consumers that use it.

# Sample outputs

This is the sample output of running few commmands of interest.

```
ATI


Quectel
RM520N-GL
Revision: RM520NGLAAR03A03M4G

OK
AT+QSPN


+QSPN: "I TIM","TIM","",0,"22201"

OK
AT+QNWPREFCFG="mode_pref"


+QNWPREFCFG: "mode_pref",AUTO

OK
AT+QNWPREFCFG="nsa_nr5g_band"


+QNWPREFCFG: "nsa_nr5g_band",78

OK
AT+QNWPREFCFG="lte_band"


+QNWPREFCFG: "lte_band",1:3:7:20

OK
AT+QCAINFO


+QCAINFO: "PCC",275,75,"LTE BAND 1",1,280,-99,-14,-67,-4
+QCAINFO: "SCC",1350,100,"LTE BAND 3",1,240,-95,-18,-68,-10,0,-,-
+QCAINFO: "SCC",648768,10,"NR5G BAND 78",920

OK
AT+QENG="servingcell"


+QENG: "servingcell","NOCONN"
+QENG: "LTE","FDD",222,01,328261F,280,275,1,4,4,BE3,-99,-14,-66,7,4,30,-
+QENG: "NR5G-NSA",222,01,920,-96,18,-10,648768,78,10,1

OK
AT+QENG="neighbourcell"


+QENG: "neighbourcell intra","LTE",275,280,-14,-99,-67,-,-,-,-,-,-
+QENG: "neighbourcell intra","LTE",275,34,-20,-105,-76,-,-,-,-,-,-
+QENG: "neighbourcell intra","LTE",275,46,-20,-106,-75,-,-,-,-,-,-
+QENG: "neighbourcell inter","LTE",1350,240,-18,-95,-68,-,-,-,-,-
+QENG: "neighbourcell inter","LTE",1350,427,-14,-94,-69,-,-,-,-,-
+QENG: "neighbourcell inter","LTE",1350,465,-17,-94,-68,-,-,-,-,-
+QENG: "neighbourcell inter","LTE",1350,157,-17,-95,-68,-,-,-,-,-
+QENG: "neighbourcell inter","LTE",1350,47,-18,-96,-69,-,-,-,-,-

OK
```

# Questions?

Please ensure to ask any clarification and let's then put answers in this document.
