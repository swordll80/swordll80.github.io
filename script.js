(function () {
  'use strict';

  var STORAGE_KEY = 'swordll80.sidebarCollapsed';
  var MOBILE_QUERY = window.matchMedia('(max-width: 768px)');
  var navData = [
    { title: '工具', target: 'tools-overview' },
    { title: 'Confluence', href: 'confluence.html' },
    { title: 'Confluence 内测', href: 'confluence_beta.html' },
    { title: '手册速查', href: 'confluence/read.html' }
  ];

  var navTree = document.getElementById('navTree');
  var sidebarToggle = document.getElementById('sidebarToggle');
  var edgeHotspot = document.getElementById('edgeHotspot');
  var drawerBackdrop = document.getElementById('drawerBackdrop');
  var sidebar = document.getElementById('sidebar');
  var content = document.getElementById('content');
  var peekTimer = 0;

  function isMobile() {
    return MOBILE_QUERY.matches;
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function renderNav() {
    navTree.innerHTML = '';
    navData.forEach(function (group) {
      var groupNode = el('div', 'nav-group open');
      var titleBtn = (group.target || group.href) ? el('a', 'nav-title') : el('button', 'nav-title');
      if (group.target) {
        titleBtn.href = '#' + group.target;
        titleBtn.setAttribute('data-nav-link', '');
        titleBtn.setAttribute('data-target', group.target);
      } else if (group.href) {
        titleBtn.href = group.href;
      } else {
        titleBtn.type = 'button';
      }
      titleBtn.innerHTML = (group.children && group.children.length ? '<span class="arrow">▶</span>' : '<span class="arrow"></span>') + '<strong>' + group.title + '</strong>';
      var children = el('div', 'nav-children');
      (group.children || []).forEach(function (item) {
        var link = el('a', 'nav-link', item.title);
        link.href = '#' + item.target;
        link.setAttribute('data-nav-link', '');
        link.setAttribute('data-target', item.target);
        children.appendChild(link);
      });
      if (group.children && group.children.length) {
        titleBtn.addEventListener('click', function () {
          groupNode.classList.toggle('open');
        });
      }
      groupNode.appendChild(titleBtn);
      if (group.children && group.children.length) groupNode.appendChild(children);
      navTree.appendChild(groupNode);
    });
  }

  function setCollapsed(collapsed, save) {
    document.body.classList.toggle('sidebar-collapsed', collapsed);
    document.body.classList.remove('sidebar-peek');
    sidebarToggle.setAttribute('aria-expanded', String(!collapsed));

    /* 手机端目录是抽屉，不保存状态，避免下次打开页面被侧栏遮住。 */
    if (save && !isMobile()) {
      localStorage.setItem(STORAGE_KEY, collapsed ? 'true' : 'false');
    }
  }

  function initSidebarState() {
    if (isMobile()) {
      setCollapsed(true, false);
      return;
    }

    var saved = localStorage.getItem(STORAGE_KEY);
    if (saved === null) {
      setCollapsed(false, false);
    } else {
      setCollapsed(saved === 'true', false);
    }
  }

  function activate(targetId) {
    var target = document.getElementById(targetId) || document.getElementById('tools-overview');

    Array.prototype.forEach.call(document.querySelectorAll('.content-section'), function (section) {
      section.classList.toggle('active', section === target);
    });

    Array.prototype.forEach.call(document.querySelectorAll('[data-target]'), function (link) {
      link.classList.toggle('active', link.getAttribute('data-target') === target.id);
    });

    document.title = (target.dataset.title || '首页') + ' · swordll80.github.io';

    if (content && content.focus) {
      try {
        content.focus({ preventScroll: true });
      } catch (e) {
        content.focus();
      }
    }

    if (isMobile()) {
      setCollapsed(true, false);
      window.scrollTo(0, 0);
    }
  }

  function handleHash() {
    var id = location.hash ? decodeURIComponent(location.hash.slice(1)) : 'tools-overview';
    activate(id);
  }



  async function hardRefreshCurrentPage() {
    try {
      try { localStorage.clear(); } catch (e) {}
      try { sessionStorage.clear(); } catch (e) {}

      if ('caches' in window) {
        try {
          var cacheNames = await caches.keys();
          await Promise.all(cacheNames.map(function (name) {
            return caches.delete(name);
          }));
        } catch (e) {}
      }

      if ('serviceWorker' in navigator) {
        try {
          var regs = await navigator.serviceWorker.getRegistrations();
          await Promise.all(regs.map(function (reg) {
            return reg.unregister();
          }));
        } catch (e) {}
      }

      var url = new URL(window.location.href);
      url.searchParams.set('_reload', String(Date.now()));
      window.location.replace(url.toString());
    } catch (e) {
      var fallback = window.location.pathname + '?_reload=' + Date.now();
      if (window.location.hash) {
        fallback += window.location.hash;
      }
      window.location.replace(fallback);
    }
  }

  function initHardRefreshButton() {
    var btn = document.getElementById('hardRefreshBtn');
    if (!btn) return;
    btn.addEventListener('click', function () {
      hardRefreshCurrentPage();
    });
  }

  renderNav();
  initHardRefreshButton();
  initSidebarState();
  handleHash();

  sidebarToggle.addEventListener('click', function () {
    setCollapsed(!document.body.classList.contains('sidebar-collapsed'), true);
  });

  if (drawerBackdrop) {
    drawerBackdrop.addEventListener('click', function () {
      setCollapsed(true, false);
    });
  }

  document.addEventListener('click', function (event) {
    var link = event.target.closest ? event.target.closest('[data-nav-link]') : null;
    if (!link) return;
    var hash = link.getAttribute('href');
    if (!hash || hash.charAt(0) !== '#') return;
    event.preventDefault();
    history.pushState(null, '', hash);
    handleHash();
  });

  window.addEventListener('hashchange', handleHash);

  if (edgeHotspot) {
    edgeHotspot.addEventListener('mouseenter', function () {
      if (!isMobile() && document.body.classList.contains('sidebar-collapsed')) {
        document.body.classList.add('sidebar-peek');
      }
    });

    edgeHotspot.addEventListener('click', function () {
      if (!isMobile() && document.body.classList.contains('sidebar-collapsed')) {
        document.body.classList.add('sidebar-peek');
      }
    });
  }

  if (sidebar) {
    sidebar.addEventListener('mouseleave', function () {
      if (!isMobile() && document.body.classList.contains('sidebar-collapsed')) {
        clearTimeout(peekTimer);
        peekTimer = setTimeout(function () {
          document.body.classList.remove('sidebar-peek');
        }, 160);
      }
    });
  }

  function handleMobileQueryChange() {
    initSidebarState();
  }

  if (MOBILE_QUERY.addEventListener) {
    MOBILE_QUERY.addEventListener('change', handleMobileQueryChange);
  } else if (MOBILE_QUERY.addListener) {
    MOBILE_QUERY.addListener(handleMobileQueryChange);
  }
})();
