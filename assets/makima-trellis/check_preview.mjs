import { chromium } from '../../.toolchain/motion-review/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
const base = 'http://localhost:5173/makima-trellis/';
const browser = await chromium.launch({headless:true, args:['--no-sandbox','--use-angle=swiftshader','--enable-webgl']});
const page = await browser.newPage({viewport:{width:1280,height:1000}});
const errors=[];
page.on('pageerror', e=>errors.push(e.message));
page.on('response', r=>{if(r.status()>=400)errors.push(`${r.status()} ${r.url()}`);});
const examples = await (await fetch(base+'examples.json')).json();
const loaded=[];
try {
  await page.goto(base);
  for (const example of examples) {
    await page.selectOption('#version', example.id);
    await page.waitForFunction(label => document.getElementById('status').textContent === `${label} · static model`, example.label, {timeout:60000});
    loaded.push(example.id);
  }
  await page.selectOption('#version', examples[0].id);
  await page.waitForFunction(()=>window.motionViewerReady);
  await page.screenshot({path:new URL('./preview.png',import.meta.url).pathname});
  await page.goto(base+'gallery.html');
  const paths=await page.locator('img').evaluateAll(xs=>xs.map(x=>x.src));
  const missing=[];
  for (const path of paths) {const r=await page.request.get(path);if(!r.ok())missing.push(path);}
  const result={loaded,errors,images:paths.length,missingImages:missing};
  await fs.writeFile(new URL('./preview-validation.json',import.meta.url),JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify(result));
  if(errors.length||missing.length)process.exitCode=1;
} finally {await browser.close();}
