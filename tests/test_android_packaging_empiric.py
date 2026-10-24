import os
import hashlib
import zipfile
import unittest
import xml.etree.ElementTree as ET

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANDROID_DIR = os.path.join(PROJECT_ROOT, "android")
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")
ASSETS_PUBLIC = os.path.join(ANDROID_DIR, "app", "src", "main", "assets", "public")
DEBUG_APK = os.path.join(ANDROID_DIR, "app", "build", "outputs", "apk", "debug", "app-debug.apk")
RELEASE_APK = os.path.join(ANDROID_DIR, "app", "build", "outputs", "apk", "release", "app-release.apk")
RELEASE_AAB = os.path.join(ANDROID_DIR, "app", "build", "outputs", "bundle", "release", "app-release.aab")
MANIFEST_PATH = os.path.join(ANDROID_DIR, "app", "src", "main", "AndroidManifest.xml")
MAIN_ACTIVITY_PATH = os.path.join(ANDROID_DIR, "app", "src", "main", "java", "com", "royalludo", "app", "MainActivity.java")
KEYSTORE_PATH = os.path.join(ANDROID_DIR, "app", "royal-ludo-release-key.jks")

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

class TestAndroidPackagingEmpiric(unittest.TestCase):
    """
    Adversarial and empirical test harness for Android Capacitor packaging.
    Validates manifest, MainActivity, asset synchronization checksums,
    and compiled binary artifacts (debug APK, release APK, release AAB).
    """

    def test_static_assets_checksum_parity(self):
        """Every file in static/ must match public/ and public/static/ with identical SHA256 checksum."""
        self.assertTrue(os.path.isdir(STATIC_DIR), "static/ directory must exist")
        self.assertTrue(os.path.isdir(ASSETS_PUBLIC), "assets/public/ directory must exist")

        static_files = []
        for root, _, files in os.walk(STATIC_DIR):
            for file in files:
                static_files.append(os.path.relpath(os.path.join(root, file), STATIC_DIR))

        self.assertGreater(len(static_files), 5, "static/ must contain multiple frontend assets")

        for rel_path in static_files:
            orig_path = os.path.join(STATIC_DIR, rel_path)
            direct_copy = os.path.join(ASSETS_PUBLIC, rel_path)
            mirror_copy = os.path.join(ASSETS_PUBLIC, "static", rel_path)

            self.assertTrue(os.path.exists(direct_copy), f"Direct asset {rel_path} missing in assets/public/")
            orig_hash = sha256_file(orig_path)
            direct_hash = sha256_file(direct_copy)
            self.assertEqual(orig_hash, direct_hash, f"SHA256 mismatch for direct asset {rel_path}")

            # For css and js files, check mirrored static/ path
            if rel_path.startswith("css") or rel_path.startswith("js"):
                self.assertTrue(os.path.exists(mirror_copy), f"Mirrored asset missing at static/{rel_path}")
                mirror_hash = sha256_file(mirror_copy)
                self.assertEqual(orig_hash, mirror_hash, f"SHA256 mismatch for mirrored asset static/{rel_path}")

    def test_manifest_security_and_audio_permissions(self):
        """AndroidManifest.xml must declare required audio, network permissions and flags."""
        self.assertTrue(os.path.exists(MANIFEST_PATH), "AndroidManifest.xml must exist")
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn('android.permission.INTERNET', content)
        self.assertIn('android.permission.RECORD_AUDIO', content)
        self.assertIn('android.permission.MODIFY_AUDIO_SETTINGS', content)
        self.assertIn('android.permission.ACCESS_NETWORK_STATE', content)
        self.assertIn('android:usesCleartextTraffic="true"', content)
        self.assertIn('android:hardwareAccelerated="true"', content)
        self.assertIn('android.hardware.microphone', content)
        self.assertIn('android:required="false"', content)

    def test_main_activity_webrtc_permission_bridge(self):
        """MainActivity.java must bridge WebChromeClient onPermissionRequest and check RECORD_AUDIO."""
        self.assertTrue(os.path.exists(MAIN_ACTIVITY_PATH), "MainActivity.java must exist")
        with open(MAIN_ACTIVITY_PATH, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("class MainActivity extends BridgeActivity", code)
        self.assertIn("onPermissionRequest", code)
        self.assertIn("RESOURCE_AUDIO_CAPTURE", code)
        self.assertIn("Manifest.permission.RECORD_AUDIO", code)
        self.assertIn("ContextCompat.checkSelfPermission", code)
        self.assertIn("ActivityCompat.requestPermissions", code)
        self.assertIn("onRequestPermissionsResult", code)
        self.assertIn("pendingPermissionRequest.grant", code)
        self.assertIn("pendingPermissionRequest.deny", code)
        self.assertIn("runOnUiThread", code)

    def test_keystore_existence_and_size(self):
        """Release keystore must exist and have valid size for RSA 2048 key."""
        self.assertTrue(os.path.exists(KEYSTORE_PATH), f"Keystore missing at {KEYSTORE_PATH}")
        size = os.path.getsize(KEYSTORE_PATH)
        self.assertGreater(size, 1000, f"Keystore size {size} is too small to be valid")

    def test_debug_apk_binary_integrity(self):
        """app-debug.apk must exist, exceed 1MB, and contain valid dex, manifest, and assets."""
        self.assertTrue(os.path.exists(DEBUG_APK), f"Debug APK missing at {DEBUG_APK}")
        apk_size = os.path.getsize(DEBUG_APK)
        self.assertGreater(apk_size, 1_000_000, f"Debug APK suspiciously small: {apk_size} bytes")

        with zipfile.ZipFile(DEBUG_APK, 'r') as zf:
            namelist = set(zf.namelist())
            self.assertIn("classes.dex", namelist, "Debug APK missing classes.dex")
            self.assertIn("AndroidManifest.xml", namelist, "Debug APK missing AndroidManifest.xml")
            self.assertIn("assets/public/index.html", namelist, "Debug APK missing assets/public/index.html")
            self.assertIn("assets/public/js/app.js", namelist, "Debug APK missing assets/public/js/app.js")
            self.assertIn("assets/public/js/audio_system.js", namelist, "Debug APK missing audio_system.js")
            self.assertIn("assets/public/css/style.css", namelist, "Debug APK missing style.css")
            self.assertIn("assets/public/static/js/app.js", namelist, "Debug APK missing mirrored app.js")

    def test_release_apk_binary_integrity(self):
        """app-release.apk must exist, exceed 1MB, and contain valid dex, manifest, and assets."""
        self.assertTrue(os.path.exists(RELEASE_APK), f"Release APK missing at {RELEASE_APK}")
        apk_size = os.path.getsize(RELEASE_APK)
        self.assertGreater(apk_size, 1_000_000, f"Release APK suspiciously small: {apk_size} bytes")

        with zipfile.ZipFile(RELEASE_APK, 'r') as zf:
            namelist = set(zf.namelist())
            self.assertIn("classes.dex", namelist, "Release APK missing classes.dex")
            self.assertIn("AndroidManifest.xml", namelist, "Release APK missing AndroidManifest.xml")
            self.assertIn("assets/public/index.html", namelist, "Release APK missing assets/public/index.html")
            self.assertIn("assets/public/js/app.js", namelist, "Release APK missing assets/public/js/app.js")
            self.assertIn("assets/public/js/audio_system.js", namelist, "Release APK missing audio_system.js")
            self.assertIn("assets/public/css/style.css", namelist, "Release APK missing style.css")
            self.assertIn("assets/public/static/js/app.js", namelist, "Release APK missing mirrored app.js")

    def test_release_aab_binary_integrity(self):
        """app-release.aab must exist, exceed 1MB, and contain valid base dex, manifest, and assets."""
        self.assertTrue(os.path.exists(RELEASE_AAB), f"Release AAB missing at {RELEASE_AAB}")
        aab_size = os.path.getsize(RELEASE_AAB)
        self.assertGreater(aab_size, 1_000_000, f"Release AAB suspiciously small: {aab_size} bytes")

        with zipfile.ZipFile(RELEASE_AAB, 'r') as zf:
            namelist = set(zf.namelist())
            self.assertIn("base/dex/classes.dex", namelist, "Release AAB missing base/dex/classes.dex")
            self.assertIn("base/manifest/AndroidManifest.xml", namelist, "Release AAB missing base manifest")
            self.assertIn("base/assets/public/index.html", namelist, "Release AAB missing index.html")
            self.assertIn("base/assets/public/js/app.js", namelist, "Release AAB missing app.js")
            self.assertIn("base/assets/public/js/audio_system.js", namelist, "Release AAB missing audio_system.js")
            self.assertIn("base/assets/public/css/style.css", namelist, "Release AAB missing style.css")
            self.assertIn("base/assets/public/static/js/app.js", namelist, "Release AAB missing mirrored app.js")

if __name__ == "__main__":
    unittest.main()
