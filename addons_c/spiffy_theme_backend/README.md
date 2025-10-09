spiffy_theme_backend
=================
* The ultimate Odoo Backend theme with the most advanced key features of all time. Get your own personalized view while working on the Backend system with a wide range of choices. Spiffy theme has 3 in 1 Theme Style, Progressive Web App, Fully Responsive for all apps, Configurable Apps Icon, App Drawer with global search, RTL & Multi-Language Support, and many other key features.

Copyright and License
---------------------
* Copyright Bizople Solutions Pvt. Ltd.

* Other proprietary

Configuration
-----------------------
* For the search functionality with records search user need to first create records in Global search menu which located in Settings > Spiffy Configuration > Global Search

Usage
-----------------------
* User can search both Menu and Recods in one popup
* T2304:
    - Updated XPath from web.FormView to web.ControlPanel to add a Close button in form view when using Split View mode.
* T2376 - VAA;
    - Update the menu item loading issue in spiffy.When open the menu by Ctrl + click it not load the apps menu items.
* T2369 - VAA:
    - Add Toggle Button for List Expand & Collapse Group & Update the index file with new feature GIF and update all features list in index.
* T2537 - HPS:
    - Add firebase file field and view in company, add firebase file by default when create new server/DB.

Known issues/Roadmap
--------------------
* Searching records based on datetime field on fixed time is not working, as odoo saves time in the UTC timezone. There is no need to solve it now but consider it to solve in future.

Changelog
---------
* 16-06-2025 - T2304 - Fixed XPath for Close button to properly hide form view in split view mode when splitView is true (tree + form)
* 20-06-2025 - BIZOPLE-T2376 - VAA - Update the menu item loading issue in spiffy.When open the menu by Ctrl + click it not load the apps menu items.
* 24-06-2025 - BIZOPLE-T2369 - VAA - Add Toggle Button for List Expand & Collapse Group & Update the index file with new feature GIF and update all features list in index.
* 26-06-2025 - T2537 - HPS - Remove fire base field from config and add in company, add post init to add file in company when create new server/DB.