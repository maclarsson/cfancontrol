# Changelog

## [1.2.0] – 2022-07-28

### Changes since 1.1.8

Added:

- Initial support for multiple fan controllers in the system
- Selection box for detected fan controllers
- Experimental support for controlling the fans of Corsair Hydro Platinum AIOs
- 'Cancel' button to fan mode configuration
- Copy and paste functionality for fan curves via context menu
- This change log

Changed:

- Prevent the start of the fan control update daemon if no fan controller is detected in the system
- Move 'Apply' button to the bottom right corner
- New format of the profile files including a version tag (current: "1")
- Streamline logging levels and messages
- Some refactoring with the sensor and device classes

Fixed:

- Correctly refresh profiles list after a profile is added or removed
- Don't use native file dialog for load/save profile as this caused problems on GNOME 42

Removed:

- 

### Know issues

- 



## About the changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/).
