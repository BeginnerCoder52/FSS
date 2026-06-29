const { chromium } = require('playwright');
(async () => {
  try {
    const browser = await chromium.launch({ args: ['--no-sandbox'] });
    const page = await browser.newPage();
    page.on('console', msg => console.log('PAGE LOG:', msg.type(), msg.text()));
    page.on('pageerror', error => console.log('PAGE ERROR:', error.message));
    console.log("Navigating to MagicMirror...");
    await page.goto('http://localhost:8080/');
    console.log("Waiting 5s for modules to load...");
    await page.waitForTimeout(5000);
    await browser.close();
    console.log("Done.");
  } catch (err) {
    console.error("Script error:", err);
  }
})();
