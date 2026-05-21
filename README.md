# IP Switch Controller

A [StreamController](https://github.com/StreamController/StreamController) plugin for controlling IP-connected signal switchers. The intended scope is input switching, not full device configuration. For anything beyond that, I would suggest using the manufacturer's first-party software.

## Supported Devices

### TESmart
All IP-connected TESmart switches should work. Tested on:
- TESmart 8-Port 4K60 HDMI Switch (HSW801-E23)

### HDFury
All IP-connected HDFury switches should work. Tested on:
- HDFury VRROOM

## Usage

Add a **TESmart: Switch Input** or **HDFury: Switch Input** action to a button. Configure the IP address and which input to switch to. The button highlights when that input is active.

## Development Setup

Clone into your StreamController plugins directory:

```bash
cd ~/.var/app/com.core447.StreamController/data/plugins
```
```bash
git clone https://github.com/ninbura/ip-switch-controller
```
