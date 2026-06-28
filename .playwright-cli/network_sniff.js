async (page) => {
  var requests = [];
  page.on('request', r => requests.push(r.url()));
  page.on('response', r => {
    var url = r.url();
    if (url.includes('api') || url.includes('chapter') || url.includes('typeset') || url.includes('content')) {
      console.log('RESP:', r.status(), url);
    }
  });
  await page.reload();
  await page.waitForTimeout(10000);
  console.log('ALL REQUESTS:');
  requests.forEach(u => console.log(u));
}
