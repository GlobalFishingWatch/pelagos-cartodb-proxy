import os
import os.path

SERVER_DIR=os.path.dirname(__file__)

# NB: When running unit tests in NOSEGAE, os.environ is not set up by
# the time we get here
SERVER_SOFTWARE = os.environ.get('SERVER_SOFTWARE', 'Development-NOSEGAE')
DEV_SERVER = SERVER_SOFTWARE.startswith('Development')
TEST_SERVER = SERVER_SOFTWARE == 'Development-NOSEGAE'

try:
    import google.appengine.api.app_identity
    APPLICATION_ID = google.appengine.api.app_identity.get_application_id()
except:
    if 'APPLICATION_ID' in os.environ:
        APPLICATION_ID = os.environ['APPLICATION_ID']
    else:
        import subprocess
        import ConfigParser
        cp = ConfigParser.ConfigParser()
        cp.readfp(subprocess.Popen(
                ["gcloud", "config", "list"],
                stdout=subprocess.PIPE).stdout)
        APPLICATION_ID = cp.get("core", "project")

APP_VERSION = os.environ.get('CURRENT_VERSION_ID', 'unittest')

TILESET_BUCKET = APPLICATION_ID
TILESET_FOLDER = 'pelagos/data/cartodb-proxy-tiles'
TILESET_URL = 'http://storage.googleapis.com/%s/%s' % (TILESET_BUCKET, TILESET_FOLDER)

# This file should NOT be committed to git
UNITTEST_GOOGLEAPI_AUTH_KEY_FILE = os.path.join(
    SERVER_DIR,
    'keys/privatekey.pem')

LOCAL_TILESETS = False
