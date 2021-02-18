# RaidToolGUI

A visual fronted for the raw data utility of Siemens MRI systems.

## Concept and functionality

This tool was initially designed as a client for the [Agora](https://www.gyrotools.com/gt/index.php/products/agora) raw data management system, but it has since expanded to comprise removable and network drives. It watches the scanner RAID disk for new raw data files that correspond to specific patterns (based on patient name and/or protocol name), and facilitates the storing them into predefined locations.

The program also scans for physiological log files that might be acquired at the same time as the raw data file, and stores them at the same location.

## Installation

Create a windows executable package with [PyInstaller](https://www.pyinstaller.org/) (a spec file is included, you might need to adapt the paths to your installation) and run it on the scanner.

## Configuration

Modify the `config.yml` file to suit your needs. A model config file is provided, with comments.

The file has four sections:
- `Global` section. This contains global configuration settings.
- `Raid` section. This is a section related to the RAID settings. It should be common to all Siemens scanners and there should be no need to change it.
- `Targets` section. This section defines the targets where the raw data should be stored. There are two possible target types: `Agora` and `Drive`. `Drive` can represent fixed, removable, or network-attached drives. Removable drives can be addressed by name (independently of the drive letter they get when attached) by specifying the `DriveRegex` variable. For each drive target, the `SkipTemp` setting can be specified, in which case the program will download the raw data file directly into the attached drive, without going through a temp folder.
- `Rules` section: for each rule, up to two regular expressions can be specified: one to match the patient, and one to match the protocol. If one is not specified, it is considered to always match. When a Patient/Protocol matches the expressions, the raw data file is marked for download to the specified `Target`s. More than one rule can match for each raw data file, in which case, it is transferred to all the targets. Files that match the `GlobalIgnorRegex` rules will never be included for download.

## Usage

When the program is launched (through the `raidToolGUI.py` script), a simple interface is shown. The "Refresh" button reloads the file list from the scanner. The selected files will then be stored on the temporary folder specified in the configuration with the "Retrieve" button. This is a necessary step, as only retrieved files will be transferred. However, if a file is destined to a target for which `SkipTemp` is defined, the file will not be actually retrieved.

Retrieved files will turn to a yellow background, showing that they are ready to be transferred to the target. This happens by clicking the "Transfer" button.

The *retrieved* and *transferred* statuses are remembered across runs of the program, to avoid redownloading existing files. However, the status can be cleared with the "Clear status" button.

If specific files need to be manually excluded from download, the "Ignore" button can be used.

The program can be minimized at any time by closing the window and it will continue working in the background. When minimized, the program will appear like a small icon, which can be moved to the icon tray at the bottom of the screen.

The program can be started in minified form by using the `-m` command line argument. It is useful to also specify the `-p` parameter, to show the icon in a specific place on the screen.