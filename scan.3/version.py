"""The single place the application's version number is written down.

The updater compares this against the newest GitHub release, so it has to be
bumped in the same commit that cuts a release, or the built application will
believe it is already current.
"""

__version__ = '1.0.0'

# The repository the updater asks about, as owner/name.
REPOSITORY = '7haTSheep/Trading-bot'
