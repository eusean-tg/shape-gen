import {chromium} from '../.toolchain/motion-review/node_modules/playwright/index.mjs';

const browser = await chromium.launch({headless: true,
  args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-webgl']});
try {
  const page = await browser.newPage({viewport: {width: 1050, height: 1400}});
  await page.goto('http://localhost:5173/preview/');
  await page.waitForFunction(() => window.motionViewerReady && !window.modelPreview.state.loading);
  await page.locator('#character-mode').selectOption('inspect');
  const clips = await page.locator('#clip option').evaluateAll(es =>
    Object.fromEntries(es.map(e => [e.textContent, e.value])));
  await page.locator('#clip').selectOption(clips.Idle_Breathe);
  await page.locator('#time').evaluate(e => {
    e.value = 1.8; e.dispatchEvent(new Event('input'));
  });
  const capture = async (name, position) => {
    await page.evaluate(position => {
      const {camera, controls} = window.modelPreview;
      camera.position.set(...position); controls.target.set(0, 1.08, 0); controls.update();
    }, position);
    await page.waitForTimeout(150);
    await page.locator('canvas').screenshot({path: `assets/teal-peasant/idle-sleeve-fix/${name}.png`});
  };
  await capture('side', [3, 1.3, 0]);
  await capture('other-side', [-3, 1.3, 0]);
  await page.locator('#color-tunic').evaluate(e => {
    e.value = '#0055ff'; e.dispatchEvent(new Event('input', {bubbles: true}));
  });
  await capture('back-blue', [-.7, 1.8, -2.7]);
  await capture('front-blue', [.7, 1.8, 2.7]);
  await page.locator('#color-sleeves').evaluate(e => {
    e.value = '#ffcc00'; e.dispatchEvent(new Event('input', {bubbles: true}));
  });
  await capture('back-blue-yellow', [.7, 1.8, -2.7]);
} finally {
  await browser.close();
}
