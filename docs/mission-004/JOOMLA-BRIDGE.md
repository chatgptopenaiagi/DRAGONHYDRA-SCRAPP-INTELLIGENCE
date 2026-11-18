# Isolated Joomla bridge

The optional `mod_dragonhydra004` module has a different identity from the existing `com_dragonhydraintelligence` extension. This mission does not install it into or alter the existing Joomla site. Actual Joomla integration stays BLOCKED until the site owner permits an installation and real Joomla communication is tested.

Installation: package the staged module folder as a ZIP, install using Joomla's extension installer, create a module instance, set the candidate loopback port and the absolute path to its `private/bridge.key`, restrict module access to authorized site users, and publish in a chosen position. The key must be outside the web root, readable only by the application owner and the specifically authorized PHP service identity. Never put the key value in a page, URL or public config. No permission change is performed automatically.

The dedicated bridge credential authorizes only GET status and a bounded observation query. It cannot import, configure sources, mint browser sessions, create backups or stop the application. PHP renders escaped text and reports unavailable data explicitly. It never substitutes synthetic records for a failed connection.

Upgrade: back up the module parameters, install the newer ZIP with the same unique module identity, then repeat authenticated read and unauthorized-write checks. Removal: unpublish/delete module instances and uninstall only `mod_dragonhydra004` through Joomla extension management; remove/revoke its dedicated credential when no longer used. The original extension, Joomla database and other modules remain untouched.
