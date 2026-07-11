const { chromium } = require('playwright');
(async () => {
  try {
    const browser = await chromium.launch({ executablePath: '/usr/bin/chromium', args: ['--no-sandbox'] });
    const page = await browser.newPage();
    await page.goto('http://localhost:8080/');
    await page.waitForTimeout(5000);
    await page.screenshot({ path: '/tmp/screen.png' });
    await browser.close();
    console.log("Screenshot taken at /tmp/screen.png");
  } catch (err) {
    console.error("Script error:", err);
  }
})();
