# Cura-QidiPrint Plugin

Plugin for Cura 4.7 that allows printing on QIDI 3D printers over network 

![Screenshot of the print button](/screenshots/print-button.png)

## Manual Installation

with Cura not running, unpack the zip file from the
[release](https://github.com/alkaes/QidiPrint/releases/latest) to this
specific folder:


  * Windows: `%USERPROFILE%\AppData\Roaming\cura\4.7\plugins\`
  * MacOS: `~/Library/Application Support/Cura/4.7/plugins/`
  * Linux: `/home/<username>/.local/share/cura/4.7/plugins/`

## Configuration

**Do NOT try to add a new "networked printer"!** This is only for Ultimaker printers.

QIDI printers are configured through the extension menu bar:

* Start Cura
* From the menu bar choose: Extensions -> QidiPrint -> QidiPrint Connections

![Screenshot of the menu bar entry](/screenshots/menu-bar.png)

* Click "Add"

![Screenshot of the edit dialog](/screenshots/edit-dialog.png)

* Enter the name of your printer
  - e.g., `X-MAKER`
* Enter the IP of your printer
  - e.g., `192.168.10.205`
* Click "Ok"
* Done!

Now you can load a model and slice it. Then look at the bottom right - there
should be the big blue button with you printer name on it!

## License

This project is using code from:
* https://github.com/Kriechi/Cura-DuetRRFPlugin
* ChituCodeWriter.py is taken from https://github.com/Spanni26/ChituCodeWriter


