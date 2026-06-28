async (page) => {
  var d = await page.evaluate(() => window._SSR_DATA);
  console.log(JSON.stringify(Object.keys(d || {}), null, 2).substring(0, 3000));
}
