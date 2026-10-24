package com.royalludo.app;

import org.junit.Test;
import java.io.File;
import java.io.FileInputStream;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

import static org.junit.Assert.*;

/**
 * Unit tests verifying Android project packaging integrity, manifest permissions,
 * WebRTC configuration contracts, and synchronized web assets.
 */
public class AndroidConfigurationTest {

    private File getAppModuleRoot() {
        File current = new File(".").getAbsoluteFile();
        if (new File(current, "src/main/AndroidManifest.xml").exists()) {
            return current;
        }
        File appDir = new File(current, "app");
        if (new File(appDir, "src/main/AndroidManifest.xml").exists()) {
            return appDir;
        }
        return current;
    }

    @Test
    public void testAndroidManifestPermissionsAndHardwareAcceleration() throws Exception {
        File appRoot = getAppModuleRoot();
        File manifestFile = new File(appRoot, "src/main/AndroidManifest.xml");
        assertTrue("AndroidManifest.xml must exist at " + manifestFile.getPath(), manifestFile.exists());

        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        DocumentBuilder builder = factory.newDocumentBuilder();
        Document doc = builder.parse(new FileInputStream(manifestFile));

        NodeList permNodes = doc.getElementsByTagName("uses-permission");
        boolean hasInternet = false;
        boolean hasRecordAudio = false;
        boolean hasModifyAudio = false;

        for (int i = 0; i < permNodes.getLength(); i++) {
            Element elem = (Element) permNodes.item(i);
            String name = elem.getAttribute("android:name");
            if ("android.permission.INTERNET".equals(name)) hasInternet = true;
            if ("android.permission.RECORD_AUDIO".equals(name)) hasRecordAudio = true;
            if ("android.permission.MODIFY_AUDIO_SETTINGS".equals(name)) hasModifyAudio = true;
        }

        assertTrue("Manifest must declare android.permission.INTERNET", hasInternet);
        assertTrue("Manifest must declare android.permission.RECORD_AUDIO for WebRTC voice chat", hasRecordAudio);
        assertTrue("Manifest must declare android.permission.MODIFY_AUDIO_SETTINGS for WebRTC voice chat", hasModifyAudio);

        NodeList appNodes = doc.getElementsByTagName("application");
        assertTrue("Manifest must have <application> node", appNodes.getLength() > 0);
        Element appElem = (Element) appNodes.item(0);
        assertEquals("true", appElem.getAttribute("android:usesCleartextTraffic"));
        assertEquals("true", appElem.getAttribute("android:hardwareAccelerated"));
    }

    @Test
    public void testCapacitorConfigJsonIntegrity() throws Exception {
        File appRoot = getAppModuleRoot();
        File configFile = new File(appRoot, "src/main/assets/capacitor.config.json");
        assertTrue("capacitor.config.json must exist in assets", configFile.exists());
        assertTrue("capacitor.config.json must not be empty", configFile.length() > 50);
    }

    @Test
    public void testSynchronizedWebAssetsAndDualMirroring() {
        File appRoot = getAppModuleRoot();
        File publicDir = new File(appRoot, "src/main/assets/public");
        assertTrue("Assets public directory must exist", publicDir.isDirectory());

        File indexHtml = new File(publicDir, "index.html");
        assertTrue("public/index.html must exist and not be empty", indexHtml.exists() && indexHtml.length() > 0);

        // Verify direct paths
        File directCss = new File(publicDir, "css/style.css");
        File directAppJs = new File(publicDir, "js/app.js");
        File directAudioJs = new File(publicDir, "js/audio_system.js");
        File directBoardJs = new File(publicDir, "js/ludo_board.js");

        assertTrue("Direct css/style.css must exist", directCss.exists() && directCss.length() > 0);
        assertTrue("Direct js/app.js must exist", directAppJs.exists() && directAppJs.length() > 0);
        assertTrue("Direct js/audio_system.js must exist", directAudioJs.exists() && directAudioJs.length() > 0);
        assertTrue("Direct js/ludo_board.js must exist", directBoardJs.exists() && directBoardJs.length() > 0);

        // Verify mirrored paths for static/css and static/js
        File mirrorCss = new File(publicDir, "static/css/style.css");
        File mirrorAppJs = new File(publicDir, "static/js/app.js");
        File mirrorAudioJs = new File(publicDir, "static/js/audio_system.js");
        File mirrorBoardJs = new File(publicDir, "static/js/ludo_board.js");

        assertTrue("Mirrored static/css/style.css must exist", mirrorCss.exists() && mirrorCss.length() > 0);
        assertTrue("Mirrored static/js/app.js must exist", mirrorAppJs.exists() && mirrorAppJs.length() > 0);
        assertTrue("Mirrored static/js/audio_system.js must exist", mirrorAudioJs.exists() && mirrorAudioJs.length() > 0);
        assertTrue("Mirrored static/js/ludo_board.js must exist", mirrorBoardJs.exists() && mirrorBoardJs.length() > 0);
    }
}
