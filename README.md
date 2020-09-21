# Cura-QidiPrint Plugin

Plugin for Cura 4.7 that allows printing on QIDI 3D printers over network 

## Manual Installation

with Cura not running, unpack the zip file from the
[release](https://github.com/alkaes/QidiPrint/releases/latest) to this
specific folder:

`C:\Users\<username>\AppData\Roaming\cura\4.7\plugins\QidiPrint`

Be careful, the unzipper often tacks on the name of the zip as a folder at the
bottom and you don't want it nested.  You want the files to show up in that
folder.

Make sure that the plugin folder name is a listed above and it does not have
any trailing version numbers (`-1.0.0`) or similar.

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
* https://github.com/Spanni26/ChituCodeWriter


