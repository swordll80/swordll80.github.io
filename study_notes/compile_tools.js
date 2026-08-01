(function () {
  'use strict';

  var config = window.COMPILE_TOOL_CONFIG || {};
  var $ = function (id) { return document.getElementById(id); };
  var editor = $('source-editor');
  var exampleSelect = $('example-select');
  var status = $('tool-status');
  var runButtons = Array.prototype.slice.call(document.querySelectorAll('[data-action]'));
  var storageKey = 'swordll80.compile.' + (config.language || 'code');
  var apiBase = config.apiBase || window.location.origin;
  var outputNames = ['output', 'assembly', 'debug'];

  function setStatus(message, kind) {
    status.textContent = message;
    status.className = 'tool-status ' + (kind || '');
  }

  function setOutput(name, text) {
    outputNames.forEach(function (item) {
      var pane = $('output-' + item);
      var tab = document.querySelector('[data-output-tab="' + item + '"]');
      if (pane) pane.classList.toggle('active', item === name);
      if (tab) tab.classList.toggle('active', item === name);
    });
    if ($('output-' + name)) $('output-' + name).textContent = text || '暂无输出。';
  }

  function withCacheBust(url) {
    return url + (url.indexOf('?') >= 0 ? '&' : '?') + 'v=' + Date.now();
  }

  function saveDraft() {
    try { localStorage.setItem(storageKey, editor.value); } catch (ignore) {}
  }

  function loadDraft() {
    try {
      var draft = localStorage.getItem(storageKey);
      if (draft) editor.value = draft;
    } catch (ignore) {}
  }

  function fillExamples() {
    (config.examples || []).forEach(function (item, index) {
      var option = document.createElement('option');
      option.value = item.url;
      option.textContent = item.title;
      if (index === 0) option.selected = true;
      exampleSelect.appendChild(option);
    });
  }

  function loadExample() {
    var url = exampleSelect.value;
    if (!url) return;
    setStatus('正在加载示例：' + url, '');
    fetch(withCacheBust(url), { cache: 'no-store' })
      .then(function (response) {
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return response.text();
      })
      .then(function (text) {
        editor.value = text;
        saveDraft();
        setStatus('示例已加载。修改后可保存到浏览器草稿，或启动本地助手编译。', '');
      })
      .catch(function (error) { setStatus('示例加载失败：' + error.message, 'error'); });
  }

  function downloadSource() {
    var blob = new Blob([editor.value], { type: 'text/plain;charset=utf-8' });
    var link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = config.filename || 'main.c';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
    setStatus('源码已下载：' + link.download, 'ready');
  }

  function getApiUrl(path) { return apiBase.replace(/\/$/, '') + path; }

  function checkServer() {
    fetch(getApiUrl('/api/status?v=' + Date.now()), { cache: 'no-store' })
      .then(function (response) {
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return response.json();
      })
      .then(function (data) {
        var available = data.tools || {};
        var names = Object.keys(available).filter(function (name) { return available[name]; });
        setStatus('本地编译助手已连接。可用工具：' + (names.join('、') || '无'), 'ready');
      })
      .catch(function () {
        setStatus('当前是静态页面：编辑、加载示例、下载源码可用；如需编译/运行，请双击本目录的启动脚本。', 'warn');
      });
  }

  function setBusy(busy) {
    runButtons.forEach(function (button) { button.disabled = busy; });
  }

  function execute(action) {
    setBusy(true);
    setStatus('正在' + (action === 'compile' ? '编译' : action === 'run' ? '编译并运行' : '编译并生成调试信息') + '……', '');
    var compiler = $('compiler-select') ? $('compiler-select').value : 'auto';
    var optimization = $('optimization-select') ? $('optimization-select').value : '0';
    var stdin = $('stdin-editor') ? $('stdin-editor').value : '';
    fetch(getApiUrl('/api/compile'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        language: config.language,
        action: action,
        compiler: compiler === 'auto' ? null : compiler,
        options: { optimization: optimization },
        source: editor.value,
        stdin: stdin
      })
    })
      .then(function (response) {
        return response.json().then(function (data) { if (!response.ok) throw new Error(data.message || response.status); return data; });
      })
      .then(function (data) {
        var output = [data.message || '', data.stdout || '', data.stderr || ''].filter(Boolean).join('\n');
        setOutput('output', output || '编译成功，没有标准输出。');
        setOutput('assembly', data.assembly || '本次操作没有生成汇编/目标文件信息。');
        setOutput('debug', data.debug || '本次操作没有调试器输出。');
        setOutput(action === 'debug' ? 'debug' : action === 'compile' ? 'assembly' : 'output', action === 'compile' ? (data.assembly || output) : (action === 'debug' ? (data.debug || output) : output));
        setStatus((data.message || (data.ok ? '完成。' : '失败。')) + (data.compiler ? ' 使用 ' + data.compiler + '。' : ''), data.ok ? 'ready' : 'error');
      })
      .catch(function (error) {
        setOutput('output', '无法连接本地编译助手。\n\n' + error.message + '\n\n请双击 start_' + (config.language === 'asm' ? 'asm' : 'c') + '_compile.bat。');
        setStatus('本地编译助手不可用，请先运行启动脚本。', 'error');
      })
      .finally(function () { setBusy(false); });
  }

  fillExamples();
  loadDraft();
  if (!editor.value) loadExample();
  checkServer();
  editor.addEventListener('input', saveDraft);
  exampleSelect.addEventListener('change', loadExample);
  $('btn-load-example').addEventListener('click', loadExample);
  $('btn-save-source').addEventListener('click', downloadSource);
  runButtons.forEach(function (button) { button.addEventListener('click', function () { execute(button.getAttribute('data-action')); }); });
  document.querySelectorAll('[data-output-tab]').forEach(function (tab) {
    tab.addEventListener('click', function () { setOutput(tab.getAttribute('data-output-tab'), $('output-' + tab.getAttribute('data-output-tab')).textContent); });
  });
  editor.addEventListener('keydown', function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      execute('run');
    }
  });
}());
